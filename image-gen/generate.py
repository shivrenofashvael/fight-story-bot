#!/usr/bin/env python3
"""
Fight Story Bot — Image Generation via RunPod ComfyUI (Flux img2img)

Takes a move image + style/outfit prompt, regenerates it through Flux,
uploads the result to R2, and returns the public URL.

Usage:
  python generate.py \
    --image-url "https://pub-f8884b60a8de489aa360109963fd9e9f.r2.dev/moves/armbar/10_armbar.jpg" \
    --style "dark anime" \
    --outfit "black track pants, green hand wraps, shirtless" \
    --move "triangle choke, squeezing thighs around opponent's neck" \
    --mood "intense, dramatic lighting" \
    --denoise 0.45

  # Use a previous generated image as the base (story continuation):
  python generate.py \
    --image-url "https://pub-f8884b60a8de489aa360109963fd9e9f.r2.dev/generated/abc123.png" \
    --style "dark anime" \
    --outfit "black track pants, green hand wraps, shirtless" \
    --move "triangle choke tightening, more pressure" \
    --mood "suffocating, close-up tension" \
    --denoise 0.35
"""

import argparse
import base64
import copy
import datetime
import hashlib
import hmac
import io
import json
import math
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(SCRIPT_DIR, "config.json")) as f:
    CONFIG = json.load(f)

with open(os.path.join(SCRIPT_DIR, "workflow_api.json")) as f:
    WORKFLOW_BASIC = json.load(f)
with open(os.path.join(SCRIPT_DIR, "workflow_controlnet.json")) as f:
    WORKFLOW_CN = json.load(f)
with open(os.path.join(SCRIPT_DIR, "workflow_sdxl_controlnet.json")) as f:
    WORKFLOW_SDXL = json.load(f)

RUNPOD_API_KEY = CONFIG["runpod_api_key"]
ENDPOINT_ID = CONFIG["runpod_endpoint_id"]
CN_ENDPOINT_ID = CONFIG.get("runpod_controlnet_endpoint_id", "")
SDXL_ENDPOINT_ID = CONFIG.get("runpod_sdxl_endpoint_id", "")

R2_ENDPOINT = CONFIG["r2_endpoint"]
R2_BUCKET = CONFIG["r2_bucket"]
R2_ACCESS_KEY = CONFIG["r2_access_key"]
R2_SECRET_KEY = CONFIG["r2_secret_key"]
R2_PUBLIC_BASE = CONFIG["r2_public_base"]


# ── Prompt Builder ──

STYLE_PRESETS = {
    "anime": (
        "A dramatic anime illustration of {scene}. "
        "Drawn in bold cel-shaded anime style with thick outlines, vibrant colors, "
        "expressive shading, and dynamic action lines. "
        "The art style looks like a frame from a high-budget anime series."
    ),
    "dark_anime": (
        "A dark and intense anime illustration of {scene}. "
        "Drawn in a gritty anime style with heavy shadows, high contrast lighting, "
        "deep blacks, and muted colors with occasional vivid highlights. "
        "The atmosphere is ominous and oppressive, like a scene from Berserk or Vinland Saga."
    ),
    "manga": (
        "A black and white manga panel depicting {scene}. "
        "Drawn with detailed ink linework, screentone shading, speed lines for motion, "
        "and dramatic composition. Pure monochrome manga art style."
    ),
    "cinematic": (
        "A cinematic film still of {scene}. "
        "Shot with dramatic lighting, shallow depth of field, film grain, "
        "warm color grading, and anamorphic lens flare. Looks like a scene from a movie."
    ),
    "dark_fantasy": (
        "A dark fantasy painting of {scene}. "
        "Painted in a dramatic oil painting style with rich textures, deep shadows, "
        "chiaroscuro lighting, and an ominous fantasy atmosphere."
    ),
    "comic": (
        "A western comic book illustration of {scene}. "
        "Drawn with bold black outlines, flat cel-shading, halftone dots, "
        "dynamic perspective, and superhero comic aesthetic."
    ),
    "neon": (
        "A cyberpunk neon-lit illustration of {scene}. "
        "The scene is bathed in vivid neon pink, blue, and purple lights against deep darkness. "
        "Glowing rim lighting on the fighters, cyberpunk atmosphere."
    ),
    "gritty": (
        "A gritty realistic painting of {scene}. "
        "Raw and visceral, with harsh directional lighting, visible sweat and strain, "
        "textured skin, and an underground fight club atmosphere."
    ),
}


def build_prompt(style, outfit, move, mood, extra=""):
    """Build a natural-language prompt for Flux. Flux works best with descriptive sentences, not tags."""

    # Build the scene description
    scene_parts = []
    if move:
        scene_parts.append(f"two young men fighting — {move}")
    else:
        scene_parts.append("two young men in an intense fight")

    if outfit:
        scene_parts.append(f"The attacker is wearing {outfit}")

    scene = ". ".join(scene_parts)

    # Get style template
    style_lower = style.lower().replace(" ", "_")
    if style_lower in STYLE_PRESETS:
        prompt = STYLE_PRESETS[style_lower].format(scene=scene)
    else:
        prompt = f"{style} of {scene}."

    # Add mood
    if mood:
        mood_desc = mood.replace(",", " and").strip()
        prompt += f" The mood is {mood_desc}."

    # Enforce male characters — be very explicit to prevent feminine features
    prompt += (
        " Both fighters are young men with flat masculine chests, muscular arms, "
        "broad shoulders, and athletic male physiques. No feminine features whatsoever. "
        "Male fighters only."
    )

    # Extra
    if extra:
        prompt += f" {extra}"

    return prompt


# ── Local Canny Edge Detection ──

def canny_edge_detect(image_bytes):
    """
    Extract Canny edges from an image using PIL (no OpenCV needed).
    Returns the edge map as PNG bytes — this acts as a structural constraint
    so Flux preserves the exact body positions when generating the styled version.
    """
    from PIL import Image, ImageFilter

    img = Image.open(io.BytesIO(image_bytes)).convert("L")  # grayscale

    # Resize to 1024x1024
    img = img.resize((1024, 1024), Image.LANCZOS)

    # Edge detection: blur to remove noise, then find edges, then enhance
    img = img.filter(ImageFilter.GaussianBlur(radius=1))
    edges = img.filter(ImageFilter.FIND_EDGES)

    # Threshold to get clean black/white edges
    edges = edges.point(lambda x: 255 if x > 30 else 0)

    # Dilate edges slightly for better visibility
    edges = edges.filter(ImageFilter.MaxFilter(size=3))

    # Invert: white lines on black background (standard for ControlNet-style input)
    edges = edges.point(lambda x: 255 - x)

    # Convert back to RGB (Flux expects color images)
    edges_rgb = Image.new("RGB", edges.size)
    edges_rgb.paste(edges, (0, 0, edges.size[0], edges.size[1]))
    edges_rgb.paste(edges, (0, 0, edges.size[0], edges.size[1]))

    # Convert to RGB properly
    edges_rgb = Image.merge("RGB", [edges, edges, edges])

    buf = io.BytesIO()
    edges_rgb.save(buf, format="PNG")
    return buf.getvalue()


# ── RunPod API ──

def runpod_request(method, path, data=None, endpoint_id=None):
    """Make a request to the RunPod API."""
    eid = endpoint_id or ENDPOINT_ID
    url = f"https://api.runpod.ai/v2/{eid}/{path}"
    headers = {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode())


def download_image(url):
    """Download an image from URL and return as bytes."""
    req = urllib.request.Request(url, headers={"User-Agent": "FightStoryBot/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _submit_and_poll(payload, endpoint_id=None, label=""):
    """Submit a job to RunPod and poll for result."""
    eid = endpoint_id or ENDPOINT_ID
    try:
        result = runpod_request("POST", "runsync", payload, endpoint_id=eid)
        if result.get("status") == "COMPLETED":
            return extract_output(result)
    except urllib.error.HTTPError as e:
        if e.code == 408:
            pass
        else:
            raise

    print(f"  Sync timed out, using async...", file=sys.stderr)
    result = runpod_request("POST", "run", payload, endpoint_id=eid)
    job_id = result["id"]

    for attempt in range(120):
        time.sleep(5)
        status = runpod_request("GET", f"status/{job_id}", endpoint_id=eid)
        state = status.get("status")
        if state == "COMPLETED":
            return extract_output(status)
        elif state in ("FAILED", "CANCELLED"):
            print(f"  [{label}] Job {state}: {status.get('error', 'unknown')}", file=sys.stderr)
            return None
        print(f"  [{label}] Status: {state} (attempt {attempt+1}/120)...", file=sys.stderr)

    print(f"  [{label}] Job timed out after 10 minutes", file=sys.stderr)
    return None


NEGATIVE_PROMPT = (
    "female, woman, breasts, boobs, feminine, girl, cleavage, "
    "deformed hands, extra fingers, mutated, disfigured, bad anatomy, "
    "extra limbs, fused limbs, tangled limbs, blurry, watermark"
)

# Animagine XL works best with quality tags + danbooru-style prompts
SDXL_NEGATIVE_PROMPT = (
    "nsfw, lowres, (bad), text, error, fewer, extra, missing, "
    "worst quality, jpeg artifacts, low quality, watermark, unfinished, "
    "displeasing, oldest, early, chromatic aberration, signature, "
    "extra digits, artistic error, username, scan, abstract, "
    "female, woman, breasts, feminine, girl, "
    "bad anatomy, bad hands, deformed, extra limbs, fused limbs"
)


def generate_image(image_url, positive_prompt, denoise=0.55, steps=28, guidance=3.5,
                   seed=None, cn_strength=0.85):
    """
    Generate a styled fight image via RunPod.

    Priority:
    1. SDXL Anime ControlNet (best for anime — sharp output + pose preservation)
    2. Flux ControlNet (pose preservation but blurry anime)
    3. Flux basic img2img (fallback — style OK but limbs can tangle)
    """
    if seed is None:
        seed = random.randint(1, 2**31)

    print(f"  Downloading source image...", file=sys.stderr)
    image_bytes = download_image(image_url)
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    # ── Try SDXL Anime ControlNet first (best quality for anime) ──
    if SDXL_ENDPOINT_ID:
        print(f"  Using SDXL Anime ControlNet (cn={cn_strength}, denoise={denoise})...", file=sys.stderr)
        workflow = copy.deepcopy(WORKFLOW_SDXL)

        # Animagine XL prompt format: quality tags + description
        sdxl_prompt = f"masterpiece, best quality, very aesthetic, absurdres, {positive_prompt}"
        workflow["6"]["inputs"]["text"] = sdxl_prompt
        workflow["7"]["inputs"]["text"] = SDXL_NEGATIVE_PROMPT
        workflow["3"]["inputs"]["seed"] = seed
        workflow["3"]["inputs"]["steps"] = steps
        workflow["3"]["inputs"]["cfg"] = 7.0  # SDXL needs higher CFG than Flux
        workflow["3"]["inputs"]["denoise"] = denoise
        workflow["25"]["inputs"]["strength"] = cn_strength

        payload = {
            "input": {
                "workflow": workflow,
                "images": [{"name": "input.png", "image": image_b64}],
            }
        }

        print(f"  Submitting to RunPod [SDXL Anime ControlNet] (steps={steps}, cn={cn_strength})...", file=sys.stderr)
        result = _submit_and_poll(payload, endpoint_id=SDXL_ENDPOINT_ID, label="SDXL")
        if result:
            return result
        print(f"  SDXL ControlNet failed, trying Flux ControlNet...", file=sys.stderr)

    # ── Try Flux ControlNet (preserves pose but quality varies) ──
    if CN_ENDPOINT_ID:
        print(f"  Using Flux ControlNet (cn_strength={cn_strength})...", file=sys.stderr)
        workflow = copy.deepcopy(WORKFLOW_CN)
        workflow["6"]["inputs"]["text"] = positive_prompt
        workflow["7"]["inputs"]["text"] = NEGATIVE_PROMPT
        workflow["3"]["inputs"]["noise_seed"] = seed
        workflow["3"]["inputs"]["steps"] = steps
        workflow["3"]["inputs"]["timestep_to_start_cfg"] = steps
        workflow["3"]["inputs"]["true_gs"] = guidance
        workflow["3"]["inputs"]["image_to_image_strength"] = denoise
        workflow["3"]["inputs"]["denoise_strength"] = 1.0
        workflow["25"]["inputs"]["strength"] = cn_strength

        payload = {
            "input": {
                "workflow": workflow,
                "images": [{"name": "input.png", "image": image_b64}],
            }
        }

        print(f"  Submitting to RunPod [Flux ControlNet] (steps={steps}, cn={cn_strength})...", file=sys.stderr)
        result = _submit_and_poll(payload, endpoint_id=CN_ENDPOINT_ID, label="CN")
        if result:
            return result
        print(f"  Flux ControlNet failed, falling back to basic img2img...", file=sys.stderr)

    # ── Fallback: basic img2img ──
    workflow = copy.deepcopy(WORKFLOW_BASIC)
    workflow["6"]["inputs"]["text"] = positive_prompt
    workflow["7"]["inputs"]["text"] = NEGATIVE_PROMPT
    workflow["3"]["inputs"]["seed"] = seed
    workflow["3"]["inputs"]["steps"] = steps
    workflow["3"]["inputs"]["denoise"] = denoise
    workflow["3"]["inputs"]["cfg"] = guidance

    payload = {
        "input": {
            "workflow": workflow,
            "images": [{"name": "input.png", "image": image_b64}],
        }
    }

    print(f"  Submitting to RunPod [Flux img2img] (steps={steps}, denoise={denoise})...", file=sys.stderr)
    return _submit_and_poll(payload, label="img2img")


def extract_output(result):
    """Extract base64 image from RunPod response."""
    output = result.get("output", {})

    # ComfyUI worker format — check both "image" and "data" keys
    if isinstance(output, dict) and "images" in output:
        images = output["images"]
        if images and isinstance(images[0], dict):
            img_data = images[0].get("image") or images[0].get("data")
            if img_data:
                return base64.b64decode(img_data)

    # Some workers return a message with base64 directly
    if isinstance(output, dict) and "message" in output:
        return base64.b64decode(output["message"])

    # Try to find any base64 image data
    if isinstance(output, str):
        return base64.b64decode(output)

    print(f"  Unexpected output format: {json.dumps(output)[:200]}", file=sys.stderr)
    return None


# ── R2 Upload ──

def sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def get_signature_key(key, date_stamp, region, service):
    k_date = sign(("AWS4" + key).encode("utf-8"), date_stamp)
    k_region = sign(k_date, region)
    k_service = sign(k_region, service)
    return sign(k_service, "aws4_request")


def upload_to_r2(image_bytes, filename):
    """Upload generated image to R2 and return the public URL."""
    object_key = f"generated/{filename}"
    now = datetime.datetime.utcnow()
    date_stamp = now.strftime("%Y%m%d")
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    region = "auto"
    service = "s3"

    content_hash = hashlib.sha256(image_bytes).hexdigest()
    host = R2_ENDPOINT.replace("https://", "")
    uri = f"/{R2_BUCKET}/{urllib.parse.quote(object_key, safe='/')}"

    canonical_headers = f"host:{host}\nx-amz-content-sha256:{content_hash}\nx-amz-date:{amz_date}\n"
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_request = f"PUT\n{uri}\n\n{canonical_headers}\n{signed_headers}\n{content_hash}"

    algorithm = "AWS4-HMAC-SHA256"
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = f"{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode()).hexdigest()}"

    signing_key = get_signature_key(R2_SECRET_KEY, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = f"{algorithm} Credential={R2_ACCESS_KEY}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"

    headers = {
        "Host": host,
        "x-amz-date": amz_date,
        "x-amz-content-sha256": content_hash,
        "Authorization": authorization,
        "Content-Type": "image/png",
    }

    url = f"{R2_ENDPOINT}/{R2_BUCKET}/{urllib.parse.quote(object_key, safe='/')}"
    req = urllib.request.Request(url, data=image_bytes, headers=headers, method="PUT")
    urllib.request.urlopen(req, timeout=120)

    public_url = f"{R2_PUBLIC_BASE}/{urllib.parse.quote(object_key, safe='/')}"
    return public_url


# ── Main ──

def main():
    p = argparse.ArgumentParser(description="Generate styled fight images via RunPod ComfyUI + ControlNet")
    p.add_argument("--image-url", required=True, help="URL of the source move image")
    p.add_argument("--style", default="anime", help="Style preset or custom text (anime, dark_anime, manga, cinematic, dark_fantasy, comic, neon, gritty)")
    p.add_argument("--outfit", default="", help="Outfit description for the executioner (dominant fighter)")
    p.add_argument("--move", default="", help="Move description (what's happening physically)")
    p.add_argument("--mood", default="intense", help="Mood modifiers, comma-separated (intense, dark, brutal, suffocating, dominant, desperate, calm_menace)")
    p.add_argument("--extra", default="", help="Extra prompt text")
    p.add_argument("--steps", type=int, default=28, help="Sampling steps (default 28 for ControlNet)")
    p.add_argument("--guidance", type=float, default=3.5, help="Flux guidance strength")
    p.add_argument("--seed", type=int, default=None, help="Random seed (random if not set)")
    p.add_argument("--denoise", type=float, default=None, help="Denoise strength (default 0.68)")
    p.add_argument("--no-upload", action="store_true", help="Save locally instead of uploading to R2")
    args = p.parse_args()

    denoise = args.denoise or 0.55

    # Build prompt
    prompt = build_prompt(args.style, args.outfit, args.move, args.mood, args.extra)
    print(f"  Prompt: {prompt[:120]}...", file=sys.stderr)

    # Generate via RunPod
    image_bytes = generate_image(
        image_url=args.image_url,
        positive_prompt=prompt,
        denoise=denoise,
        steps=args.steps,
        guidance=args.guidance,
        seed=args.seed,
    )

    if not image_bytes:
        print(json.dumps({"error": "Image generation failed"}))
        sys.exit(1)

    # Upload or save
    if args.no_upload:
        filename = f"fight_gen_{int(time.time())}.png"
        with open(filename, "wb") as f:
            f.write(image_bytes)
        print(json.dumps({"local_path": filename, "prompt": prompt}))
    else:
        timestamp = int(time.time())
        seed_str = args.seed or "rand"
        filename = f"{timestamp}_{seed_str}.png"
        url = upload_to_r2(image_bytes, filename)
        print(json.dumps({"url": url, "prompt": prompt, "denoise": denoise}))


if __name__ == "__main__":
    main()
