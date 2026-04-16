# Fight Story Bot — Full Architecture Plan

## The Problem

Every story Claude generates converges on the same choreography, tone, and structure despite months of prompt engineering. Rules and blacklists fail because LLM defaults reassert at generation time.

## The Solution

A **Claude Desktop Custom Skill** backed by a **Supabase cloud database** that:

1. **Injects vivid choreographic prose** (500-1500 words) into context before each story — not rules, but a physical reality Claude must inhabit
2. **Sends character photos** mid-story ("imagine Amir in this outfit")
3. **Learns from feedback** — your post-story reactions shape future selections
4. **Accepts image uploads from your phone** — snap a photo, name the character, it's in the database
5. **Tracks everything online** — history, feedback, images, character data, moves, training set — all in Supabase, live and updatable from anywhere

---

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│           Claude Desktop App                 │
│  ┌───────────────────────────────────────┐  │
│  │  Fight Story Bot Skill                │  │
│  │  ├── SKILL.md (trigger + directives)  │  │
│  │  └── seed_engine.py (queries Supa-    │  │
│  │      base, selects seed, returns      │  │
│  │      creative brief + image URLs)     │  │
│  └───────────────────────────────────────┘  │
│                     │                        │
│         urllib HTTP requests                 │
│                     ▼                        │
│  ┌───────────────────────────────────────┐  │
│  │         Supabase (Cloud)              │  │
│  │                                       │  │
│  │  Database Tables:                     │  │
│  │  ├── characters (30 profiles)         │  │
│  │  ├── moves (818 moves)               │  │
│  │  ├── training_set (284 seeds)         │  │
│  │  ├── story_history (auto-logged)      │  │
│  │  └── feedback (ratings + notes)       │  │
│  │                                       │  │
│  │  Storage Buckets:                     │  │
│  │  ├── character-images/ (3,579 photos) │  │
│  │  └── move-images/ (826 photos)        │  │
│  │                                       │  │
│  │  Edge Functions:                      │  │
│  │  └── upload-image (phone → bucket)    │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘

┌──────────────────┐
│  Pouria's Phone  │
│  Opens upload    │──→ Supabase Edge Function
│  page, picks     │    → stores image + metadata
│  character,      │
│  snaps photo     │
└──────────────────┘
```

---

## What Happens In Each Mode

### 1. Story Mode: "Write a story between Pouria and Amir"

```
1. Skill triggers → runs seed_engine.py --character Amir --mode story
2. Script queries Supabase:
   - Fetches Amir's profile (stats, tone, outfit, characteristics)
   - Fetches all 284 training set entries
   - Fetches last 20 story_history entries
   - Fetches last 20 feedback entries (learns what scored well)
3. Anti-repetition engine selects:
   - A choreographic seed (full prose, 500-1500 words)
   - A deep pattern (Decision Moment, Utilitarian Hold, etc.)
   - An archetype (Discovery / Hidden Competence / Known Expert)
   - Weighted TOWARD patterns that got good feedback
   - Weighted AWAY from recently used seeds, settings, entries
4. Script picks 1-3 random Amir photos from Supabase storage
   - Returns public URLs Claude can display
5. Logs selection to story_history in Supabase
6. Outputs JSON to Claude with: seed prose, character data, image URLs, pattern, archetype
7. Claude writes the story:
   - Inhabits the seed's physical reality (positions, surfaces, clothing, entry)
   - Builds Pouria's inner experience ON TOP of that reality
   - At a key moment, says "imagine him like this:" and shows an Amir photo
     that matches the scene's outfit/setting
8. After the story, Claude asks: "How was this? (1-5) and any notes?"
9. Feedback → Supabase feedback table → influences next story
```

### 2. Photo Mode: Pouria uploads a character/move image

```
1. Pouria uploads a photo + says "write a story of Amir doing this to me"
2. Skill triggers → runs seed_engine.py --character Amir --mode photo
3. Script returns: character data, compatible moves, anti-repetition notes
   (NO seed selected — the uploaded IMAGE is the seed)
4. Claude analyzes the image:
   - Extracts: body positions, clothing, setting, hold configuration, physique
   - THIS becomes the choreographic reality
5. Claude writes from inside that visual
6. Feedback logged as usual
```

### 3. Roleplay Mode: "Roleplay as Danial"

```
1. Skill triggers → runs seed_engine.py --character Danial --mode roleplay
2. Script returns: full character profile (tone, dialogue style, aggression),
   opening scenario seed, 2-3 Danial photos for visual grounding
3. Claude BECOMES Danial — uses his voice, his mannerisms
4. Pouria types his own dialogue
5. Every 3-4 exchanges, skill silently picks a new seed for transitions
6. Danial's photos can appear during roleplay ("*cracks knuckles*" + photo)
```

### 4. Fight Mode: "FIGHT Pouria and Mehrab"

```
1. Skill triggers → runs seed_engine.py --character Mehrab --mode fight --rounds 3
2. Script selects 3 different seeds (one per round), different moves each
3. Claude writes 300-500 words per round, building an arc
4. Mehrab photos appear between rounds
```

### 5. Phone Image Upload

```
1. Pouria opens a simple web page (hosted as Supabase edge function)
2. Selects character name from dropdown
3. Takes or selects photo
4. Uploads → stored in Supabase storage bucket under character name
5. Metadata entry created in character_images table
6. Next time that character appears in a story, the new photo is in the pool
```

---

## Database Schema (Supabase)

### Table: characters
```sql
id              UUID PRIMARY KEY
name            TEXT UNIQUE NOT NULL
outfit          TEXT
characteristics TEXT
context         TEXT
genre           TEXT
finisher        TEXT
aggression      INTEGER (1-10)
strength        INTEGER (1-10)
technique       INTEGER (1-10)
tone            TEXT
dominance       INTEGER (1-10)
showmanship     INTEGER (1-10)
```

### Table: moves
```sql
id              INTEGER PRIMARY KEY
name            TEXT NOT NULL
description     TEXT
tags            TEXT
hints           TEXT
mrs             INTEGER  -- Minimum Required Strength
mrt             INTEGER  -- Minimum Required Technique
```

### Table: training_set
```sql
id              INTEGER PRIMARY KEY
name            TEXT
description     TEXT   -- The 500-1500 word choreographic prose
tags            TEXT   -- Comma-separated: "seated headscissors, couch, leggings..."
hints           TEXT
mrs             INTEGER
mrt             INTEGER
setting_tags    TEXT[] -- Extracted: ["couch", "apartment", "living room"]
entry_tags      TEXT[] -- Extracted: ["seated", "front headscissors"]
```

### Table: story_history
```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
created_at      TIMESTAMPTZ DEFAULT now()
character_name  TEXT REFERENCES characters(name)
mode            TEXT  -- story/photo/roleplay/fight
seed_id         INTEGER REFERENCES training_set(id)
seed_name       TEXT
move_name       TEXT
pattern         TEXT  -- Decision Moment, Utilitarian Hold, etc.
archetype       TEXT  -- Discovery, Hidden Competence, Known Expert
setting_tags    TEXT[]
entry_tags      TEXT[]
image_urls      TEXT[] -- which character photos were shown
```

### Table: feedback
```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
created_at      TIMESTAMPTZ DEFAULT now()
story_id        UUID REFERENCES story_history(id)
rating          INTEGER (1-5)
notes           TEXT  -- free text: "the entry was too similar to last time"
what_worked     TEXT  -- "the couch setting was great"
what_didnt      TEXT  -- "character felt too stoic again"
```

### Table: character_images
```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
character_name  TEXT REFERENCES characters(name)
storage_path    TEXT NOT NULL  -- path in Supabase storage bucket
public_url      TEXT NOT NULL
tags            TEXT[]  -- ["gym", "casual", "shirtless", "outdoor"]
uploaded_at     TIMESTAMPTZ DEFAULT now()
source          TEXT  -- "bulk_import" or "phone_upload"
```

### Storage Buckets
- `character-images/` — organized as `{character_name}/{filename}.jpg`
- `move-images/` — organized as `{move_category}/{filename}.jpg`

---

## Anti-Repetition Engine (in seed_engine.py)

### 5 Dimensions Tracked

| Dimension | Recency Window | Rule |
|-----------|---------------|------|
| Seed ID | last 30 stories | Hard exclude last 5, penalize last 30 (0.2x) |
| Deep Pattern | last 15 | Inverse frequency weighting |
| Archetype | last 10 | Exclude if >40% of window. 2x bonus for Hidden Competence |
| Setting tags | last 10 | Hard exclude last 2. Ban: underground/cage/basement |
| Entry method | last 10 | Hard exclude last 2. Ban: standing-bend-slides-in |

### Feedback Learning

- Stories with rating 4-5: their seed's tags get a 1.5x bonus in future selection
- Stories with rating 1-2: their seed's tags get a 0.3x penalty
- Specific "what_worked" notes get pattern-matched: if "couch setting" appears in good feedback, couch-tagged seeds get boosted
- Specific "what_didnt" notes: if "too stoic" appears, the script adds an explicit note "CHARACTER MUST NOT BE STOIC" to the output

---

## Feedback Flow

After every story, Claude asks:

```
---
How was this story?

Rate 1-5: ___
What worked? ___
What didn't? ___
```

Pouria can answer as briefly as "4, loved the couch migration, character was too quiet" or just "2" or skip entirely. Whatever he gives gets logged. Over time, the feedback table builds a preference profile that actively shapes seed selection.

---

## Image Integration

### Character Photos During Stories

The seed_engine.py script picks 1-3 photos of the character from Supabase storage and returns their public URLs. SKILL.md instructs Claude:

- At the start: "This is {character}:" + photo (sets the visual)
- Mid-story when describing outfit/physique: show a photo that matches
- Photos are selected based on tag relevance (if the seed involves gym setting, prefer gym-tagged photos)

### Future: Scene Generation

A future edge function could call an image generation API (DALL-E, Flux, etc.) with a prompt derived from the story's current moment. This would be triggered by a tool call from Claude. Not in Phase 1 but the architecture supports it — just add an edge function.

---

## Phone Upload Page

A minimal HTML page served by a Supabase edge function:

```
┌─────────────────────────────┐
│  Fight Story Bot - Upload   │
│                             │
│  Character: [Dropdown ▼]    │
│                             │
│  [📷 Take Photo]            │
│  [📁 Choose from Gallery]   │
│                             │
│  Tags (optional):           │
│  [gym] [casual] [outdoor]   │
│                             │
│  [Upload →]                 │
└─────────────────────────────┘
```

Opens in any phone browser. No app install. Photo goes straight to Supabase storage + metadata entry.

---

## Files to Build

### Phase 1: Supabase Setup
1. Create Supabase project "fight-story-bot"
2. Run migrations: all 6 tables above
3. Bulk import CSVs into tables (characters, moves, training_set)
4. Resize & upload 3,579 character images to storage (compress to ~500px wide for free tier 1GB limit)
5. Upload 826 move images to storage
6. Deploy upload-image edge function
7. Enable public access on storage buckets (images are not sensitive)

### Phase 2: Skill
8. `fight-story-bot/SKILL.md` — trigger + creative directives + priority hierarchy + feedback prompt
9. `fight-story-bot/seed_engine.py` — queries Supabase, runs anti-repetition, returns JSON with seed + images + character + pattern
10. `fight-story-bot/config.json` — Supabase URL + anon key (publishable, safe to embed)

### Phase 3: Data Pipeline
11. Python script to resize images and bulk-upload to Supabase storage
12. Python script to parse CSVs and insert into Supabase tables
13. Extract setting_tags and entry_tags from training_set descriptions

---

## Supabase Details

- **Organization**: AI Agent (gtrqzuolrisdytdrqiry)
- **Cost**: $0/month (free tier)
- **Free tier limits**: 500MB database, 1GB storage, 500K edge function invocations
- **Storage strategy**: Resize all images to ~500px wide before upload (~100KB each → ~440MB total, fits in 1GB)

---

## Verification Plan

1. Run seed_engine.py 10 times with same character → confirm 10 different seeds
2. Check Supabase story_history table grows correctly
3. Submit feedback for 5 stories → confirm next selections are influenced
4. Open phone upload page → upload a photo → confirm it appears in Supabase storage
5. In Claude Desktop: "Write a story between Pouria and Amir" → confirm:
   - Seed prose appears in context
   - Character photo is shown
   - Story inhabits the seed's choreography (not default standing-bend-lock)
   - Feedback prompt appears after story
6. Test Persian mode: "یه داستان بین پوریا و مهراب بنویس"
7. Test photo mode: upload a move image directly
8. Test roleplay mode: "Roleplay as Danial"
