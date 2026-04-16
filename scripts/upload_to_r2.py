#!/usr/bin/env python3
"""
Upload images to Cloudflare R2 at ORIGINAL quality (no resize).
Updates Supabase metadata tables with R2 public URLs.
"""

import hashlib
import hmac
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ── R2 Config ──
R2_ENDPOINT = "https://bdd925441bf82cc09aa0dbc918caa900.r2.cloudflarestorage.com"
R2_BUCKET = "database"
R2_ACCESS_KEY = "bb0c426f63b28e698e7566c494f33f17"
R2_SECRET_KEY = "e91c280b081cee046738b346cd804b0490c7eb7ca7260ce5ff070c3c6e8df15c"
R2_PUBLIC_BASE = "https://pub-f8884b60a8de489aa360109963fd9e9f.r2.dev"

# ── Supabase Config ──
SUPABASE_URL = "https://vfvljfwcrwvxttmxxzfa.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZmdmxqZndjcnd2eHR0bXh4emZhIiwi"
    "cm9sZSI6ImFub24iLCJpYXQiOjE3NzUxNjQ0MDQsImV4cCI6MjA5MDc0MDQwNH0."
    "MLeA_Gk_IC9YmfJepdhSyXUQ7gPS8SnfDb7fA4hIqx0"
)

# ── Sources ──
CHAR_SOURCE = Path("/Volumes/T7 Shield/Antigravity Projects/DeepGrapple/dataset/characters")
MOVE_SOURCE = Path("/Users/pouriamousavi/Documents/RPG/data/images/moves")
SKIP_FOLDERS = {"imports_temp", "others", ".DS_Store"}

# ── 10GB Safety Limit ──
MAX_BYTES = 9_500_000_000  # 9.5GB hard limit (leave 500MB headroom)
total_uploaded_bytes = 0


def sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def get_signature_key(key, date_stamp, region, service):
    k_date = sign(("AWS4" + key).encode("utf-8"), date_stamp)
    k_region = sign(k_date, region)
    k_service = sign(k_region, service)
    return sign(k_service, "aws4_request")


def r2_upload(object_key, file_bytes, content_type="image/jpeg"):
    """Upload bytes to R2 using AWS Signature V4."""
    now = datetime.datetime.utcnow()
    date_stamp = now.strftime("%Y%m%d")
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    region = "auto"
    service = "s3"

    content_hash = hashlib.sha256(file_bytes).hexdigest()
    host = "bdd925441bf82cc09aa0dbc918caa900.r2.cloudflarestorage.com"
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
        "Content-Type": content_type,
    }

    url = f"{R2_ENDPOINT}/{R2_BUCKET}/{urllib.parse.quote(object_key, safe='/')}"
    req = urllib.request.Request(url, data=file_bytes, headers=headers, method="PUT")
    resp = urllib.request.urlopen(req, timeout=120)
    return resp.status


def r2_public_url(object_key):
    """Get the public URL for an R2 object."""
    return f"{R2_PUBLIC_BASE}/{urllib.parse.quote(object_key, safe='/')}"


def supabase_batch_upsert(table, rows):
    """Upsert rows to Supabase."""
    if not rows:
        return
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal,resolution=merge-duplicates",
    }
    body = json.dumps(rows).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        urllib.request.urlopen(req, timeout=30)
    except Exception as e:
        print(f"    Supabase upsert error: {e}", flush=True)


def get_content_type(filename):
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext == "png":
        return "image/png"
    elif ext == "webp":
        return "image/webp"
    return "image/jpeg"


def upload_single(prefix, name, filepath):
    """Upload a single file to R2. Returns (object_key, size) or (None, error_msg)."""
    global total_uploaded_bytes
    try:
        with open(filepath, "rb") as f:
            data = f.read()

        size = len(data)
        if total_uploaded_bytes + size > MAX_BYTES:
            return None, "SAFETY LIMIT: would exceed 9.5GB"

        object_key = f"{prefix}/{name}/{os.path.basename(filepath)}"
        ct = get_content_type(filepath)
        r2_upload(object_key, data, ct)
        total_uploaded_bytes += size
        return object_key, size
    except Exception as e:
        return None, str(e)


def process_folder(prefix, folder_name, folder_path, table, name_field):
    """Process all images in a folder: upload to R2, update Supabase metadata."""
    global total_uploaded_bytes

    files = sorted([
        f for f in os.listdir(folder_path)
        if not f.startswith(".") and f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    ])

    if not files:
        return

    total = len(files)
    print(f"\n  {folder_name}: {total} images", flush=True)

    ok = 0
    errs = 0
    meta_rows = []

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(upload_single, prefix, folder_name, os.path.join(folder_path, f)): f
            for f in files
        }
        for future in as_completed(futures):
            fname = futures[future]
            result, info = future.result()
            if result:
                ok += 1
                public_url = r2_public_url(result)
                row = {
                    name_field: folder_name,
                    "storage_path": f"r2://{R2_BUCKET}/{result}",
                    "public_url": public_url,
                    "source": "r2_bulk_import",
                }
                if table == "move_images":
                    row["move_category"] = folder_name.lower().replace(" ", "_")
                meta_rows.append(row)
            else:
                errs += 1
                if "SAFETY LIMIT" in str(info):
                    print(f"    STOPPED: {info}", flush=True)
                    pool.shutdown(wait=False, cancel_futures=True)
                    return

            if (ok + errs) % 25 == 0:
                print(f"    {folder_name}: {ok+errs}/{total} (ok={ok}, err={errs}) [{total_uploaded_bytes/1e9:.2f}GB used]", flush=True)

    # Batch insert metadata (don't update existing — insert new rows)
    for i in range(0, len(meta_rows), 20):
        batch = meta_rows[i:i + 20]
        supabase_batch_upsert(table, batch)

    print(f"    {folder_name}: done (uploaded={ok}, errors={errs}) [{total_uploaded_bytes/1e9:.2f}GB total]", flush=True)


def main():
    global total_uploaded_bytes
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    print(f"R2 Upload — Original Quality")
    print(f"Bucket: {R2_BUCKET}")
    print(f"Safety limit: {MAX_BYTES/1e9:.1f}GB\n")

    if mode in ("all", "characters"):
        if not CHAR_SOURCE.exists():
            print(f"ERROR: Character source not found: {CHAR_SOURCE}")
        else:
            folders = sorted([
                f for f in os.listdir(CHAR_SOURCE)
                if f not in SKIP_FOLDERS and not f.startswith(".") and os.path.isdir(CHAR_SOURCE / f)
            ])
            print(f"=== CHARACTER IMAGES ({len(folders)} characters) ===")
            for i, folder in enumerate(folders, 1):
                print(f"\n[{i}/{len(folders)}] {folder}", flush=True)
                process_folder("characters", folder, CHAR_SOURCE / folder, "character_images", "character_name")

                if total_uploaded_bytes >= MAX_BYTES:
                    print("\nSAFETY LIMIT REACHED. Stopping.", flush=True)
                    break

    if mode in ("all", "moves") and total_uploaded_bytes < MAX_BYTES:
        if not MOVE_SOURCE.exists():
            print(f"ERROR: Move source not found: {MOVE_SOURCE}")
        else:
            folders = sorted([
                f for f in os.listdir(MOVE_SOURCE)
                if not f.startswith(".") and os.path.isdir(MOVE_SOURCE / f)
            ])
            print(f"\n=== MOVE IMAGES ({len(folders)} categories) ===")
            for i, folder in enumerate(folders, 1):
                print(f"\n[{i}/{len(folders)}] {folder}", flush=True)
                process_folder("moves", folder, MOVE_SOURCE / folder, "move_images", "move_name")

                if total_uploaded_bytes >= MAX_BYTES:
                    print("\nSAFETY LIMIT REACHED. Stopping.", flush=True)
                    break

    print(f"\n{'='*50}")
    print(f"DONE. Total uploaded: {total_uploaded_bytes/1e9:.2f}GB / 9.5GB limit")
    print(f"Remaining headroom: {(MAX_BYTES - total_uploaded_bytes)/1e9:.2f}GB")


if __name__ == "__main__":
    main()
