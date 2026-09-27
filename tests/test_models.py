import pytest
from pydantic import ValidationError
from shared.models import RecordExtraction, EpisodeExtraction, RecordBehavior
from shared.enums import Archetype, PhotoCategory, Product, Platform, PhotoOrigin, Outcome

def get_valid_episode(overrides):
    base = dict(
        episode_no=1,
        target_description="test",
        photo_category=PhotoCategory.DOCUMENT_TEXT,
        photo_origin=list(PhotoOrigin)[0],
        outcome=list(Outcome)[0],
        archetype_primary=Archetype.UTILITY_LOOKUP,
        summary_en="test",
        quote_original="test",
        quote_en="test",
        extraction_confidence="high"
    )
    base.update(overrides)
    return EpisodeExtraction(**base)

def test_utility_lookup_valid():
    ep = get_valid_episode({})
    assert ep.photo_category == PhotoCategory.DOCUMENT_TEXT

def test_utility_lookup_invalid():
    with pytest.raises(ValidationError) as exc:
        get_valid_episode({"photo_category": PhotoCategory.PET_ANIMAL})
    assert "utility_lookup archetype is only allowed with photo categories" in str(exc.value)

def test_out_of_scope_no_episodes():
    rec = RecordExtraction(
        record_id="rec1",
        out_of_scope=True,
        out_of_scope_reason="It is about a web search",
        episodes=[]
    )
    assert rec.out_of_scope is True

def test_out_of_scope_with_episodes_invalid():
    with pytest.raises(ValidationError) as exc:
        RecordExtraction(
            record_id="rec1",
            out_of_scope=True,
            out_of_scope_reason="Test",
            episodes=[get_valid_episode({})]
        )
    assert "episodes cannot exist when out_of_scope is true" in str(exc.value)

def test_out_of_scope_missing_reason_invalid():
    with pytest.raises(ValidationError) as exc:
        RecordExtraction(
            record_id="rec1",
            out_of_scope=True,
            episodes=[]
        )
    assert "out_of_scope_reason is required when out_of_scope is true" in str(exc.value)
