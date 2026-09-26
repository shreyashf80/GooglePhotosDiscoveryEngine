"""
Tests for scoring logic (shared/constants.py) and analyze stage rule logic.

References:
  FR-70  — evidence strength
  FR-74  — hypothesis status
  FR-81  — severity weights
  FR-82  — stakes weights
  FR-83  — opportunity score
  FR-87  — gap score
  FR-88  — retrieval funnel stage mapping
"""

import pytest
from shared.constants import (
    compute_evidence_strength,
    compute_hypothesis_status,
    compute_severity,
    compute_stakes_weight,
    compute_gap_score,
    SEVERITY_WEIGHTS,
    STAKES_WEIGHTS,
)


# ---- FR-70: Evidence strength ----

class TestEvidenceStrength:
    def test_strong(self):
        assert compute_evidence_strength(30) == "strong"
        assert compute_evidence_strength(100) == "strong"

    def test_directional(self):
        assert compute_evidence_strength(15) == "directional"
        assert compute_evidence_strength(29) == "directional"

    def test_anecdotal(self):
        assert compute_evidence_strength(14) == "anecdotal"
        assert compute_evidence_strength(0) == "anecdotal"


# ---- FR-81: Severity scoring ----

class TestSeverity:
    def test_gave_up(self):
        assert compute_severity("gave_up") == 3.0

    def test_still_searching(self):
        assert compute_severity("still_searching") == 3.0

    def test_found_with_effort(self):
        assert compute_severity("found_with_effort") == 2.0

    def test_found_easily(self):
        assert compute_severity("found_easily") == 1.0

    def test_unknown_excluded(self):
        assert compute_severity("unknown") is None

    def test_nonsense_excluded(self):
        assert compute_severity("not_a_real_outcome") is None


# ---- FR-82: Stakes weights ----

class TestStakesWeight:
    def test_practical_urgent(self):
        assert compute_stakes_weight("practical_urgent") == 1.5

    def test_sentimental(self):
        assert compute_stakes_weight("sentimental") == 1.3

    def test_practical_routine(self):
        assert compute_stakes_weight("practical_routine") == 1.0

    def test_unknown(self):
        assert compute_stakes_weight("unknown") == 1.0

    def test_default(self):
        assert compute_stakes_weight("not_a_real_stakes") == 1.0


# ---- FR-74: Hypothesis status ----

class TestHypothesisStatus:
    def test_insufficient_data(self):
        assert compute_hypothesis_status(5, 2, 10) == "insufficient_data"

    def test_supported(self):
        # support >= 2 * contradict, relevant >= 15
        assert compute_hypothesis_status(20, 5, 25) == "supported"

    def test_contradicted(self):
        # contradict >= 2 * support, relevant >= 15
        assert compute_hypothesis_status(3, 10, 15) == "contradicted"

    def test_mixed(self):
        # Neither ratio met
        assert compute_hypothesis_status(10, 8, 20) == "mixed"

    def test_edge_exact_ratio(self):
        # support = exactly 2x contradict
        assert compute_hypothesis_status(10, 5, 15) == "supported"

    def test_zero_support_zero_contradict(self):
        assert compute_hypothesis_status(0, 0, 20) == "mixed"


# ---- FR-87: Gap score ----

class TestGapScore:
    def test_not_searchable(self):
        assert compute_gap_score(0.4, "no") == pytest.approx(0.4)

    def test_partial(self):
        assert compute_gap_score(0.4, "partial") == pytest.approx(0.2)

    def test_fully_searchable(self):
        assert compute_gap_score(0.4, "yes") == pytest.approx(0.0)

    def test_not_verified(self):
        assert compute_gap_score(0.4, "not_verified") is None


# ---- FR-88: Funnel stage mapping rules ----

class TestFunnelRules:
    """Test the funnel stage classification logic from analyze.py."""

    def test_express_no_queries(self):
        from pipeline.stages.analyze import _episode_hits_express
        ep = {"has_forgotten_cues": False}
        assert _episode_hits_express(ep, cues=[], queries=[]) is True

    def test_express_all_vague_cues(self):
        from pipeline.stages.analyze import _episode_hits_express
        ep = {"has_forgotten_cues": False}
        cues = [
            {"cue_type": "time_absolute", "value": "a while ago", "precision": "vague"},
            {"cue_type": "place_type", "value": "some café", "precision": "vague"},
        ]
        queries = [{"query_text": "cafe", "query_style": "keyword_object", "position": 1}]
        assert _episode_hits_express(ep, cues, queries) is True

    def test_express_has_forgotten_cues(self):
        from pipeline.stages.analyze import _episode_hits_express
        ep = {"has_forgotten_cues": True}
        cues = [{"cue_type": "person_named", "value": "John", "precision": "exact"}]
        queries = [{"query_text": "John", "query_style": "keyword_person", "position": 1}]
        assert _episode_hits_express(ep, cues, queries) is True

    def test_express_not_hit(self):
        from pipeline.stages.analyze import _episode_hits_express
        ep = {"has_forgotten_cues": False}
        cues = [{"cue_type": "person_named", "value": "John", "precision": "exact"}]
        queries = [{"query_text": "John", "query_style": "keyword_person", "position": 1}]
        assert _episode_hits_express(ep, cues, queries) is False

    def test_understand_zero_results(self):
        from pipeline.stages.analyze import _episode_hits_understand
        ep = {"failure_modes": ["zero_results"]}
        assert _episode_hits_understand(ep) is True

    def test_understand_wrong_results(self):
        from pipeline.stages.analyze import _episode_hits_understand
        ep = {"failure_modes": ["wrong_results", "vocabulary_mismatch"]}
        assert _episode_hits_understand(ep) is True

    def test_understand_not_hit(self):
        from pipeline.stages.analyze import _episode_hits_understand
        ep = {"failure_modes": ["too_many_results"]}
        assert _episode_hits_understand(ep) is False

    def test_evaluate_too_many(self):
        from pipeline.stages.analyze import _episode_hits_evaluate
        ep = {"failure_modes": ["too_many_results"], "workarounds": []}
        assert _episode_hits_evaluate(ep) is True

    def test_evaluate_timeline_scroll(self):
        from pipeline.stages.analyze import _episode_hits_evaluate
        ep = {"failure_modes": [], "workarounds": ["timeline_scroll"]}
        assert _episode_hits_evaluate(ep) is True

    def test_evaluate_not_hit(self):
        from pipeline.stages.analyze import _episode_hits_evaluate
        ep = {"failure_modes": ["zero_results"], "workarounds": ["asked_sender_resend"]}
        assert _episode_hits_evaluate(ep) is False

    def test_refine_refinement_missing(self):
        from pipeline.stages.analyze import _episode_hits_refine
        ep = {"failure_modes": ["refinement_missing"]}
        queries = [{"query_text": "x", "query_style": "keyword_object", "position": 1}]
        assert _episode_hits_refine(ep, queries) is True

    def test_refine_three_queries(self):
        from pipeline.stages.analyze import _episode_hits_refine
        ep = {"failure_modes": []}
        queries = [
            {"query_text": "a", "query_style": "keyword_object", "position": 1},
            {"query_text": "b", "query_style": "keyword_object", "position": 2},
            {"query_text": "c", "query_style": "keyword_object", "position": 3},
        ]
        assert _episode_hits_refine(ep, queries) is True

    def test_refine_two_queries_no_failure(self):
        from pipeline.stages.analyze import _episode_hits_refine
        ep = {"failure_modes": []}
        queries = [
            {"query_text": "a", "query_style": "keyword_object", "position": 1},
            {"query_text": "b", "query_style": "keyword_object", "position": 2},
        ]
        assert _episode_hits_refine(ep, queries) is False


# ---- Archetype stats computation ----

class TestArchetypeStatsComputation:
    """Test the archetype stats computation with synthetic data."""

    def test_basic_archetype_stats(self):
        from pipeline.stages.analyze import _compute_archetype_stats
        episodes = [
            {
                "episode_id": "e1", "archetype_primary": "vocabulary_mismatch",
                "outcome": "gave_up", "stakes": "sentimental",
                "photo_category": "people_moment", "photo_origin": "own_camera",
                "failure_modes": ["vocabulary_mismatch", "zero_results"],
                "workarounds": ["timeline_scroll"],
                "extraction_confidence": "high", "source": "reddit", "lang": "en",
            },
            {
                "episode_id": "e2", "archetype_primary": "vocabulary_mismatch",
                "outcome": "found_with_effort", "stakes": "practical_routine",
                "photo_category": "document_text", "photo_origin": "own_camera",
                "failure_modes": ["wrong_results"],
                "workarounds": ["none_gave_up"],
                "extraction_confidence": "high", "source": "playstore", "lang": "en",
            },
            {
                "episode_id": "e3", "archetype_primary": "provenance_lost",
                "outcome": "still_searching", "stakes": "practical_urgent",
                "photo_category": "screenshot_digital", "photo_origin": "received_messaging",
                "failure_modes": ["cue_not_supported"],
                "workarounds": ["asked_sender_resend"],
                "extraction_confidence": "medium", "source": "reddit", "lang": "hi",
            },
        ]
        cues_by_episode = {
            "e1": [{"cue_type": "subject_object", "value": "cake", "precision": "exact"}],
            "e2": [{"cue_type": "text_in_image", "value": "receipt", "precision": "exact"}],
            "e3": [{"cue_type": "source_sender", "value": "friend", "precision": "approximate"}],
        }

        stats = _compute_archetype_stats(episodes, cues_by_episode, {})
        assert len(stats) == 2

        vm_stat = [s for s in stats if s["archetype"] == "vocabulary_mismatch"][0]
        assert vm_stat["episode_count"] == 2
        assert vm_stat["avg_severity"] == 2.5  # (3.0 + 2.0) / 2
        assert vm_stat["avg_stakes_weight"] == 1.15  # (1.3 + 1.0) / 2
        assert vm_stat["evidence_strength"] == "anecdotal"

        pl_stat = [s for s in stats if s["archetype"] == "provenance_lost"][0]
        assert pl_stat["episode_count"] == 1
        assert pl_stat["avg_severity"] == 3.0

    def test_opportunity_score_normalization(self):
        from pipeline.stages.analyze import _compute_archetype_stats
        episodes = [
            {
                "episode_id": f"e{i}", "archetype_primary": "vocabulary_mismatch",
                "outcome": "gave_up", "stakes": "practical_urgent",
                "photo_category": "document_text", "photo_origin": "own_camera",
                "failure_modes": [], "workarounds": [],
                "extraction_confidence": "high", "source": "reddit", "lang": "en",
            }
            for i in range(10)
        ]
        stats = _compute_archetype_stats(episodes, {}, {})
        assert len(stats) == 1
        # Only one archetype -> it should be 100.0
        assert stats[0]["opportunity_score"] == 100.0

    def test_empty_episodes(self):
        from pipeline.stages.analyze import _compute_archetype_stats
        stats = _compute_archetype_stats([], {}, {})
        assert stats == []
