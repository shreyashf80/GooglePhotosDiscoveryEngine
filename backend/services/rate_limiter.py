"""
In-memory rate limiter for chat endpoint.

FR-106: 10 requests/minute per IP, 150 requests/day global.
Uses simple sliding window counters stored in memory.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import NamedTuple


class RateLimitResult(NamedTuple):
    allowed: bool
    retry_after_seconds: int


class RateLimiter:
    """In-memory rate limiter with per-IP and global limits."""

    def __init__(
        self,
        per_ip_limit: int = 10,
        per_ip_window: int = 60,
        global_daily_limit: int = 150,
    ) -> None:
        self._per_ip_limit = per_ip_limit
        self._per_ip_window = per_ip_window
        self._global_daily_limit = global_daily_limit

        # Per-IP: list of request timestamps
        self._ip_requests: dict[str, list[float]] = defaultdict(list)
        # Global: list of request timestamps within the current day
        self._global_requests: list[float] = []
        self._day_start: float = self._get_day_start()

    @staticmethod
    def _get_day_start() -> float:
        """Get the start of the current UTC day as a timestamp."""
        now = time.time()
        # Round down to start of day
        return now - (now % 86400)

    def _cleanup_ip(self, ip: str) -> None:
        """Remove expired per-IP timestamps."""
        cutoff = time.time() - self._per_ip_window
        self._ip_requests[ip] = [
            t for t in self._ip_requests[ip] if t > cutoff
        ]

    def _cleanup_global(self) -> None:
        """Reset global counter at day boundary."""
        current_day_start = self._get_day_start()
        if current_day_start != self._day_start:
            self._global_requests = []
            self._day_start = current_day_start

    def check(self, ip: str) -> RateLimitResult:
        """
        Check if a request from the given IP is allowed.

        Returns:
            RateLimitResult with allowed=True if OK, or retry_after_seconds if not.
        """
        now = time.time()

        # Check global daily limit
        self._cleanup_global()
        if len(self._global_requests) >= self._global_daily_limit:
            # Time until next day
            next_day = self._day_start + 86400
            retry_after = int(next_day - now) + 1
            return RateLimitResult(allowed=False, retry_after_seconds=retry_after)

        # Check per-IP limit
        self._cleanup_ip(ip)
        if len(self._ip_requests[ip]) >= self._per_ip_limit:
            oldest = self._ip_requests[ip][0]
            retry_after = int(oldest + self._per_ip_window - now) + 1
            return RateLimitResult(allowed=False, retry_after_seconds=max(1, retry_after))

        # Record the request
        self._ip_requests[ip].append(now)
        self._global_requests.append(now)

        return RateLimitResult(allowed=True, retry_after_seconds=0)


# Singleton instance
chat_rate_limiter = RateLimiter()
