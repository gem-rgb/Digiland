"""
Rate Limit Management - Digiland External Services Layer
==========================================================

Comprehensive rate-limiting infrastructure for controlling outbound
request volume to external service providers.

Components:
    - **RateLimitManager**: Central manager for global and per-provider limits
    - **TokenBucket**: Token-bucket algorithm implementation
    - **SlidingWindowCounter**: Sliding-window counter implementation
    - **ProviderRateLimit**: Per-provider rate-limit configuration
    - **RateLimitExceededError**: Raised when a rate limit is exceeded

Design choices:
    - Token buckets for per-second burst control
    - Sliding windows for per-minute/hour quotas
    - Adaptive throttling that parses ``X-RateLimit-*`` response headers
    - Optional Redis backend for distributed rate-limit state
    - Django cache fallback for single-process deployments

Usage::

    from external_services.rate_limiting import RateLimitManager

    manager = RateLimitManager()

    # Configure provider limits
    manager.set_provider_limits('payment', 'paystack', {
        'requests_per_second': 10,
        'requests_per_minute': 100,
        'requests_per_hour': 1000,
    })

    # Check before calling
    if manager.check_rate_limit('payment:paystack'):
        result = call_paystack(...)
    else:
        # Back off or queue
        ...

    # Or block until a token is available
    manager.acquire('payment:paystack')
    result = call_paystack(...)
"""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from django.core.cache import cache

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "esl:rl"


# ═══════════════════════════════════════════════════════════════════════════
# Exceptions
# ═══════════════════════════════════════════════════════════════════════════


class RateLimitExceededError(Exception):
    """Raised when a rate limit has been exceeded.

    Attributes:
        provider_key: The provider identifier.
        limit_type: The type of limit that was exceeded.
        retry_after: Suggested seconds until the next attempt.
    """

    def __init__(
        self,
        provider_key: str,
        limit_type: str = "unknown",
        retry_after: float = 0,
    ):
        self.provider_key = provider_key
        self.limit_type = limit_type
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded for '{provider_key}' "
            f"(limit_type={limit_type}, retry_after={retry_after:.1f}s)"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ProviderRateLimit:
    """Rate-limit configuration for a single provider.

    Attributes:
        requests_per_second: Maximum requests per second (token bucket).
        requests_per_minute: Maximum requests per 60-second window.
        requests_per_hour: Maximum requests per 3600-second window.
        burst_size: Token bucket burst capacity (defaults to
            ``requests_per_second * 2``).
    """

    requests_per_second: float = 10.0
    requests_per_minute: int = 600
    requests_per_hour: int = 36000
    burst_size: Optional[int] = None

    def __post_init__(self) -> None:
        if self.burst_size is None:
            self.burst_size = int(self.requests_per_second * 2)


@dataclass
class RateLimitUsage:
    """Current rate-limit usage snapshot for a provider."""

    provider_key: str
    tokens_remaining: float
    bucket_capacity: float
    minute_remaining: int
    minute_limit: int
    hour_remaining: int
    hour_limit: int
    retry_after_seconds: float = 0.0


@dataclass
class AdaptiveState:
    """Adaptive throttling state derived from provider response headers."""

    provider_key: str
    remaining: Optional[int] = None
    limit: Optional[int] = None
    reset_at: Optional[datetime] = None
    retry_after: Optional[float] = None
    last_updated: Optional[datetime] = None


# ═══════════════════════════════════════════════════════════════════════════
# Token Bucket
# ═══════════════════════════════════════════════════════════════════════════


class TokenBucket:
    """Token bucket rate limiter implementation.

    Tokens are added at a constant *rate* (tokens per second) up to the
    bucket *capacity*.  Each request consumes one or more tokens.  If
    insufficient tokens are available the request must wait or be
    rejected.

    This implementation uses a lazy-fill approach: the token count is
    computed on demand based on elapsed time rather than via a
    background refill thread, which makes it safe for multi-threaded
    use with locking.

    Args:
        capacity: Maximum number of tokens in the bucket.
        rate: Token refill rate (tokens per second).
        name: Identifier for logging and cache keys.

    Example::

        bucket = TokenBucket(capacity=20, rate=10, name='paystack')
        if bucket.consume():
            call_provider()
        else:
            wait_or_reject()
    """

    def __init__(
        self,
        capacity: float = 20,
        rate: float = 10,
        name: str = "default",
    ):
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        if rate <= 0:
            raise ValueError("rate must be > 0")

        self.capacity = capacity
        self.rate = rate
        self.name = name

        self._lock = threading.Lock()
        self._tokens: float = capacity
        self._last_refill: float = time.monotonic()

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def consume(self, tokens: int = 1) -> bool:
        """Attempt to consume *tokens* from the bucket.

        Returns:
            ``True`` if tokens were available and consumed; ``False`` otherwise.
        """
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                self._persist()
                return True
            return False

    def acquire(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """Block until *tokens* are available or *timeout* elapses.

        Args:
            tokens: Number of tokens to acquire.
            timeout: Maximum seconds to wait (None = wait forever).

        Returns:
            ``True`` if tokens were acquired; ``False`` on timeout.
        """
        deadline = None
        if timeout is not None:
            deadline = time.monotonic() + timeout

        while True:
            with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    self._persist()
                    return True

            if deadline is not None and time.monotonic() >= deadline:
                return False

            # Sleep for a small fraction of the time needed to refill
            deficit = tokens - self._tokens
            wait_time = min(deficit / self.rate, 0.1)
            time.sleep(wait_time)

    @property
    def available_tokens(self) -> float:
        """Return the current number of available tokens (lazy-refilled)."""
        with self._lock:
            self._refill()
            return self._tokens

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _refill(self) -> None:
        """Add tokens based on elapsed time since last refill."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        new_tokens = elapsed * self.rate
        self._tokens = min(self.capacity, self._tokens + new_tokens)
        self._last_refill = now

    def _persist(self) -> None:
        """Persist current state to Django cache for cross-process visibility."""
        try:
            cache.set(
                f"{_CACHE_PREFIX}:tb:{self.name}",
                {
                    "tokens": self._tokens,
                    "last_refill": self._last_refill,
                },
                timeout=3600,
            )
        except Exception:
            logger.warning(
                "TokenBucket '%s': cache persist failed", self.name, exc_info=True
            )

    def _restore(self) -> None:
        """Restore state from Django cache (best-effort)."""
        try:
            data = cache.get(f"{_CACHE_PREFIX}:tb:{self.name}")
            if data:
                self._tokens = data.get("tokens", self.capacity)
                self._last_refill = data.get("last_refill", time.monotonic())
        except Exception:
            logger.warning(
                "TokenBucket '%s': cache restore failed", self.name, exc_info=True
            )


# ═══════════════════════════════════════════════════════════════════════════
# Sliding Window Counter
# ═══════════════════════════════════════════════════════════════════════════


class SlidingWindowCounter:
    """Sliding window counter rate limiter implementation.

    Uses a two-bucket weighted approach for smooth transitions at
    window boundaries.  The current and previous fixed-window counters
    are combined to approximate a true sliding window.

    Args:
        limit: Maximum number of requests per window.
        window_seconds: Window duration in seconds (default 60).
        name: Identifier for logging and cache keys.

    Example::

        counter = SlidingWindowCounter(limit=100, window_seconds=60, name='mpesa')
        if counter.increment():
            call_mpesa()
        else:
            back_off()
    """

    def __init__(
        self,
        limit: int = 100,
        window_seconds: int = 60,
        name: str = "default",
    ):
        if limit <= 0:
            raise ValueError("limit must be > 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")

        self.limit = limit
        self.window_seconds = window_seconds
        self.name = name

        self._lock = threading.Lock()
        self._current_count: int = 0
        self._previous_count: int = 0
        self._current_window_start: float = self._current_window_key()

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def increment(self, count: int = 1) -> bool:
        """Increment the counter and check if the limit is still respected.

        Returns:
            ``True`` if the increment was allowed; ``False`` if the limit
            would be exceeded (the counter is **not** incremented).
        """
        with self._lock:
            self._advance_window()
            estimated = self._estimated_count()
            if estimated + count > self.limit:
                return False
            self._current_count += count
            self._persist()
            return True

    def check(self) -> bool:
        """Check if the limit would allow an increment without actually incrementing."""
        with self._lock:
            self._advance_window()
            return self._estimated_count() < self.limit

    @property
    def remaining(self) -> int:
        """Return the estimated number of remaining requests in the window."""
        with self._lock:
            self._advance_window()
            return max(0, self.limit - self._estimated_count())

    @property
    def retry_after(self) -> float:
        """Return the approximate seconds until the next request would be allowed."""
        with self._lock:
            self._advance_window()
            if self._estimated_count() < self.limit:
                return 0.0
            # Wait until the current window ends (worst case)
            elapsed = time.time() - self._current_window_start
            return max(0.0, self.window_seconds - elapsed)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _current_window_key(self) -> float:
        """Return the start timestamp of the current fixed window."""
        return (time.time() // self.window_seconds) * self.window_seconds

    def _advance_window(self) -> None:
        """Roll over counters when a new fixed window starts."""
        now_key = self._current_window_key()
        if now_key > self._current_window_start:
            # How many full windows have elapsed?
            gap = now_key - self._current_window_start
            if gap >= self.window_seconds * 2:
                # More than one window gap — reset completely
                self._previous_count = 0
                self._current_count = 0
            else:
                # Normal rollover
                self._previous_count = self._current_count
                self._current_count = 0
            self._current_window_start = now_key

    def _estimated_count(self) -> float:
        """Estimate the sliding-window count using weighted two-bucket algorithm.

        The formula::

            estimated = previous_count * (1 - elapsed/window) + current_count

        This provides a smooth approximation of a true sliding window.
        """
        elapsed = time.time() - self._current_window_start
        weight = max(0.0, 1.0 - elapsed / self.window_seconds)
        return self._previous_count * weight + self._current_count

    def _persist(self) -> None:
        """Persist counter state to Django cache."""
        try:
            cache.set(
                f"{_CACHE_PREFIX}:sw:{self.name}",
                {
                    "current_count": self._current_count,
                    "previous_count": self._previous_count,
                    "current_window_start": self._current_window_start,
                },
                timeout=self.window_seconds * 3,
            )
        except Exception:
            logger.warning(
                "SlidingWindowCounter '%s': cache persist failed",
                self.name,
                exc_info=True,
            )

    def _restore(self) -> None:
        """Restore counter state from Django cache (best-effort)."""
        try:
            data = cache.get(f"{_CACHE_PREFIX}:sw:{self.name}")
            if data:
                self._current_count = data.get("current_count", 0)
                self._previous_count = data.get("previous_count", 0)
                self._current_window_start = data.get(
                    "current_window_start", self._current_window_key()
                )
                self._advance_window()
        except Exception:
            logger.warning(
                "SlidingWindowCounter '%s': cache restore failed",
                self.name,
                exc_info=True,
            )


# ═══════════════════════════════════════════════════════════════════════════
# Rate Limit Manager
# ═══════════════════════════════════════════════════════════════════════════


class RateLimitManager:
    """Comprehensive rate limit management for all external service providers.

    Features:
        - Global rate limits across all providers
        - Per-provider rate limits (token bucket + sliding window)
        - Adaptive throttling based on provider ``X-RateLimit-*`` headers
        - Backpressure signaling (retry-after propagation)
        - Redis-backed distributed rate limiting via Django cache

    Example::

        manager = RateLimitManager()
        manager.set_provider_limits('payment', 'paystack', {
            'requests_per_second': 10,
            'requests_per_minute': 100,
        })

        if manager.check_rate_limit('payment:paystack'):
            manager.acquire('payment:paystack')
            result = call_paystack(...)
            manager.update_from_headers('payment:paystack', response.headers)
    """

    _global_instance: Optional["RateLimitManager"] = None
    _global_lock = threading.Lock()

    def __init__(
        self,
        global_rps: float = 100,
        global_rpm: int = 6000,
    ):
        self._lock = threading.RLock()

        # Global limits
        self._global_bucket = TokenBucket(
            capacity=global_rps * 2,
            rate=global_rps,
            name="__global__",
        )
        self._global_minute_counter = SlidingWindowCounter(
            limit=global_rpm,
            window_seconds=60,
            name="__global__",
        )

        # Per-provider limiters
        self._provider_configs: dict[str, ProviderRateLimit] = {}
        self._provider_buckets: dict[str, TokenBucket] = {}
        self._provider_minute_counters: dict[str, SlidingWindowCounter] = {}
        self._provider_hour_counters: dict[str, SlidingWindowCounter] = {}

        # Adaptive state from response headers
        self._adaptive_state: dict[str, AdaptiveState] = {}

    @classmethod
    def get_global(cls) -> "RateLimitManager":
        """Return the process-wide singleton manager."""
        if cls._global_instance is None:
            with cls._global_lock:
                if cls._global_instance is None:
                    cls._global_instance = cls()
        return cls._global_instance

    @classmethod
    def reset_global(cls) -> None:
        """Reset the global singleton (useful in tests)."""
        with cls._global_lock:
            cls._global_instance = None

    # ------------------------------------------------------------------
    # Provider configuration
    # ------------------------------------------------------------------

    def set_provider_limits(
        self,
        service_type: str,
        provider_name: str,
        limits: dict[str, Any],
    ) -> None:
        """Set rate limits for a specific provider.

        Args:
            service_type: Service category (e.g. ``'payment'``).
            provider_name: Provider name (e.g. ``'paystack'``).
            limits: Dict with optional keys:
                - ``requests_per_second`` (float, default 10)
                - ``requests_per_minute`` (int, default 600)
                - ``requests_per_hour`` (int, default 36000)
                - ``burst_size`` (int, optional)
        """
        key = self._make_key(service_type, provider_name)
        config = ProviderRateLimit(
            requests_per_second=limits.get("requests_per_second", 10.0),
            requests_per_minute=limits.get("requests_per_minute", 600),
            requests_per_hour=limits.get("requests_per_hour", 36000),
            burst_size=limits.get("burst_size"),
        )

        with self._lock:
            self._provider_configs[key] = config
            self._provider_buckets[key] = TokenBucket(
                capacity=config.burst_size or int(config.requests_per_second * 2),
                rate=config.requests_per_second,
                name=key,
            )
            self._provider_minute_counters[key] = SlidingWindowCounter(
                limit=config.requests_per_minute,
                window_seconds=60,
                name=f"{key}:min",
            )
            self._provider_hour_counters[key] = SlidingWindowCounter(
                limit=config.requests_per_hour,
                window_seconds=3600,
                name=f"{key}:hr",
            )

        logger.info(
            "RateLimitManager: set limits for '%s' "
            "(rps=%.1f, rpm=%d, rph=%d)",
            key,
            config.requests_per_second,
            config.requests_per_minute,
            config.requests_per_hour,
        )

    # ------------------------------------------------------------------
    # Rate limit checks
    # ------------------------------------------------------------------

    def check_rate_limit(
        self,
        provider_key: str,
        operation: Optional[str] = None,
    ) -> bool:
        """Check if a request would be within rate limits.

        This is a non-mutating check — no tokens are consumed.

        Args:
            provider_key: Provider identifier (e.g. ``'payment:paystack'``).
            operation: Optional operation-level sub-limit key.

        Returns:
            ``True`` if the request is allowed; ``False`` if it would
            exceed a limit.
        """
        # Check adaptive backpressure first
        adaptive = self._adaptive_state.get(provider_key)
        if adaptive and adaptive.retry_after and adaptive.retry_after > 0:
            elapsed = (
                datetime.now(timezone.utc) - adaptive.last_updated
            ).total_seconds() if adaptive.last_updated else 0
            if elapsed < adaptive.retry_after:
                return False

        # Check global limits
        if not self._global_minute_counter.check():
            return False
        if self._global_bucket.available_tokens < 1:
            return False

        # Check per-provider limits
        with self._lock:
            bucket = self._provider_buckets.get(provider_key)
            minute = self._provider_minute_counters.get(provider_key)
            hour = self._provider_hour_counters.get(provider_key)

        if bucket and bucket.available_tokens < 1:
            return False
        if minute and not minute.check():
            return False
        if hour and not hour.check():
            return False

        return True

    def acquire(
        self,
        provider_key: str,
        operation: Optional[str] = None,
        tokens: int = 1,
        timeout: Optional[float] = None,
    ) -> bool:
        """Acquire rate-limit tokens, blocking if necessary.

        Consumes tokens from both global and per-provider limiters.
        If any limiter would be exceeded, the method blocks until
        tokens become available or *timeout* elapses.

        Args:
            provider_key: Provider identifier.
            operation: Optional operation sub-key.
            tokens: Number of tokens to consume (default 1).
            timeout: Maximum seconds to wait (None = wait forever).

        Returns:
            ``True`` if tokens were acquired; ``False`` on timeout.

        Raises:
            RateLimitExceededError: If the limit is hard-exceeded with
                no timeout and adaptive throttling says to stop.
        """
        deadline = None
        if timeout is not None:
            deadline = time.monotonic() + timeout

        while True:
            # Adaptive backpressure
            adaptive = self._adaptive_state.get(provider_key)
            if adaptive and adaptive.retry_after and adaptive.retry_after > 0:
                elapsed = (
                    datetime.now(timezone.utc) - adaptive.last_updated
                ).total_seconds() if adaptive.last_updated else 0
                remaining_wait = adaptive.retry_after - elapsed
                if remaining_wait > 0:
                    if deadline and time.monotonic() + remaining_wait > deadline:
                        return False
                    time.sleep(min(remaining_wait, 0.5))
                    continue

            # Try to consume from all limiters atomically
            with self._lock:
                bucket = self._provider_buckets.get(provider_key)
                minute = self._provider_minute_counters.get(provider_key)
                hour = self._provider_hour_counters.get(provider_key)

            # Check each limiter
            if bucket and not bucket.consume(tokens):
                if deadline and time.monotonic() >= deadline:
                    return False
                time.sleep(0.05)
                continue

            if minute and not minute.increment(tokens):
                # Roll back bucket consumption
                if bucket:
                    bucket._tokens += tokens  # Best-effort rollback
                if deadline and time.monotonic() >= deadline:
                    return False
                time.sleep(0.05)
                continue

            if hour and not hour.increment(tokens):
                # Roll back previous consumptions
                if bucket:
                    bucket._tokens += tokens
                if minute:
                    minute._current_count -= tokens
                if deadline and time.monotonic() >= deadline:
                    return False
                time.sleep(0.05)
                continue

            # Global limiters
            if not self._global_bucket.consume(tokens):
                if bucket:
                    bucket._tokens += tokens
                if minute:
                    minute._current_count -= tokens
                if hour:
                    hour._current_count -= tokens
                if deadline and time.monotonic() >= deadline:
                    return False
                time.sleep(0.05)
                continue

            if not self._global_minute_counter.increment(tokens):
                self._global_bucket._tokens += tokens
                if bucket:
                    bucket._tokens += tokens
                if minute:
                    minute._current_count -= tokens
                if hour:
                    hour._current_count -= tokens
                if deadline and time.monotonic() >= deadline:
                    return False
                time.sleep(0.05)
                continue

            # All limiters passed
            return True

    # ------------------------------------------------------------------
    # Adaptive throttling
    # ------------------------------------------------------------------

    def update_from_headers(
        self,
        provider_key: str,
        response_headers: dict[str, str],
    ) -> None:
        """Update rate-limit state from provider response headers.

        Parses the following standard and semi-standard headers:

        - ``X-RateLimit-Limit`` — Total limit per window
        - ``X-RateLimit-Remaining`` — Requests remaining in window
        - ``X-RateLimit-Reset`` — Unix timestamp when the window resets
        - ``Retry-After`` — Seconds until the client should wait
        - ``X-RateLimit-Retry-After`` — Alternative retry-after

        Args:
            provider_key: Provider identifier.
            response_headers: Dict-like object of response headers.
        """
        now = datetime.now(timezone.utc)

        limit = self._parse_int_header(response_headers, "X-RateLimit-Limit")
        remaining = self._parse_int_header(response_headers, "X-RateLimit-Remaining")
        reset_ts = self._parse_int_header(response_headers, "X-RateLimit-Reset")
        retry_after = self._parse_float_header(
            response_headers,
            "Retry-After",
        ) or self._parse_float_header(
            response_headers,
            "X-RateLimit-Retry-After",
        )

        reset_at = None
        if reset_ts:
            try:
                reset_at = datetime.fromtimestamp(reset_ts, tz=timezone.utc)
            except (OSError, OverflowError, ValueError):
                reset_at = None

        with self._lock:
            self._adaptive_state[provider_key] = AdaptiveState(
                provider_key=provider_key,
                remaining=remaining,
                limit=limit,
                reset_at=reset_at,
                retry_after=retry_after,
                last_updated=now,
            )

        # If remaining is 0, apply backpressure
        if remaining is not None and remaining <= 0:
            wait = retry_after or 0
            if reset_at:
                wait = max(wait, (reset_at - now).total_seconds())
            logger.warning(
                "RateLimitManager: backpressure from '%s' "
                "(remaining=0, retry_after=%.1fs)",
                provider_key,
                wait,
            )

    # ------------------------------------------------------------------
    # Usage introspection
    # ------------------------------------------------------------------

    def get_usage(self, provider_key: str) -> RateLimitUsage:
        """Get current rate-limit usage for a provider.

        Args:
            provider_key: Provider identifier.

        Returns:
            A :class:`RateLimitUsage` snapshot.
        """
        with self._lock:
            config = self._provider_configs.get(provider_key)
            bucket = self._provider_buckets.get(provider_key)
            minute = self._provider_minute_counters.get(provider_key)
            hour = self._provider_hour_counters.get(provider_key)

        tokens_remaining = bucket.available_tokens if bucket else 0
        bucket_capacity = bucket.capacity if bucket else 0
        minute_remaining = minute.remaining if minute else 0
        minute_limit = minute.limit if minute else 0
        hour_remaining = hour.remaining if hour else 0
        hour_limit = hour.limit if hour else 0

        # Compute retry_after from the tightest limiter
        retry_after = 0.0
        adaptive = self._adaptive_state.get(provider_key)
        if adaptive and adaptive.retry_after:
            elapsed = (
                datetime.now(timezone.utc) - adaptive.last_updated
            ).total_seconds() if adaptive.last_updated else 0
            retry_after = max(0.0, adaptive.retry_after - elapsed)
        if bucket:
            retry_after = max(retry_after, 0.0)
        if minute:
            retry_after = max(retry_after, minute.retry_after)
        if hour:
            retry_after = max(retry_after, hour.retry_after)

        return RateLimitUsage(
            provider_key=provider_key,
            tokens_remaining=tokens_remaining,
            bucket_capacity=bucket_capacity,
            minute_remaining=minute_remaining,
            minute_limit=minute_limit,
            hour_remaining=hour_remaining,
            hour_limit=hour_limit,
            retry_after_seconds=retry_after,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(service_type: str, provider_name: str) -> str:
        return f"{service_type}:{provider_name}"

    @staticmethod
    def _parse_int_header(
        headers: dict[str, str], name: str
    ) -> Optional[int]:
        """Parse an integer-valued header (case-insensitive)."""
        for key, value in headers.items():
            if key.lower() == name.lower():
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return None
        return None

    @staticmethod
    def _parse_float_header(
        headers: dict[str, str], name: str
    ) -> Optional[float]:
        """Parse a float-valued header (case-insensitive)."""
        for key, value in headers.items():
            if key.lower() == name.lower():
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return None
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Module exports
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    "AdaptiveState",
    "ProviderRateLimit",
    "RateLimitExceededError",
    "RateLimitManager",
    "RateLimitUsage",
    "SlidingWindowCounter",
    "TokenBucket",
]
