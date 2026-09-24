"""
KeyPool — round-robin Gemini API key rotation with per-key RPM ceiling,
exponential backoff cooldown on 429/quota errors, and pause-when-all-cooling.

References:
  FR-50  — comma-separated key list, round-robin
  FR-51  — cooldown with exponential backoff; pause when all cooling
  FR-52  — per-key RPM ceiling enforced client-side
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class _KeyState:
    """Internal state for a single API key."""
    index: int
    key: str
    request_timestamps: list[float] = field(default_factory=list)
    cooldown_until: float = 0.0
    consecutive_errors: int = 0

    def __repr__(self) -> str:
        masked = f"{self.key[:3]}...{self.key[-3:]}" if len(self.key) > 6 else "***"
        return (
            f"_KeyState(index={self.index}, key='{masked}', "
            f"cooldown_until={self.cooldown_until:.1f}, consecutive_errors={self.consecutive_errors})"
        )


class KeyPool:
    """
    Round-robin API key pool with per-key rate limiting and cooldown.

    Usage:
        pool = KeyPool(keys=["k1", "k2", "k3"], rpm_per_key=15)
        key = pool.acquire()  # blocks if all keys cooling
        try:
            # make API call
            pool.report_success(key)
        except QuotaError:
            pool.report_error(key)
    """

    def __init__(self, keys: list[str], rpm_per_key: int = 15) -> None:
        if not keys:
            raise ValueError("KeyPool requires at least one API key")
        self._keys: list[_KeyState] = [
            _KeyState(index=i, key=k) for i, k in enumerate(keys)
        ]
        self._rpm_per_key = rpm_per_key
        self._next_index = 0
        self._base_cooldown = 5.0  # seconds
        self._max_cooldown = 300.0  # 5 minutes max

    @property
    def size(self) -> int:
        return len(self._keys)

    def acquire(self) -> str:
        """
        Acquire the next available key, respecting RPM limits and cooldowns.
        Blocks (sleeps) if all keys are cooling down.
        Returns the API key string.
        """
        attempts = 0
        while True:
            now = time.monotonic()

            # Try each key in round-robin order
            for _ in range(len(self._keys)):
                state = self._keys[self._next_index]
                self._next_index = (self._next_index + 1) % len(self._keys)

                # Skip keys in cooldown
                if state.cooldown_until > now:
                    continue

                # Enforce RPM ceiling: remove timestamps older than 60s
                cutoff = now - 60.0
                state.request_timestamps = [
                    t for t in state.request_timestamps if t > cutoff
                ]

                if len(state.request_timestamps) >= self._rpm_per_key:
                    continue  # This key is at RPM limit

                # Key is available
                state.request_timestamps.append(now)
                return state.key

            # All keys are either cooling or at RPM limit
            # Find the earliest time a key becomes available
            earliest_available = float("inf")
            for state in self._keys:
                if state.cooldown_until > now:
                    earliest_available = min(earliest_available, state.cooldown_until)
                elif state.request_timestamps:
                    # When will the oldest request in the window expire?
                    cutoff = now - 60.0
                    active = [t for t in state.request_timestamps if t > cutoff]
                    if len(active) >= self._rpm_per_key and active:
                        earliest_available = min(earliest_available, active[0] + 60.0)

            wait_time = max(0.1, earliest_available - now)
            if wait_time > 600:
                wait_time = 1.0  # safety cap

            logger.warning(
                "All keys busy or cooling. Waiting %.1fs. Attempt %d.",
                wait_time,
                attempts + 1,
            )
            time.sleep(wait_time)
            attempts += 1

    def report_success(self, key: str) -> None:
        """Report a successful API call — reset consecutive error count."""
        state = self._find_state(key)
        if state:
            state.consecutive_errors = 0

    def report_error(self, key: str) -> None:
        """
        Report a 429/quota error — put key into exponential backoff cooldown.
        Logs the key by index only, never the key value.
        """
        state = self._find_state(key)
        if not state:
            return

        state.consecutive_errors += 1
        cooldown = min(
            self._base_cooldown * (2 ** (state.consecutive_errors - 1)),
            self._max_cooldown,
        )
        state.cooldown_until = time.monotonic() + cooldown
        logger.warning(
            "Key index %d entered cooldown for %.1fs (consecutive errors: %d)",
            state.index,
            cooldown,
            state.consecutive_errors,
        )

    def get_key_index(self, key: str) -> int | None:
        """Return the index of a key (for logging). Never log the key itself."""
        state = self._find_state(key)
        return state.index if state else None

    def _find_state(self, key: str) -> _KeyState | None:
        for state in self._keys:
            if state.key == key:
                return state
        return None

    def all_cooling(self) -> bool:
        """Check if all keys are currently in cooldown."""
        now = time.monotonic()
        return all(state.cooldown_until > now for state in self._keys)

    def available_count(self) -> int:
        """Return the number of keys not currently in cooldown."""
        now = time.monotonic()
        return sum(1 for state in self._keys if state.cooldown_until <= now)
