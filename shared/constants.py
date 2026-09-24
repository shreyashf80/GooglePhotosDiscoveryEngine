"""
Shared constants — configurable thresholds for scoring and analysis.
All values match PRD exactly and are loaded from env vars with sensible defaults.

References:
  FR-70  — evidence strength thresholds
  FR-74  — hypothesis status rules
  FR-81  — severity weights by outcome
  FR-82  — stakes weights
  FR-83  — opportunity score formula
  FR-87  — gap score formula
"""

import os


def _env_int(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)))


def _env_float(key: str, default: float) -> float:
    return float(os.getenv(key, str(default)))


# --- FR-81: Severity weights by outcome ---
SEVERITY_WEIGHTS: dict[str, float] = {
    "gave_up": 3.0,
    "still_searching": 3.0,
    "found_with_effort": 2.0,
    "found_easily": 1.0,
    # "unknown" is excluded from the average
}

# --- FR-82: Stakes weights ---
STAKES_WEIGHTS: dict[str, float] = {
    "practical_urgent": 1.5,
    "sentimental": 1.3,
    "practical_routine": 1.0,
    "unknown": 1.0,
}

# --- FR-70: Evidence strength thresholds ---
EVIDENCE_STRONG_THRESHOLD = _env_int("EVIDENCE_STRONG_THRESHOLD", 30)
EVIDENCE_DIRECTIONAL_THRESHOLD = _env_int("EVIDENCE_DIRECTIONAL_THRESHOLD", 15)
# < EVIDENCE_DIRECTIONAL_THRESHOLD => anecdotal

# --- FR-74: Hypothesis status rules ---
HYPOTHESIS_RELEVANT_THRESHOLD = _env_int("HYPOTHESIS_RELEVANT_THRESHOLD", 15)
HYPOTHESIS_SUPPORT_RATIO = _env_float("HYPOTHESIS_SUPPORT_RATIO", 2.0)
# supported: support >= ratio * contradict AND relevant >= threshold
# contradicted: contradict >= ratio * support AND relevant >= threshold
# mixed: relevant >= threshold but neither supported nor contradicted
# insufficient_data: relevant < threshold

# --- FR-83: Opportunity score ---
# opportunity_score = share_of_episodes * avg_severity * avg_stakes_weight
# Normalized to 0–100 across archetypes.

# --- FR-87: Gap score ---
# gap_score = remembered_share * multiplier
# multiplier: searchable=no -> 1.0, partial -> 0.5, yes -> 0.0
GAP_SCORE_MULTIPLIERS: dict[str, float] = {
    "no": 1.0,
    "partial": 0.5,
    "yes": 0.0,
}

# --- NFR-4: Storage warning thresholds ---
STORAGE_WARN_BYTES = _env_int("STORAGE_WARN_BYTES", 300 * 1024 * 1024)  # 300 MB
STORAGE_LIMIT_BYTES = 500 * 1024 * 1024  # 500 MB Neon free tier


def compute_evidence_strength(episode_count: int) -> str:
    """Return evidence strength label based on episode count (FR-70)."""
    if episode_count >= EVIDENCE_STRONG_THRESHOLD:
        return "strong"
    elif episode_count >= EVIDENCE_DIRECTIONAL_THRESHOLD:
        return "directional"
    else:
        return "anecdotal"


def compute_hypothesis_status(
    support_count: int,
    contradict_count: int,
    relevant_count: int,
) -> str:
    """Return hypothesis status based on counts (FR-74)."""
    if relevant_count < HYPOTHESIS_RELEVANT_THRESHOLD:
        return "insufficient_data"
    if (
        support_count > 0
        and support_count >= HYPOTHESIS_SUPPORT_RATIO * contradict_count
        and relevant_count >= HYPOTHESIS_RELEVANT_THRESHOLD
    ):
        return "supported"
    if (
        contradict_count > 0
        and contradict_count >= HYPOTHESIS_SUPPORT_RATIO * support_count
        and relevant_count >= HYPOTHESIS_RELEVANT_THRESHOLD
    ):
        return "contradicted"
    return "mixed"


def compute_severity(outcome: str) -> float | None:
    """Return severity weight for an outcome (FR-81). None if unknown."""
    return SEVERITY_WEIGHTS.get(outcome)


def compute_stakes_weight(stakes: str) -> float:
    """Return stakes weight (FR-82)."""
    return STAKES_WEIGHTS.get(stakes, 1.0)


def compute_gap_score(remembered_share: float, searchable: str) -> float | None:
    """Return gap score for a cue type (FR-87). None if searchable not verified."""
    multiplier = GAP_SCORE_MULTIPLIERS.get(searchable)
    if multiplier is None:
        return None
    return remembered_share * multiplier
