#!/usr/bin/env python3
"""Import CSV data into Supabase tables via REST API."""

import csv
import json
import urllib.request
import urllib.error
import sys
import os

SUPABASE_URL = "https://vfvljfwcrwvxttmxxzfa.supabase.co"
ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZmdmxqZndjcnd2eHR0bXh4emZhIiwi"
    "cm9sZSI6ImFub24iLCJpYXQiOjE3NzUxNjQ0MDQsImV4cCI6MjA5MDc0MDQwNH0."
    "MLeA_Gk_IC9YmfJepdhSyXUQ7gPS8SnfDb7fA4hIqx0"
)

BATCH_SIZE = 10

# Paths
CHARACTERS_CSV = "/Users/pouriamousavi/Documents/RPG/data/Characters_rows (1).csv"
MOVES_CSV = "/Users/pouriamousavi/Documents/RPG/data/Moves_rows (2).csv"
TRAINING_CSV = "/Users/pouriamousavi/Desktop/new_moves_output.csv"

# Setting and entry tag keywords
SETTING_KEYWORDS = [
    "bedroom", "couch", "mat", "gym", "apartment", "hotel",
    "living room", "floor", "carpet", "garage", "patio",
    "outdoor", "basement", "pool", "backyard", "kitchen",
    "bathroom", "studio",
]
ENTRY_KEYWORDS = [
    "standing", "seated", "side", "reverse", "front", "ground",
    "kneeling", "mounted", "figure-4", "transition",
]


def insert_batch(table_name, rows):
    """Insert a batch of rows into a Supabase table via REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{table_name}"
    data = json.dumps(rows).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "apikey": ANON_KEY,
            "Authorization": f"Bearer {ANON_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  ERROR {e.code}: {body}")
        raise


def safe_int(value):
    """Convert a value to int, returning None if empty or invalid."""
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def read_csv(path):
    """Read a CSV file and return (headers, rows) handling multi-line fields."""
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, quotechar='"', skipinitialspace=True)
        headers = next(reader)
        rows = list(reader)
    return headers, rows


def import_characters():
    """Import Characters CSV into the characters table."""
    print("=" * 60)
    print("IMPORTING CHARACTERS")
    print("=" * 60)

    headers, rows = read_csv(CHARACTERS_CSV)
    print(f"Read {len(rows)} character rows with columns: {headers}")

    # Column mapping: CSV header -> DB column
    column_map = {
        "Name": "name",
        "Outfit": "outfit",
        "Characteristics": "characteristics",
        "Context": "context",
        "Genre": "genre",
        "Finisher": "finisher",
        "Aggression level": "aggression",
        "Strength": "strength",
        "Technique": "technique",
        "Erotic actions": "erotic_actions",
        "id": "original_id",
        "Tone": "tone",
        "Dominance": "dominance",
        "Showmanship": "showmanship",
    }

    int_fields = {"aggression", "strength", "technique", "erotic_actions", "dominance", "showmanship"}

    db_rows = []
    for row in rows:
        if len(row) < len(headers):
            row.extend([""] * (len(headers) - len(row)))
        record = {}
        for i, h in enumerate(headers):
            db_col = column_map.get(h)
            if db_col is None:
                continue
            val = row[i].strip() if i < len(row) else ""
            if db_col in int_fields:
                val = safe_int(val)
            elif val == "":
                val = None
            record[db_col] = val
        db_rows.append(record)

    print(f"Prepared {len(db_rows)} records for insert")

    for i in range(0, len(db_rows), BATCH_SIZE):
        batch = db_rows[i : i + BATCH_SIZE]
        status = insert_batch("characters", batch)
        print(f"  Inserted characters {i + 1}-{i + len(batch)} (HTTP {status})")

    print(f"Done: {len(db_rows)} characters imported.\n")


def import_moves():
    """Import Moves CSV into the moves table."""
    print("=" * 60)
    print("IMPORTING MOVES")
    print("=" * 60)

    headers, rows = read_csv(MOVES_CSV)
    print(f"Read {len(rows)} move rows with columns: {headers}")

    column_map = {
        "id": "id",
        "Name": "name",
        "Description": "description",
        "Tags": "tags",
        "Hints": "hints",
        "MRS": "mrs",
        "MRT": "mrt",
    }

    db_rows = []
    for row in rows:
        if len(row) < len(headers):
            row.extend([""] * (len(headers) - len(row)))
        record = {}
        for i, h in enumerate(headers):
            db_col = column_map.get(h)
            if db_col is None:
                continue
            val = row[i].strip() if i < len(row) else ""
            if db_col == "id":
                val = safe_int(val)
            elif val == "":
                val = None
            record[db_col] = val
        db_rows.append(record)

    print(f"Prepared {len(db_rows)} records for insert")

    for i in range(0, len(db_rows), BATCH_SIZE):
        batch = db_rows[i : i + BATCH_SIZE]
        status = insert_batch("moves", batch)
        print(f"  Inserted moves {i + 1}-{i + len(batch)} (HTTP {status})")

    print(f"Done: {len(db_rows)} moves imported.\n")


def extract_tags(tags_str, keywords):
    """Extract tags from a comma-separated string that match any keyword. Returns a list for Postgres array columns."""
    if not tags_str:
        return []
    tags = [t.strip() for t in tags_str.split(",") if t.strip()]
    matched = []
    for tag in tags:
        tag_lower = tag.lower()
        for kw in keywords:
            if kw in tag_lower:
                matched.append(tag.strip())
                break
    return matched


def import_training_set():
    """Import Training Set CSV into the training_set table."""
    print("=" * 60)
    print("IMPORTING TRAINING SET")
    print("=" * 60)

    headers, rows = read_csv(TRAINING_CSV)
    print(f"Read {len(rows)} training set rows with columns: {headers}")

    column_map = {
        "id": "id",
        "Name": "name",
        "Description": "description",
        "Tags": "tags",
        "Hints": "hints",
        "MRS": "mrs",
        "MRT": "mrt",
    }

    db_rows = []
    for row in rows:
        if len(row) < len(headers):
            row.extend([""] * (len(headers) - len(row)))
        record = {}
        tags_val = ""
        for i, h in enumerate(headers):
            db_col = column_map.get(h)
            if db_col is None:
                continue
            val = row[i].strip() if i < len(row) else ""
            if db_col == "id":
                val = safe_int(val)
            elif db_col == "tags":
                tags_val = val
                if val == "":
                    val = None
            elif val == "":
                val = None
            record[db_col] = val

        # Extract setting_tags and entry_tags from the Tags field
        record["setting_tags"] = extract_tags(tags_val, SETTING_KEYWORDS)
        record["entry_tags"] = extract_tags(tags_val, ENTRY_KEYWORDS)
        db_rows.append(record)

    print(f"Prepared {len(db_rows)} records for insert")

    for i in range(0, len(db_rows), BATCH_SIZE):
        batch = db_rows[i : i + BATCH_SIZE]
        status = insert_batch("training_set", batch)
        print(f"  Inserted training_set {i + 1}-{i + len(batch)} (HTTP {status})")

    print(f"Done: {len(db_rows)} training_set rows imported.\n")


def main():
    print("Supabase CSV Importer")
    print(f"Target: {SUPABASE_URL}\n")

    try:
        import_characters()
    except Exception as e:
        print(f"FAILED importing characters: {e}\n")

    try:
        import_moves()
    except Exception as e:
        print(f"FAILED importing moves: {e}\n")

    try:
        import_training_set()
    except Exception as e:
        print(f"FAILED importing training_set: {e}\n")

    print("All imports complete.")


if __name__ == "__main__":
    main()
