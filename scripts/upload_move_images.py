#!/usr/bin/env python3
"""
Upload move images to Supabase Storage with resizing.
Resizes images to fit within 500px on longest side using macOS sips,
uploads to move-images bucket. No metadata table needed.
"""

import json
import os
import shutil
import subprocess
import sys
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

SOURCE_DIR = Path("/Users/pouriamousavi/Documents/RPG/data/images/moves")
BUCKET_NAME = "move-images"
TEMP_DIR = Path("/tmp/fight-story-bot-resize-moves")
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


def file_exists_in_storage(category, filename):
    """Check if a file already exists in storage via HEAD request."""
    path = f"{category}/{filename}"
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


def upload_file(category, filename, file_path):
    """Upload a single file to Supabase Storage."""
    ext = filename.rsplit(".", 1)[-1].lower()
    content_type = "image/png" if ext == "png" else "image/jpeg"

    storage_path = f"{category}/{filename}"
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{urllib.request.quote(storage_path, safe='/')}"

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    headers = api_headers(content_type)
    headers["x-upsert"] = "true"

    status, body = api_request("POST", url, data=file_bytes, headers=headers, timeout=120)

    if status not in (200, 201):
        raise RuntimeError(f"Upload failed ({status}): {body[:200]}")


def get_image_files(folder):
    """Return sorted list of image files in a folder."""
    extensions = {".jpg", ".jpeg", ".png"}
    files = []
    for entry in os.listdir(folder):
        if Path(entry).suffix.lower() in extensions:
            files.append(entry)
    files.sort()
    return files


# ── Main ───────────────────────────────────────────────────────────────────────

def process_category(category_name, category_dir):
    """Process all images for a single move category."""
    images = get_image_files(category_dir)
    if not images:
        print(f"  No images found in {category_name}, skipping.")
        return

    total = len(images)
    print(f"\nProcessing {category_name}: {total} images")

    # Create temp dir for this category
    cat_temp = TEMP_DIR / category_name
    cat_temp.mkdir(parents=True, exist_ok=True)

    uploaded = 0
    skipped = 0
    errors = 0

    for i, filename in enumerate(images, 1):
        source_path = category_dir / filename

        # Check if already uploaded
        if file_exists_in_storage(category_name, filename):
            skipped += 1
            if skipped <= 3 or skipped % 50 == 0:
                print(f"  Skipping {category_name}: {i}/{total} (already exists) [{filename}]")
            continue

        temp_path = cat_temp / filename

        try:
            # Resize
            resize_image(source_path, temp_path)

            # Upload
            upload_file(category_name, filename, temp_path)
            uploaded += 1

            # Insert metadata into move_images table
            move_name = category_name.replace("_", " ").title()
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{urllib.request.quote(category_name, safe='')}/{urllib.request.quote(filename, safe='')}"
            meta = {
                "move_name": move_name,
                "move_category": category_name,
                "storage_path": f"{BUCKET_NAME}/{category_name}/{filename}",
                "public_url": public_url,
                "source": "bulk_import"
            }
            meta_url = f"{SUPABASE_URL}/rest/v1/move_images"
            meta_headers = api_headers("application/json")
            meta_headers["Prefer"] = "return=minimal"
            try:
                api_request("POST", meta_url, data=json.dumps(meta).encode(), headers=meta_headers, timeout=10)
            except Exception:
                pass  # Non-critical, continue

            # Progress
            print(f"  Uploading {category_name}: {i}/{total} [{filename}]")

        except Exception as e:
            errors += 1
            print(f"  ERROR {category_name}: {i}/{total} [{filename}] - {e}")

        finally:
            # Clean up individual temp file
            if temp_path.exists():
                temp_path.unlink()

    # Clean up temp dir for this category
    shutil.rmtree(cat_temp, ignore_errors=True)

    print(f"  Done {category_name}: uploaded={uploaded}, skipped={skipped}, errors={errors}")


def main():
    if not SOURCE_DIR.exists():
        print(f"Error: Source directory not found: {SOURCE_DIR}")
        sys.exit(1)

    # Create temp directory
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # Create bucket
    print("Creating storage bucket...")
    create_bucket()

    # Get category folders
    folders = sorted([
        d for d in os.listdir(SOURCE_DIR)
        if (SOURCE_DIR / d).is_dir()
    ])

    print(f"\nFound {len(folders)} move categories")

    for idx, folder_name in enumerate(folders, 1):
        category_dir = SOURCE_DIR / folder_name
        print(f"\n[{idx}/{len(folders)}] {folder_name}")
        try:
            process_category(folder_name, category_dir)
        except Exception as e:
            print(f"  FATAL ERROR for {folder_name}: {e}")

    # Final cleanup
    shutil.rmtree(TEMP_DIR, ignore_errors=True)

    print("\n" + "=" * 60)
    print("Upload complete!")
    print(f"Processed {len(folders)} categories")
    print("=" * 60)


if __name__ == "__main__":
    main()
