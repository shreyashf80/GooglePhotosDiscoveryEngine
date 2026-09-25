"""
Test M2 filter stage (T-2.1, T-2.3).

Tests:
  1. Keyword prefilter detects English terms
  2. Keyword prefilter detects Hindi terms
  3. Keyword prefilter detects Hinglish terms
  4. Keyword prefilter returns False for irrelevant text
  5. Keyword prefilter handles empty text
  6. Keyword prefilter is case-insensitive
  7. Keyword prefilter matches multi-word phrases
  8. Filter prompt template has {{RECORDS_JSON}} placeholder
  9. Filter prompt template contains relevance classes
  10. FilterResultItem model validation
  11. FilterBatchResponse model validation
  12. KEYWORD_PREFILTER_ALL is non-empty set
  13. All keyword lists are non-empty
  14. FILTER_BATCH_SIZE is 25

Reqs: FR-30, FR-31, NFR-8
"""

import pytest
from pathlib import Path


# ============================================================
# Test 1-7: Keyword prefilter (FR-30)
# ============================================================

def test_keyword_hit_english():
    """English search-related terms should be detected."""
    from pipeline.stages.filter import check_keyword_hit
    
    assert check_keyword_hit("I can't find my old photo from last year")
    assert check_keyword_hit("where is the photo I took in Goa")
    assert check_keyword_hit("tried searching for my receipt")
    assert check_keyword_hit("scroll through thousands of photos")
    assert check_keyword_hit("looking for a picture from college")
    assert check_keyword_hit("ask photos to find my dog")


def test_keyword_hit_hindi():
    """Hindi (Devanagari) terms should be detected."""
    from pipeline.stages.filter import check_keyword_hit
    
    assert check_keyword_hit("मेरी फोटो नहीं मिल रही")
    assert check_keyword_hit("ढूंढ रहा हूँ पुरानी तस्वीर")
    assert check_keyword_hit("खोज रहा हूँ एक फोटो")


def test_keyword_hit_hinglish():
    """Hinglish (Latin script Hindi) terms should be detected."""
    from pipeline.stages.filter import check_keyword_hit
    
    assert check_keyword_hit("photo nahi mil rahi hai bhai")
    assert check_keyword_hit("woh photo dhoond raha hu jo rohit ne bheji thi")
    assert check_keyword_hit("nhi mil raha purana pic")
    assert check_keyword_hit("khoj raha hu ek photo")


def test_keyword_miss_irrelevant():
    """Irrelevant text should not match."""
    from pipeline.stages.filter import check_keyword_hit
    
    assert not check_keyword_hit("Great app for editing photos! Love the filters.")
    assert not check_keyword_hit("Storage plans are too expensive")
    assert not check_keyword_hit("Nice update to the UI")


def test_keyword_hit_empty():
    """Empty text should return False."""
    from pipeline.stages.filter import check_keyword_hit
    
    assert not check_keyword_hit("")
    assert not check_keyword_hit(None)


def test_keyword_hit_case_insensitive():
    """Keywords should match case-insensitively."""
    from pipeline.stages.filter import check_keyword_hit
    
    assert check_keyword_hit("SEARCH for my photo")
    assert check_keyword_hit("Can't FIND the old pic")
    assert check_keyword_hit("WHERE IS my photo")


def test_keyword_hit_multiword_phrases():
    """Multi-word keyword phrases should match."""
    from pipeline.stages.filter import check_keyword_hit
    
    assert check_keyword_hit("I am looking for an old photo")
    assert check_keyword_hit("can't see my pictures anywhere")
    assert check_keyword_hit("lost track of where the photo is")
    assert check_keyword_hit("ask photos about my trip")


# ============================================================
# Test 8-9: Prompt template checks
# ============================================================

def test_filter_prompt_has_placeholder():
    """Filter prompt should contain {{RECORDS_JSON}} placeholder."""
    prompt_path = Path(__file__).resolve().parent.parent / "pipeline" / "prompts" / "filter_v1.md"
    content = prompt_path.read_text()
    assert "{{RECORDS_JSON}}" in content


def test_filter_prompt_contains_classes():
    """Filter prompt should list all 5 relevance classes."""
    prompt_path = Path(__file__).resolve().parent.parent / "pipeline" / "prompts" / "filter_v1.md"
    content = prompt_path.read_text()
    assert "specific_episode" in content
    assert "general_search_complaint" in content
    assert "success_or_tip" in content
    assert "lost_not_hidden" in content
    assert "irrelevant" in content


# ============================================================
# Test 10-11: Filter models
# ============================================================

def test_filter_result_item_model():
    """FilterResultItem should validate correctly."""
    from pipeline.stages.filter import FilterResultItem
    
    item = FilterResultItem(
        record_id="test_001",
        relevance_class="specific_episode",
        lang="en",
        reason="User tried to find a specific photo.",
    )
    assert item.record_id == "test_001"
    assert item.relevance_class.value == "specific_episode"


def test_filter_batch_response_model():
    """FilterBatchResponse should validate a list of results."""
    from pipeline.stages.filter import FilterBatchResponse, FilterResultItem
    
    batch = FilterBatchResponse(results=[
        FilterResultItem(
            record_id="test_001",
            relevance_class="specific_episode",
            lang="en",
            reason="test",
        ),
        FilterResultItem(
            record_id="test_002",
            relevance_class="irrelevant",
            lang="en",
            reason="test",
        ),
    ])
    assert len(batch.results) == 2


# ============================================================
# Test 12-14: Config checks
# ============================================================

def test_keyword_prefilter_all_nonempty():
    """KEYWORD_PREFILTER_ALL should be a non-empty set."""
    from pipeline.config import KEYWORD_PREFILTER_ALL
    
    assert isinstance(KEYWORD_PREFILTER_ALL, set)
    assert len(KEYWORD_PREFILTER_ALL) > 20


def test_keyword_lists_nonempty():
    """Each keyword list should be non-empty."""
    from pipeline.config import KEYWORD_PREFILTER_EN, KEYWORD_PREFILTER_HI, KEYWORD_PREFILTER_HINGLISH
    
    assert len(KEYWORD_PREFILTER_EN) > 10
    assert len(KEYWORD_PREFILTER_HI) > 5
    assert len(KEYWORD_PREFILTER_HINGLISH) > 5


def test_filter_batch_size():
    """FILTER_BATCH_SIZE should be 25."""
    from pipeline.config import FILTER_BATCH_SIZE
    
    assert FILTER_BATCH_SIZE == 25
