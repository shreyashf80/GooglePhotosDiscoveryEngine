"""
Tests for shared enums, Pydantic models, and constants.

Validates:
  - Enum values match extraction_spec.md
  - Pydantic model validation (valid and invalid inputs)
  - Constants and scoring functions match PRD
  - Edge cases: max episodes, emergent label requirement, empty cue lists
"""

import pytest

from shared.enums import (
    Archetype,
    CueType,
    EvidenceStrength,
    ExtractionConfidence,
    FailureMode,
    HypothesisStatus,
    Outcome,
    PhotoCategory,
    PhotoOrigin,
    Precision,
    QueryStyle,
    RelevanceClass,
    Stakes,
    Workaround,
    MEMORY_CATEGORIES,
    UTILITY_CATEGORIES,
)
from shared.models import (
    ChatRequest,
    CueObject,
    EpisodeExtraction,
    FilterResult,
    ForgottenCue,
    QueryTried,
    RawRecord,
    RecordExtraction,
)
from shared.constants import (
    SEVERITY_WEIGHTS,
    STAKES_WEIGHTS,
    compute_evidence_strength,
    compute_gap_score,
    compute_hypothesis_status,
    compute_severity,
    compute_stakes_weight,
)


# ============================================================
# Enum tests
# ============================================================

class TestEnums:
    def test_relevance_class_values(self):
        assert set(RelevanceClass) == {
            "specific_episode", "general_search_complaint",
            "success_or_tip", "lost_not_hidden", "irrelevant",
        }

    def test_photo_category_count(self):
        # 13 values per spec Section 3.1
        assert len(PhotoCategory) == 13

    def test_memory_utility_groups(self):
        assert PhotoCategory.PEOPLE_MOMENT in MEMORY_CATEGORIES
        assert PhotoCategory.DOCUMENT_TEXT in UTILITY_CATEGORIES
        # No overlap
        assert MEMORY_CATEGORIES & UTILITY_CATEGORIES == set()

    def test_cue_type_count(self):
        # 18 cue types per spec Section 3.3
        assert len(CueType) == 18

    def test_failure_mode_values(self):
        assert "zero_results" in [fm.value for fm in FailureMode]
        assert "unknown" in [fm.value for fm in FailureMode]

    def test_archetype_values(self):
        assert len(Archetype) == 8
        assert Archetype.EMERGENT == "emergent"


# ============================================================
# Pydantic model tests
# ============================================================

class TestCueObject:
    def test_valid_cue(self):
        cue = CueObject(cue_type="time_absolute", value="March 2024", precision="exact")
        assert cue.cue_type == CueType.TIME_ABSOLUTE
        assert cue.precision == Precision.EXACT

    def test_invalid_cue_type(self):
        with pytest.raises(ValueError):
            CueObject(cue_type="invalid_type", value="test", precision="exact")

    def test_invalid_precision(self):
        with pytest.raises(ValueError):
            CueObject(cue_type="time_absolute", value="test", precision="very_exact")


class TestEpisodeExtraction:
    def _make_episode(self, **overrides):
        defaults = {
            "target_description": "Photo of a medicine",
            "photo_category": "health_medical",
            "photo_origin": "own_camera",
            "outcome": "found_with_effort",
            "archetype_primary": "vocabulary_mismatch",
            "summary_en": "User searched for medicine photo.",
            "quote_original": "Searched 'medicine', nothing.",
            "quote_en": "Searched 'medicine', nothing.",
            "extraction_confidence": "high",
        }
        defaults.update(overrides)
        return EpisodeExtraction(**defaults)

    def test_valid_episode(self):
        ep = self._make_episode()
        assert ep.photo_category == PhotoCategory.HEALTH_MEDICAL
        assert ep.outcome == Outcome.FOUND_WITH_EFFORT

    def test_emergent_requires_label(self):
        with pytest.raises(ValueError, match="emergent_label is required"):
            self._make_episode(archetype_primary="emergent")

    def test_emergent_with_label(self):
        ep = self._make_episode(
            archetype_primary="emergent",
            emergent_label="shared album confusion",
        )
        assert ep.emergent_label == "shared album confusion"

    def test_invalid_outcome(self):
        with pytest.raises(ValueError):
            self._make_episode(outcome="invalid_outcome")

    def test_default_empty_lists(self):
        ep = self._make_episode()
        assert ep.cues_remembered == []
        assert ep.cues_forgotten == []
        assert ep.queries_tried == []
        assert ep.failure_modes == []
        assert ep.workarounds == []

    def test_with_cues_and_queries(self):
        ep = self._make_episode(
            cues_remembered=[
                {"cue_type": "subject_object", "value": "medicine", "precision": "approximate"}
            ],
            queries_tried=[
                {"query_text": "medicine", "query_style": "keyword_object"}
            ],
            failure_modes=["zero_results"],
            workarounds=["timeline_scroll"],
        )
        assert len(ep.cues_remembered) == 1
        assert ep.cues_remembered[0].cue_type == CueType.SUBJECT_OBJECT


class TestRecordExtraction:
    def test_max_three_episodes(self):
        episode_data = {
            "target_description": "Test",
            "photo_category": "other",
            "photo_origin": "unknown",
            "outcome": "unknown",
            "archetype_primary": "vocabulary_mismatch",
            "summary_en": "Test",
            "quote_original": "Test",
            "quote_en": "Test",
            "extraction_confidence": "low",
        }
        # 3 episodes should be fine
        RecordExtraction(
            record_id="test_1",
            episodes=[episode_data, episode_data, episode_data],
        )

        # 4 episodes should raise
        with pytest.raises(ValueError, match="at most 3"):
            RecordExtraction(
                record_id="test_2",
                episodes=[episode_data] * 4,
            )

    def test_zero_episodes_for_general_complaint(self):
        # General complaints can have 0 episodes
        rec = RecordExtraction(
            record_id="test_3",
            general_failure_modes=["zero_results", "vocabulary_mismatch"],
            episodes=[],
        )
        assert len(rec.episodes) == 0
        assert len(rec.general_failure_modes) == 2


class TestFilterResult:
    def test_valid(self):
        fr = FilterResult(
            record_id="rd_123",
            relevance_class="specific_episode",
            reason="Describes searching for a specific photo",
        )
        assert fr.relevance_class == RelevanceClass.SPECIFIC_EPISODE

    def test_invalid_class(self):
        with pytest.raises(ValueError):
            FilterResult(
                record_id="rd_123",
                relevance_class="not_a_class",
                reason="Test",
            )


class TestChatRequest:
    def test_valid(self):
        cr = ChatRequest(question="What do people search for?")
        assert cr.question == "What do people search for?"

    def test_empty_question(self):
        with pytest.raises(ValueError):
            ChatRequest(question="")


# ============================================================
# Constants and scoring tests
# ============================================================

class TestSeverityWeights:
    def test_gave_up_is_3(self):
        assert compute_severity("gave_up") == 3.0

    def test_found_easily_is_1(self):
        assert compute_severity("found_easily") == 1.0

    def test_unknown_returns_none(self):
        assert compute_severity("unknown") is None

    def test_all_defined_outcomes(self):
        assert "gave_up" in SEVERITY_WEIGHTS
        assert "still_searching" in SEVERITY_WEIGHTS
        assert "found_with_effort" in SEVERITY_WEIGHTS
        assert "found_easily" in SEVERITY_WEIGHTS


class TestStakesWeights:
    def test_practical_urgent_is_1_5(self):
        assert compute_stakes_weight("practical_urgent") == 1.5

    def test_sentimental_is_1_3(self):
        assert compute_stakes_weight("sentimental") == 1.3

    def test_unknown_is_1_0(self):
        assert compute_stakes_weight("unknown") == 1.0


class TestEvidenceStrength:
    def test_strong(self):
        assert compute_evidence_strength(30) == "strong"
        assert compute_evidence_strength(100) == "strong"

    def test_directional(self):
        assert compute_evidence_strength(15) == "directional"
        assert compute_evidence_strength(29) == "directional"

    def test_anecdotal(self):
        assert compute_evidence_strength(0) == "anecdotal"
        assert compute_evidence_strength(14) == "anecdotal"


class TestHypothesisStatus:
    def test_insufficient_data(self):
        assert compute_hypothesis_status(10, 2, 12) == "insufficient_data"

    def test_supported(self):
        # support >= 2x contradict and >= 15 relevant
        assert compute_hypothesis_status(30, 10, 40) == "supported"

    def test_contradicted(self):
        assert compute_hypothesis_status(5, 20, 25) == "contradicted"

    def test_mixed(self):
        # Neither condition met, but enough data
        assert compute_hypothesis_status(15, 15, 30) == "mixed"

    def test_edge_case_zero_contradict(self):
        # support=20, contradict=0 -> positive support >= 2*0 -> supported
        assert compute_hypothesis_status(20, 0, 20) == "supported"

    def test_zero_support_zero_contradict_returns_mixed(self):
        # support=0, contradict=0, relevant=20 -> neither supported nor contradicted -> mixed (FR-74)
        assert compute_hypothesis_status(0, 0, 20) == "mixed"

    def test_zero_support_positive_contradict_returns_contradicted(self):
        # support=0, contradict=20 -> contradicted
        assert compute_hypothesis_status(0, 20, 20) == "contradicted"


class TestGapScore:
    def test_no_searchable(self):
        assert compute_gap_score(0.5, "no") == 0.5

    def test_partial_searchable(self):
        assert compute_gap_score(0.5, "partial") == 0.25

    def test_yes_searchable(self):
        assert compute_gap_score(0.5, "yes") == 0.0

    def test_unknown_searchable(self):
        # Not in the lookup, should return None
        assert compute_gap_score(0.5, "not_verified") is None
