"""
Observability framework for the External Services Layer.

Every external request generates:
- Trace with correlation ID
- Metrics (count, latency, success rate)
- Structured logs with correlation ID

Usage::

    from external_services.observability import observability

    # Set correlation ID from incoming request
    observability.set_correlation_id(request.headers.get('X-Correlation-ID'))

    # Trace an external service call
    with observability.trace('payment', 'paystack', 'initialize_payment') as span:
        span.add_event('request_sent', {'url': url})
        result = provider.initialize_payment(amount, currency, reference)
        span.add_event('response_received', {'status': result.status})
        return result

    # Record provider health
    observability.metrics.record_provider_health('paystack', True, 45.2)

    # Record cost
    observability.metrics.record_cost('paystack', 'payment', 'initialize', 1, 0.015, 'USD')
"""

import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

from django.conf import settings

logger = logging.getLogger('external_services.observability')


@dataclass
class TraceSpan:
    """Represents a single trace span for an external service operation.

    A span captures the lifecycle of a single operation — start time,
    end time, status, and any events or attributes recorded during
    execution.  Spans are linked by ``trace_id`` for distributed
    tracing across service boundaries.

    Attributes:
        trace_id: Correlation ID linking spans across services.
        span_id: Unique identifier for this span.
        parent_span_id: ID of the parent span (for nested calls).
        operation: Name of the operation being performed.
        service_type: Category of service (payment, messaging, etc.).
        provider_name: Name of the external provider.
        start_time: Epoch timestamp when the span started.
        end_time: Epoch timestamp when the span ended.
        status: Current status — ``started``, ``success``, or ``error``.
        error_message: Error details if the span ended in error.
        attributes: Arbitrary key-value metadata attached to the span.
        events: Chronological list of notable events within the span.
    """

    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    operation: str = ''
    service_type: str = ''
    provider_name: str = ''
    start_time: float = 0.0
    end_time: Optional[float] = None
    status: str = 'started'
    error_message: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        """Return the span duration in milliseconds.

        Returns 0.0 if the span has not yet ended.
        """
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Record a notable event within the span.

        Args:
            name: Human-readable event name (e.g. ``request_sent``).
            attributes: Optional key-value metadata for the event.
        """
        self.events.append({
            'name': name,
            'timestamp': time.time(),
            'attributes': attributes or {},
        })

    def finish(self, status: str = 'success', error_message: Optional[str] = None) -> None:
        """Mark the span as completed.

        Args:
            status: Final status — ``success`` or ``error``.
            error_message: Description of the error, if any.
        """
        self.end_time = time.time()
        self.status = status
        self.error_message = error_message


class MetricsCollector:
    """Collects and aggregates metrics for external service operations.

    Three metric types are supported:

    * **Counters** — monotonically increasing values (request count,
      error count, cost accumulation).
    * **Histograms** — distributions of values (request latency).
    * **Gauges** — point-in-time values (provider health status).

    In production, these should be exported to Prometheus or a similar
    time-series database via the :meth:`get_metrics` interface.
    """

    def __init__(self) -> None:
        self._counters: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._gauges: Dict[str, float] = {}

    def record_request(
        self,
        service_type: str,
        provider_name: str,
        operation: str,
        status: str,
        duration_ms: float,
        error_type: Optional[str] = None,
    ) -> None:
        """Record metrics for a single external service request.

        Args:
            service_type: Category of service (payment, messaging, etc.).
            provider_name: External provider name.
            operation: Operation name (e.g. ``initialize_payment``).
            status: ``success`` or ``error``.
            duration_ms: Request latency in milliseconds.
            error_type: Exception class name, if applicable.
        """
        key = f"{service_type}:{provider_name}:{operation}"

        # Total requests
        self._counters[f"requests_total:{key}"] = (
            self._counters.get(f"requests_total:{key}", 0) + 1
        )

        # Status-specific counters
        if status == 'success':
            self._counters[f"success_total:{key}"] = (
                self._counters.get(f"success_total:{key}", 0) + 1
            )
        elif status == 'error':
            self._counters[f"error_total:{key}"] = (
                self._counters.get(f"error_total:{key}", 0) + 1
            )
            if error_type:
                self._counters[f"error_{error_type}:{key}"] = (
                    self._counters.get(f"error_{error_type}:{key}", 0) + 1
                )

        # Latency histogram
        self._histograms.setdefault(f"duration_ms:{key}", []).append(duration_ms)

        # Update success rate gauge
        total = self._counters.get(f"requests_total:{key}", 0)
        successes = self._counters.get(f"success_total:{key}", 0)
        if total > 0:
            self._gauges[f"success_rate:{key}"] = successes / total

    def record_provider_health(
        self,
        provider_name: str,
        is_healthy: bool,
        response_time_ms: float,
    ) -> None:
        """Record a health check result for a provider.

        Args:
            provider_name: Provider identifier.
            is_healthy: Whether the provider passed the health check.
            response_time_ms: Health check response time in ms.
        """
        self._gauges[f"health:{provider_name}"] = 1 if is_healthy else 0
        self._gauges[f"health_response_ms:{provider_name}"] = response_time_ms

    def record_cost(
        self,
        provider_name: str,
        service_type: str,
        operation: str,
        cost: float,
        currency: str = 'USD',
    ) -> None:
        """Record the cost of an external service operation.

        Args:
            provider_name: Provider identifier.
            service_type: Category of service.
            operation: Operation name.
            cost: Monetary cost of the operation.
            currency: ISO 4217 currency code.
        """
        key = f"cost:{provider_name}:{service_type}:{operation}"
        self._counters[key] = self._counters.get(key, 0) + cost

    def get_metrics(self) -> Dict[str, Any]:
        """Return a snapshot of all collected metrics.

        Returns:
            Dictionary with ``counters``, ``histograms``, and ``gauges``.
        """
        return {
            'counters': dict(self._counters),
            'histograms': {k: list(v) for k, v in self._histograms.items()},
            'gauges': dict(self._gauges),
        }

    def get_percentile_latency(
        self,
        service_type: str,
        provider_name: str,
        operation: str,
        percentile: float = 0.95,
    ) -> Optional[float]:
        """Calculate a percentile latency for a given operation.

        Args:
            service_type: Category of service.
            provider_name: Provider identifier.
            operation: Operation name.
            percentile: Target percentile (0.0–1.0).

        Returns:
            Latency in milliseconds at the given percentile, or None
            if no data is available.
        """
        key = f"duration_ms:{service_type}:{provider_name}:{operation}"
        values = self._histograms.get(key, [])
        if not values:
            return None
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        return sorted_values[min(index, len(sorted_values) - 1)]


class ObservabilityManager:
    """Central manager for tracing and metrics across the External Services Layer.

    Provides a context-manager API for tracing operations, automatically
    recording metrics on success/failure, and propagating correlation
    IDs across thread boundaries.

    Usage::

        from external_services.observability import observability

        with observability.trace('payment', 'paystack', 'charge') as span:
            result = provider.charge(amount, currency)
            return result
    """

    def __init__(self) -> None:
        self.metrics = MetricsCollector()
        self._active_traces: Dict[str, TraceSpan] = {}
        self._correlation_ids: Dict[int, str] = {}

    @contextmanager
    def trace(
        self,
        service_type: str,
        provider_name: str,
        operation: str,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """Context manager that traces an external service operation.

        Creates a :class:`TraceSpan`, yields it to the caller, and
        automatically records success/error metrics when the block exits.

        Args:
            service_type: Category of service.
            provider_name: Provider identifier.
            operation: Operation name.
            attributes: Optional metadata to attach to the span.

        Yields:
            The active :class:`TraceSpan`.
        """
        import threading

        thread_id = threading.current_thread().ident
        trace_id = self._correlation_ids.get(thread_id, uuid.uuid4().hex)
        span_id = uuid.uuid4().hex[:16]

        span = TraceSpan(
            trace_id=trace_id,
            span_id=span_id,
            operation=operation,
            service_type=service_type,
            provider_name=provider_name,
            start_time=time.time(),
            attributes=attributes or {},
        )
        self._active_traces[span_id] = span

        logger.info(
            "[ESL] %s/%s/%s started",
            service_type,
            provider_name,
            operation,
            extra={'trace_id': trace_id, 'span_id': span_id},
        )

        try:
            yield span
            span.finish('success')
            self.metrics.record_request(
                service_type, provider_name, operation,
                'success', span.duration_ms,
            )
        except Exception as e:
            span.finish('error', str(e))
            self.metrics.record_request(
                service_type, provider_name, operation,
                'error', span.duration_ms,
                type(e).__name__,
            )
            raise
        finally:
            logger.info(
                "[ESL] %s/%s/%s %s %.1fms",
                service_type,
                provider_name,
                operation,
                span.status,
                span.duration_ms,
                extra={'trace_id': trace_id, 'span_id': span_id},
            )
            self._active_traces.pop(span_id, None)

    def set_correlation_id(self, correlation_id: str) -> None:
        """Set the correlation ID for the current thread.

        This ID is automatically attached to all subsequent trace spans
        created on the same thread, enabling distributed tracing across
        service boundaries.

        Args:
            correlation_id: The correlation ID (typically from an
                incoming request header).
        """
        import threading

        self._correlation_ids[threading.current_thread().ident] = correlation_id

    def get_active_spans(self) -> List[TraceSpan]:
        """Return a list of all currently active (in-flight) trace spans."""
        return list(self._active_traces.values())


# Module-level singleton
observability = ObservabilityManager()
