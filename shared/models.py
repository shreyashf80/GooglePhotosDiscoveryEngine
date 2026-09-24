"""
Shared Pydantic v2 models — single source of truth.
Generated from extraction_spec.md Sections 2–3 and architecture.md Section 4.

These models are used by both pipeline and backend. No other module redefines them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from shared.enums import (
    Archetype,
    CueType,
    ExtractionConfidence,
    EvidenceStrength,
    FailureMode,
    HypothesisStatus,
    ItemType,
    Outcome,
    PhotoAgeBucket,
    PhotoCategory,
    PhotoOrigin,
    Platform,
    Precision,
    Product,
    QueryStyle,
    RelevanceClass,
    RoleHint,
    Searchable,
    Source,
    Stakes,
    Workaround,
)


# ---------------------------------------------------------------------------
# Extraction sub-objects (spec Section 3.3, 3.4)
# ---------------------------------------------------------------------------

class CueObject(BaseModel):
    """A remembered cue — extraction_spec Section 3.3."""
    cue_type: CueType
    value: str
    precision: Precision


class ForgottenCue(BaseModel):
    """An explicitly forgotten cue — extraction_spec Section 2.2."""
    cue_type: CueType
    evidence: str


class QueryTried(BaseModel):
    """A search query the user tried — extraction_spec Section 3.4."""
    query_text: str
    query_style: QueryStyle


# ---------------------------------------------------------------------------
# Episode extraction (spec Section 2.2)
# ---------------------------------------------------------------------------

class EpisodeExtraction(BaseModel):
    """One retrieval episode extracted from a record."""
    target_description: str = Field(max_length=200)
    photo_category: PhotoCategory
    photo_origin: PhotoOrigin
    photo_age_bucket: PhotoAgeBucket = PhotoAgeBucket.UNKNOWN
    photo_age_evidence: Optional[str] = None
    cues_remembered: list[CueObject] = Field(default_factory=list)
    cues_forgotten: list[ForgottenCue] = Field(default_factory=list)
    queries_tried: list[QueryTried] = Field(default_factory=list)
    failure_modes: list[FailureMode] = Field(default_factory=list)
    workarounds: list[Workaround] = Field(default_factory=list)
    outcome: Outcome
    stakes: Stakes = Stakes.UNKNOWN
    role_hints: list[RoleHint] = Field(default_factory=list)
    archetype_primary: Archetype
    archetype_secondary: Optional[Archetype] = None
    emergent_label: Optional[str] = Field(default=None, max_length=60)
    summary_en: str
    quote_original: str = Field(max_length=400)
    quote_en: str = Field(max_length=400)
    extraction_confidence: ExtractionConfidence

    @model_validator(mode="after")
    def check_emergent_label(self) -> "EpisodeExtraction":
        if self.archetype_primary == Archetype.EMERGENT and not self.emergent_label:
            raise ValueError("emergent_label is required when archetype_primary is 'emergent'")
        return self


# ---------------------------------------------------------------------------
# Record-level extraction (spec Section 2.1)
# ---------------------------------------------------------------------------

class RecordExtraction(BaseModel):
    """Full extraction result for one record."""
    record_id: str
    product: Product = Product.GOOGLE_PHOTOS
    platform: Platform = Platform.UNKNOWN
    mentions_ask_photos: bool = False
    ask_photos_note: Optional[str] = None
    general_failure_modes: list[FailureMode] = Field(default_factory=list)
    episodes: list[EpisodeExtraction] = Field(default_factory=list, max_length=3)

    @field_validator("episodes")
    @classmethod
    def max_three_episodes(cls, v: list[EpisodeExtraction]) -> list[EpisodeExtraction]:
        if len(v) > 3:
            raise ValueError("A record can have at most 3 episodes")
        return v


# ---------------------------------------------------------------------------
# Stage 1: Filter result
# ---------------------------------------------------------------------------

class FilterResult(BaseModel):
    """Result of Stage 1 relevance classification for one record."""
    record_id: str
    relevance_class: RelevanceClass
    lang: Optional[str] = None
    reason: str


# ---------------------------------------------------------------------------
# Raw record model (for pipeline use)
# ---------------------------------------------------------------------------

class RawRecord(BaseModel):
    """A raw ingested record before processing."""
    record_id: str
    source: Source
    item_type: ItemType
    product: Product = Product.GOOGLE_PHOTOS
    url: Optional[str] = None
    author_hash: Optional[str] = None
    created_at: Optional[datetime] = None
    text: Optional[str] = None
    extra: Optional[dict] = None


# ---------------------------------------------------------------------------
# Analysis result models (for API responses)
# ---------------------------------------------------------------------------

class HypothesisRow(BaseModel):
    """A hypothesis with its computed status and counts."""
    hypothesis_id: str
    title: str
    statement: str
    status: HypothesisStatus
    support_count: int = 0
    contradict_count: int = 0
    relevant_count: int = 0
    evidence_strength: EvidenceStrength
    details: Optional[dict] = None
    computed_at: Optional[datetime] = None


class ArchetypeStatsRow(BaseModel):
    """Computed stats for one archetype."""
    archetype: Archetype
    episode_count: int = 0
    share_of_episodes: float = 0.0
    outcome_distribution: dict = Field(default_factory=dict)
    top_cue_types: list[dict] = Field(default_factory=list)
    top_failure_modes: list[dict] = Field(default_factory=list)
    top_workarounds: list[dict] = Field(default_factory=list)
    source_mix: dict = Field(default_factory=dict)
    language_mix: dict = Field(default_factory=dict)
    category_mix: dict = Field(default_factory=dict)
    avg_severity: float = 0.0
    avg_stakes_weight: float = 0.0
    opportunity_score: float = 0.0
    evidence_strength: EvidenceStrength = EvidenceStrength.ANECDOTAL
    computed_at: Optional[datetime] = None


class CueStatsRow(BaseModel):
    """Computed stats for one cue type."""
    cue_type: CueType
    remembered_share: float = 0.0
    precision_exact: float = 0.0
    precision_approximate: float = 0.0
    precision_vague: float = 0.0
    forgotten_count: int = 0
    failure_rate: float = 0.0
    gap_score: Optional[float] = None
    computed_at: Optional[datetime] = None


class CapabilityReferenceRow(BaseModel):
    """PM-curated capability reference for one cue type."""
    cue_type: CueType
    searchable: Searchable
    note: Optional[str] = None
    verified_how: Optional[str] = None
    verified_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Chat models (PRD Section 12)
# ---------------------------------------------------------------------------

class Citation(BaseModel):
    """One citation in a chat response."""
    id: str  # E1, E2, etc.
    episode_id: str
    quote_en: str
    quote_original: Optional[str] = None
    source: str
    url: Optional[str] = None
    created_at: Optional[str] = None


class ChatRequest(BaseModel):
    """Incoming chat request."""
    question: str = Field(min_length=1, max_length=1000)
    filters: Optional[dict] = None


class ChatResponse(BaseModel):
    """Chat response with citations."""
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    literature_citations: list[dict] = Field(default_factory=list)
    rewritten_query: Optional[str] = None
    stats_used: bool = False
    cached: bool = False
