"""
Shared enums — single source of truth generated from extraction_spec.md.
All enums are StrEnum so they serialize cleanly in JSON and Pydantic.

Sections referenced:
  - extraction_spec.md Section 1 (RelevanceClass)
  - extraction_spec.md Sections 3.1–3.6 (PhotoCategory, PhotoOrigin, PhotoAgeBucket,
    CueType, Precision, QueryStyle, FailureMode, Workaround)
  - extraction_spec.md Section 2.2 (Outcome, Stakes, ExtractionConfidence)
  - extraction_spec.md Section 4 (Archetype)
  - extraction_spec.md Section 5 / PRD FR-70, FR-74 (EvidenceStrength, HypothesisStatus)
"""

from enum import StrEnum


# --- Section 1: Relevance classification ---

class RelevanceClass(StrEnum):
    SPECIFIC_EPISODE = "specific_episode"
    GENERAL_SEARCH_COMPLAINT = "general_search_complaint"
    SUCCESS_OR_TIP = "success_or_tip"
    LOST_NOT_HIDDEN = "lost_not_hidden"
    IRRELEVANT = "irrelevant"


# --- Section 3.1: Photo category ---

class PhotoCategory(StrEnum):
    PEOPLE_MOMENT = "people_moment"
    EVENT_OCCASION = "event_occasion"
    TRAVEL_PLACE = "travel_place"
    PET_ANIMAL = "pet_animal"
    FOOD = "food"
    OBJECT_PRODUCT = "object_product"
    DOCUMENT_TEXT = "document_text"
    HEALTH_MEDICAL = "health_medical"
    RECEIPT_FINANCIAL = "receipt_financial"
    SCREENSHOT_DIGITAL = "screenshot_digital"
    MEME_FORWARD = "meme_forward"
    OTHER = "other"
    UNKNOWN = "unknown"


# Derived groups (computed, not extracted) — spec Section 3.1
MEMORY_CATEGORIES = frozenset({
    PhotoCategory.PEOPLE_MOMENT,
    PhotoCategory.EVENT_OCCASION,
    PhotoCategory.TRAVEL_PLACE,
    PhotoCategory.PET_ANIMAL,
    PhotoCategory.FOOD,
})

UTILITY_CATEGORIES = frozenset({
    PhotoCategory.DOCUMENT_TEXT,
    PhotoCategory.HEALTH_MEDICAL,
    PhotoCategory.RECEIPT_FINANCIAL,
    PhotoCategory.SCREENSHOT_DIGITAL,
    PhotoCategory.OBJECT_PRODUCT,
})


# --- Section 3.2: Photo origin ---

class PhotoOrigin(StrEnum):
    OWN_CAMERA = "own_camera"
    RECEIVED_MESSAGING = "received_messaging"
    SHARED_ALBUM_OR_PARTNER = "shared_album_or_partner"
    SCREENSHOT = "screenshot"
    DOWNLOADED_WEB = "downloaded_web"
    SCANNED = "scanned"
    IMPORTED_DEVICE_OR_BACKUP = "imported_device_or_backup"
    UNKNOWN = "unknown"


# --- Section 2.2: Photo age bucket ---

class PhotoAgeBucket(StrEnum):
    UNDER_6M = "under_6m"
    SIX_12M = "6_12m"
    ONE_3Y = "1_3y"
    THREE_Y_PLUS = "3y_plus"
    UNKNOWN = "unknown"


# --- Section 3.3: Cue type ---

class CueType(StrEnum):
    TIME_ABSOLUTE = "time_absolute"
    TIME_SEASON = "time_season"
    TIME_LIFE_STAGE = "time_life_stage"
    TIME_EVENT_ANCHOR = "time_event_anchor"
    PLACE_NAMED = "place_named"
    PLACE_TYPE = "place_type"
    PERSON_NAMED = "person_named"
    PERSON_RELATION = "person_relation"
    GROUP_SOCIAL = "group_social"
    SUBJECT_OBJECT = "subject_object"
    SCENE_ACTIVITY = "scene_activity"
    TEXT_IN_IMAGE = "text_in_image"
    SOURCE_SENDER = "source_sender"
    CONVERSATION_CONTEXT = "conversation_context"
    PERSONAL_STATE = "personal_state"
    EMOTIONAL_TONE = "emotional_tone"
    PURPOSE_USE = "purpose_use"
    ADJACENCY = "adjacency"


# --- Section 3.3: Precision ---

class Precision(StrEnum):
    EXACT = "exact"
    APPROXIMATE = "approximate"
    VAGUE = "vague"


# --- Section 3.4: Query style ---

class QueryStyle(StrEnum):
    KEYWORD_OBJECT = "keyword_object"
    KEYWORD_PERSON = "keyword_person"
    KEYWORD_PLACE = "keyword_place"
    KEYWORD_EVENT = "keyword_event"
    DATE_OR_FILTER = "date_or_filter"
    TEXT_OCR = "text_ocr"
    NATURAL_LANGUAGE = "natural_language"
    ASK_PHOTOS_CONVERSATION = "ask_photos_conversation"
    ALBUM_BROWSE = "album_browse"
    UNKNOWN = "unknown"


# --- Section 3.5: Failure mode ---

class FailureMode(StrEnum):
    ZERO_RESULTS = "zero_results"
    WRONG_RESULTS = "wrong_results"
    TOO_MANY_RESULTS = "too_many_results"
    CUE_NOT_SUPPORTED = "cue_not_supported"
    VOCABULARY_MISMATCH = "vocabulary_mismatch"
    DATE_IMPRECISION = "date_imprecision"
    REFINEMENT_MISSING = "refinement_missing"
    ASK_PHOTOS_FAILURE = "ask_photos_failure"
    UI_FRICTION = "ui_friction"
    UNKNOWN = "unknown"


# --- Section 3.6: Workaround ---

class Workaround(StrEnum):
    TIMELINE_SCROLL = "timeline_scroll"
    DATE_JUMP = "date_jump"
    ALBUM_OR_FOLDER_BROWSE = "album_or_folder_browse"
    SEARCHED_SOURCE_APP = "searched_source_app"
    ASKED_SENDER_RESEND = "asked_sender_resend"
    ASKED_SOMEONE_ELSE = "asked_someone_else"
    USED_OTHER_APP = "used_other_app"
    USED_ASK_PHOTOS = "used_ask_photos"
    NONE_GAVE_UP = "none_gave_up"
    OTHER = "other"


# --- Section 2.2: Outcome ---

class Outcome(StrEnum):
    FOUND_EASILY = "found_easily"
    FOUND_WITH_EFFORT = "found_with_effort"
    GAVE_UP = "gave_up"
    STILL_SEARCHING = "still_searching"
    UNKNOWN = "unknown"


# --- Section 2.2: Stakes ---

class Stakes(StrEnum):
    SENTIMENTAL = "sentimental"
    PRACTICAL_ROUTINE = "practical_routine"
    PRACTICAL_URGENT = "practical_urgent"
    UNKNOWN = "unknown"


# --- Section 4: Archetype ---

class Archetype(StrEnum):
    NEEDLE_IN_FLOOD = "needle_in_flood"
    VOCABULARY_MISMATCH = "vocabulary_mismatch"
    PROVENANCE_LOST = "provenance_lost"
    EVENT_ANCHORED_TIME = "event_anchored_time"
    TIME_DRIFT = "time_drift"
    UTILITY_LOOKUP = "utility_lookup"
    REFINEMENT_DEAD_END = "refinement_dead_end"
    EMERGENT = "emergent"


# --- Section 2.2: Extraction confidence ---

class ExtractionConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- PRD FR-70: Evidence strength ---

class EvidenceStrength(StrEnum):
    STRONG = "strong"
    DIRECTIONAL = "directional"
    ANECDOTAL = "anecdotal"


# --- PRD FR-74: Hypothesis status ---

class HypothesisStatus(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    MIXED = "mixed"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Section 2.1: Product ---

class Product(StrEnum):
    GOOGLE_PHOTOS = "google_photos"
    APPLE_PHOTOS = "apple_photos"
    SAMSUNG_GALLERY = "samsung_gallery"
    OTHER = "other"


# --- Section 2.1: Platform ---

class Platform(StrEnum):
    ANDROID = "android"
    IOS = "ios"
    WEB = "web"
    UNKNOWN = "unknown"


# --- Record status (architecture.md Section 3.2) ---

class RecordStatus(StrEnum):
    RAW = "raw"
    DEDUPED = "deduped"
    FILTERED = "filtered"
    EXCLUDED = "excluded"
    EXTRACTED = "extracted"
    EMBEDDED = "embedded"
    EXTRACT_FAILED = "extract_failed"


# --- Source names ---

class Source(StrEnum):
    REDDIT = "reddit"
    PLAYSTORE = "playstore"
    APPSTORE = "appstore"
    YOUTUBE = "youtube"
    COMMUNITY = "community"
    HN = "hn"
    CSV = "csv"


# --- Item type ---

class ItemType(StrEnum):
    POST = "post"
    COMMENT = "comment"
    REVIEW = "review"


# --- Capability reference searchable ---

class Searchable(StrEnum):
    YES = "yes"
    PARTIAL = "partial"
    NO = "no"


# --- Role hints ---

class RoleHint(StrEnum):
    PARENT = "parent"
    TRAVELER = "traveler"
    STUDENT = "student"
    PROFESSIONAL = "professional"
    CAREGIVER = "caregiver"
    SMALL_BUSINESS = "small_business"
    ELDERLY_USER = "elderly_user"
