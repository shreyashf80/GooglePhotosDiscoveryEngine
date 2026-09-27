# Research Sources: Memory and Personal Photo Retrieval

Literature layer for the Recall Gap discovery engine (PRD literature layer, FR-62). Each `##` section is one source and one retrieval chunk. The `era` line says how to weigh it; the `tags` line lists the research questions (RQ) and hypotheses (H) it speaks to.

## How to read the eras

- **current (2022 to 2026):** evidence about today's apps and AI search. Use for "where retrieval breaks now".
- **memory_science:** how human memory and search behavior work. These mechanisms have not changed with smartphones, so older studies stay valid. Use for "what people remember and forget, and why".
- **historical_baseline:** pre-smartphone product studies. Use only for comparison with current data, never as evidence of how today's apps perform.

All findings were checked against the original paper or an official summary in September 2026. Two pre-smartphone product studies (Naaman 2004, Kirk 2006) were removed because they describe tools that no longer exist.

## Coverage map

| Research question / hypothesis | Sources |
|---|---|
| RQ: What old photos are hard to retrieve | Smartphone replication 2022, Whittaker 2010 (baseline) |
| RQ: What users remember | Sellen & Whittaker 2010, Elsweiler 2007, Arguello 2021 |
| RQ: What users forget | Wagenaar 1986, Henkel 2014, Elsweiler 2007 |
| RQ: How queries are formed with incomplete memory | Arguello 2021, Teevan 2004 |
| RQ: How people remember visual info over time | Wagenaar 1986, Shum 1998, Living-in-history 2021, Henkel 2014 |
| RQ: Where current retrieval breaks | Smartphone replication 2022, Survey 2024, DeepImageSearch 2026, Ask Photos 2024, TechCrunch 2026 |
| H1 Relational anchoring beats dates | Shum 1998, Living-in-history 2021, Sellen & Whittaker 2010, Wagenaar 1986 |
| H3 Vocabulary mismatch | Arguello 2021, Elsweiler 2007, DeepImageSearch 2026 |
| H4 Needle in a flood | Smartphone replication 2022, Survey 2024 |
| H6 Time drift | Wagenaar 1986, Shum 1998 |
| H7 Refinement dead end | Teevan 2004 |
| H8 Silent abandonment / believes lost | Smartphone replication 2022, Whittaker 2010, Sellen & Whittaker 2010, TechCrunch 2026 |

## Smartphone replication (2022): Retrieving family photos in the smartphone era

- **Citation:** It's too much for us to handle: The effect of smartphone use on long-term retrieval of family photos (2022). *Personal and Ubiquitous Computing*.
- **Link:** https://link.springer.com/article/10.1007/s00779-022-01677-x
- **era:** current (smartphone era replication of Whittaker 2010)
- **tags:** RQ-old-photos, RQ-where-breaks, H4, H8
- **Method:** Replicated the Whittaker et al. (2010) family photo retrieval study about a decade later, with smartphone users.
- **Findings:**
  - Smartphones greatly increased collection size.
  - Timeline, search and face recognition in smartphone apps reduced retrieval failures to 29% on average.
  - Retrieval from computer folders got worse: failures rose from 43% to 71%.
  - Overall failure rates and retrieval time were not significantly different from ten years earlier: bigger libraries cancelled out better search.
- **Relevance:** The most direct current evidence for the problem statement. Even with modern search, roughly 3 in 10 attempts to find a remembered family photo fail, and growing libraries offset search improvements (supports H4, needle in a flood).

## Personal image retrieval survey (2024): Challenges with growing collections

- **Citation:** Challenges of personal image retrieval and organization: An academic perspective (2024). Springer conference chapter.
- **Link:** https://link.springer.com/chapter/10.1007/978-3-031-57867-0_20
- **era:** current (2024)
- **tags:** RQ-where-breaks, H4, segments
- **Method:** Survey of university students, analyzed with a machine learning model (XGBoost, 73% accuracy) to find factors linked to retrieval difficulty.
- **Findings:**
  - Difficulty finding photos was associated with the number of photos taken per year, photos posted on social media, and photos stored across other devices.
  - Contributing issues included disorganization, poor labeling, sheer volume and photos scattered across devices.
- **Relevance:** Recent evidence that volume and fragmentation across devices drive retrieval difficulty. Connects to the backup and "believes lost" behavior seen in your Reddit data.

## Whittaker, Bergman & Clough (2010): Long-term family photo retrieval

- **Citation:** Whittaker, S., Bergman, O., & Clough, P. (2010). Easy on that trigger dad: a study of long term family photo retrieval. *Personal and Ubiquitous Computing*, 14(1).
- **Link:** https://link.springer.com/article/10.1007/s00779-009-0218-7
- **era:** historical_baseline (pre-smartphone; compare with the 2022 replication)
- **tags:** RQ-old-photos, RQ-where-breaks, H8, believes_lost
- **Method:** 18 parents who organized their family's digital photos attempted 71 retrieval tasks for significant events that were on average 3.1 years old.
- **Findings:**
  - Participants found the photos in only 61% of tasks, failing on almost 40%.
  - 75% of the failures involved photos participants believed were stored digitally but could not locate.
  - Retrieval took about 3 minutes on average (153 seconds when successful, 226 seconds when not).
  - Participants disagreed that retrieval was fast or easy (2.06 and 2.28 on a 5-point scale).
  - The few participants with systematic folder hierarchies succeeded more often.
- **Relevance:** Direct evidence that retrieving older personal photos fails often even for motivated users, and that people believe the photo exists but cannot reach it. Supports the `believes_lost` behavior and the core problem statement.

## Wagenaar (1986): Autobiographical memory over six years

- **Citation:** Wagenaar, W. A. (1986). My memory: A study of autobiographical memory over six years. *Cognitive Psychology*, 18, 225-252.
- **Link:** https://www.sciencedirect.com/science/article/abs/pii/0010028586900137
- **era:** memory_science (how human memory and search behavior work; does not expire)
- **tags:** RQ-forget, RQ-memory-over-time, H1, H6
- **Method:** The author recorded about 2,400 of his own life events over six years, each with what, who, where and when, then tested recall using those cues.
- **Findings:**
  - Temporal information ("when") functions differently from what, who and where as a memory cue.
  - Up to about 20% of events became irretrievable, though there was evidence none were completely forgotten, suggesting retrieval failure rather than loss.
  - Pleasant events were recalled better than unpleasant ones.
- **Relevance:** Classic evidence that "when" is a weak retrieval cue and that failure is often about access, not memory loss. Supports designing search around what, who and where rather than dates.

## Shum (1998): Temporal landmarks in autobiographical memory

- **Citation:** Shum, M. S. (1998). The role of temporal landmarks in autobiographical memory processes. *Psychological Bulletin*, 124(3), 423-442.
- **Link:** https://psycnet.apa.org/record/1998-11174-005
- **era:** memory_science (how human memory and search behavior work; does not expire)
- **tags:** RQ-memory-over-time, H1, H6
- **Findings:** People reconstruct when something happened by relating it to landmark events (a move, a wedding, a new job) rather than recalling calendar dates directly.
- **Relevance:** Theoretical basis for H1. If people date memories as "before or after" landmarks, a search that only accepts calendar dates mismatches how memory works.

## Living-in-history effect (2021): Dating memories by public events

- **Citation:** Living-in-history effect in the dating of important autobiographical memories (2021). *PMC* open access.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC8631255/
- **era:** memory_science (how human memory and search behavior work; does not expire)
- **tags:** RQ-memory-over-time, H1
- **Findings:**
  - 32% of important memories were dated by reference to public events; 58% for war veterans vs 28% for others.
  - Builds on Shum (1998) and Brown's transition theory: major transitions create life chapters that people use to organize and date memories.
- **Relevance:** Quantitative support that people anchor memories to events and life periods. Maps to the `time_event_anchor` and `time_life_stage` cues.

## Henkel (2014): Photo-taking impairment effect

- **Citation:** Henkel, L. A. (2014). Point-and-shoot memories: The influence of taking photos on memory for a museum tour. *Psychological Science*, 25(2), 396-402.
- **Link:** https://journals.sagepub.com/doi/abs/10.1177/0956797613504438
- **era:** memory_science (how human memory and search behavior work; does not expire)
- **tags:** RQ-forget, RQ-memory-over-time
- **Findings:**
  - People remembered objects they photographed less accurately than objects they only observed, and recalled fewer visual details about them.
  - Zooming in on a detail while photographing preserved memory for the object.
  - Explanation: people rely on the camera to remember for them.
- **Relevance:** Explains why users often recall the context around a photo (why, when, with whom) better than what is visually in it, which is exactly what visual-label search depends on.

## Sellen & Whittaker (2010): Beyond total capture

- **Citation:** Sellen, A. J., & Whittaker, S. (2010). Beyond total capture: a constructive critique of lifelogging. *Communications of the ACM*, 53(5), 70-77.
- **Link:** https://dl.acm.org/doi/10.1145/1735223.1735243
- **era:** memory_science (how human memory and search behavior work; does not expire)
- **tags:** RQ-remember, H1, H8
- **Findings:**
  - Five memory functions: recollecting, reminiscing, retrieving, reflecting and remembering intentions.
  - Psychological research shows place, events and people are stronger memory cues than time.
  - Digital collections are cues that trigger memory, not memories themselves.
  - Improved search alone did not increase use of personal archives; value depends on fitting how people actually remember.
- **Relevance:** Supports designing retrieval around people, places and events instead of dates, and cautions that better search technology alone may not change behavior.

## Elsweiler, Ruthven & Jones (2007): Memory lapses in personal information management

- **Citation:** Elsweiler, D., Ruthven, I., & Jones, C. (2007). Towards memory supporting personal information management tools. *Journal of the American Society for Information Science and Technology*, 58(7).
- **Link:** https://onlinelibrary.wiley.com/doi/abs/10.1002/asi.20570
- **era:** memory_science (how human memory and search behavior work; does not expire)
- **tags:** RQ-remember, RQ-forget, H3
- **Method:** Week-long diary study with 25 participants, plus questionnaires and interviews.
- **Findings:**
  - 261 memory lapses recorded, about 1.43 per participant per day.
  - People retained fragments of context (visual descriptions, surrounding events, emotions) but usually not enough detail for query-based search.
  - Design principles: support retrieval from small fragments of recollection and offer multiple ways in, not a single query box.
- **Relevance:** Strong support for the gap between what people remember (fragments of context) and what search requires (precise terms). Core to H3 and the gap matrix.

## Teevan, Alvarado, Ackerman & Karger (2004): Orienteering in directed search

- **Citation:** Teevan, J., Alvarado, C., Ackerman, M. S., & Karger, D. R. (2004). The perfect search engine is not enough: a study of orienteering behavior in directed search. *Proceedings of CHI 2004*.
- **Link:** https://www.microsoft.com/en-us/research/publication/perfect-search-engine-not-enough-study-orienteering-behavior-directed-search/
- **era:** memory_science (how human memory and search behavior work; does not expire)
- **tags:** RQ-queries, H7
- **Findings:**
  - Most search for known personal items did not use keyword search.
  - People preferred small navigation steps (orienteering) over jumping straight to the target, even when they knew what they wanted.
  - Orienteering let people specify less up front and understand results in context.
- **Relevance:** Reframes timeline scrolling as a rational strategy, not just a workaround. Suggests opportunities in guided, step-by-step narrowing rather than one perfect query (H7).

## Arguello et al. (2021): Tip-of-the-tongue known-item retrieval

- **Citation:** Arguello, J., Ferguson, A., Fine, E., Mitra, B., Zamani, H., & Diaz, F. (2021). Tip of the tongue known-item retrieval: A case study in movie identification. *Proceedings of CHIIR 2021*.
- **Link:** https://arxiv.org/abs/2101.07124
- **era:** memory_science (how human memory and search behavior work; does not expire)
- **tags:** RQ-queries, RQ-remember, H3
- **Findings:**
  - People describing partially remembered items draw on three kinds of information: the item's content, the circumstances of their earlier exposure to it, and their previous failed searches.
  - They hedge, use emotional language and make relative rather than absolute comparisons.
  - Such searches may need specialized query understanding.
- **Relevance:** Closest research analogue to "I remember a photo but can't describe it". Circumstances of exposure map to `source_sender`, `conversation_context` and `personal_state` cues.

## DeepImageSearch (2026): Context-aware retrieval in personal visual histories

- **Citation:** DeepImageSearch: Benchmarking multimodal agents for context-aware image retrieval in visual histories (2026). arXiv:2602.10809.
- **Link:** https://arxiv.org/abs/2602.10809
- **era:** current (2024 to 2026)
- **tags:** RQ-where-breaks, H1, H3
- **Findings:**
  - Frames personal image retrieval as reasoning across events in a photo timeline, where the target is identified through context spread over multiple photos.
  - The best model reached only 28.7% exact match and 55.0% F1; embedding-based retrieval reached roughly 12 to 14% Recall@3.
  - Main failures: breakdowns in multi-step reasoning, visual discrimination, and grounding the search in the right event or time.
- **Relevance:** Current AI still struggles with exactly the context-based queries users make ("the photo from after the trip"). Supports the claim that the gap is not solved by generic semantic search.

## Google (2024): Ask Photos announcement

- **Citation:** Google (2024). Ask Photos: A new way to search your photos with Gemini. Google Blog.
- **Link:** https://blog.google/products-and-platforms/products/photos/ask-photos-google-io-2024/
- **era:** current (2024 to 2026)
- **tags:** RQ-where-breaks, gap-matrix
- **Findings:** Google positioned Ask Photos as natural-language search that understands context and subjects of photos, can read text in images, answer questions such as where you camped last year, and remember user corrections. Google described it as experimental.
- **Relevance:** Documents the intended capabilities. Compare with the hands-on capability tests in `capability_reference.yaml`, where sender, personal state and relative-event queries still failed.

## TechCrunch (2026): User pushback on Ask Photos

- **Citation:** TechCrunch (10 March 2026). Google gives in to users' complaints over AI-powered Ask Photos search feature.
- **Link:** https://techcrunch.com/2026/03/10/google-gives-in-to-users-complaints-over-ai-powered-ask-photos-search-feature/
- **era:** current (2024 to 2026)
- **tags:** RQ-where-breaks, H8
- **Findings:**
  - Users reported that Ask Photos failed to find some photos and was less accurate than the previous search.
  - Google added a toggle on the search screen to switch between Ask Photos and classic search.
  - The rollout had been paused in mid-2025 to address latency.
- **Relevance:** Public evidence that the AI search layer has not closed the retrieval gap and that users actively revert. Useful context for the Ask Photos rows in the gap matrix.
