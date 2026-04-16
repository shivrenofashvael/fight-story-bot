#!/usr/bin/env python3
"""
Upload character images to Supabase Storage with resizing.
Resizes images to fit within 500px on longest side using macOS sips,
uploads to character-images bucket, and inserts metadata into character_images table.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────────

SUPABASE_URL = "https://vfvljfwcrwvxttmxxzfa.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZmdmxqZndjcnd2eHR0bXh4emZhIiwi"
    "cm9sZSI6ImFub24iLCJpYXQiOjE3NzUxNjQ0MDQsImV4cCI6MjA5MDc0MDQwNH0."
    "MLeA_Gk_IC9YmfJepdhSyXUQ7gPS8SnfDb7fA4hIqx0"
)

SOURCE_DIR = Path("/Volumes/T7 Shield/Antigravity Projects/DeepGrapple/dataset/characters")
BUCKET_NAME = "character-images"
TEMP_DIR = Path("/tmp/fight-story-bot-resize")
SKIP_FOLDERS = {"imports_temp", "others"}
METADATA_BATCH_SIZE = 10
RESIZE_MAX_PX = 500


# ── Helpers ────────────────────────────────────────────────────────────────────

def api_headers(content_type=None):
    """Return standard Supabase API headers."""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def api_request(method, url, data=None, headers=None, timeout=60):
    """Make an HTTP request and return (status_code, response_body)."""
    if isinstance(data, dict):
        data = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, body
    except urllib.error.URLError as e:
        return 0, str(e.reason)


def create_bucket():
    """Create the storage bucket (idempotent)."""
    url = f"{SUPABASE_URL}/storage/v1/bucket"
    payload = {"id": BUCKET_NAME, "name": BUCKET_NAME, "public": True}
    status, body = api_request("POST", url, data=payload, headers=api_headers("application/json"))
    if status in (200, 201):
        print(f"Bucket '{BUCKET_NAME}' created.")
    elif "already exists" in body.lower() or status == 409:
        print(f"Bucket '{BUCKET_NAME}' already exists.")
    else:
        print(f"Warning: bucket creation returned {status}: {body}")


def file_exists_in_storage(character_name, filename):
    """Check if a file already exists in storage via HEAD request."""
    path = f"{character_name}/{filename}"
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{urllib.request.quote(path, safe='/')}"
    status, _ = api_request("HEAD", url, headers=api_headers())
    return status == 200


def resize_image(source_path, dest_path):
    """Resize image using macOS sips to fit within RESIZE_MAX_PX on longest side."""
    result = subprocess.run(
        ["sips", "-Z", str(RESIZE_MAX_PX), str(source_path), "--out", str(dest_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"sips failed: {result.stderr.strip()}")


def upload_file(character_name, filename, file_path):
    """Upload a single file to Supabase Storage. Returns public URL on success."""
    ext = filename.rsplit(".", 1)[-1].lower()
    content_type = "image/png" if ext == "png" else "image/jpeg"

    storage_path = f"{character_name}/{filename}"
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{urllib.request.quote(storage_path, safe='/')}"

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    headers = api_headers(content_type)
    # Upsert to handle re-runs
    headers["x-upsert"] = "true"

    status, body = api_request("POST", url, data=file_bytes, headers=headers, timeout=120)

    if status in (200, 201):
        public_url = (
            f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/"
            f"{urllib.request.quote(storage_path, safe='/')}"
        )
        return storage_path, public_url
    else:
        raise RuntimeError(f"Upload failed ({status}): {body[:200]}")


def insert_metadata_batch(records):
    """Insert a batch of metadata records into the character_images table."""
    if not records:
        return
    url = f"{SUPABASE_URL}/rest/v1/character_images"
    headers = api_headers("application/json")
    headers["Prefer"] = "return=minimal"
    status, body = api_request("POST", url, data=records, headers=headers)
    if status not in (200, 201):
        print(f"  Warning: metadata insert returned {status}: {body[:200]}")


def get_image_files(folder):
    """Return sorted list of image files in a folder."""
    extensions = {".jpg", ".jpeg", ".png"}
    files = []
    for entry in os.listdir(folder):
        if entry.startswith("._") or entry.startswith("."):
            continue
        if Path(entry).suffix.lower() in extensions:
            files.append(entry)
    files.sort()
    return files


# ── Main ───────────────────────────────────────────────────────────────────────

def process_character(character_name, character_dir):
    """Process all images for a single character."""
    images = get_image_files(character_dir)
    if not images:
        print(f"  No images found in {character_name}, skipping.")
        return

    total = len(images)
    print(f"\nProcessing {character_name}: {total} images")

    # Create temp dir for this character
    char_temp = TEMP_DIR / character_name
    char_temp.mkdir(parents=True, exist_ok=True)

    metadata_batch = []
    uploaded = 0
    skipped = 0
    errors = 0

    for i, filename in enumerate(images, 1):
        source_path = character_dir / filename

        # Check if already uploaded
        if file_exists_in_storage(character_name, filename):
            skipped += 1
            if skipped <= 3 or skipped % 50 == 0:
                print(f"  Skipping {character_name}: {i}/{total} (already exists) [{filename}]")
            continue

        temp_path = char_temp / filename

        try:
            # Resize
            resize_image(source_path, temp_path)

            # Upload
            storage_path, public_url = upload_file(character_name, filename, temp_path)
            uploaded += 1

            # Queue metadata
            metadata_batch.append({
                "character_name": character_name,
                "storage_path": f"{BUCKET_NAME}/{storage_path}",
                "public_url": public_url,
                "source": "bulk_import",
            })

            # Flush metadata batch
            if len(metadata_batch) >= METADATA_BATCH_SIZE:
                insert_metadata_batch(metadata_batch)
                metadata_batch = []

            # Progress
            print(f"  Uploading {character_name}: {i}/{total} [{filename}]")

        except Exception as e:
            errors += 1
            print(f"  ERROR {character_name}: {i}/{total} [{filename}] - {e}")

        finally:
            # Clean up individual temp file
            if temp_path.exists():
                temp_path.unlink()

    # Flush remaining metadata
    if metadata_batch:
        insert_metadata_batch(metadata_batch)

    # Clean up temp dir for this character
    shutil.rmtree(char_temp, ignore_errors=True)

    print(f"  Done {character_name}: uploaded={uploaded}, skipped={skipped}, errors={errors}")


def main():
    if not SOURCE_DIR.exists():
        print(f"Error: Source directory not found: {SOURCE_DIR}")
        print("Make sure the external drive is connected.")
        sys.exit(1)

    # Create temp directory
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # Create bucket
    print("Creating storage bucket...")
    create_bucket()

    # Get character folders
    folders = sorted([
        d for d in os.listdir(SOURCE_DIR)
        if (SOURCE_DIR / d).is_dir() and d not in SKIP_FOLDERS
    ])

    print(f"\nFound {len(folders)} character folders (skipping {SKIP_FOLDERS})")

    total_uploaded = 0
    total_errors = 0

    for idx, folder_name in enumerate(folders, 1):
        character_dir = SOURCE_DIR / folder_name
        print(f"\n[{idx}/{len(folders)}] {folder_name}")
        try:
            process_character(folder_name, character_dir)
        except Exception as e:
            print(f"  FATAL ERROR for {folder_name}: {e}")
            total_errors += 1

    # Final cleanup
    shutil.rmtree(TEMP_DIR, ignore_errors=True)

    print("\n" + "=" * 60)
    print("Upload complete!")
    print(f"Processed {len(folders)} characters")
    print("=" * 60)


if __name__ == "__main__":
    main()
