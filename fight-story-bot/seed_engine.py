#!/usr/bin/env python3
"""
Fight Story Bot — Seed Engine v2 (network-based, reads from Supabase)
"""

import argparse
import json
import os
import random
import sys
import urllib.request
import urllib.parse
import urllib.error
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(SCRIPT_DIR, "config.json")) as f:
    config = json.load(f)

SUPABASE_URL = config["supabase_url"]
SUPABASE_KEY = config["supabase_anon_key"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

DEEP_PATTERNS = [
    "Decision Moment", "Utilitarian Hold", "Discovery Arc",
    "Hidden Competence", "Informed Resistance", "Provocation From Inside",
    "Hypothetical Narration", "Commanded Participation",
]
ARCHETYPES = ["Discovery", "Hidden Competence", "Known Expert"]
ARCHETYPE_BONUSES = {"Discovery": 1.0, "Hidden Competence": 2.0, "Known Expert": 1.0}


def supabase_get(table, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def supabase_post(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {**HEADERS, "Prefer": "return=representation"}
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def get_character(name):
    data = supabase_get("characters", {"name": f"ilike.{name}", "limit": "1"})
    if not data:
        data = supabase_get("characters", {"name": f"ilike.%{name}%", "limit": "1"})
    return data[0] if data else None


def get_compatible_moves(strength, technique):
    return supabase_get("moves", {
        "mrs": f"lte.{strength}", "mrt": f"lte.{technique}",
        "select": "id,name,description,tags,hints,mrs,mrt", "limit": "100",
    })


def get_recent_history(limit=20):
    return supabase_get("story_history", {"select": "*", "order": "created_at.desc", "limit": str(limit)})


def get_recent_feedback(limit=20):
    return supabase_get("feedback", {"select": "*", "order": "created_at.desc", "limit": str(limit)})


def get_character_images(name, limit=6):
    """Get a diverse spread of character images for Claude to choose from."""
    data = supabase_get("character_images", {"character_name": f"ilike.{name}", "select": "public_url,tags", "limit": "500"})
    if not data:
        return []
    if len(data) <= limit:
        return data
    # Pick images spread across the full range (not clustered at the start)
    step = len(data) // limit
    spread = [data[i * step] for i in range(limit)]
    return spread


def get_move_images(move_name, limit=5):
    cat = move_name.lower().replace(" ", "_").replace("-", "_")
    data = supabase_get("move_images", {"move_category": f"ilike.%{cat}%", "select": "public_url,move_name,move_category", "limit": "50"})
    if not data:
        data = supabase_get("move_images", {"move_name": f"ilike.%{move_name}%", "select": "public_url,move_name,move_category", "limit": "50"})
    return random.sample(data, limit) if len(data) > limit else data


def get_style_examples():
    data = supabase_get("training_set", {"select": "id,name,description", "limit": "257"})
    if data and len(data) > 2:
        samples = random.sample(data, 2)
        return [{"name": s["name"], "excerpt": (s.get("description") or "")[:300] + "..."} for s in samples]
    return []


def select_move(compatible, history, feedback, specific=None):
    if specific:
        for m in compatible:
            if specific.lower() in m["name"].lower():
                return m
    if not compatible:
        return None
    recent = [h.get("move_name") for h in history[:10] if h.get("move_name")]
    last3 = set(recent[:3])
    scored = []
    for m in compatible:
        score = 1.0
        if m["name"] in last3: score *= 0.05
        elif m["name"] in recent: score *= 0.3
        scored.append((m, score))
    moves, weights = zip(*scored)
    return random.choices(list(moves), weights=list(weights), k=1)[0]


def select_pattern(history):
    recent = [h.get("pattern") for h in history[:15] if h.get("pattern")]
    counts = Counter(recent)
    mx = max(counts.values()) if counts else 1
    weights = [(mx + 1 - counts.get(p, 0)) * (3.0 if counts.get(p, 0) == 0 else 1.0) for p in DEEP_PATTERNS]
    return random.choices(DEEP_PATTERNS, weights=weights, k=1)[0]


def select_archetype(history):
    recent = [h.get("archetype") for h in history[:10] if h.get("archetype")]
    counts = Counter(recent)
    total = len(recent) if recent else 1
    weights = []
    for a in ARCHETYPES:
        c = counts.get(a, 0)
        if total > 3 and c / total > 0.4: weights.append(0.01)
        else: weights.append((total + 1 - c) * ARCHETYPE_BONUSES.get(a, 1.0))
    return random.choices(ARCHETYPES, weights=weights, k=1)[0]


def build_notes(history, feedback):
    notes = []
    recent_moves = [h.get("move_name") for h in history[:5] if h.get("move_name")]
    if recent_moves: notes.append(f"Last 5 moves: {', '.join(recent_moves)}.")
    recent_arch = [h.get("archetype") for h in history[:3] if h.get("archetype")]
    if recent_arch: notes.append(f"Last 3 archetypes: {', '.join(recent_arch)}.")
    return " ".join(notes) if notes else "No history yet."


def build_feedback_summary(feedback):
    """Summarize recent feedback as LESSONS LEARNED for the next story."""
    if not feedback:
        return None
    lessons = []
    for fb in feedback[:5]:  # last 5 feedback entries
        worked = fb.get("what_worked")
        didnt = fb.get("what_didnt")
        rating = fb.get("rating")
        if worked:
            lessons.append(f"KEEP DOING (rated {rating}/5): {worked}")
        if didnt:
            lessons.append(f"STOP DOING (rated {rating}/5): {didnt}")
    if not lessons:
        return None
    return {
        "MANDATORY_READ": "You MUST read every lesson below and show how you will apply them BEFORE writing the story.",
        "lessons": lessons,
        "total_feedback_entries": len(feedback),
    }


def log_story(character_name, mode, move, pattern, archetype, image_urls):
    return supabase_post("story_history", {
        "character_name": character_name, "mode": mode,
        "move_name": move.get("name") if move else None,
        "pattern": pattern, "archetype": archetype, "image_urls": image_urls,
    })


def log_feedback(rating, worked, didnt):
    supabase_post("feedback", {"rating": int(rating) if rating else None, "what_worked": worked, "what_didnt": didnt})
    print(json.dumps({"status": "feedback_logged"}))


def run_selection(character_name, mode, rounds=1, move_name=None):
    character = get_character(character_name)
    if not character:
        print(json.dumps({"error": f"Character '{character_name}' not found"}))
        sys.exit(1)

    strength = character.get("strength") or 5
    technique = character.get("technique") or 5
    compatible = get_compatible_moves(strength, technique)
    history = get_recent_history(20)
    feedback = get_recent_feedback(20)

    char_imgs = get_character_images(character_name, 6)
    char_urls = [i["public_url"] for i in char_imgs]
    primary = char_urls[0] if char_urls else None
    style = get_style_examples()

    results = []
    used = set()

    for r in range(rounds):
        move = select_move(compatible, history, feedback, move_name if r == 0 else None)
        if move and move["name"] in used:
            other = [m for m in compatible if m["name"] not in used]
            if other: move = select_move(other, history, feedback)
        if move: used.add(move["name"])

        move_imgs = get_move_images(move["name"], 5) if move else []
        pattern = select_pattern(history)
        archetype = select_archetype(history)

        logged = log_story(character_name, mode, move, pattern, archetype, char_urls)
        story_id = logged[0].get("id") if logged else None

        results.append({
            "round": r + 1, "story_id": story_id,
            "move": {"name": move["name"], "description": move.get("description"), "tags": move.get("tags"), "hints": move.get("hints")} if move else None,
            "move_images": [i["public_url"] for i in move_imgs],
            "selected_pattern": pattern, "selected_archetype": archetype,
        })

    feedback_data = build_feedback_summary(feedback)

    output = {
        "▶▶▶_STEP_1_FEEDBACK_FIRST": "═══════════════════════════════════════════════════",
        "MANDATORY_FEEDBACK_CHECK": True,
        "FEEDBACK_INSTRUCTIONS": "You MUST read ALL feedback lessons below, then OUTPUT your feedback plan showing how you will apply EACH lesson, BEFORE choosing an image or writing anything. If you skip this, the story is INVALID and must be restarted.",
        "feedback_lessons": feedback_data,
        "▶▶▶_STEP_2_CHOOSE_IMAGE": "═══════════════════════════════════════════════════",
        "character_images": char_urls,
        "IMAGE_CHOICE_INSTRUCTIONS": "Look at ALL images above. Pick the one that best fits your story. Describe EVERY clothing item visible in that photo. This description becomes the ONLY outfit for the entire story.",
        "▶▶▶_STEP_3_OUTFIT_LOCK": "═══════════════════════════════════════════════════",
        "OUTFIT_LOCK_RULES": [
            "WARNING: The database HAS an 'outfit' column but it is EXCLUDED from this output ON PURPOSE. That column is a legacy default. IGNORE it completely.",
            "The character has NO default outfit in this output.",
            "The ONLY outfit is what you SEE in the chosen photo above.",
            "Do NOT invent: white shorts, black trunks, generic gym wear, or ANY clothing not visible in the photo.",
            "If the photo shows sneakers, the character wears sneakers. If barefoot, barefoot.",
            "If a move involves bare skin but the photo shows clothing there, ADAPT the move to account for clothing.",
            "BEFORE every clothing mention in the story, re-read your outfit description. If it doesn't match, FIX IT.",
            "VIOLATION = writing ANY clothing item you did not describe from the chosen photo.",
        ],
        "▶▶▶_STEP_4_WRITE_STORY": "═══════════════════════════════════════════════════",
        "character": {
            "name": character.get("name"),
            "characteristics": character.get("characteristics"), "context": character.get("context"),
            "genre": character.get("genre"), "tone": character.get("tone"),
            "aggression": character.get("aggression"), "strength": character.get("strength"),
            "technique": character.get("technique"), "dominance": character.get("dominance"),
            "showmanship": character.get("showmanship"), "finisher": character.get("finisher"),
            "NOTE": "There is NO outfit field here. Outfit comes ONLY from the chosen image.",
        },
        "primary_character_image": primary,
        "compatible_moves_list": [m["name"] for m in compatible[:20]],
        "style_examples": style, "anti_repetition_notes": build_notes(history, feedback),
        "mode": mode,
    }

    if rounds == 1: output.update(results[0])
    else: output["rounds"] = results
    print(json.dumps(output, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--character", type=str)
    p.add_argument("--mode", default="story", choices=["story", "photo", "roleplay", "fight"])
    p.add_argument("--rounds", type=int, default=1)
    p.add_argument("--move", type=str)
    p.add_argument("--log-feedback", action="store_true")
    p.add_argument("--rating", type=int)
    p.add_argument("--worked", type=str)
    p.add_argument("--didnt", type=str)
    args = p.parse_args()

    if args.log_feedback:
        log_feedback(args.rating, args.worked, args.didnt)
        return
    if not args.character:
        print(json.dumps({"error": "Missing --character"}))
        sys.exit(1)
    rounds = args.rounds if args.mode == "fight" else 3  # stories get 2-3 moves too
    run_selection(args.character, args.mode, rounds=rounds, move_name=args.move)

if __name__ == "__main__":
    main()
