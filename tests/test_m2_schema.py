"""
Test M2 schema validation (T-2.6).

Tests:
  1. Valid extraction with all fields
  2. Valid extraction with minimal fields
  3. Invalid enum value rejected
  4. More than 3 episodes rejected
  5. Empty cues list accepted
  6. Missing required field rejected
  7. 0 episodes for general complaint accepted
  8. Emergent archetype without label rejected
  9. Emergent archetype with label accepted
  10. FilterResult validation
  11. FilterResult invalid class rejected
  12. RecordExtraction product defaults
  13. Photo age bucket validation
  14. Cue object precision validation
  15. QueryTried validation
  16. General failure modes for non-general complaint
  17. Max episodes boundary (exactly 3)
  18. EpisodeExtraction target_description max length
  19. Multiple episodes in one record
  20. ForgottenCue validation

Reqs: NFR-8, DR-1
"""

import pytest
from pydantic import ValidationError

from shared.enums import (
    Archetype,
    CueType,
    ExtractionConfidence,
    FailureMode,
    Outcome,
    PhotoAgeBucket,
    PhotoCategory,
    PhotoOrigin,
    Platform,
    Precision,
    Product,
    QueryStyle,
    RelevanceClass,
    Stakes,
    Workaround,
)
from shared.models import (
    CueObject,
    EpisodeExtraction,
    FilterResult,
    ForgottenCue,
    QueryTried,
    RecordExtraction,
)


def _make_episode(**overrides) -> dict:
    """Helper to create a valid episode dict with defaults."""
    base = {
        "target_description": "Photo of medicine prescribed during illness",
        "photo_category": "health_medical",
        "photo_origin": "unknown",
        "photo_age_bucket": "6_12m",
        "photo_age_evidence": "last year",
        "cues_remembered": [
            {"cue_type": "subject_object", "value": "medicine from doctor", "precision": "approximate"},
        ],
        "cues_forgotten": [],
        "queries_tried": [
            {"query_text": "medicine", "query_style": "keyword_object"},
        ],
        "failure_modes": ["zero_results"],
        "workarounds": ["timeline_scroll"],
        "outcome": "found_with_effort",
        "stakes": "practical_urgent",
        "role_hints": [],
        "archetype_primary": "vocabulary_mismatch",
        "archetype_secondary": None,
        "emergent_label": None,
        "summary_en": "User searched for a medicine photo and found it by scrolling.",
        "quote_original": "Searched medicine, nothing. Scrolled 3 months.",
        "quote_en": "Searched medicine, nothing. Scrolled 3 months.",
        "extraction_confidence": "high",
    }
    base.update(overrides)
    return base


def _make_record_extraction(**overrides) -> dict:
    """Helper to create a valid RecordExtraction dict."""
    base = {
        "record_id": "test_001",
        "product": "google_photos",
        "platform": "unknown",
        "mentions_ask_photos": False,
        "ask_photos_note": None,
        "general_failure_modes": [],
        "episodes": [_make_episode()],
    }
    base.update(overrides)
    return base


# ============================================================
# Test 1: Valid extraction with all fields
# ============================================================
def test_valid_extraction_all_fields():
    """A fully populated extraction should validate successfully."""
    data = _make_record_extraction()
    result = RecordExtraction.model_validate(data)
    assert result.record_id == "test_001"
    assert len(result.episodes) == 1
    assert result.episodes[0].photo_category == PhotoCategory.HEALTH_MEDICAL
    assert result.episodes[0].outcome == Outcome.FOUND_WITH_EFFORT


# ============================================================
# Test 2: Valid extraction with minimal fields
# ============================================================
def test_valid_extraction_minimal():
    """An extraction with only required fields should validate."""
    ep = _make_episode(
        cues_remembered=[],
        queries_tried=[],
        failure_modes=[],
        workarounds=[],
        photo_age_evidence=None,
    )
    data = _make_record_extraction(episodes=[ep])
    result = RecordExtraction.model_validate(data)
    assert len(result.episodes) == 1


# ============================================================
# Test 3: Invalid enum value rejected
# ============================================================
def test_invalid_enum_value():
    """An unknown enum value should fail validation."""
    ep = _make_episode(photo_category="nonexistent_category")
    data = _make_record_extraction(episodes=[ep])
    with pytest.raises(ValidationError):
        RecordExtraction.model_validate(data)


# ============================================================
# Test 4: More than 3 episodes rejected
# ============================================================
def test_max_episodes_exceeded():
    """More than 3 episodes should fail validation."""
    episodes = [_make_episode() for _ in range(4)]
    data = _make_record_extraction(episodes=episodes)
    with pytest.raises(ValidationError):
        RecordExtraction.model_validate(data)


# ============================================================
# Test 5: Empty cues list accepted
# ============================================================
def test_empty_cues_list():
    """An episode with no cues should validate."""
    ep = _make_episode(cues_remembered=[], cues_forgotten=[])
    data = _make_record_extraction(episodes=[ep])
    result = RecordExtraction.model_validate(data)
    assert result.episodes[0].cues_remembered == []


# ============================================================
# Test 6: Missing required field rejected
# ============================================================
def test_missing_required_field():
    """Missing a required field should fail validation."""
    ep = _make_episode()
    del ep["outcome"]
    data = _make_record_extraction(episodes=[ep])
    with pytest.raises(ValidationError):
        RecordExtraction.model_validate(data)


# ============================================================
# Test 7: 0 episodes for general complaint
# ============================================================
def test_zero_episodes_general_complaint():
    """A general complaint with 0 episodes and general_failure_modes is valid."""
    data = _make_record_extraction(
        episodes=[],
        general_failure_modes=["zero_results", "vocabulary_mismatch"],
    )
    result = RecordExtraction.model_validate(data)
    assert len(result.episodes) == 0
    assert len(result.general_failure_modes) == 2


# ============================================================
# Test 8: Emergent archetype without label rejected
# ============================================================
def test_emergent_without_label():
    """Emergent archetype requires emergent_label."""
    ep = _make_episode(
        archetype_primary="emergent",
        emergent_label=None,
    )
    data = _make_record_extraction(episodes=[ep])
    with pytest.raises(ValidationError, match="emergent_label"):
        RecordExtraction.model_validate(data)


# ============================================================
# Test 9: Emergent archetype with label accepted
# ============================================================
def test_emergent_with_label():
    """Emergent archetype with a label should validate."""
    ep = _make_episode(
        archetype_primary="emergent",
        emergent_label="shared album confusion",
    )
    data = _make_record_extraction(episodes=[ep])
    result = RecordExtraction.model_validate(data)
    assert result.episodes[0].emergent_label == "shared album confusion"


# ============================================================
# Test 10: FilterResult validation
# ============================================================
def test_filter_result_valid():
    """A valid FilterResult should validate."""
    data = {
        "record_id": "test_001",
        "relevance_class": "specific_episode",
        "lang": "en",
        "reason": "User tried to find a specific photo.",
    }
    result = FilterResult.model_validate(data)
    assert result.relevance_class == RelevanceClass.SPECIFIC_EPISODE


# ============================================================
# Test 11: FilterResult invalid class rejected
# ============================================================
def test_filter_result_invalid_class():
    """An invalid relevance class should fail."""
    data = {
        "record_id": "test_001",
        "relevance_class": "nonexistent_class",
        "reason": "test",
    }
    with pytest.raises(ValidationError):
        FilterResult.model_validate(data)


# ============================================================
# Test 12: RecordExtraction product defaults
# ============================================================
def test_record_extraction_product_default():
    """Product should default to google_photos."""
    data = {
        "record_id": "test_001",
        "episodes": [],
    }
    result = RecordExtraction.model_validate(data)
    assert result.product == Product.GOOGLE_PHOTOS


# ============================================================
# Test 13: Photo age bucket validation
# ============================================================
def test_photo_age_bucket_all_values():
    """All photo_age_bucket enum values should be accepted."""
    for bucket in PhotoAgeBucket:
        ep = _make_episode(photo_age_bucket=bucket.value)
        data = _make_record_extraction(episodes=[ep])
        result = RecordExtraction.model_validate(data)
        assert result.episodes[0].photo_age_bucket == bucket


# ============================================================
# Test 14: Cue object precision validation
# ============================================================
def test_cue_precision_values():
    """All precision values should be accepted."""
    for prec in Precision:
        cue = CueObject(cue_type=CueType.TIME_ABSOLUTE, value="March 2024", precision=prec)
        assert cue.precision == prec


# ============================================================
# Test 15: QueryTried validation
# ============================================================
def test_query_tried_all_styles():
    """All query_style values should be accepted."""
    for style in QueryStyle:
        q = QueryTried(query_text="test", query_style=style)
        assert q.query_style == style


# ============================================================
# Test 16: General failure modes for non-general complaint
# ============================================================
def test_general_failure_modes_empty_for_specific():
    """general_failure_modes can be empty for specific_episode records."""
    data = _make_record_extraction(general_failure_modes=[])
    result = RecordExtraction.model_validate(data)
    assert result.general_failure_modes == []


# ============================================================
# Test 17: Exactly 3 episodes (boundary)
# ============================================================
def test_exactly_three_episodes():
    """Exactly 3 episodes should validate."""
    episodes = [_make_episode() for _ in range(3)]
    data = _make_record_extraction(episodes=episodes)
    result = RecordExtraction.model_validate(data)
    assert len(result.episodes) == 3


# ============================================================
# Test 18: EpisodeExtraction target_description
# ============================================================
def test_target_description_max_length():
    """target_description exceeding max_length should fail."""
    long_desc = "x" * 201
    ep = _make_episode(target_description=long_desc)
    data = _make_record_extraction(episodes=[ep])
    with pytest.raises(ValidationError):
        RecordExtraction.model_validate(data)


# ============================================================
# Test 19: Multiple episodes in one record
# ============================================================
def test_multiple_episodes():
    """A record with 2 different episodes should validate."""
    ep1 = _make_episode(target_description="Photo of medicine")
    ep2 = _make_episode(
        target_description="Photo of receipt",
        photo_category="receipt_financial",
        archetype_primary="utility_lookup",
    )
    data = _make_record_extraction(episodes=[ep1, ep2])
    result = RecordExtraction.model_validate(data)
    assert len(result.episodes) == 2
    assert result.episodes[1].photo_category == PhotoCategory.RECEIPT_FINANCIAL


# ============================================================
# Test 20: ForgottenCue validation
# ============================================================
def test_forgotten_cue_valid():
    """A valid ForgottenCue should validate."""
    fc = ForgottenCue(cue_type=CueType.TIME_ABSOLUTE, evidence="I can't remember when")
    assert fc.cue_type == CueType.TIME_ABSOLUTE
    assert fc.evidence == "I can't remember when"
