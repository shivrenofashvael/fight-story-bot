#!/usr/bin/env python3
"""
Backup Cloudflare R2 images and Supabase database tables to local storage.

Usage:
    python3 backup.py              # incremental backup (only new/changed since last run)
    python3 backup.py --full       # full backup (check every object)
    python3 backup.py --incremental  # same as default
"""

import argparse
import datetime
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

# ── Configuration ──
R2_ENDPOINT = "https://bdd925441bf82cc09aa0dbc918caa900.r2.cloudflarestorage.com"
R2_BUCKET = "database"
R2_ACCESS_KEY = "bb0c426f63b28e698e7566c494f33f17"
R2_SECRET_KEY = "e91c280b081cee046738b346cd804b0490c7eb7ca7260ce5ff070c3c6e8df15c"
R2_REGION = "auto"

SUPABASE_URL = "https://vfvljfwcrwvxttmxxzfa.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZmdmxqZndjcnd2eHR0bXh4emZhIiwi"
    "cm9sZSI6ImFub24iLCJpYXQiOjE3NzUxNjQ0MDQsImV4cCI6MjA5MDc0MDQwNH0."
    "MLeA_Gk_IC9YmfJepdhSyXUQ7gPS8SnfDb7fA4hIqx0"
)

BACKUP_DIR = Path("/Users/pouriamousavi/Documents/RPG/backup")
IMAGES_DIR = BACKUP_DIR / "images"
DB_DIR = BACKUP_DIR / "database"
LAST_BACKUP_FILE = BACKUP_DIR / ".last_backup"
MANIFEST_FILE = BACKUP_DIR / ".manifest.json"

SUPABASE_TABLES = [
    "characters",
    "moves",
    "training_set",
    "character_images",
    "move_images",
    "story_history",
    "feedback",
]

# ── AWS Signature V4 ──

def sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def get_signature_key(key, date_stamp, region, service):
    k_date = sign(("AWS4" + key).encode("utf-8"), date_stamp)
    k_region = sign(k_date, region)
    k_service = sign(k_region, service)
    return sign(k_service, "aws4_request")


def make_s3_request(method, path, query_params=None, headers_extra=None):
    """Make a signed S3 API request to R2."""
    now = datetime.datetime.utcnow()
    date_stamp = now.strftime("%Y%m%d")
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")

    host = R2_ENDPOINT.replace("https://", "")
    canonical_uri = "/" + path.lstrip("/")

    # Build sorted query string
    if query_params:
        sorted_params = sorted(query_params.items())
        canonical_querystring = urllib.parse.urlencode(sorted_params, quote_via=urllib.parse.quote)
    else:
        canonical_querystring = ""

    # Headers
    headers = {
        "host": host,
        "x-amz-date": amz_date,
        "x-amz-content-sha256": "UNSIGNED-PAYLOAD",
    }
    if headers_extra:
        headers.update(headers_extra)

    signed_headers = ";".join(sorted(headers.keys()))
    canonical_headers = ""
    for k in sorted(headers.keys()):
        canonical_headers += f"{k}:{headers[k]}\n"

    payload_hash = "UNSIGNED-PAYLOAD"

    canonical_request = (
        f"{method}\n"
        f"{canonical_uri}\n"
        f"{canonical_querystring}\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{payload_hash}"
    )

    credential_scope = f"{date_stamp}/{R2_REGION}/s3/aws4_request"
    string_to_sign = (
        f"AWS4-HMAC-SHA256\n"
        f"{amz_date}\n"
        f"{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )

    signing_key = get_signature_key(R2_SECRET_KEY, date_stamp, R2_REGION, "s3")
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"AWS4-HMAC-SHA256 Credential={R2_ACCESS_KEY}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    url = f"{R2_ENDPOINT}{canonical_uri}"
    if canonical_querystring:
        url += f"?{canonical_querystring}"

    req = urllib.request.Request(url, method=method)
    req.add_header("x-amz-date", amz_date)
    req.add_header("x-amz-content-sha256", "UNSIGNED-PAYLOAD")
    req.add_header("Authorization", authorization)

    return urllib.request.urlopen(req, timeout=120)


# ── R2 Operations ──

def list_all_objects():
    """List all objects in the R2 bucket using ListObjectsV2 with pagination."""
    objects = []
    continuation_token = None

    while True:
        params = {
            "list-type": "2",
            "max-keys": "1000",
        }
        if continuation_token:
            params["continuation-token"] = continuation_token

        resp = make_s3_request("GET", f"/{R2_BUCKET}", query_params=params)
        body = resp.read().decode("utf-8")
        root = ET.fromstring(body)

        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"

        for content in root.findall(f"{ns}Contents"):
            key = content.find(f"{ns}Key").text
            size_el = content.find(f"{ns}Size")
            etag_el = content.find(f"{ns}ETag")
            last_mod_el = content.find(f"{ns}LastModified")

            obj = {
                "key": key,
                "size": int(size_el.text) if size_el is not None else 0,
                "etag": etag_el.text.strip('"') if etag_el is not None else "",
                "last_modified": last_mod_el.text if last_mod_el is not None else "",
            }
            objects.append(obj)

        is_truncated = root.find(f"{ns}IsTruncated")
        if is_truncated is not None and is_truncated.text.lower() == "true":
            next_token = root.find(f"{ns}NextContinuationToken")
            if next_token is not None:
                continuation_token = next_token.text
            else:
                break
        else:
            break

        print(f"  Listed {len(objects)} objects so far...", end="\r")

    print(f"  Listed {len(objects)} objects total.       ")
    return objects


def download_object(key, dest_path):
    """Download a single object from R2 to local path."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    resp = make_s3_request("GET", f"/{R2_BUCKET}/{key}")
    data = resp.read()
    dest_path.write_bytes(data)
    return len(data)


# ── Manifest for tracking ──

def load_manifest():
    """Load the local manifest of previously backed-up files."""
    if MANIFEST_FILE.exists():
        try:
            return json.loads(MANIFEST_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_manifest(manifest):
    """Save the manifest to disk."""
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2))


# ── Supabase Export ──

def export_supabase_table(table_name):
    """Export a Supabase table as JSON. Handles pagination for large tables."""
    all_rows = []
    offset = 0
    page_size = 1000

    while True:
        url = (
            f"{SUPABASE_URL}/rest/v1/{table_name}"
            f"?select=*&offset={offset}&limit={page_size}"
        )
        req = urllib.request.Request(url)
        req.add_header("apikey", SUPABASE_KEY)
        req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
        req.add_header("Accept", "application/json")
        req.add_header("Prefer", "count=exact")

        try:
            resp = urllib.request.urlopen(req, timeout=60)
            data = json.loads(resp.read().decode("utf-8"))
            if not data:
                break
            all_rows.extend(data)
            if len(data) < page_size:
                break
            offset += page_size
        except urllib.error.HTTPError as e:
            print(f"  WARNING: Could not export '{table_name}': HTTP {e.code}")
            if e.code == 404:
                print(f"    Table '{table_name}' may not exist or RLS blocks access.")
            return None
        except Exception as e:
            print(f"  WARNING: Could not export '{table_name}': {e}")
            return None

    return all_rows


# ── Main Backup Logic ──

def backup_r2_images(full_mode=False):
    """Backup all R2 images to local storage."""
    print("\n[1/2] Backing up R2 images...")
    print("  Listing objects in R2 bucket...")

    remote_objects = list_all_objects()
    manifest = load_manifest()

    # Determine last backup time for incremental mode
    last_backup_time = None
    if not full_mode and LAST_BACKUP_FILE.exists():
        try:
            last_backup_time = LAST_BACKUP_FILE.read_text().strip()
            print(f"  Incremental mode: checking objects modified after {last_backup_time}")
        except IOError:
            pass

    new_count = 0
    skipped_count = 0
    error_count = 0
    total_new_bytes = 0

    for i, obj in enumerate(remote_objects, 1):
        key = obj["key"]
        size = obj["size"]
        etag = obj["etag"]
        local_path = IMAGES_DIR / key

        # Check if we need to download this file
        needs_download = False

        if key not in manifest:
            needs_download = True
        elif manifest[key].get("etag") != etag or manifest[key].get("size") != size:
            needs_download = True
        elif not local_path.exists():
            needs_download = True
        elif local_path.stat().st_size != size:
            needs_download = True

        # In incremental mode, skip objects that haven't changed since last backup
        if not full_mode and not needs_download:
            skipped_count += 1
            if i % 500 == 0:
                print(f"  Progress: {i}/{len(remote_objects)} checked, {new_count} new, {skipped_count} skipped", end="\r")
            continue

        # Download the object
        try:
            downloaded_bytes = download_object(key, local_path)
            manifest[key] = {
                "etag": etag,
                "size": size,
                "last_modified": obj["last_modified"],
                "backed_up_at": datetime.datetime.utcnow().isoformat(),
            }
            new_count += 1
            total_new_bytes += downloaded_bytes
            if new_count % 10 == 0 or new_count <= 5:
                print(f"  Downloaded: {key} ({size:,} bytes)")
            if new_count % 50 == 0:
                # Save manifest periodically
                save_manifest(manifest)
        except Exception as e:
            print(f"  ERROR downloading {key}: {e}")
            error_count += 1

        if i % 500 == 0:
            print(f"  Progress: {i}/{len(remote_objects)} checked, {new_count} new, {skipped_count} skipped", end="\r")

    # Final save
    save_manifest(manifest)
    print(f"\n  R2 backup done: {new_count} new/updated, {skipped_count} unchanged, {error_count} errors")

    return len(remote_objects), new_count, error_count


def backup_database():
    """Export all Supabase tables as JSON files."""
    print("\n[2/2] Exporting Supabase database tables...")
    DB_DIR.mkdir(parents=True, exist_ok=True)

    exported = 0
    for table in SUPABASE_TABLES:
        print(f"  Exporting '{table}'...", end=" ")
        rows = export_supabase_table(table)
        if rows is not None:
            dest = DB_DIR / f"{table}.json"
            dest.write_text(json.dumps(rows, indent=2, ensure_ascii=False, default=str))
            print(f"{len(rows)} rows")
            exported += 1
        else:
            print("skipped")

    print(f"  Database export done: {exported}/{len(SUPABASE_TABLES)} tables exported")
    return exported


def get_backup_size():
    """Calculate total backup directory size."""
    total = 0
    if BACKUP_DIR.exists():
        for f in BACKUP_DIR.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    return total


def format_size(num_bytes):
    """Format bytes as human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f}{unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f}PB"


def count_local_files():
    """Count image files in the backup directory."""
    count = 0
    if IMAGES_DIR.exists():
        for f in IMAGES_DIR.rglob("*"):
            if f.is_file():
                count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description="Backup R2 images and Supabase database")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full backup: re-check every object regardless of last backup time",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Incremental backup: only check objects modified since last run (default)",
    )
    args = parser.parse_args()

    full_mode = args.full
    mode_str = "FULL" if full_mode else "INCREMENTAL"

    print(f"{'=' * 60}")
    print(f"  R2 + Supabase Backup — {mode_str} mode")
    print(f"  Started at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Backup dir: {BACKUP_DIR}")
    print(f"{'=' * 60}")

    # Ensure backup directories exist
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    DB_DIR.mkdir(parents=True, exist_ok=True)

    start_time = time.time()

    # Step 1: Backup R2 images
    r2_total, r2_new, r2_errors = backup_r2_images(full_mode=full_mode)

    # Step 2: Export database tables
    db_exported = backup_database()

    # Update last backup timestamp
    LAST_BACKUP_FILE.write_text(datetime.datetime.utcnow().isoformat())

    # Calculate stats
    elapsed = time.time() - start_time
    local_file_count = count_local_files()
    total_size = get_backup_size()

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"Backup complete:")
    print(f"  R2 objects:      {r2_total}")
    print(f"  Local files:     {local_file_count} ({r2_new} new)")
    print(f"  Database tables: {db_exported} exported")
    print(f"  Total size:      {format_size(total_size)}")
    print(f"  Errors:          {r2_errors}")
    print(f"  Duration:        {elapsed:.1f}s")
    print(f"  Backup location: {BACKUP_DIR}")
    print(f"{'=' * 60}")

    if r2_errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
