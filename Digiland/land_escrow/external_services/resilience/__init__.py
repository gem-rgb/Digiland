"""
Resilience Engineering Framework - Digiland External Services Layer
====================================================================

Comprehensive resilience patterns for protecting external service
integrations against failures, latency spikes, and cascading outages.

Components:
    - **RetryPolicy**: Configurable retry with exponential backoff + jitter
    - **TimeoutPolicy**: Connection / read / total timeout handling
    - **BulkheadIsolation**: Semaphore-based concurrency limits per provider
    - **GracefulDegradation**: Fallback chains, cached defaults, custom fallbacks
    - **ResiliencePipeline**: Orchestrates Bulkhead -> CircuitBreaker -> Timeout
      -> Retry -> Fallback in a single unified ``execute()`` call

Usage::

    from external_services.resilience import (
        RetryPolicy, TimeoutPolicy, BulkheadIsolation,
        GracefulDegradation, ResiliencePipeline,
    )
    from external_services.circuit_breaker import CircuitBreaker

    pipeline = ResiliencePipeline(
        circuit_breaker=CircuitBreaker('paystack'),
        retry_policy=RetryPolicy(max_retries=3, base_delay=1.0),
        timeout_policy=TimeoutPolicy(connect_timeout=5, read_timeout=30),
        bulkhead=BulkheadIsolation(max_concurrent=10),
        degradation=GracefulDegradation(
            fallback_chain=[backup_provider],
            cache_fallback=True,
        ),
    )

    result = pipeline.execute(primary_func, arg1, arg2)
"""

import logging
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ═══════════════════════════════════════════════════════════════════════════
# Exceptions
# ═══════════════════════════════════════════════════════════════════════════


class RetryExhaustedError(Exception):
    """All retry attempts have been exhausted.

    Attributes:
        attempts: Number of attempts made.
        last_exception: The exception from the final attempt.
    """

    def __init__(self, attempts: int, last_exception: Optional[Exception] = None):
        self.attempts = attempts
        self.last_exception = last_exception
        msg = f"All {attempts} retry attempt(s) exhausted"
        if last_exception:
            msg += f": {last_exception}"
        super().__init__(msg)


class TimeoutError(Exception):
    """An operation exceeded its configured timeout.

    Attributes:
        timeout_type: The kind of timeout that fired.
        timeout_seconds: The configured limit in seconds.
    """

    def __init__(self, timeout_type: str = "total", timeout_seconds: float = 0):
        self.timeout_type = timeout_type
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Timeout ({timeout_type}) exceeded: {timeout_seconds}s"
        )


class BulkheadRejectedException(Exception):
    """A request was rejected because the bulkhead capacity was full.

    Attributes:
        name: Bulkhead identifier.
        max_concurrent: Maximum concurrent requests allowed.
        max_queue: Maximum queued requests allowed.
    """

    def __init__(self, name: str, max_concurrent: int, max_queue: int):
        self.name = name
        self.max_concurrent = max_concurrent
        self.max_queue = max_queue
        super().__init__(
            f"Bulkhead '{name}' capacity exceeded "
            f"(max_concurrent={max_concurrent}, max_queue={max_queue})"
        )


class FallbackExhaustedError(Exception):
    """All fallback strategies have been exhausted."""

    def __init__(self, primary_error: Optional[Exception] = None):
        self.primary_error = primary_error
        msg = "All fallback strategies exhausted"
        if primary_error:
            msg += f" (primary error: {primary_error})"
        super().__init__(msg)


# ═══════════════════════════════════════════════════════════════════════════
# Retry Policy
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class RetryAttempt:
    """Record of a single retry attempt."""

    attempt_number: int
    start_time: datetime
    end_time: datetime
    success: bool
    exception: Optional[Exception] = None
    delay_before: float = 0.0  # seconds waited before this attempt


class RetryPolicy:
    """Configurable retry policy with exponential backoff and jitter.

    Features:
        - Maximum retry attempts (not counting the initial call)
        - Exponential backoff with configurable base and max delay
        - Random jitter to avoid thundering-herd effects
        - Whitelist of retryable exception types
        - Per-retry timeout
        - Retry budget (max retries per minute across all callers)

    Args:
        max_retries: Maximum number of retry attempts (default 3).
        base_delay: Base delay in seconds for exponential backoff (default 1.0).
        max_delay: Maximum delay cap in seconds (default 60.0).
        exponential_base: Multiplier for each backoff step (default 2).
        jitter: Whether to add random jitter to delays (default True).
        retryable_exceptions: Exception types that trigger a retry.
            Defaults to ``(Exception,)``.
        retry_budget_per_minute: Maximum total retries allowed per minute
            across all callers of this policy instance (default 60).
            Set to ``0`` to disable the budget.

    Example::

        policy = RetryPolicy(max_retries=3, base_delay=0.5, jitter=True)
        result = policy.execute(unreliable_api_call, "arg1")
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: int = 2,
        jitter: bool = True,
        retryable_exceptions: Optional[tuple[type[Exception], ...]] = None,
        retry_budget_per_minute: int = 60,
    ):
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if base_delay < 0:
            raise ValueError("base_delay must be >= 0")
        if max_delay < 0:
            raise ValueError("max_delay must be >= 0")
        if exponential_base < 1:
            raise ValueError("exponential_base must be >= 1")

        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or (Exception,)
        self.retry_budget_per_minute = retry_budget_per_minute

        # Budget tracking
        self._budget_lock = threading.Lock()
        self._retry_timestamps: list[float] = []

        # Last attempt history
        self._last_attempts: list[RetryAttempt] = []

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    def execute(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute *func* with the retry policy.

        The initial call counts as attempt 0.  If it fails with a
        retryable exception, subsequent retries are attempted up to
        *max_retries* times, with exponential backoff between attempts.

        Args:
            func: The callable to execute.
            *args: Positional arguments forwarded to *func*.
            **kwargs: Keyword arguments forwarded to *func*.

        Returns:
            The return value of *func* on success.

        Raises:
            RetryExhaustedError: If all attempts are exhausted.
            Any non-retryable exception raised by *func*.
        """
        self._last_attempts = []
        last_exception: Optional[Exception] = None
        total_attempts = self.max_retries + 1  # initial + retries

        for attempt in range(total_attempts):
            # Compute delay (none before the first attempt)
            delay = 0.0
            if attempt > 0:
                delay = self._compute_delay(attempt)
                # Budget check
                if not self._consume_budget():
                    logger.warning(
                        "RetryPolicy: retry budget exhausted, not retrying "
                        "(attempt %d/%d)",
                        attempt,
                        total_attempts,
                    )
                    raise RetryExhaustedError(attempt, last_exception)
                time.sleep(delay)

            start = datetime.now(timezone.utc)
            try:
                result = func(*args, **kwargs)
            except BaseException as exc:
                end = datetime.now(timezone.utc)
                self._last_attempts.append(
                    RetryAttempt(
                        attempt_number=attempt,
                        start_time=start,
                        end_time=end,
                        success=False,
                        exception=exc,
                        delay_before=delay,
                    )
                )

                if not isinstance(exc, self.retryable_exceptions):
                    # Non-retryable: re-raise immediately
                    raise

                last_exception = exc
                logger.debug(
                    "RetryPolicy: attempt %d/%d failed: %s",
                    attempt + 1,
                    total_attempts,
                    exc,
                )
            else:
                end = datetime.now(timezone.utc)
                self._last_attempts.append(
                    RetryAttempt(
                        attempt_number=attempt,
                        start_time=start,
                        end_time=end,
                        success=True,
                        delay_before=delay,
                    )
                )
                return result

        raise RetryExhaustedError(total_attempts, last_exception)

    # ------------------------------------------------------------------
    # Backoff computation
    # ------------------------------------------------------------------

    def _compute_delay(self, attempt: int) -> float:
        """Compute the delay before the given attempt (1-indexed).

        Uses exponential backoff: ``base_delay * exponential_base^(attempt-1)``
        capped at *max_delay*, with optional random jitter.
        """
        raw = self.base_delay * (self.exponential_base ** (attempt - 1))
        delay = min(raw, self.max_delay)
        if self.jitter:
            # Full jitter strategy: random between 0 and delay
            delay = random.uniform(0, delay)
        return delay

    # ------------------------------------------------------------------
    # Budget tracking
    # ------------------------------------------------------------------

    def _consume_budget(self) -> bool:
        """Check and consume a retry budget slot.  Returns False if budget exhausted."""
        if self.retry_budget_per_minute <= 0:
            return True  # budget disabled

        now = time.monotonic()
        window = 60.0  # 1-minute sliding window

        with self._budget_lock:
            # Prune old timestamps
            cutoff = now - window
            self._retry_timestamps = [
                ts for ts in self._retry_timestamps if ts > cutoff
            ]
            if len(self._retry_timestamps) >= self.retry_budget_per_minute:
                return False
            self._retry_timestamps.append(now)
            return True

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def last_attempts(self) -> list[RetryAttempt]:
        """Return the attempt history from the most recent ``execute()`` call."""
        return list(self._last_attempts)


# ═══════════════════════════════════════════════════════════════════════════
# Timeout Policy
# ═══════════════════════════════════════════════════════════════════════════


class TimeoutPolicy:
    """Timeout handling for external service calls.

    Provides three timeout dimensions:
        - **connect_timeout**: Maximum time to establish a connection.
        - **read_timeout**: Maximum time to wait for data after connecting.
        - **total_timeout**: Absolute upper bound for the entire operation,
          including retries.

    The policy can be used directly to enforce a total timeout via
    ``enforce_total()``, or its attributes can be passed to HTTP clients
    (e.g. ``requests.get(..., timeout=(connect, read))``).

    Args:
        connect_timeout: Seconds allowed for connection (default 5).
        read_timeout: Seconds allowed for reading data (default 30).
        total_timeout: Absolute seconds budget for the entire operation
            (default 120).

    Example::

        policy = TimeoutPolicy(connect_timeout=3, read_timeout=10, total_timeout=60)
        result = policy.enforce_total(slow_function, arg1)
    """

    def __init__(
        self,
        connect_timeout: float = 5,
        read_timeout: float = 30,
        total_timeout: float = 120,
    ):
        if connect_timeout < 0:
            raise ValueError("connect_timeout must be >= 0")
        if read_timeout < 0:
            raise ValueError("read_timeout must be >= 0")
        if total_timeout < 0:
            raise ValueError("total_timeout must be >= 0")

        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.total_timeout = total_timeout

    @property
    def requests_timeout(self) -> tuple[float, float]:
        """Return ``(connect_timeout, read_timeout)`` for the *requests* library."""
        return (self.connect_timeout, self.read_timeout)

    @property
    def httpx_timeout(self) -> dict[str, float]:
        """Return a dict suitable for ``httpx.Timeout()``."""
        return {
            "connect": self.connect_timeout,
            "read": self.read_timeout,
            "write": self.read_timeout,
            "pool": self.connect_timeout,
        }

    def enforce_total(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute *func* with a wall-clock total timeout.

        Uses a background thread so that the GIL does not prevent
        timeout enforcement on blocking I/O.

        Args:
            func: The callable to execute.
            *args: Positional arguments forwarded to *func*.
            **kwargs: Keyword arguments forwarded to *func*.

        Returns:
            The return value of *func*.

        Raises:
            TimeoutError: If *total_timeout* is exceeded.
        """
        if self.total_timeout <= 0:
            return func(*args, **kwargs)

        result_container: list[Any] = []
        exception_container: list[Exception] = []

        def _target() -> None:
            try:
                result_container.append(func(*args, **kwargs))
            except Exception as exc:
                exception_container.append(exc)

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join(timeout=self.total_timeout)

        if thread.is_alive():
            # Thread is still running — timeout exceeded
            raise TimeoutError("total", self.total_timeout)

        if exception_container:
            raise exception_container[0]

        return result_container[0]

    def remaining(self, started_at: float) -> float:
        """Return remaining total-timeout budget given a monotonic start time.

        Args:
            started_at: A ``time.monotonic()`` value from before the operation.

        Returns:
            Remaining seconds (0 if exhausted).
        """
        if self.total_timeout <= 0:
            return float("inf")
        elapsed = time.monotonic() - started_at
        return max(0.0, self.total_timeout - elapsed)


# ═══════════════════════════════════════════════════════════════════════════
# Bulkhead Isolation
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class BulkheadStats:
    """Snapshot of bulkhead metrics."""

    name: str
    active_count: int
    queued_count: int
    max_concurrent: int
    max_queue: int
    total_rejected: int
    total_executed: int


class BulkheadIsolation:
    """Bulkhead pattern to isolate provider failures via concurrency limits.

    Uses a semaphore to limit the number of concurrent executions and a
    bounded queue for requests that arrive when all slots are occupied.

    Args:
        name: Identifier for logging and metrics (default ``'default'``).
        max_concurrent: Maximum concurrent executions (default 10).
        max_queue: Maximum number of requests waiting in the queue
            (default 100).  Set to 0 to reject immediately when full.

    Example::

        bulkhead = BulkheadIsolation(name='payment', max_concurrent=5)
        result = bulkhead.execute(payment_call, amount=1000)
    """

    def __init__(
        self,
        name: str = "default",
        max_concurrent: int = 10,
        max_queue: int = 100,
    ):
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be >= 1")
        if max_queue < 0:
            raise ValueError("max_queue must be >= 0")

        self.name = name
        self.max_concurrent = max_concurrent
        self.max_queue = max_queue

        self._semaphore = threading.Semaphore(max_concurrent)
        self._queue_semaphore = threading.Semaphore(max_queue) if max_queue > 0 else None
        self._lock = threading.Lock()
        self._active_count = 0
        self._queued_count = 0
        self._total_rejected = 0
        self._total_executed = 0

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    def execute(
        self,
        func: Callable[..., T],
        *args: Any,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> T:
        """Execute *func* within the bulkhead's concurrency limits.

        If all concurrent slots are occupied the request enters a queue
        (up to *max_queue* deep).  If the queue is also full (or
        *max_queue* is 0) the request is rejected immediately.

        Args:
            func: The callable to execute.
            *args: Positional arguments forwarded to *func*.
            timeout: Maximum seconds to wait for a slot (None = wait forever).
            **kwargs: Keyword arguments forwarded to *func*.

        Returns:
            The return value of *func*.

        Raises:
            BulkheadRejectedException: If the queue is full.
        """
        # Try to enter the queue
        if self._queue_semaphore is not None:
            acquired_queue = self._queue_semaphore.acquire(timeout=timeout)
            if not acquired_queue:
                with self._lock:
                    self._total_rejected += 1
                raise BulkheadRejectedException(
                    self.name, self.max_concurrent, self.max_queue
                )
            with self._lock:
                self._queued_count += 1

        # Wait for an execution slot
        acquired_exec = self._semaphore.acquire(timeout=timeout)
        if not acquired_exec:
            if self._queue_semaphore is not None:
                self._queue_semaphore.release()
                with self._lock:
                    self._queued_count -= 1
                    self._total_rejected += 1
            else:
                with self._lock:
                    self._total_rejected += 1
            raise BulkheadRejectedException(
                self.name, self.max_concurrent, self.max_queue
            )

        with self._lock:
            self._active_count += 1
            if self._queue_semaphore is not None:
                self._queued_count -= 1
                self._queue_semaphore.release()  # free queue slot

        try:
            result = func(*args, **kwargs)
        finally:
            with self._lock:
                self._active_count -= 1
                self._total_executed += 1
            self._semaphore.release()

        return result

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_stats(self) -> BulkheadStats:
        """Return a snapshot of current bulkhead metrics."""
        with self._lock:
            return BulkheadStats(
                name=self.name,
                active_count=self._active_count,
                queued_count=self._queued_count,
                max_concurrent=self.max_concurrent,
                max_queue=self.max_queue,
                total_rejected=self._total_rejected,
                total_executed=self._total_executed,
            )


# ═══════════════════════════════════════════════════════════════════════════
# Graceful Degradation
# ═══════════════════════════════════════════════════════════════════════════


class GracefulDegradation:
    """Graceful degradation with layered fallback strategies.

    When the primary function fails the degradation strategy tries, in
    order:

    1. **Fallback chain** — a list of alternative callables tried
       sequentially until one succeeds.
    2. **Cached response** — look up a cached result via the Django
       cache framework using a key derived from the function and
       arguments.
    3. **Custom fallback** — a user-supplied callable that receives
       the primary exception and returns a default.
    4. **Default value** — a static value returned as a last resort.

    If none of the above yields a result, :class:`FallbackExhaustedError`
    is raised.

    Args:
        fallback_chain: Ordered list of alternative callables.
        cache_fallback: Whether to attempt a cache lookup (default True).
        cache_ttl: Seconds to cache successful primary results (default 300).
        default_value: Static fallback value (default None).
        custom_fallback: Callable ``(exception) -> value`` for custom logic.

    Example::

        degradation = GracefulDegradation(
            fallback_chain=[backup_api, tertiary_api],
            cache_fallback=True,
            default_value={},
        )
        result = degradation.execute(primary_api, request_data)
    """

    def __init__(
        self,
        fallback_chain: Optional[list[Callable]] = None,
        cache_fallback: bool = True,
        cache_ttl: int = 300,
        default_value: Any = None,
        custom_fallback: Optional[Callable[[Exception], Any]] = None,
    ):
        self.fallback_chain = fallback_chain or []
        self.cache_fallback = cache_fallback
        self.cache_ttl = cache_ttl
        self.default_value = default_value
        self.custom_fallback = custom_fallback

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    def execute(
        self,
        primary_func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute *primary_func* with fallback chain on failure.

        On success the result is optionally cached for future fallback
        lookups.

        Args:
            primary_func: The primary callable.
            *args: Positional arguments forwarded to *primary_func* and
                each fallback callable.
            **kwargs: Keyword arguments forwarded similarly.

        Returns:
            The result from the primary or a successful fallback.

        Raises:
            FallbackExhaustedError: If all strategies fail.
        """
        primary_error: Optional[Exception] = None

        # 1. Try primary
        try:
            result = primary_func(*args, **kwargs)
            if self.cache_fallback:
                self._cache_result(primary_func, args, kwargs, result)
            return result
        except Exception as exc:
            primary_error = exc
            logger.debug(
                "GracefulDegradation: primary failed: %s", exc
            )

        # 2. Try fallback chain
        for idx, fallback in enumerate(self.fallback_chain):
            try:
                result = fallback(*args, **kwargs)
                logger.info(
                    "GracefulDegradation: fallback #%d succeeded", idx
                )
                # Note: we intentionally do NOT cache fallback chain results
                # to avoid cross-contamination between different degradation
                # instances that share the same primary function. Only
                # primary-success results are cached as "last known good".
                return result
            except Exception as exc:
                logger.debug(
                    "GracefulDegradation: fallback #%d failed: %s", idx, exc
                )

        # 3. Try cached response
        if self.cache_fallback:
            cached = self._get_cached_result(primary_func, args, kwargs)
            if cached is not None:
                logger.info("GracefulDegradation: cache fallback hit")
                return cached

        # 4. Try custom fallback
        if self.custom_fallback is not None:
            try:
                result = self.custom_fallback(primary_error)
                logger.info("GracefulDegradation: custom fallback succeeded")
                return result
            except Exception as exc:
                logger.debug(
                    "GracefulDegradation: custom fallback failed: %s", exc
                )

        # 5. Return default value if configured
        if self.default_value is not None:
            logger.info("GracefulDegradation: returning default value")
            return self.default_value

        raise FallbackExhaustedError(primary_error)

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cache_key(func: Callable, args: tuple, kwargs: dict) -> str:
        """Derive a deterministic cache key from the function and arguments."""
        from hashlib import sha256

        # Include bytecode to disambiguate functions with the same qualname
        # (e.g. multiple lambda expressions in tests or REPL sessions).
        code_hash = ""
        try:
            code_hash = sha256(func.__code__.co_code).hexdigest()[:8]
        except AttributeError:
            pass
        raw = (
            f"{func.__module__}.{func.__qualname__}:{code_hash}"
            f":{args}:{sorted(kwargs.items())}"
        )
        digest = sha256(raw.encode()).hexdigest()[:16]
        return f"esl:degradation:{digest}"

    def _cache_result(
        self, func: Callable, args: tuple, kwargs: dict, result: Any
    ) -> None:
        """Store a successful result in the Django cache."""
        try:
            from django.core.cache import cache

            cache.set(
                self._cache_key(func, args, kwargs),
                result,
                timeout=self.cache_ttl,
            )
        except Exception:
            logger.warning(
                "GracefulDegradation: failed to cache result", exc_info=True
            )

    def _get_cached_result(
        self, func: Callable, args: tuple, kwargs: dict
    ) -> Any:
        """Retrieve a previously cached result (or ``_SENTINEL`` on miss)."""
        try:
            from django.core.cache import cache

            key = self._cache_key(func, args, kwargs)
            result = cache.get(key, _SENTINEL)
            if result is not _SENTINEL:
                return result
        except Exception:
            logger.warning(
                "GracefulDegradation: cache lookup failed", exc_info=True
            )
        return None


# Unique sentinel for cache miss detection (cannot be confused with None)
_SENTINEL = object()


# ═══════════════════════════════════════════════════════════════════════════
# Resilience Pipeline
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class PipelineResult:
    """Outcome of a ResiliencePipeline execution."""

    value: Any
    source: str  # 'primary', 'fallback', 'cached', 'default'
    attempts: int = 1
    total_duration_seconds: float = 0.0
    circuit_breaker_state: Optional[str] = None


class ResiliencePipeline:
    """Combine all resilience patterns into a single execution pipeline.

    The execution order is::

        Bulkhead -> Circuit Breaker -> Timeout -> Retry -> Fallback

    Each layer is optional; if not provided the pipeline passes through
    to the next layer.

    Args:
        circuit_breaker: A :class:`~external_services.circuit_breaker.CircuitBreaker`.
        retry_policy: A :class:`RetryPolicy`.
        timeout_policy: A :class:`TimeoutPolicy`.
        bulkhead: A :class:`BulkheadIsolation`.
        degradation: A :class:`GracefulDegradation`.

    Example::

        pipeline = ResiliencePipeline(
            circuit_breaker=cb,
            retry_policy=RetryPolicy(max_retries=2),
            timeout_policy=TimeoutPolicy(total_timeout=30),
            bulkhead=BulkheadIsolation(max_concurrent=5),
            degradation=GracefulDegradation(default_value={}),
        )
        result = pipeline.execute(external_call, data)
    """

    def __init__(
        self,
        circuit_breaker: Any = None,
        retry_policy: Optional[RetryPolicy] = None,
        timeout_policy: Optional[TimeoutPolicy] = None,
        bulkhead: Optional[BulkheadIsolation] = None,
        degradation: Optional[GracefulDegradation] = None,
    ):
        self.circuit_breaker = circuit_breaker
        self.retry_policy = retry_policy
        self.timeout_policy = timeout_policy
        self.bulkhead = bulkhead
        self.degradation = degradation

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    def execute(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute *func* through the full resilience pipeline.

        Returns:
            The result from the primary function or a fallback source.

        Raises:
            CircuitBreakerOpenError: If the circuit breaker is open and
                no degradation strategy is available.
            RetryExhaustedError: If retries are exhausted and no fallback.
            TimeoutError: If the timeout is exceeded and no fallback.
            BulkheadRejectedException: If the bulkhead is full and no fallback.
            FallbackExhaustedError: If degradation is enabled but all
                strategies fail.
        """
        start = time.monotonic()

        try:
            result = self._execute_inner(func, *args, **kwargs)
        except Exception as exc:
            # If degradation is configured, attempt fallback
            if self.degradation is not None:
                try:
                    value = self.degradation.execute(func, *args, **kwargs)
                    return value  # Fallback handled internally
                except FallbackExhaustedError:
                    raise exc
            raise

        return result

    def _execute_inner(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Run through Bulkhead -> CB -> Timeout -> Retry layers."""
        # Layer 1: Bulkhead
        if self.bulkhead is not None:
            return self.bulkhead.execute(
                self._with_cb_timeout_retry, func, *args, **kwargs
            )
        return self._with_cb_timeout_retry(func, *args, **kwargs)

    def _with_cb_timeout_retry(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Layer 2: Circuit Breaker."""
        if self.circuit_breaker is not None:
            return self.circuit_breaker.call(
                self._with_timeout_retry, func, *args, **kwargs
            )
        return self._with_timeout_retry(func, *args, **kwargs)

    def _with_timeout_retry(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Layer 3+4: Timeout wrapping Retry wrapping the raw function."""
        if self.timeout_policy is not None and self.retry_policy is not None:
            # Enforce total timeout across all retries
            return self.timeout_policy.enforce_total(
                self.retry_policy.execute, func, *args, **kwargs
            )
        if self.timeout_policy is not None:
            return self.timeout_policy.enforce_total(func, *args, **kwargs)
        if self.retry_policy is not None:
            return self.retry_policy.execute(func, *args, **kwargs)
        return func(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# Module exports
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    "BulkheadIsolation",
    "BulkheadRejectedException",
    "BulkheadStats",
    "FallbackExhaustedError",
    "GracefulDegradation",
    "PipelineResult",
    "ResiliencePipeline",
    "RetryAttempt",
    "RetryExhaustedError",
    "RetryPolicy",
    "TimeoutError",
    "TimeoutPolicy",
]
