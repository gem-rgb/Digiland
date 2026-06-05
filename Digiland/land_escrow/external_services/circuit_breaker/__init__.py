"""
Circuit Breaker Framework - Digiland External Services Layer
=============================================================

Production-grade circuit breaker pattern implementation for protecting
external service calls from cascading failures.

Architecture:
    CLOSED  ──(failure_threshold reached)──>  OPEN
      ^                                           |
      |                                           |
      └──(success in HALF_OPEN)──  HALF_OPEN  <───┘
                                     │
                                     └──(failure in HALF_OPEN)──>  OPEN

Features:
    - Configurable failure threshold for state transitions
    - Configurable recovery timeout before half-open probe
    - Half-open state for safe recovery testing
    - Per-provider circuit breaker instances via registry
    - Thread-safe state management with locking
    - Automatic state transitions with event callbacks
    - Metrics tracking (failure/success counts, timing)
    - Django cache-backed state persistence for multi-process coordination

Usage:
    from external_services.circuit_breaker import CircuitBreaker, circuit_breaker

    # Direct usage
    cb = CircuitBreaker(name='paystack', failure_threshold=5, recovery_timeout=60)
    result = cb.call(external_api_call, arg1, arg2)

    # Decorator usage
    @circuit_breaker(name='stripe', failure_threshold=3)
    def call_stripe_api():
        ...

    # Registry usage
    from external_services.circuit_breaker import CircuitBreakerRegistry
    registry = CircuitBreakerRegistry()
    cb = registry.get_or_create('payment', 'mpesa')
    result = cb.call(payment_func)
"""

import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import Any, Optional, TypeVar

from django.core.cache import cache

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Cache key prefix for Django-cache-backed persistence
# ---------------------------------------------------------------------------
_CACHE_PREFIX = "esl:cb"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CircuitBreakerOpenError(Exception):
    """Raised when a call is attempted while the circuit breaker is open.

    Attributes:
        name: The circuit breaker identifier.
        state: The current state string.
        last_failure_time: Timestamp of the most recent failure.
    """

    def __init__(
        self,
        name: str,
        state: str = "open",
        last_failure_time: Optional[datetime] = None,
    ):
        self.name = name
        self.state = state
        self.last_failure_time = last_failure_time
        msg = (
            f"Circuit breaker '{name}' is {state}. "
            f"Last failure: {last_failure_time.isoformat() if last_failure_time else 'N/A'}"
        )
        super().__init__(msg)


# ---------------------------------------------------------------------------
# State enum & event dataclasses
# ---------------------------------------------------------------------------


class CircuitState(str, Enum):
    """Possible circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerStats:
    """Snapshot of circuit breaker metrics."""

    name: str
    state: str
    failure_count: int
    success_count: int
    last_failure_time: Optional[datetime]
    last_success_time: Optional[datetime]
    last_state_change_time: Optional[datetime]
    total_calls: int
    rejected_calls: int
    open_duration_seconds: float = 0.0


@dataclass
class StateTransitionEvent:
    """Emitted when a circuit breaker changes state."""

    breaker_name: str
    old_state: str
    new_state: str
    timestamp: datetime
    reason: str
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Callback protocol
# ---------------------------------------------------------------------------

StateChangeCallback = Callable[[StateTransitionEvent], None]


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------


class CircuitBreaker:
    """
    Circuit breaker with three states: CLOSED, OPEN, HALF_OPEN.

    In the **CLOSED** state all calls are allowed.  Consecutive failures
    increment the failure counter; once it reaches *failure_threshold* the
    breaker transitions to OPEN.

    In the **OPEN** state all calls are immediately rejected by raising
    :class:`CircuitBreakerOpenError`.  After *recovery_timeout* seconds
    the breaker transitions to HALF_OPEN.

    In the **HALF_OPEN** state a limited number of probe calls
    (*half_open_max_calls*) are allowed.  If any probe fails the breaker
    returns to OPEN; if all probes succeed it transitions to CLOSED.

    State is persisted to the Django cache so that multiple
    processes/workers share a consistent view of the circuit.

    Args:
        name: Unique identifier (typically the provider name).
        failure_threshold: Consecutive failures required to open the circuit.
        recovery_timeout: Seconds to wait before transitioning OPEN -> HALF_OPEN.
        half_open_max_calls: Number of successful probe calls needed to close.
        expected_exceptions: Exception types that count as failures.
            Defaults to ``(Exception,)`` — all exceptions are counted.

    Example::

        cb = CircuitBreaker("paystack", failure_threshold=5, recovery_timeout=30)
        try:
            result = cb.call(risky_operation, "arg1")
        except CircuitBreakerOpenError:
            # Fallback or graceful degradation
            ...
    """

    CLOSED = CircuitState.CLOSED.value
    OPEN = CircuitState.OPEN.value
    HALF_OPEN = CircuitState.HALF_OPEN.value

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60,
        half_open_max_calls: int = 3,
        expected_exceptions: Optional[tuple[type[Exception], ...]] = None,
    ):
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if recovery_timeout < 0:
            raise ValueError("recovery_timeout must be >= 0")
        if half_open_max_calls < 1:
            raise ValueError("half_open_max_calls must be >= 1")

        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.expected_exceptions = expected_exceptions or (Exception,)

        # Thread-safety lock for in-process mutations
        self._lock = threading.RLock()

        # In-memory state (authoritative when cache unavailable)
        self._state = self.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_success_time: Optional[datetime] = None
        self._last_state_change_time: Optional[datetime] = None
        self._opened_at: Optional[datetime] = None
        self._total_calls = 0
        self._rejected_calls = 0

        # Callbacks
        self._on_state_change: list[StateChangeCallback] = []

        # Attempt to restore persisted state on init
        self._restore_state()

    # ------------------------------------------------------------------
    # Cache persistence helpers
    # ------------------------------------------------------------------

    @property
    def _cache_key(self) -> str:
        return f"{_CACHE_PREFIX}:{self.name}"

    def _persist_state(self) -> None:
        """Write current state to Django cache for cross-process visibility."""
        payload = {
            "state": self._state,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "half_open_success_count": self._half_open_success_count,
            "last_failure_time": (
                self._last_failure_time.isoformat() if self._last_failure_time else None
            ),
            "last_success_time": (
                self._last_success_time.isoformat() if self._last_success_time else None
            ),
            "last_state_change_time": (
                self._last_state_change_time.isoformat()
                if self._last_state_change_time
                else None
            ),
            "opened_at": (
                self._opened_at.isoformat() if self._opened_at else None
            ),
            "total_calls": self._total_calls,
            "rejected_calls": self._rejected_calls,
        }
        try:
            cache.set(self._cache_key, payload, timeout=None)
        except Exception:
            # Cache unavailability must never crash the circuit breaker
            logger.warning(
                "CircuitBreaker '%s': failed to persist state to cache",
                self.name,
                exc_info=True,
            )

    def _restore_state(self) -> None:
        """Restore state from Django cache (best-effort)."""
        try:
            payload = cache.get(self._cache_key)
            if payload is None:
                return
            self._state = payload.get("state", self.CLOSED)
            self._failure_count = payload.get("failure_count", 0)
            self._success_count = payload.get("success_count", 0)
            self._half_open_success_count = payload.get(
                "half_open_success_count", 0
            )
            self._last_failure_time = self._parse_iso(
                payload.get("last_failure_time")
            )
            self._last_success_time = self._parse_iso(
                payload.get("last_success_time")
            )
            self._last_state_change_time = self._parse_iso(
                payload.get("last_state_change_time")
            )
            self._opened_at = self._parse_iso(payload.get("opened_at"))
            self._total_calls = payload.get("total_calls", 0)
            self._rejected_calls = payload.get("rejected_calls", 0)
        except Exception:
            logger.warning(
                "CircuitBreaker '%s': failed to restore state from cache",
                self.name,
                exc_info=True,
            )

    @staticmethod
    def _parse_iso(value: Optional[str]) -> Optional[datetime]:
        """Parse an ISO-8601 string to a timezone-aware datetime."""
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Core public API
    # ------------------------------------------------------------------

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute *func* through the circuit breaker.

        If the circuit is OPEN the call is rejected immediately (raising
        :class:`CircuitBreakerOpenError`).  If the circuit is HALF_OPEN
        the call is allowed as a probe.  If the circuit is CLOSED the
        call is allowed normally.

        Args:
            func: The callable to execute.
            *args: Positional arguments forwarded to *func*.
            **kwargs: Keyword arguments forwarded to *func*.

        Returns:
            The return value of *func*.

        Raises:
            CircuitBreakerOpenError: If the circuit is OPEN.
            Any exception raised by *func* (recorded as a failure).
        """
        with self._lock:
            self._total_calls += 1

            current_state = self._compute_state()

            if current_state == self.OPEN:
                self._rejected_calls += 1
                self._persist_state()
                raise CircuitBreakerOpenError(
                    self.name,
                    state=self.OPEN,
                    last_failure_time=self._last_failure_time,
                )

        # Execute outside the lock so that slow calls don't block others
        try:
            result = func(*args, **kwargs)
        except BaseException as exc:
            if isinstance(exc, self.expected_exceptions):
                self.record_failure()
            raise
        else:
            self.record_success()
            return result

    def record_success(self) -> None:
        """Record a successful call and potentially close the circuit.

        In CLOSED state this simply increments the success counter.
        In HALF_OPEN state this increments the half-open success counter
        and transitions to CLOSED if the threshold is met.
        """
        with self._lock:
            self._success_count += 1
            self._last_success_time = datetime.now(timezone.utc)

            if self._state == self.HALF_OPEN:
                self._half_open_success_count += 1
                if self._half_open_success_count >= self.half_open_max_calls:
                    self._transition_to(self.CLOSED, reason="half_open_success_threshold_met")

            self._persist_state()

    def record_failure(self) -> None:
        """Record a failed call and potentially open the circuit.

        In CLOSED state consecutive failures are counted; once the
        threshold is reached the circuit opens.
        In HALF_OPEN state any single failure re-opens the circuit.
        """
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now(timezone.utc)

            if self._state == self.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    self._transition_to(
                        self.OPEN,
                        reason=f"failure_threshold_reached({self._failure_count}/{self.failure_threshold})",
                    )
            elif self._state == self.HALF_OPEN:
                self._transition_to(self.OPEN, reason="half_open_probe_failed")

            self._persist_state()

    # ------------------------------------------------------------------
    # State property
    # ------------------------------------------------------------------

    @property
    def state(self) -> str:
        """Get current circuit breaker state (may trigger HALF_OPEN transition)."""
        with self._lock:
            return self._compute_state()

    @property
    def is_open(self) -> bool:
        """Check if the circuit is open (calls should be rejected)."""
        return self.state == self.OPEN

    def _compute_state(self) -> str:
        """Compute the effective state, transitioning to HALF_OPEN if the
        recovery timeout has elapsed while OPEN.

        Must be called while holding ``self._lock``.
        """
        if self._state == self.OPEN and self._opened_at is not None:
            elapsed = (datetime.now(timezone.utc) - self._opened_at).total_seconds()
            if elapsed >= self.recovery_timeout:
                self._transition_to(
                    self.HALF_OPEN,
                    reason=f"recovery_timeout_elapsed({elapsed:.1f}s>={self.recovery_timeout}s)",
                )
        return self._state

    # ------------------------------------------------------------------
    # Manual controls
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        with self._lock:
            self._transition_to(self.CLOSED, reason="manual_reset")
            self._failure_count = 0
            self._half_open_success_count = 0
            self._persist_state()

    def force_open(self) -> None:
        """Manually force the circuit breaker to OPEN state."""
        with self._lock:
            self._transition_to(self.OPEN, reason="manual_force_open")
            self._persist_state()

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> CircuitBreakerStats:
        """Get a snapshot of circuit breaker statistics.

        Returns:
            A :class:`CircuitBreakerStats` dataclass with current metrics.
        """
        with self._lock:
            current_state = self._compute_state()
            open_duration = 0.0
            if current_state == self.OPEN and self._opened_at is not None:
                open_duration = (
                    datetime.now(timezone.utc) - self._opened_at
                ).total_seconds()

            return CircuitBreakerStats(
                name=self.name,
                state=current_state,
                failure_count=self._failure_count,
                success_count=self._success_count,
                last_failure_time=self._last_failure_time,
                last_success_time=self._last_success_time,
                last_state_change_time=self._last_state_change_time,
                total_calls=self._total_calls,
                rejected_calls=self._rejected_calls,
                open_duration_seconds=open_duration,
            )

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_state_change(self, callback: StateChangeCallback) -> None:
        """Register a callback to be invoked on state transitions.

        Args:
            callback: A callable that accepts a :class:`StateTransitionEvent`.
        """
        with self._lock:
            self._on_state_change.append(callback)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _transition_to(self, new_state: str, reason: str = "") -> None:
        """Transition to *new_state* and emit event callbacks.

        Must be called while holding ``self._lock``.
        """
        old_state = self._state
        if old_state == new_state:
            return

        self._state = new_state
        self._last_state_change_time = datetime.now(timezone.utc)

        if new_state == self.OPEN:
            self._opened_at = datetime.now(timezone.utc)
            self._half_open_success_count = 0
        elif new_state == self.CLOSED:
            self._failure_count = 0
            self._half_open_success_count = 0
            self._opened_at = None
        elif new_state == self.HALF_OPEN:
            self._half_open_success_count = 0

        event = StateTransitionEvent(
            breaker_name=self.name,
            old_state=old_state,
            new_state=new_state,
            timestamp=self._last_state_change_time,
            reason=reason,
        )

        logger.info(
            "CircuitBreaker '%s': %s -> %s (reason: %s)",
            self.name,
            old_state,
            new_state,
            reason,
        )

        # Fire callbacks outside the lock to prevent deadlocks
        self._fire_callbacks(event)

    def _fire_callbacks(self, event: StateTransitionEvent) -> None:
        """Invoke registered state-change callbacks (best-effort)."""
        for callback in self._on_state_change:
            try:
                callback(event)
            except Exception:
                logger.exception(
                    "CircuitBreaker '%s': state-change callback raised an exception",
                    self.name,
                )

    def __repr__(self) -> str:
        return (
            f"<CircuitBreaker name={self.name!r} state={self.state} "
            f"failures={self._failure_count}/{self.failure_threshold}>"
        )


# ---------------------------------------------------------------------------
# Circuit Breaker Registry
# ---------------------------------------------------------------------------


class CircuitBreakerRegistry:
    """Central registry for all circuit breaker instances.

    Provides a single point of access for creating, retrieving, and
    monitoring circuit breakers across the application.  Instances are
    keyed by ``(service_type, provider_name)`` tuples.

    Example::

        registry = CircuitBreakerRegistry()
        cb = registry.get_or_create('payment', 'paystack', failure_threshold=3)
        stats = registry.get_all_stats()
    """

    _global_instance: Optional["CircuitBreakerRegistry"] = None
    _global_lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._breakers: dict[str, CircuitBreaker] = {}

    @classmethod
    def get_global(cls) -> "CircuitBreakerRegistry":
        """Return the process-wide singleton registry."""
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
    # Public API
    # ------------------------------------------------------------------

    def get_or_create(
        self,
        service_type: str,
        provider_name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60,
        half_open_max_calls: int = 3,
        expected_exceptions: Optional[tuple[type[Exception], ...]] = None,
    ) -> CircuitBreaker:
        """Get an existing circuit breaker or create a new one.

        If a breaker with the given key already exists it is returned
        unchanged (the extra parameters are ignored).

        Args:
            service_type: Service category (e.g. ``'payment'``).
            provider_name: Provider name (e.g. ``'paystack'``).
            failure_threshold: Consecutive failures to open the circuit.
            recovery_timeout: Seconds before OPEN -> HALF_OPEN.
            half_open_max_calls: Successful probes to close the circuit.
            expected_exceptions: Exception types that count as failures.

        Returns:
            The :class:`CircuitBreaker` instance.
        """
        key = self._make_key(service_type, provider_name)
        with self._lock:
            if key not in self._breakers:
                cb = CircuitBreaker(
                    name=key,
                    failure_threshold=failure_threshold,
                    recovery_timeout=recovery_timeout,
                    half_open_max_calls=half_open_max_calls,
                    expected_exceptions=expected_exceptions,
                )
                self._breakers[key] = cb
            return self._breakers[key]

    def get(self, service_type: str, provider_name: str) -> Optional[CircuitBreaker]:
        """Retrieve an existing circuit breaker or ``None``."""
        key = self._make_key(service_type, provider_name)
        with self._lock:
            return self._breakers.get(key)

    def get_all(self) -> dict[str, CircuitBreaker]:
        """Return a shallow copy of all registered circuit breakers."""
        with self._lock:
            return dict(self._breakers)

    def get_all_stats(self) -> dict[str, CircuitBreakerStats]:
        """Return stats for all registered circuit breakers."""
        with self._lock:
            return {key: cb.get_stats() for key, cb in self._breakers.items()}

    def reset_all(self) -> None:
        """Reset every registered circuit breaker to CLOSED."""
        with self._lock:
            for cb in self._breakers.values():
                cb.reset()

    def remove(self, service_type: str, provider_name: str) -> bool:
        """Remove a circuit breaker from the registry.

        Returns:
            ``True`` if the breaker existed and was removed.
        """
        key = self._make_key(service_type, provider_name)
        with self._lock:
            return self._breakers.pop(key, None) is not None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(service_type: str, provider_name: str) -> str:
        return f"{service_type}:{provider_name}"


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def circuit_breaker(
    name: Optional[str] = None,
    service_type: Optional[str] = None,
    provider_name: Optional[str] = None,
    failure_threshold: int = 5,
    recovery_timeout: float = 60,
    half_open_max_calls: int = 3,
    expected_exceptions: Optional[tuple[type[Exception], ...]] = None,
):
    """Decorator that wraps a function call in a circuit breaker.

    The breaker name can be supplied directly or derived from
    ``service_type`` and ``provider_name``.  If neither is given the
    function's fully-qualified name is used.

    Args:
        name: Explicit circuit breaker name (takes priority).
        service_type: Service category for registry-based naming.
        provider_name: Provider name for registry-based naming.
        failure_threshold: Consecutive failures to open the circuit.
        recovery_timeout: Seconds before OPEN -> HALF_OPEN.
        half_open_max_calls: Successful probes to close the circuit.
        expected_exceptions: Exception types that count as failures.

    Example::

        @circuit_breaker(service_type='payment', provider_name='mpesa')
        def initiate_stk_push(phone, amount):
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        breaker_name = name
        if breaker_name is None:
            if service_type and provider_name:
                breaker_name = CircuitBreakerRegistry._make_key(
                    service_type, provider_name
                )
            else:
                breaker_name = f"{func.__module__}.{func.__qualname__}"

        cb = CircuitBreaker(
            name=breaker_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_max_calls=half_open_max_calls,
            expected_exceptions=expected_exceptions,
        )

        # Also register in the global registry for observability
        registry = CircuitBreakerRegistry.get_global()
        with registry._lock:
            registry._breakers[breaker_name] = cb

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return cb.call(func, *args, **kwargs)

        # Attach breaker reference for introspection
        wrapper.circuit_breaker = cb  # type: ignore[attr-defined]
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerRegistry",
    "CircuitBreakerOpenError",
    "CircuitBreakerStats",
    "CircuitState",
    "StateTransitionEvent",
    "circuit_breaker",
]
