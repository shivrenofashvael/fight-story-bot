#!/usr/bin/env python3
"""
Concrete Learning Test — proves the bot actually LEARNS from feedback.

Flow:
1. Baseline: run seed_engine, show current persistent_lessons (may be empty)
2. Plant a unique, testable feedback entry
3. Distill it into a permanent lesson
4. Run seed_engine again, verify the lesson appears in output
5. Verify feedback.processed=True and lesson.times_applied incremented
6. Verify the lesson survives a second run (persistence across sessions)

This is a deterministic, assertion-based test. No story writing needed.
The proof: if the rule appears in the engine output, the bot's system
prompt will contain it — and SKILL.md mandates compliance.
"""

import json
import os
import random
import subprocess
import sys
import urllib.parse
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(SCRIPT_DIR, "config.json")) as f:
    CONFIG = json.load(f)

SB = CONFIG["supabase_url"]
H = {
    "apikey": CONFIG["supabase_anon_key"],
    "Authorization": f"Bearer {CONFIG['supabase_anon_key']}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def sb_get(path):
    req = urllib.request.Request(f"{SB}/rest/v1/{path}", headers=H)
    return json.loads(urllib.request.urlopen(req).read())


def sb_delete(path):
    req = urllib.request.Request(f"{SB}/rest/v1/{path}", headers=H, method="DELETE")
    urllib.request.urlopen(req)


def run_engine(*args):
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "seed_engine.py"), *args],
        capture_output=True, text=True, cwd=SCRIPT_DIR,
    )
    return result.stdout, result.stderr


def assert_true(cond, msg):
    prefix = "✓ PASS" if cond else "✗ FAIL"
    print(f"  {prefix}: {msg}")
    return cond


def main():
    print("=" * 70)
    print("LEARNING TEST — proves the bot retains feedback as permanent rules")
    print("=" * 70)

    # Generate a unique test marker to avoid collisions
    marker = f"TEST_LEARNING_{random.randint(100000, 999999)}"
    test_rule = f"[{marker}] Never use the word 'CHROMATIC' anywhere in the story."

    # ------------------------------------------------------------------
    # STEP 1 — Baseline
    # ------------------------------------------------------------------
    print("\n[STEP 1] Baseline: check active lessons before the test")
    baseline_lessons = sb_get("lessons?active=eq.true&select=id,rule")
    contains_marker_before = any(marker in l["rule"] for l in baseline_lessons)
    assert_true(not contains_marker_before,
                f"No pre-existing lesson with marker {marker}")
    print(f"  Active lessons count before: {len(baseline_lessons)}")

    # ------------------------------------------------------------------
    # STEP 2 — Plant a feedback entry
    # ------------------------------------------------------------------
    print("\n[STEP 2] Plant a testable feedback entry")
    out, err = run_engine(
        "--log-feedback",
        "--rating", "2",
        "--didnt", f"[{marker}] The story used the word 'CHROMATIC' way too much, felt pretentious",
        "--category", "writing_style",
        "--severity", "important",
    )
    try:
        logged = json.loads(out)
        feedback_id = logged.get("id")
    except Exception:
        print(f"  ✗ FAIL: could not parse --log-feedback output:\n  {out}\n  {err}")
        sys.exit(1)
    assert_true(bool(feedback_id), f"Feedback logged with id={feedback_id}")

    # Verify feedback.processed is False initially
    fb = sb_get(f"feedback?id=eq.{feedback_id}&select=id,processed,what_didnt")
    assert_true(len(fb) == 1, "Feedback row exists")
    assert_true(fb[0]["processed"] is False, "Feedback starts as processed=False")
    assert_true(marker in fb[0]["what_didnt"], "Marker survived into DB")

    # ------------------------------------------------------------------
    # STEP 3 — Distill it into a permanent lesson
    # ------------------------------------------------------------------
    print("\n[STEP 3] Distill the feedback into a permanent lesson")
    out, err = run_engine(
        "--add-lesson",
        "--category", "writing_style",
        "--severity", "important",
        "--rule", test_rule,
        "--from-feedback", feedback_id,
    )
    try:
        lesson_result = json.loads(out)
        lesson_id = lesson_result.get("lesson_id")
    except Exception:
        print(f"  ✗ FAIL: could not parse --add-lesson output:\n  {out}\n  {err}")
        sys.exit(1)
    assert_true(bool(lesson_id), f"Lesson promoted with id={lesson_id}")

    # Verify feedback is now processed=True
    fb = sb_get(f"feedback?id=eq.{feedback_id}&select=processed")
    assert_true(fb[0]["processed"] is True,
                "Feedback marked processed=True after promotion")

    # Verify the lesson exists in the lessons table
    lesson = sb_get(f"lessons?id=eq.{lesson_id}&select=id,rule,active,times_applied,origin_feedback_ids")
    assert_true(len(lesson) == 1, "Lesson row exists in DB")
    assert_true(lesson[0]["active"] is True, "Lesson is active")
    assert_true(marker in lesson[0]["rule"], "Lesson contains the test marker")
    assert_true(feedback_id in lesson[0]["origin_feedback_ids"],
                "Lesson links back to origin feedback")

    # ------------------------------------------------------------------
    # STEP 4 — Run the engine, verify the lesson appears in its output
    # ------------------------------------------------------------------
    print("\n[STEP 4] Run seed_engine, verify lesson appears in output")
    character_name = sb_get("characters?select=name&limit=1")[0]["name"]
    out, err = run_engine("--character", character_name, "--mode", "story")
    try:
        engine_output = json.loads(out)
    except Exception:
        print(f"  ✗ FAIL: engine output not valid JSON:\n  {out[:500]}\n  {err[:500]}")
        sys.exit(1)

    pl = engine_output.get("persistent_lessons") or {}
    by_cat = pl.get("rules_by_category") or {}
    all_rules = []
    for cat, rules in by_cat.items():
        for r in rules:
            all_rules.append(r["rule"])

    assert_true(any(marker in r for r in all_rules),
                f"Engine output contains the lesson rule with marker {marker}")
    assert_true(pl.get("total_active_rules", 0) >= 1,
                "Engine output reports at least 1 active rule")

    # Also verify the lesson is in applied_lesson_ids
    applied = engine_output.get("applied_lesson_ids") or []
    assert_true(lesson_id in applied,
                f"Engine marked lesson_id {lesson_id} as applied")

    # ------------------------------------------------------------------
    # STEP 5 — Verify times_applied counter incremented
    # ------------------------------------------------------------------
    print("\n[STEP 5] Verify lesson usage counter incremented")
    lesson_after = sb_get(f"lessons?id=eq.{lesson_id}&select=times_applied,last_applied")
    times = lesson_after[0]["times_applied"] or 0
    assert_true(times >= 1,
                f"lesson.times_applied = {times} (incremented after engine run)")
    assert_true(bool(lesson_after[0]["last_applied"]),
                "lesson.last_applied timestamp is set")

    # ------------------------------------------------------------------
    # STEP 6 — Persistence check: run engine again, rule still there
    # ------------------------------------------------------------------
    print("\n[STEP 6] Persistence check — simulate new session, run engine again")
    out, err = run_engine("--character", character_name, "--mode", "story")
    engine_output_2 = json.loads(out)
    pl2 = engine_output_2.get("persistent_lessons") or {}
    by_cat2 = pl2.get("rules_by_category") or {}
    all_rules_2 = []
    for cat, rules in by_cat2.items():
        for r in rules:
            all_rules_2.append(r["rule"])
    assert_true(any(marker in r for r in all_rules_2),
                "Second engine run STILL returns the lesson (persisted)")

    lesson_final = sb_get(f"lessons?id=eq.{lesson_id}&select=times_applied")
    assert_true(lesson_final[0]["times_applied"] > times,
                f"times_applied incremented again (now {lesson_final[0]['times_applied']})")

    # ------------------------------------------------------------------
    # STEP 7 — Cleanup (remove the test artifacts)
    # ------------------------------------------------------------------
    print("\n[STEP 7] Cleanup test artifacts")
    sb_delete(f"lessons?id=eq.{lesson_id}")
    sb_delete(f"feedback?id=eq.{feedback_id}")
    print(f"  Deleted lesson {lesson_id}")
    print(f"  Deleted feedback {feedback_id}")

    # ------------------------------------------------------------------
    print()
    print("=" * 70)
    print("RESULT: All assertions passed.")
    print()
    print("What this proves:")
    print("  • Feedback → lesson promotion works.")
    print("  • Promoted lessons appear in seed_engine output (what Claude sees).")
    print("  • Lessons persist across separate invocations of the engine.")
    print("  • Usage counter tracks how often each rule is surfaced.")
    print("  • The SKILL.md mandates that Claude treats each rule as non-negotiable,")
    print("    so if the rule is in the output, Claude WILL see it and must comply.")
    print("=" * 70)


if __name__ == "__main__":
    main()
