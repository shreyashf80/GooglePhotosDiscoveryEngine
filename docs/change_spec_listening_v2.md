# Change Spec: Broad Listening and Data-Derived Hypotheses (v2)

Status: Approved | Date: 2026-09-27 | Overrides `PRD.md`, `extraction_spec.md` and `architecture.md` where they conflict; update those docs to match.

## 1. Purpose

The tool listens to **every public complaint and conversation about failing to find photos**, at volume. It groups the reasons people give **bottom-up**, and **the data produces the hypotheses**, ranked by how often and how independently they occur and how severe they are. User research comes later and validates them.

Changes from the previous design:
- The unit of evidence is a **signal** (any relevant post, review or comment), not a complete episode.
- No predefined hypotheses or archetypes drive the analysis.
- Scope is **core + adjacent**: every findability complaint is heard; adjacent ones (backup, sync, storage location, hidden places) are tagged and shown separately so core memory-based retrieval findings stay clean.

## 2. Flow

```
Collect (Play Store, App Store, YouTube, Reddit, Hacker News)
  -> Keyword prefilter (wide, multilingual)
  -> Filter v3: 7 classes, each with scope core / adjacent / out
  -> Signals v1: summary + 1 to 3 reasons in the user's framing + funnel stage per reason
  -> Themes: reasons clustered bottom-up, separately for core and adjacent, named by Gemini
  -> Ranking: occurrence x independence x severity
  -> Derived hypotheses (derive_hypotheses_v1) for themes above threshold
Detailed episodes (extract v2) continue only for specific_episode and success_or_tip, for the gap matrix
```

## 3. Collection strategy (volume first, cost second)

| Priority | Source | Method | Cost | Notes |
|---|---|---|---|---|
| 1 | Play Store: Google Photos (`com.google.android.apps.photos`), Samsung Gallery (`com.sec.android.gallery3d`) | `google-play-scraper` with continuation tokens, 200 per call, 60 s timeout per call, stop at 24-month cutoff. Locales: en-us, en-in, en-gb, en-ca, en-au, hi-in. Pull ratings 1 to 3 first, then 4 to 5. Up to 20,000 raw reviews total | Free | Keep only keyword matches before the LLM |
| 2 | App Store: Google Photos iOS (configurable id) | Try Apple's public customer reviews RSS feed first (JSON, up to 10 pages per country; countries us, in, gb, ca, au). If blocked, fall back to SerpApi `apple_reviews` up to 40 searches | Free / SerpApi | Record which method was used |
| 3 | YouTube | `search.list` for recent videos on finding old photos, Google Photos search, Ask Photos, Apple Photos search (up to 20 searches), then all comment pages within daily quota | Free quota | |
| 4 | Reddit (Apify) | Comment mining on every relevant thread first; then winning terms (`"google photos" "can't find"`, r/googlephotos `find`, `looking for`, `where is`, `search`), then r/iphone, r/applehelp, r/ios, r/samsung, r/Android, r/GooglePixel. Max 3 to 15 comments per post | Remaining Apify balance, stop $0.50 before zero | Estimate cost before each run |
| 5 | Hacker News | Algolia API, stories and comments on photo search, last 24 months, up to 500 | Free | |

**Keyword prefilter** (applied to every source before the LLM; configurable list): find, finding, search, searching, locate, looking for, can't see, cannot see, can't find, missing, disappeared, vanished, where did, where are, old photo, old pic, scroll, scrolling, results, ask photos, gemini, memories, face group, people album, backup, backed up, sync, not showing, whatsapp, dhoondh, dhundh, nahi mil, nhi mil, khoj, gayab, फोटो, ढूंढ, खोज, नहीं मिल, गायब.

All ingestion runs as background jobs logging to `data/collection.log`, resumable, idempotent.

## 4. Keep / Change / Add / Remove

### 4.1 Pipeline

| Component | Decision | Details |
|---|---|---|
| Ingestion | **Change** | Per section 3. |
| Filter v2 | **Replace** with `filter_v3.md` | 7 classes. Scope mapping: `specific_episode`, `general_search_complaint`, `success_or_tip`, `believes_lost` = core; `adjacent_findability` = adjacent; `lost_not_hidden`, `irrelevant` = out. Store `scope` on `raw_records`. |
| Reprocess | **Add** | Rerun filter v3 on every existing record that still has text. |
| Signals stage | **Add** | `signals_v1.md` on all core and adjacent records, batches of 20. |
| Extract v2 | **Keep, narrow** | Only `specific_episode` and `success_or_tip`, for cues and queries (gap matrix). Its archetype fields are ignored. |
| Embeddings | **Add** | BGE-small for `signal_summary_en` and each reason `text`, `halfvec(384)`. Episode embeddings stay. |
| Themes stage | **Add** | Cluster reason embeddings separately for core and adjacent (agglomerative, cosine; tune to 6 to 15 clusters per scope). Gemini names each cluster and writes one line. Clusters with fewer than 5 distinct authors go to "Other". |
| Ranking | **Add** | Per theme: `signals`, `distinct_authors` (after dedup), `sources` count, `severe_share` = share with outcome `gave_up`, `still_searching` or `believes_lost`. `rank_score = distinct_authors x (1 + severe_share)`. Formula shown in UI and configurable. |
| Evidence strength | **Change** | Based on distinct authors: strong 30+, directional 15 to 29, anecdotal under 15. |
| Derive hypotheses | **Add** | `derive_hypotheses_v1.md` for every theme with at least 10 distinct authors, core and adjacent. Hypotheses ranked by their theme's `rank_score`. Hypothesis evidence = the theme's signals. |
| Prior hypotheses H1 to H8 and their rules | **Remove from analysis and UI** | Leave the code dormant, don't run it in `analyze`. |
| Archetype stats, opportunity scores, emergent labels | **Remove** | Stop computing. |
| Funnel stats | **Change** | From reasons' `funnel_stage` across all signals, split by scope. |
| Gap matrix, cue stats, capability reference | **Keep** | Label "from N detailed episodes plus hands-on tests". |
| Segment stats | **Change** | Themes x source, product, class, language. |
| Duplicate detection | **Change** | Signals: same author, or same thread with summary cosine above 0.92. Duplicates excluded from counts. |
| Research handoff drafts | **Change** | Use each derived hypothesis's `research_question`; no separate LLM drafts. |
| Literature layer | **Keep** | Related research passed to derive stage by tag and embedding similarity; never affects counts. |
| `analyze` order | **Change** | dedup signals, embeddings, themes, ranking, derive hypotheses, funnel, gap matrix, segments. |

### 4.2 Database

| Item | Decision |
|---|---|
| Snapshot | Neon branch `before-listening-v2` before any migration or reprocessing |
| `raw_records` | Add `scope` |
| `signals` (record_id, summary_en, is_success, outcome, emotional_cost, frequency, product, platform, mentions_ask_photos, quote_original, quote_en, embedding, is_duplicate, prompt_version, model_id) | Add |
| `signal_reasons` (signal_id, text, funnel_stage, specificity, embedding, theme_id) | Add |
| `themes` (id, scope, name, description, signals, distinct_authors, sources_count, severe_share, rank_score, evidence_strength, mixes jsonb, quotes jsonb) | Add |
| `hypotheses` | Add `origin` (`data_derived`), `theme_id`, `rank`, and the derive output fields. Old H1 to H8 rows: set `origin = prior`, hidden |
| `archetype_stats`, `emergent_labels`, `hypothesis_evidence` for priors | Stop writing; don't drop |

### 4.3 API

| Route | Decision |
|---|---|
| `/themes?scope=`, `/themes/{id}` | Add |
| `/hypotheses` | Change: data-derived only, ranked |
| `/signals` (filters: scope, class, theme, source, product, funnel_stage, outcome) | Add; `/episodes` remains for cue detail |
| `/overview` | Change: signals by scope, class and source; top themes; funnel by scope |
| `/archetypes`, `/archetypes/compare`, `/emergent-labels` | Remove |
| `/segments` | Change: theme axis |
| `/handoff` | Change: ranked hypotheses with research questions |
| `/chat` | Change: retrieve signals plus research; top themes and hypotheses in the stats snapshot |

### 4.4 Frontend

| Page | Decision |
|---|---|
| Overview | **Change**: KPI "Retrieval signals" with core vs adjacent split and breakdown by source and class; top 5 core themes; funnel by scope |
| Themes (new, 2nd in sidebar) | **Add**: tabs Core / Adjacent; themes ranked by `rank_score` with signal count, distinct authors, sources, severe share, evidence strength, funnel mix, 3 quotes, link to signals; compare two themes |
| Hypothesis board | **Change**: data-derived hypotheses ranked, each showing statement, why we believe it, counter-evidence, what would disprove it, rank score, evidence strength, research note and linked signals. Adjacent hypotheses in a separate section. No prior hypotheses |
| Archetype explorer, emergent patterns | **Remove** |
| Gap matrix | **Keep** with episode-count note |
| Segment explorer | **Change**: themes instead of archetypes |
| Evidence browser | **Change**: all signals with filters (scope, class, theme, source, product, funnel stage, outcome); episodes show cue detail when expanded |
| Ask the corpus | **Keep**, citations to signals |
| Research handoff | **Change**: ranked hypotheses with their research questions; export as Markdown |
| How it works | **Change**: explain listening flow, scope tagging, ranking formula, limitations (public posts skew to frustrated users; failure is often silent; counts are signals, not prevalence) |

### 4.5 Files to delete

Scratch scripts in the repo root (`run_new_sources.py`, `make_v2_moves.py`, `reprocess.py` and similar). Move anything still needed into `/pipeline`.

## 5. Rules

1. Themes and hypotheses come only from signals. Research never creates or changes them.
2. Every theme and hypothesis links to its underlying signals.
3. Adjacent themes and hypotheses are always labeled "Adjacent: outside search" in the UI.
4. Prompts are versioned files; never edit in place.
5. Snapshot before migrations or bulk reprocessing. Never mock labels on real data.

## 6. Done when

- Overview shows total signals split core vs adjacent, by source and class.
- Themes page shows named core and adjacent themes, ranked, with quotes.
- Hypothesis board shows only data-derived hypotheses, ranked, each clickable to its signals.
- Archetypes, emergent labels and prior hypotheses are gone from UI and API.
- `analyze` reruns the whole flow end to end.
