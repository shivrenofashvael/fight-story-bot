#!/usr/bin/env python3
"""
Fight Story Bot — Seed Engine v3 (severity-aware + persistent lessons + male-only images)
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

FEEDBACK_CATEGORIES = [
    "writing_style", "pacing", "move_logic", "image_choice",
    "character_voice", "move_mechanics", "story_structure", "other",
]


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


def supabase_patch(table, match_params, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}?" + urllib.parse.urlencode(match_params)
    headers = {**HEADERS, "Prefer": "return=representation"}
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="PATCH")
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
        "select": "id,name,description,tags,hints,mrs,mrt,severity,forces_outcome,is_finisher,can_be_partial,image_fallback_category",
        "limit": "100",
    })


def get_recent_history(limit=20):
    return supabase_get("story_history", {"select": "*", "order": "created_at.desc", "limit": str(limit)})


def get_recent_feedback(limit=20, only_unprocessed=False):
    params = {"select": "*", "order": "created_at.desc", "limit": str(limit)}
    if only_unprocessed:
        params["processed"] = "eq.false"
    return supabase_get("feedback", params)


def get_active_lessons():
    """Fetch all active distilled lessons — these are the persistent rules."""
    return supabase_get("lessons", {
        "active": "eq.true",
        "select": "id,category,severity,rule,times_applied",
        "order": "severity.asc,times_applied.desc",
        "limit": "200",
    })


def get_character_images(name, limit=6):
    data = supabase_get("character_images", {"character_name": f"ilike.{name}", "select": "public_url,tags", "limit": "500"})
    if not data:
        return []
    if len(data) <= limit:
        return data
    step = len(data) // limit
    spread = [data[i * step] for i in range(limit)]
    return spread


def _query_images(category_pattern, male_only, limit=100):
    params = {
        "move_category": f"ilike.%{category_pattern}%",
        "select": "public_url,move_name,move_category,gender_check,tags",
        "limit": str(limit),
    }
    if male_only:
        params["gender_check"] = "eq.male_male"
    return supabase_get("move_images", params)


def get_move_images(move_name, limit=8, male_only=True, fallback_category=None):
    """Fetch move images, filtered to male_male by default.

    Cascade:
    1. Primary category + male_male
    2. Primary category + not_checked (tolerated until classifier runs)
    3. Fallback category (from moves.image_fallback_category) + male_male
    4. Fallback category + not_checked
    5. Primary category, any gender (last resort)
    Returns empty list if nothing matches anywhere.
    """
    cat = move_name.lower().replace(" ", "_").replace("-", "_")

    # 1. Primary + male_male
    data = _query_images(cat, male_only=True) if male_only else _query_images(cat, male_only=False)

    # 2. Primary + not_checked
    if not data and male_only:
        params = {
            "move_category": f"ilike.%{cat}%",
            "gender_check": "eq.not_checked",
            "select": "public_url,move_name,move_category,gender_check,tags",
            "limit": "100",
        }
        data = supabase_get("move_images", params)

    # 3. Fallback category: combine male_male AND not_checked to maximize variety
    # Only if fallback_category is explicitly set on the move.
    if not data and fallback_category:
        fb_male = _query_images(fallback_category, male_only=True)
        fb_unchecked_params = {
            "move_category": f"ilike.%{fallback_category}%",
            "gender_check": "eq.not_checked",
            "select": "public_url,move_name,move_category,gender_check,tags",
            "limit": "100",
        }
        fb_unchecked = supabase_get("move_images", fb_unchecked_params)
        seen = set()
        data = []
        for r in fb_male + fb_unchecked:
            key = r.get("public_url")
            if key and key not in seen:
                seen.add(key)
                data.append(r)

    # NO last-resort pulls from has_female / unclear images. If nothing clean
    # exists, return empty — the story proceeds without images for that move.
    if not data:
        return []
    return random.sample(data, limit) if len(data) > limit else data


def get_style_examples():
    data = supabase_get("training_set", {"select": "id,name,description", "limit": "257"})
    if data and len(data) > 2:
        samples = random.sample(data, 2)
        return [{"name": s["name"], "excerpt": (s.get("description") or "")[:300] + "..."} for s in samples]
    return []


def select_moves_sequence(compatible, history, rounds=3, specific_first=None):
    """Select a sequence of moves for the story, respecting finisher rules.

    Rules:
    - Only ONE finisher per story, and it MUST be last.
    - Moves that force_outcome != 'none' cannot appear mid-fight unless can_be_partial=true.
      (If they do appear mid-fight, the bot is warned they MUST be shown as aborted/partial.)
    - Anti-repetition: weight down moves from recent stories.
    """
    if not compatible:
        return []

    recent = [h.get("move_name") for h in history[:10] if h.get("move_name")]
    last3 = set(recent[:3])

    def score_move(m):
        s = 1.0
        if m["name"] in last3: s *= 0.05
        elif m["name"] in recent: s *= 0.3
        return s

    finishers = [m for m in compatible if m.get("is_finisher")]
    non_finishers = [m for m in compatible if not m.get("is_finisher")]

    selected = []
    used = set()

    # Handle specific first move
    if specific_first:
        for m in compatible:
            if specific_first.lower() in m["name"].lower():
                selected.append(m)
                used.add(m["name"])
                break

    # Fill middle moves with non-finishers (preferred) or partial-capable finishers
    mid_count = rounds - 1 - len(selected)
    mid_pool = [m for m in non_finishers if m["name"] not in used]
    if len(mid_pool) < mid_count:
        # Supplement with finishers that can be partial
        mid_pool += [m for m in finishers if m.get("can_be_partial") and m["name"] not in used]

    for _ in range(mid_count):
        candidates = [m for m in mid_pool if m["name"] not in used]
        if not candidates:
            break
        weights = [score_move(m) for m in candidates]
        pick = random.choices(candidates, weights=weights, k=1)[0]
        selected.append(pick)
        used.add(pick["name"])

    # Last move: prefer a finisher
    final_pool = [m for m in finishers if m["name"] not in used]
    if not final_pool:
        final_pool = [m for m in compatible if m["name"] not in used]
    if final_pool:
        weights = [score_move(m) for m in final_pool]
        selected.append(random.choices(final_pool, weights=weights, k=1)[0])

    return selected[:rounds]


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


def build_lessons_block(lessons):
    """Format persistent lessons for system-prompt injection."""
    if not lessons:
        return None
    by_cat = {}
    for l in lessons:
        cat = l.get("category") or "other"
        by_cat.setdefault(cat, []).append(l)

    formatted = {
        "MANDATORY_READ": (
            "These are PERMANENT RULES distilled from every piece of feedback Pouria has ever given. "
            "Every rule here is non-negotiable. If a rule applies to this story, you MUST follow it. "
            "If you violate a rule, the story is INVALID."
        ),
        "total_active_rules": len(lessons),
        "rules_by_category": {
            cat: [
                {"severity": l.get("severity"), "rule": l.get("rule"), "times_applied": l.get("times_applied", 0)}
                for l in ls
            ]
            for cat, ls in by_cat.items()
        },
    }
    return formatted


def build_unprocessed_feedback_block(unprocessed):
    """Raw feedback that hasn't been distilled into lessons yet."""
    if not unprocessed:
        return None
    return {
        "MANDATORY_DISTILL": (
            "These are RECENT FEEDBACK entries that have NOT yet been distilled into permanent lessons. "
            "BEFORE writing this story, you MUST: (1) apply them to this story, AND (2) call "
            "`python seed_engine.py --add-lesson --category <CAT> --severity <SEV> --rule \"<RULE>\" "
            "--from-feedback <FEEDBACK_ID>` to promote each one into a permanent rule. "
            f"Categories: {', '.join(FEEDBACK_CATEGORIES)}. Severities: critical/important/minor."
        ),
        "feedback_entries": [
            {
                "id": fb.get("id"),
                "rating": fb.get("rating"),
                "category": fb.get("category"),
                "severity": fb.get("severity"),
                "what_worked": fb.get("what_worked"),
                "what_didnt": fb.get("what_didnt"),
                "notes": fb.get("notes"),
                "created_at": fb.get("created_at"),
            }
            for fb in unprocessed
        ],
    }


def log_story(character_name, mode, moves_list, pattern, archetype, image_urls):
    """Log a story. moves_list can be multi-move; we log the first move name for backwards compat."""
    first_move = moves_list[0] if moves_list else None
    return supabase_post("story_history", {
        "character_name": character_name, "mode": mode,
        "move_name": first_move.get("name") if first_move else None,
        "pattern": pattern, "archetype": archetype, "image_urls": image_urls,
    })


def log_feedback(rating, worked, didnt, category=None, severity="important", notes=None, story_id=None):
    data = {
        "rating": int(rating) if rating else None,
        "what_worked": worked,
        "what_didnt": didnt,
        "processed": False,
    }
    if category and category in FEEDBACK_CATEGORIES:
        data["category"] = category
    if severity in ("critical", "important", "minor"):
        data["severity"] = severity
    if notes:
        data["notes"] = notes
    if story_id:
        data["story_id"] = story_id
    result = supabase_post("feedback", data)
    print(json.dumps({
        "status": "feedback_logged",
        "id": result[0].get("id") if result else None,
        "next_step": "Call --add-lesson to distill this into a permanent rule",
    }))


def add_lesson(category, severity, rule, from_feedback=None):
    """Promote one or more feedback entries into a permanent lesson."""
    if category not in FEEDBACK_CATEGORIES:
        print(json.dumps({"error": f"category must be one of {FEEDBACK_CATEGORIES}"}))
        sys.exit(1)
    if severity not in ("critical", "important", "minor"):
        print(json.dumps({"error": "severity must be critical/important/minor"}))
        sys.exit(1)

    origin_ids = []
    if from_feedback:
        origin_ids = from_feedback if isinstance(from_feedback, list) else [from_feedback]

    data = {
        "category": category,
        "severity": severity,
        "rule": rule,
        "origin_feedback_ids": origin_ids,
        "active": True,
    }
    result = supabase_post("lessons", data)

    # Mark source feedback as processed
    for fid in origin_ids:
        try:
            supabase_patch("feedback", {"id": f"eq.{fid}"}, {"processed": True})
        except Exception as e:
            print(f"  warn: could not mark feedback {fid} processed: {e}", file=sys.stderr)

    print(json.dumps({
        "status": "lesson_added",
        "lesson_id": result[0].get("id") if result else None,
        "marked_processed": origin_ids,
    }))


def retire_lesson(lesson_id):
    """Deactivate a lesson that's no longer relevant (e.g., contradicted by new feedback)."""
    supabase_patch("lessons", {"id": f"eq.{lesson_id}"}, {"active": False})
    print(json.dumps({"status": "lesson_retired", "id": lesson_id}))


def increment_lesson_usage(lesson_ids):
    """Track that lessons were applied to a story (so we know which are useful)."""
    from datetime import datetime
    now = datetime.utcnow().isoformat()
    for lid in lesson_ids:
        try:
            # Fetch current count
            current = supabase_get("lessons", {"id": f"eq.{lid}", "select": "times_applied"})
            count = (current[0].get("times_applied") or 0) + 1 if current else 1
            supabase_patch("lessons", {"id": f"eq.{lid}"}, {"times_applied": count, "last_applied": now})
        except Exception:
            pass


def run_selection(character_name, mode, rounds=3, move_name=None):
    character = get_character(character_name)
    if not character:
        print(json.dumps({"error": f"Character '{character_name}' not found"}))
        sys.exit(1)

    strength = character.get("strength") or 5
    technique = character.get("technique") or 5
    compatible = get_compatible_moves(strength, technique)
    history = get_recent_history(20)
    unprocessed_fb = get_recent_feedback(20, only_unprocessed=True)
    lessons = get_active_lessons()

    char_imgs = get_character_images(character_name, 6)
    char_urls = [i["public_url"] for i in char_imgs]
    primary = char_urls[0] if char_urls else None
    style = get_style_examples()

    # Select a sequence that respects finisher rules
    selected_moves = select_moves_sequence(compatible, history, rounds=rounds, specific_first=move_name)

    results = []
    for r, move in enumerate(selected_moves):
        imgs = get_move_images(
            move["name"], limit=8, male_only=True,
            fallback_category=move.get("image_fallback_category"),
        )
        pattern = select_pattern(history)
        archetype = select_archetype(history)

        results.append({
            "round": r + 1,
            "is_finisher_round": (r == len(selected_moves) - 1) and move.get("is_finisher", False),
            "move": {
                "name": move["name"],
                "description": move.get("description"),
                "tags": move.get("tags"),
                "hints": move.get("hints"),
                "severity": move.get("severity"),
                "forces_outcome": move.get("forces_outcome"),
                "is_finisher": move.get("is_finisher", False),
                "can_be_partial": move.get("can_be_partial", True),
            },
            "move_images": [i["public_url"] for i in imgs],
            "move_images_count": len(imgs),
            "selected_pattern": pattern,
            "selected_archetype": archetype,
        })

    # Log the story
    logged = log_story(character_name, mode, selected_moves,
                       results[0]["selected_pattern"] if results else None,
                       results[0]["selected_archetype"] if results else None,
                       char_urls)
    story_id = logged[0].get("id") if logged else None

    # Track lesson applications
    if lessons:
        increment_lesson_usage([l["id"] for l in lessons])

    output = {
        "▶▶▶_STEP_1_PERSISTENT_LESSONS": "═══════════════════════════════════════════════════",
        "PERSISTENT_LESSONS_INSTRUCTIONS": (
            "These are PERMANENT RULES distilled from every feedback Pouria has ever given. "
            "You MUST treat each one as non-negotiable. Before writing anything, output a "
            "'Lessons Applied' section showing how each rule affects your decisions for THIS story."
        ),
        "persistent_lessons": build_lessons_block(lessons),

        "▶▶▶_STEP_2_UNPROCESSED_FEEDBACK": "═══════════════════════════════════════════════════",
        "unprocessed_feedback": build_unprocessed_feedback_block(unprocessed_fb),

        "▶▶▶_STEP_3_CHOOSE_CHARACTER_IMAGE": "═══════════════════════════════════════════════════",
        "character_images": char_urls,
        "IMAGE_CHOICE_INSTRUCTIONS": (
            "Look at ALL character images above. Pick the one that best fits the story you will write. "
            "Describe EVERY clothing item visible. This is the ONLY outfit for the entire story."
        ),

        "▶▶▶_STEP_4_OUTFIT_LOCK": "═══════════════════════════════════════════════════",
        "OUTFIT_LOCK_RULES": [
            "The character has NO default outfit. The 'outfit' column in the DB is EXCLUDED on purpose.",
            "The ONLY outfit is what you SEE in the chosen photo.",
            "Do NOT invent clothing not visible in the photo.",
            "If a move mechanic references bare skin but photo shows clothing there, ADAPT the mechanic.",
            "VIOLATION = writing any clothing item you did not describe from the chosen photo.",
        ],

        "▶▶▶_STEP_5_STORY_STRUCTURE": "═══════════════════════════════════════════════════",
        "FINISHER_RULES": [
            "The LAST move in `rounds[]` is marked with `is_finisher_round: true` if it is a finisher.",
            "If is_finisher_round is true, the fight MUST END on that move. No surviving. No standing back up.",
            "forces_outcome tells you WHAT happens: unconscious = knocked out, broken_limb = limb breaks, incapacitated = can't continue, death = dies, none = continues.",
            "If a move with forces_outcome != 'none' appears in MID-sequence (not last), it MUST be shown as PARTIAL / aborted / escaped — otherwise the fight is over and later moves are impossible.",
            "If can_be_partial is false and the move is NOT the final move, something is wrong — do not soften it, but show an explicit reason the full outcome didn't occur (interruption, loss of grip, etc.).",
            "Cumulative damage: after a 'heavy' move, the opponent is visibly impaired. After two 'heavy' moves, they are barely functional.",
        ],
        "WRITING_STYLE_RULES": [
            "The move `description` field is PURE MECHANICS (what happens to bodies, anatomically). It is NOT prose. You MUST write fresh prose that conveys these mechanics — DO NOT copy phrases from the description.",
            "Never repeat metaphors across stories. Every physical sensation, every moment of dread, every stance description should be invented fresh.",
            "NEVER use move names as section headers. Reveal the move name inline, AFTER the hold is fully locked, as Pouria's dawning realization.",
            "First person, present tense, from Pouria's perspective.",
        ],

        "▶▶▶_STEP_6_CHARACTER_DATA": "═══════════════════════════════════════════════════",
        "character": {
            "name": character.get("name"),
            "characteristics": character.get("characteristics"),
            "context": character.get("context"),
            "genre": character.get("genre"),
            "tone": character.get("tone"),
            "aggression": character.get("aggression"),
            "strength": character.get("strength"),
            "technique": character.get("technique"),
            "dominance": character.get("dominance"),
            "showmanship": character.get("showmanship"),
            "finisher": character.get("finisher"),
            "NOTE": "No outfit field — outfit comes only from the chosen image.",
        },
        "primary_character_image": primary,
        "compatible_moves_available": len(compatible),
        "style_examples": style,
        "anti_repetition_notes": build_notes(history, unprocessed_fb),
        "mode": mode,
        "story_id": story_id,
        "rounds": results,
        "applied_lesson_ids": [l["id"] for l in lessons] if lessons else [],
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--character", type=str)
    p.add_argument("--mode", default="story", choices=["story", "photo", "roleplay", "fight"])
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--move", type=str)

    # Feedback
    p.add_argument("--log-feedback", action="store_true")
    p.add_argument("--rating", type=int)
    p.add_argument("--worked", type=str)
    p.add_argument("--didnt", type=str)
    p.add_argument("--category", type=str)
    p.add_argument("--severity", type=str, default="important")
    p.add_argument("--notes", type=str)
    p.add_argument("--story-id", type=str)

    # Lessons
    p.add_argument("--add-lesson", action="store_true")
    p.add_argument("--rule", type=str)
    p.add_argument("--from-feedback", type=str, action="append",
                   help="Feedback ID to mark as processed (can be repeated)")
    p.add_argument("--retire-lesson", type=str)
    p.add_argument("--list-lessons", action="store_true")

    args = p.parse_args()

    if args.log_feedback:
        log_feedback(args.rating, args.worked, args.didnt, args.category, args.severity, args.notes, args.story_id)
        return
    if args.add_lesson:
        if not (args.category and args.rule):
            print(json.dumps({"error": "--add-lesson requires --category and --rule"}))
            sys.exit(1)
        add_lesson(args.category, args.severity, args.rule, args.from_feedback)
        return
    if args.retire_lesson:
        retire_lesson(args.retire_lesson)
        return
    if args.list_lessons:
        lessons = get_active_lessons()
        print(json.dumps(lessons, indent=2, ensure_ascii=False))
        return

    if not args.character:
        print(json.dumps({"error": "Missing --character"}))
        sys.exit(1)
    rounds = args.rounds
    run_selection(args.character, args.mode, rounds=rounds, move_name=args.move)


if __name__ == "__main__":
    main()
