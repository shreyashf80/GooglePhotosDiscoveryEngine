"""
Test M2 extract stage (T-2.5, T-2.6, T-2.8, T-2.10, T-2.11).

Tests:
  1. English detection accepts English text
  2. English detection rejects Hindi text
  3. English detection handles short text
  4. Extract prompt template has {{RECORDS_JSON}} placeholder
  5. Extract prompt template contains all archetypes
  6. Extract prompt template contains all cue types
  7. Extract prompt template contains all failure modes
  8. EXTRACT_BATCH_SIZE is 10
  9. MAX_EXTRACT_RETRIES is 3
  10. PROMPT_VERSION is extract_v1
  11. Validate english outputs downgrades confidence
  12. General failure modes writeback data structure
  13. Emergent label tracking data structure
  14. RecordExtraction to episode persistence field mapping
  15. Extract prompt contains examples

Reqs: FR-40, FR-41, FR-42, FR-43, FR-45, FR-46, NFR-8
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from shared.enums import (
    Archetype,
    CueType,
    ExtractionConfidence,
    FailureMode,
    Outcome,
    PhotoCategory,
    PhotoOrigin,
    Platform,
    Precision,
    Product,
    QueryStyle,
    Stakes,
    Workaround,
)
from shared.models import (
    CueObject,
    EpisodeExtraction,
    ForgottenCue,
    QueryTried,
    RecordExtraction,
)


# ============================================================
# Test 1-3: English detection (T-2.10, FR-41)
# ============================================================

def test_english_detection_accepts_english():
    """English text should be detected as English."""
    from pipeline.stages.extract import _is_likely_english
    assert _is_likely_english("This is a perfectly normal English sentence about finding photos.")


def test_english_detection_rejects_hindi():
    """Hindi text should not be detected as English."""
    from pipeline.stages.extract import _is_likely_english
    # Note: langdetect may be probabilistic, so we test longer text
    result = _is_likely_english("यह एक हिंदी वाक्य है जो फोटो खोजने के बारे में है और काफी लंबा है")
    assert not result


def test_english_detection_handles_short():
    """Short text should be treated as OK (too short to detect)."""
    from pipeline.stages.extract import _is_likely_english
    assert _is_likely_english("ok")
    assert _is_likely_english("")


# ============================================================
# Test 4-6: Extract prompt template checks
# ============================================================

def test_extract_prompt_has_placeholder():
    """Extract prompt should contain {{RECORDS_JSON}} placeholder."""
    prompt_path = Path(__file__).resolve().parent.parent / "pipeline" / "prompts" / "extract_v1.md"
    content = prompt_path.read_text()
    assert "{{RECORDS_JSON}}" in content


def test_extract_prompt_contains_archetypes():
    """Extract prompt should list all archetype values."""
    prompt_path = Path(__file__).resolve().parent.parent / "pipeline" / "prompts" / "extract_v1.md"
    content = prompt_path.read_text()
    for arch in Archetype:
        assert arch.value in content, f"Missing archetype: {arch.value}"


def test_extract_prompt_contains_cue_types():
    """Extract prompt should list all cue types."""
    prompt_path = Path(__file__).resolve().parent.parent / "pipeline" / "prompts" / "extract_v1.md"
    content = prompt_path.read_text()
    for ct in CueType:
        assert ct.value in content, f"Missing cue type: {ct.value}"


# ============================================================
# Test 7: Extract prompt contains failure modes
# ============================================================

def test_extract_prompt_contains_failure_modes():
    """Extract prompt should list all failure mode values."""
    prompt_path = Path(__file__).resolve().parent.parent / "pipeline" / "prompts" / "extract_v1.md"
    content = prompt_path.read_text()
    for fm in FailureMode:
        assert fm.value in content, f"Missing failure mode: {fm.value}"


# ============================================================
# Test 8-10: Config checks
# ============================================================

def test_extract_batch_size():
    """EXTRACT_BATCH_SIZE should be 10."""
    from pipeline.config import EXTRACT_BATCH_SIZE
    assert EXTRACT_BATCH_SIZE == 10


def test_max_extract_retries():
    """MAX_EXTRACT_RETRIES should be 3."""
    from pipeline.config import MAX_EXTRACT_RETRIES
    assert MAX_EXTRACT_RETRIES == 3


def test_prompt_version():
    """PROMPT_VERSION should be extract_v1."""
    from pipeline.stages.extract import PROMPT_VERSION
    assert PROMPT_VERSION == "extract_v1"


# ============================================================
# Test 11: English output validation downgrades confidence (T-2.10)
# ============================================================

def test_validate_english_outputs_downgrades():
    """Non-English summary_en should downgrade extraction_confidence to low."""
    from pipeline.stages.extract import _validate_english_outputs

    extraction = RecordExtraction(
        record_id="test_001",
        episodes=[
            EpisodeExtraction(
                target_description="A photo test",
                photo_category=PhotoCategory.HEALTH_MEDICAL,
                photo_origin=PhotoOrigin.UNKNOWN,
                outcome=Outcome.FOUND_WITH_EFFORT,
                archetype_primary=Archetype.VOCABULARY_MISMATCH,
                summary_en="यह एक हिंदी सारांश है जो फोटो खोजने के बारे में है और काफी लंबा है ताकि भाषा पहचान काम करे",
                quote_original="test quote",
                quote_en="test quote english",
                extraction_confidence=ExtractionConfidence.HIGH,
            )
        ],
    )

    result = _validate_english_outputs(extraction)
    assert result.episodes[0].extraction_confidence == "low"


# ============================================================
# Test 12: General failure modes data structure (T-2.11)
# ============================================================

def test_general_failure_modes_structure():
    """General search complaint with failure modes should validate."""
    extraction = RecordExtraction(
        record_id="test_002",
        general_failure_modes=[FailureMode.ZERO_RESULTS, FailureMode.VOCABULARY_MISMATCH],
        episodes=[],
    )
    assert len(extraction.general_failure_modes) == 2
    assert extraction.general_failure_modes[0] == FailureMode.ZERO_RESULTS


# ============================================================
# Test 13: Emergent label tracking data (T-2.8)
# ============================================================

def test_emergent_label_tracking_data():
    """Episodes with emergent archetype should have emergent_label."""
    ep = EpisodeExtraction(
        target_description="Shared album photo confusion",
        photo_category=PhotoCategory.OTHER,
        photo_origin=PhotoOrigin.SHARED_ALBUM_OR_PARTNER,
        outcome=Outcome.STILL_SEARCHING,
        archetype_primary=Archetype.EMERGENT,
        emergent_label="shared album confusion",
        summary_en="User confused by shared album photos.",
        quote_original="Can't tell which album it's in",
        quote_en="Can't tell which album it's in",
        extraction_confidence=ExtractionConfidence.MEDIUM,
    )
    assert ep.archetype_primary == Archetype.EMERGENT
    assert ep.emergent_label == "shared album confusion"


# ============================================================
# Test 14: RecordExtraction field mapping for persistence
# ============================================================

def test_record_extraction_field_mapping():
    """All expected fields should be accessible for persistence."""
    extraction = RecordExtraction(
        record_id="test_003",
        product=Product.GOOGLE_PHOTOS,
        platform=Platform.ANDROID,
        mentions_ask_photos=True,
        ask_photos_note="Ask Photos could not find the image",
        general_failure_modes=[],
        episodes=[
            EpisodeExtraction(
                target_description="Photo of cake from birthday party",
                photo_category=PhotoCategory.EVENT_OCCASION,
                photo_origin=PhotoOrigin.OWN_CAMERA,
                photo_age_bucket="1_3y",
                photo_age_evidence="2 years ago",
                cues_remembered=[
                    CueObject(cue_type=CueType.SUBJECT_OBJECT, value="birthday cake", precision=Precision.APPROXIMATE),
                    CueObject(cue_type=CueType.TIME_EVENT_ANCHOR, value="birthday party", precision=Precision.APPROXIMATE),
                ],
                cues_forgotten=[
                    ForgottenCue(cue_type=CueType.TIME_ABSOLUTE, evidence="can't remember exact date"),
                ],
                queries_tried=[
                    QueryTried(query_text="birthday cake", query_style=QueryStyle.KEYWORD_OBJECT),
                    QueryTried(query_text="2024 birthday", query_style=QueryStyle.KEYWORD_EVENT),
                ],
                failure_modes=[FailureMode.TOO_MANY_RESULTS],
                workarounds=[Workaround.TIMELINE_SCROLL],
                outcome=Outcome.FOUND_WITH_EFFORT,
                stakes=Stakes.SENTIMENTAL,
                role_hints=[],
                archetype_primary=Archetype.NEEDLE_IN_FLOOD,
                archetype_secondary=Archetype.EVENT_ANCHORED_TIME,
                summary_en="User searched for birthday cake photo but got too many results.",
                quote_original="Searched birthday cake, got hundreds of results",
                quote_en="Searched birthday cake, got hundreds of results",
                extraction_confidence=ExtractionConfidence.HIGH,
            )
        ],
    )

    assert extraction.platform == Platform.ANDROID
    assert extraction.mentions_ask_photos is True
    ep = extraction.episodes[0]
    assert len(ep.cues_remembered) == 2
    assert len(ep.cues_forgotten) == 1
    assert len(ep.queries_tried) == 2
    assert ep.archetype_secondary == Archetype.EVENT_ANCHORED_TIME


# ============================================================
# Test 15: Extract prompt contains example
# ============================================================

def test_extract_prompt_contains_examples():
    """Extract prompt should contain worked examples."""
    prompt_path = Path(__file__).resolve().parent.parent / "pipeline" / "prompts" / "extract_v1.md"
    content = prompt_path.read_text()
    assert "ex_1" in content  # Example record ID
    assert "provenance_lost" in content
    assert "received_messaging" in content
