# Spec: Relevance Classification, Episode Extraction and Taxonomy

Version 1.0 | Google Photos Memory-Based Retrieval Discovery Engine

## 0. Principles (apply to every LLM call)

1. **Evidence only.** Extract what the post states or clearly shows. If a field is not supported by the text, return `unknown` or an empty list. Never guess.
2. **English output.** Input can be any language (English, Hindi, Hinglish, others). Every output field is written in English except `quote_original`.
3. **Unit of analysis.** One input record = one post, review, or comment. A record can contain 0 to 3 episodes (e.g. a Reddit comment describing two different photos).
4. **Cues forgotten must be explicit.** Only fill `cues_forgotten` if the user says they don't remember something or their behaviour clearly shows it ("I have no idea what year"). Absence of a cue is not forgetting.
5. **Batching.** Records are sent in batches of 10 to 20, each with a `record_id`. Output is an array keyed by the same `record_id`.

---

## 1. Stage 1: Relevance classification (Gemini Flash-Lite)

Each record gets exactly one `relevance_class`:

| Value | Definition | Example |
|---|---|---|
| `specific_episode` | User tried (or is trying) to find one particular photo or small set of photos | "Trying to find the pic of my dad's prescription from last year, search shows nothing" |
| `general_search_complaint` | Complains about search or finding photos in general, no specific target | "Google Photos search is useless now" |
| `success_or_tip` | User found a hard-to-find photo, or shares a method that works | "Tip: search the text on the receipt, it finds it instantly" |
| `lost_not_hidden` | Photo is gone or never saved: deletion, sync failure, backup loss, account issue | "All my 2023 photos disappeared after changing phones" |
| `irrelevant` | Anything else: pricing, storage, editing, UI unrelated to finding | "Why is storage so expensive" |

**Tie-breaking rules**
- If it describes a specific photo AND a general complaint, choose `specific_episode`.
- If the user is unsure whether the photo is lost or just unfindable, choose `specific_episode` and set `outcome: unknown`.
- `success_or_tip` records still go through extraction (they tell us which cues work).

Output per record:
```json
{ "record_id": "rd_123", "relevance_class": "specific_episode", "lang": "hi-Latn", "reason": "short English reason" }
```

Only `specific_episode`, `general_search_complaint` and `success_or_tip` go to Stage 2.

---

## 2. Stage 2: Episode extraction (Gemini Flash)

### 2.1 Record-level fields

| Field | Type | Notes |
|---|---|---|
| `record_id` | string | Passed through |
| `product` | enum | `google_photos`, `apple_photos`, `samsung_gallery`, `other` |
| `platform` | enum | `android`, `ios`, `web`, `unknown` |
| `mentions_ask_photos` | bool | True if Ask Photos or Gemini-based search is mentioned |
| `ask_photos_note` | string or null | One sentence on what happened with Ask Photos |
| `general_failure_modes` | list of enum | Only for `general_search_complaint`, uses the failure_mode enum |
| `episodes` | list (0 to 3) | Empty for general complaints |

### 2.2 Episode fields

| Field | Type | Definition |
|---|---|---|
| `target_description` | string | What they were looking for, in plain English, max 20 words |
| `photo_category` | enum | See 3.1 |
| `photo_origin` | enum | See 3.2 |
| `photo_age_bucket` | enum | `under_6m`, `6_12m`, `1_3y`, `3y_plus`, `unknown` |
| `photo_age_evidence` | string or null | The words that justify the age bucket |
| `cues_remembered` | list of cue objects | See 3.3 |
| `cues_forgotten` | list of {`cue_type`, `evidence`} | Explicit only |
| `queries_tried` | list of {`query_text`, `query_style`} | Verbatim query text, translated to English if needed, see 3.4 |
| `failure_modes` | list of enum | See 3.5 |
| `workarounds` | list of enum | See 3.6 |
| `outcome` | enum | `found_easily`, `found_with_effort`, `gave_up`, `still_searching`, `unknown` |
| `stakes` | enum | `sentimental`, `practical_routine`, `practical_urgent`, `unknown` |
| `role_hints` | list of enum | `parent`, `traveler`, `student`, `professional`, `caregiver`, `small_business`, `elderly_user` (only if stated) |
| `archetype_primary` | enum | See section 4 |
| `archetype_secondary` | enum or null | See section 4 |
| `emergent_label` | string or null | Only if `archetype_primary` is `emergent`, max 6 words |
| `summary_en` | string | 1 to 2 sentences, English. This is what gets embedded |
| `quote_original` | string | Most informative verbatim span, max 40 words, original language |
| `quote_en` | string | English translation of `quote_original` (same text if already English) |
| `extraction_confidence` | enum | `high`, `medium`, `low` |

**Definitions for `outcome`**
- `found_easily`: found via search on first or second try
- `found_with_effort`: found eventually through many queries, long scrolling or outside help
- `gave_up`: explicitly stopped trying or concluded it can't be found
- `still_searching`: post is a request for help

**Definitions for `stakes`**
- `sentimental`: emotional value (family, deceased relative, milestone)
- `practical_routine`: needed for an everyday task (recipe, product model, parking spot)
- `practical_urgent`: health, legal, financial, travel documents, or time pressure stated

---

## 3. Enum definitions

### 3.1 `photo_category` (what's in the photo)

| Value | Includes |
|---|---|
| `people_moment` | Candid or posed photos where people are the point |
| `event_occasion` | Weddings, birthdays, festivals, concerts, graduations |
| `travel_place` | Trips, landmarks, cafés, restaurants, outdoor places |
| `pet_animal` | Pets and animals |
| `food` | Meals, dishes, recipes |
| `object_product` | Products, items, cars, furniture, things to buy or remember |
| `document_text` | IDs, certificates, notes, whiteboards, forms, book pages |
| `health_medical` | Medicines, prescriptions, reports, injuries |
| `receipt_financial` | Receipts, bills, invoices, payment proof |
| `screenshot_digital` | Screenshots of chats, apps, websites, tickets |
| `meme_forward` | Memes, jokes, forwarded images |
| `other` | Anything else |
| `unknown` | Not stated |

Derived group (computed, not extracted): `memory` = people_moment, event_occasion, travel_place, pet_animal, food. `utility` = document_text, health_medical, receipt_financial, screenshot_digital, object_product.

### 3.2 `photo_origin` (how it got into the library)

`own_camera`, `received_messaging` (WhatsApp, Telegram, SMS, etc.), `shared_album_or_partner` (Google Photos sharing, partner sharing), `screenshot`, `downloaded_web`, `scanned`, `imported_device_or_backup`, `unknown`

### 3.3 Cue objects

```json
{ "cue_type": "time_event_anchor", "value": "around the Coldplay concert", "precision": "approximate" }
```

`precision`: `exact` (specific date, name, place), `approximate` (month, rough area, "around then"), `vague` ("a while ago", "some café")

| `cue_type` | Definition | Example |
|---|---|---|
| `time_absolute` | Calendar date, month or year | "March 2024" |
| `time_season` | Season, festival period, weather period | "during monsoon" |
| `time_life_stage` | A phase of the user's life | "when my son was a baby", "in college" |
| `time_event_anchor` | Relative to another remembered event | "right after our Goa trip" |
| `place_named` | A specific named place | "Goa", "Blue Tokai Bandra" |
| `place_type` | A kind of place | "a small café", "some beach" |
| `person_named` | A specific named person | "Riya" |
| `person_relation` | A person described by relationship | "my mom", "my manager" |
| `group_social` | Group or who was present | "the whole college gang" |
| `subject_object` | Main object or subject | "medicine strip", "birthday cake" |
| `scene_activity` | What was happening | "dancing", "hiking" |
| `text_in_image` | Words or numbers visible in the photo | "the bill said 1,240" |
| `source_sender` | Who sent it or which app it came from | "my friend sent it on WhatsApp" |
| `conversation_context` | What the chat or situation was about when it arrived | "when we were planning the trip" |
| `personal_state` | User's state at the time | "when I was sick", "when I was stressed about exams" |
| `emotional_tone` | Feeling associated with the photo | "the really funny one" |
| `purpose_use` | Why it was taken or why it's needed now | "needed it for insurance claim" |
| `adjacency` | Taken near another known photo | "right before the group selfie" |

Note: visual attributes, device details and file metadata are intentionally excluded in v1 to keep extraction accurate. If they appear, mention them in `summary_en` only.

### 3.4 `query_style`

`keyword_object`, `keyword_person`, `keyword_place`, `keyword_event`, `date_or_filter`, `text_ocr`, `natural_language` (a full sentence), `ask_photos_conversation`, `album_browse`, `unknown`

### 3.5 `failure_mode`

| Value | Definition |
|---|---|
| `zero_results` | Search returned nothing |
| `wrong_results` | Results returned but not the target |
| `too_many_results` | Right type of result, too many to scan |
| `cue_not_supported` | User remembers something the product can't search by (sender, event, context) |
| `vocabulary_mismatch` | User's words don't match how the system labels the photo |
| `date_imprecision` | User's date memory is off or the date filter was too rigid |
| `refinement_missing` | No way to narrow or correct results ("older", "not this") |
| `ask_photos_failure` | Ask Photos answered wrongly, refused, or was unavailable |
| `ui_friction` | Slow loading, scroll jumps, hard navigation |
| `unknown` | Failure implied but not described |

### 3.6 `workaround`

`timeline_scroll`, `date_jump`, `album_or_folder_browse`, `searched_source_app` (e.g. searched in WhatsApp), `asked_sender_resend`, `asked_someone_else`, `used_other_app`, `used_ask_photos`, `none_gave_up`, `other`

---

## 4. Archetype taxonomy

Assign one `archetype_primary`, optionally one `archetype_secondary`.

| Value | Definition | Typical signals |
|---|---|---|
| `needle_in_flood` | User remembers the subject but it appears in hundreds of photos; ranking fails | recurring subject, `too_many_results`, `timeline_scroll` |
| `vocabulary_mismatch` | User describes by meaning or purpose, system indexes by visual labels | `purpose_use` or `personal_state` cues, `zero_results` or `wrong_results` |
| `provenance_lost` | Photo came from someone else; user remembers sender or chat, not content details | `photo_origin` received, `source_sender` cue |
| `event_anchored_time` | User can place it relative to another event but not on a calendar | `time_event_anchor` or `time_life_stage` cues |
| `time_drift` | User has a date in mind but it's wrong or too imprecise | `date_imprecision`, date queries failing |
| `utility_lookup` | Functional photo needed for a task, remembered by text or purpose | utility category, `text_in_image`, `purpose_use` |
| `refinement_dead_end` | Several queries, no way to narrow, falls back to scrolling | 3+ queries, `refinement_missing` |
| `emergent` | None of the above fits well | Fill `emergent_label` |

Emergent labels are reviewed by the PM weekly and either promoted to the taxonomy or merged into an existing archetype.

---

## 5. Hypothesis evidence rules (computed in code, not by the LLM)

| ID | Hypothesis | Supporting if | Contradicting if |
|---|---|---|---|
| H1 | Relational anchoring beats dates | episode has `time_event_anchor` or `time_life_stage` cue AND no `time_absolute` with `exact` precision | episode has `time_absolute` exact AND outcome is found_easily |
| H2 | Received photos are hardest | `photo_origin` is received_messaging or shared_album_or_partner AND outcome in (gave_up, found_with_effort) | received origin AND outcome is found_easily |
| H3 | Vocabulary mismatch | failure includes `vocabulary_mismatch`, or cues include `purpose_use`/`personal_state` with zero or wrong results | same cue types AND found_easily |
| H4 | Needle in a flood | failure includes `too_many_results` | recurring subject AND found_easily |
| H5 | Utility photos are a distinct segment | compare cue and failure distributions between memory and utility groups (statistical, not per episode) | distributions not meaningfully different |
| H6 | Time drift grows with age | `date_imprecision` share rises with `photo_age_bucket` (statistical) | flat or falling share |
| H7 | Refinement dead end | 3+ queries tried AND workaround includes `timeline_scroll` | 3+ queries AND found via search |
| H8 | Silent abandonment | workaround includes `timeline_scroll` described as habitual, or `asked_sender_resend`, or `none_gave_up` | explicit "search always works for me" in `success_or_tip` |

Hypothesis status on the board: `supported`, `mixed`, `contradicted`, `insufficient_data` (fewer than 15 relevant episodes).

---

## 6. Worked examples

### Example A (English)
Input: "Trying to find a pic of the medicine my doctor gave me when I had dengue last year. Searched 'medicine', 'tablet', 'dengue'. Nothing. Ended up scrolling through like 3 months of photos."

```json
{
  "record_id": "ps_881",
  "product": "google_photos",
  "platform": "unknown",
  "mentions_ask_photos": false,
  "ask_photos_note": null,
  "general_failure_modes": [],
  "episodes": [{
    "target_description": "Photo of medicine prescribed during an illness last year",
    "photo_category": "health_medical",
    "photo_origin": "unknown",
    "photo_age_bucket": "6_12m",
    "photo_age_evidence": "last year",
    "cues_remembered": [
      {"cue_type": "subject_object", "value": "medicine from doctor", "precision": "approximate"},
      {"cue_type": "personal_state", "value": "when I had dengue", "precision": "approximate"},
      {"cue_type": "time_absolute", "value": "last year", "precision": "vague"}
    ],
    "cues_forgotten": [],
    "queries_tried": [
      {"query_text": "medicine", "query_style": "keyword_object"},
      {"query_text": "tablet", "query_style": "keyword_object"},
      {"query_text": "dengue", "query_style": "keyword_event"}
    ],
    "failure_modes": ["zero_results", "vocabulary_mismatch"],
    "workarounds": ["timeline_scroll"],
    "outcome": "found_with_effort",
    "stakes": "practical_urgent",
    "role_hints": [],
    "archetype_primary": "vocabulary_mismatch",
    "archetype_secondary": "refinement_dead_end",
    "emergent_label": null,
    "summary_en": "User searched for a medicine photo using illness and object keywords, got nothing, and found it by scrolling three months of timeline.",
    "quote_original": "Searched 'medicine', 'tablet', 'dengue'. Nothing. Ended up scrolling through like 3 months of photos.",
    "quote_en": "Searched 'medicine', 'tablet', 'dengue'. Nothing. Ended up scrolling through like 3 months of photos.",
    "extraction_confidence": "high"
  }]
}
```

Note: `found_with_effort` is used because scrolling "ended up" implies they found it. If unclear, use `unknown`.

### Example B (Hinglish)
Input: "Bhai woh photo nahi mil rahi jo Rohit ne WhatsApp pe bheji thi Lonavala trip ke time. Search mein Lonavala daala toh sirf meri khud ki photos aayi."

Key extracted fields:
- `photo_origin`: `received_messaging`
- `cues_remembered`: `person_named` "Rohit" (exact), `source_sender` "sent on WhatsApp" (exact), `time_event_anchor` "during Lonavala trip" (approximate)
- `queries_tried`: "Lonavala" / `keyword_place`
- `failure_modes`: `wrong_results`, `cue_not_supported`
- `outcome`: `still_searching`
- `archetype_primary`: `provenance_lost`, `archetype_secondary`: `event_anchored_time`
- `quote_en`: "Bro, I can't find the photo Rohit sent on WhatsApp during the Lonavala trip. When I searched Lonavala only my own photos showed up."

---

## 7. Edge cases

| Situation | Rule |
|---|---|
| Review is only a star rating with "search bad" | `general_search_complaint`, no episodes |
| Competitor review mentions switching from Google Photos | `product` = the app being reviewed; note comparison in `summary_en` |
| Reddit comment replies with a solution to another user | `success_or_tip`, extract the cues and query that worked |
| Photo found via Ask Photos | `workarounds` includes `used_ask_photos`, `mentions_ask_photos` true |
| Sarcasm or unclear outcome | `outcome: unknown`, `extraction_confidence: low` |
| Post over 1,500 words | Truncate to first 1,500 words before sending, flag `truncated: true` in DB |

---

## 8. Golden set (accuracy check)

Hand-label 30 records before running the full pipeline.

| Source | Count |
|---|---|
| Reddit | 10 |
| Play Store | 8 |
| App Store | 5 |
| Community forum | 4 |
| YouTube | 3 |

Must include: at least 5 Hindi or Hinglish, at least 5 `irrelevant`, at least 3 `lost_not_hidden`, at least 3 `success_or_tip`.

Metrics shown on the Methodology page:
- Relevance class accuracy (target 85%+)
- Per-field accuracy for enums: category, origin, outcome, archetype (target 75%+)
- Cue recall: share of hand-labelled cues the model found (target 70%+)

If any target is missed, revise definitions or prompt before the full run, not after.

---

## 9. Data sufficiency and decision points

The goal is not maximum volume. The goal is enough evidence to make four research decisions for Part 2.

### 9.1 Volume targets

| Metric | Minimum | Target |
|---|---|---|
| `specific_episode` records (all sources) | 120 | 200+ |
| `success_or_tip` records | 20 | 40+ |
| Episodes per hypothesis to assign a status | 15 | 30+ |
| Episodes per archetype for side-by-side comparison | 20 | 40+ |
| Episodes per segment cell (e.g. utility x received) | 10 | 20+ |

### 9.2 Evidence strength labels (shown everywhere in the UI)

| Label | Episode count | How to use it |
|---|---|---|
| `strong` | 30+ | Can drive a decision |
| `directional` | 15 to 29 | Worth testing in Part 2, not a conclusion |
| `anecdotal` | under 15 | Only as interview probes |

### 9.3 Decision points

| ID | Decision | Made from | Output for Part 2 |
|---|---|---|---|
| D1 | Which 2 to 3 hypotheses to validate | Hypothesis board: status `supported` or `mixed`, ranked by opportunity score | Hypotheses to test in interviews and retrieval tasks |
| D2 | Which user segments to recruit | Segment explorer: segments with highest `gave_up` + `found_with_effort` share | Screener criteria |
| D3 | Which archetype to go deep on | Archetype explorer: highest frequency x severity with at least `directional` evidence | Focus area for task-based testing |
| D4 | What to drop | Hypotheses `contradicted` or `insufficient_data` | Kill list, or kept only as open interview probes |

### 9.4 If volume falls short

Apply in this order until the minimums are met:
1. Add targeted Reddit and forum search terms: "can't find photo", "find old photo", "google photos search not working", "ask photos", Hindi and Hinglish equivalents.
2. Include YouTube comments on Ask Photos and Google Photos search tutorial videos.
3. Add competitor reviews (Apple Photos, Samsung Gallery) that describe the same retrieval behaviour.
4. Loosen Stage 1: treat `general_search_complaint` records with a clear failure mode as supporting evidence for failure-mode counts only.
