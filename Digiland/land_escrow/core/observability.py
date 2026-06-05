"""
Observability integration for error tracking.

Metrics:
- Error rates by category, code, endpoint
- Retry rates
- Fallback usage
- Recovery success rates
- Failure hotspots
- Mean time to recovery

Integrations:
- OpenTelemetry traces + metrics
- Prometheus counters + histograms
- Sentry error capture
- Structured logging with correlation IDs

All observability data uses INTERNAL error codes and details.
User-facing data is NEVER included in observability metrics.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class ErrorObservability:
    """Track and report error metrics.

    Usage::

        observability = ErrorObservability()

        # Track an error
        observability.track_error(
            error_code="PAYMENT_PROVIDER_UNAVAILABLE",
            request_id="abc-123",
            user_id="user-456",
            metadata={"provider": "stripe"},
        )

        # Track a retry
        observability.track_retry("PAYMENT_PROVIDER_UNAVAILABLE", 2, "abc-123")

        # Track a fallback activation
        observability.track_fallback("SEARCH_UNAVAILABLE", "cached_response", "abc-123")

        # Track a recovery
        observability.track_recovery(
            "PAYMENT_PROVIDER_UNAVAILABLE", "retry", "abc-123", 5000
        )

        # Get hotspots
        hotspots = observability.get_error_hotspots(time_window_minutes=60)

        # Get error rate
        rate = observability.get_error_rate(time_window_minutes=60)
    """

    # Redis key prefixes
    ERROR_COUNT_PREFIX = "digiland:obs:error_count:"
    RETRY_COUNT_PREFIX = "digiland:obs:retry_count:"
    FALLBACK_COUNT_PREFIX = "digiland:obs:fallback_count:"
    RECOVERY_COUNT_PREFIX = "digiland:obs:recovery_count:"
    RECOVERY_TIME_PREFIX = "digiland:obs:recovery_time:"
    ERROR_TIMELINE_PREFIX = "digiland:obs:timeline:"
    ERROR_BY_ENDPOINT_PREFIX = "digiland:obs:endpoint_errors:"

    # Default TTL for metrics
    METRICS_TTL = 86400  # 24 hours

    def track_error(
        self,
        error_code: str,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track an error occurrence.

        Args:
            error_code: Error code from the taxonomy.
            request_id: Request/correlation ID.
            user_id: User ID, if available.
            metadata: Additional context.
        """
        now = datetime.now(timezone.utc)
        minute_key = now.strftime("%Y%m%d%H%M")

        # Increment total error count
        self._increment(f"{self.ERROR_COUNT_PREFIX}total", minute_key)

        # Increment error count by code
        self._increment(f"{self.ERROR_COUNT_PREFIX}code:{error_code}", minute_key)

        # Increment error count by category
        from .error_taxonomy import get_error_definition
        definition = get_error_definition(error_code)
        if definition:
            category = (
                definition.category.value
                if hasattr(definition.category, "value")
                else str(definition.category)
            )
            self._increment(f"{self.ERROR_COUNT_PREFIX}category:{category}", minute_key)

        # Track in timeline for hotspot detection
        self._add_to_timeline(error_code, now)

        # Log with structured context
        log_data = {
            "error_code": error_code,
            "request_id": request_id,
            "user_id": user_id,
            "timestamp": now.isoformat(),
        }
        if metadata:
            log_data["metadata"] = metadata

        logger.info(
            "Error tracked: code=%s request=%s",
            error_code,
            request_id,
            extra=log_data,
        )

        # Send to OpenTelemetry if available
        self._otel_track_error(error_code, metadata)

        # Send to Prometheus if available
        self._prometheus_track_error(error_code)

        # Send to Sentry if available
        self._sentry_track_error(error_code, request_id, metadata)

    def track_retry(
        self,
        error_code: str,
        attempt: int,
        request_id: Optional[str] = None,
    ) -> None:
        """Track a retry attempt.

        Args:
            error_code: The error code being retried.
            attempt: The attempt number (1-based).
            request_id: Request/correlation ID.
        """
        now = datetime.now(timezone.utc)
        minute_key = now.strftime("%Y%m%d%H%M")

        self._increment(f"{self.RETRY_COUNT_PREFIX}total", minute_key)
        self._increment(f"{self.RETRY_COUNT_PREFIX}code:{error_code}", minute_key)

        logger.info(
            "Retry tracked: code=%s attempt=%d request=%s",
            error_code,
            attempt,
            request_id,
            extra={
                "error_code": error_code,
                "attempt": attempt,
                "request_id": request_id,
            },
        )

        self._otel_track_retry(error_code, attempt)
        self._prometheus_track_retry(error_code, attempt)

    def track_fallback(
        self,
        error_code: str,
        fallback_type: str,
        request_id: Optional[str] = None,
    ) -> None:
        """Track a fallback activation.

        Args:
            error_code: The error code that triggered the fallback.
            fallback_type: Type of fallback (cached_response, default_value, etc.).
            request_id: Request/correlation ID.
        """
        now = datetime.now(timezone.utc)
        minute_key = now.strftime("%Y%m%d%H%M")

        self._increment(f"{self.FALLBACK_COUNT_PREFIX}total", minute_key)
        self._increment(
            f"{self.FALLBACK_COUNT_PREFIX}type:{fallback_type}", minute_key
        )

        logger.info(
            "Fallback tracked: code=%s type=%s request=%s",
            error_code,
            fallback_type,
            request_id,
            extra={
                "error_code": error_code,
                "fallback_type": fallback_type,
                "request_id": request_id,
            },
        )

        self._otel_track_fallback(error_code, fallback_type)
        self._prometheus_track_fallback(error_code, fallback_type)

    def track_recovery(
        self,
        error_code: str,
        recovery_method: str,
        request_id: Optional[str] = None,
        time_to_recovery_ms: Optional[float] = None,
    ) -> None:
        """Track a successful recovery.

        Args:
            error_code: The error code that was recovered.
            recovery_method: How the recovery happened (retry, fallback, manual).
            request_id: Request/correlation ID.
            time_to_recovery_ms: Time from error to recovery in milliseconds.
        """
        now = datetime.now(timezone.utc)
        minute_key = now.strftime("%Y%m%d%H%M")

        self._increment(f"{self.RECOVERY_COUNT_PREFIX}total", minute_key)
        self._increment(
            f"{self.RECOVERY_COUNT_PREFIX}method:{recovery_method}", minute_key
        )

        # Track recovery time
        if time_to_recovery_ms is not None:
            self._record_recovery_time(error_code, time_to_recovery_ms)

        logger.info(
            "Recovery tracked: code=%s method=%s time=%sms request=%s",
            error_code,
            recovery_method,
            time_to_recovery_ms,
            request_id,
            extra={
                "error_code": error_code,
                "recovery_method": recovery_method,
                "time_to_recovery_ms": time_to_recovery_ms,
                "request_id": request_id,
            },
        )

        self._otel_track_recovery(error_code, recovery_method, time_to_recovery_ms)
        self._prometheus_track_recovery(error_code, recovery_method, time_to_recovery_ms)

    def get_error_hotspots(
        self, time_window_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """Get the most frequent errors in the time window.

        Args:
            time_window_minutes: Look-back window in minutes.

        Returns:
            List of dicts with error_code and count, sorted by frequency.
        """
        now = datetime.now(timezone.utc)
        hotspots: Dict[str, int] = {}

        # Aggregate error counts across the time window
        for minute_offset in range(time_window_minutes):
            from datetime import timedelta
            minute_time = now - timedelta(minutes=minute_offset)
            minute_key = minute_time.strftime("%Y%m%d%H%M")

            # Get all error codes for this minute
            try:
                timeline_key = f"{self.ERROR_TIMELINE_PREFIX}{minute_key}"
                data = cache.get(timeline_key, "{}")
                if isinstance(data, str):
                    minute_errors = json.loads(data)
                else:
                    minute_errors = data or {}

                for code, count in minute_errors.items():
                    hotspots[code] = hotspots.get(code, 0) + count
            except Exception:
                continue

        # Sort by frequency
        sorted_hotspots = sorted(
            hotspots.items(), key=lambda x: x[1], reverse=True
        )

        return [
            {"error_code": code, "count": count}
            for code, count in sorted_hotspots[:20]
        ]

    def get_error_rate(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """Get the overall error rate.

        Args:
            time_window_minutes: Look-back window in minutes.

        Returns:
            Dict with error rate information.
        """
        now = datetime.now(timezone.utc)
        total_errors = 0

        from datetime import timedelta
        for minute_offset in range(time_window_minutes):
            minute_time = now - timedelta(minutes=minute_offset)
            minute_key = minute_time.strftime("%Y%m%d%H%M")
            try:
                key = f"{self.ERROR_COUNT_PREFIX}total:{minute_key}"
                count = cache.get(key, 0)
                total_errors += count
            except Exception:
                continue

        # Calculate rate (errors per minute)
        error_rate_per_minute = total_errors / max(time_window_minutes, 1)

        return {
            "total_errors": total_errors,
            "time_window_minutes": time_window_minutes,
            "error_rate_per_minute": round(error_rate_per_minute, 2),
            "hotspots": self.get_error_hotspots(time_window_minutes)[:5],
        }

    # ------------------------------------------------------------------
    # Internal: Counter helpers
    # ------------------------------------------------------------------

    def _increment(self, prefix: str, minute_key: str, amount: int = 1) -> None:
        """Increment a counter in cache."""
        try:
            key = f"{prefix}:{minute_key}"
            current = cache.get(key, 0)
            cache.set(key, current + amount, timeout=self.METRICS_TTL)
        except Exception:
            pass

    def _add_to_timeline(self, error_code: str, timestamp: datetime) -> None:
        """Add an error to the timeline for hotspot detection."""
        try:
            minute_key = timestamp.strftime("%Y%m%d%H%M")
            timeline_key = f"{self.ERROR_TIMELINE_PREFIX}{minute_key}"
            data = cache.get(timeline_key, "{}")
            if isinstance(data, str):
                timeline = json.loads(data)
            else:
                timeline = data or {}

            timeline[error_code] = timeline.get(error_code, 0) + 1
            cache.set(timeline_key, json.dumps(timeline), timeout=self.METRICS_TTL)
        except Exception:
            pass

    def _record_recovery_time(
        self, error_code: str, time_ms: float
    ) -> None:
        """Record a recovery time measurement."""
        try:
            key = f"{self.RECOVERY_TIME_PREFIX}{error_code}"
            data = cache.get(key, "[]")
            if isinstance(data, str):
                times = json.loads(data)
            else:
                times = data or []

            times.append(time_ms)
            # Keep last 100 measurements
            if len(times) > 100:
                times = times[-100:]

            cache.set(key, json.dumps(times), timeout=self.METRICS_TTL)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Integration: OpenTelemetry
    # ------------------------------------------------------------------

    def _otel_track_error(
        self, error_code: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send error to OpenTelemetry."""
        try:
            from opentelemetry import metrics
            meter = metrics.get_meter("digiland.errors")
            counter = meter.create_counter(
                "digiland.error.total",
                description="Total errors by code",
            )
            counter.add(1, {"error_code": error_code})
        except ImportError:
            pass
        except Exception:
            pass

    def _otel_track_retry(self, error_code: str, attempt: int) -> None:
        """Send retry to OpenTelemetry."""
        try:
            from opentelemetry import metrics
            meter = metrics.get_meter("digiland.errors")
            counter = meter.create_counter(
                "digiland.retry.total",
                description="Total retries by error code",
            )
            counter.add(1, {"error_code": error_code, "attempt": str(attempt)})
        except ImportError:
            pass
        except Exception:
            pass

    def _otel_track_fallback(self, error_code: str, fallback_type: str) -> None:
        """Send fallback to OpenTelemetry."""
        try:
            from opentelemetry import metrics
            meter = metrics.get_meter("digiland.errors")
            counter = meter.create_counter(
                "digiland.fallback.total",
                description="Total fallbacks by type",
            )
            counter.add(1, {"error_code": error_code, "fallback_type": fallback_type})
        except ImportError:
            pass
        except Exception:
            pass

    def _otel_track_recovery(
        self,
        error_code: str,
        recovery_method: str,
        time_to_recovery_ms: Optional[float],
    ) -> None:
        """Send recovery to OpenTelemetry."""
        try:
            from opentelemetry import metrics
            meter = metrics.get_meter("digiland.errors")
            counter = meter.create_counter(
                "digiland.recovery.total",
                description="Total recoveries by method",
            )
            counter.add(1, {"error_code": error_code, "recovery_method": recovery_method})

            if time_to_recovery_ms is not None:
                histogram = meter.create_histogram(
                    "digiland.recovery.time_ms",
                    description="Time to recovery in milliseconds",
                )
                histogram.record(
                    time_to_recovery_ms,
                    {"error_code": error_code, "recovery_method": recovery_method},
                )
        except ImportError:
            pass
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Integration: Prometheus
    # ------------------------------------------------------------------

    def _prometheus_track_error(self, error_code: str) -> None:
        """Increment Prometheus error counter."""
        try:
            from prometheus_client import Counter
            c = Counter(
                "digiland_error_total",
                "Total errors by code",
                ["error_code"],
            )
            c.labels(error_code=error_code).inc()
        except ImportError:
            pass
        except Exception:
            pass

    def _prometheus_track_retry(self, error_code: str, attempt: int) -> None:
        """Increment Prometheus retry counter."""
        try:
            from prometheus_client import Counter
            c = Counter(
                "digiland_retry_total",
                "Total retries",
                ["error_code"],
            )
            c.labels(error_code=error_code).inc()
        except ImportError:
            pass
        except Exception:
            pass

    def _prometheus_track_fallback(
        self, error_code: str, fallback_type: str
    ) -> None:
        """Increment Prometheus fallback counter."""
        try:
            from prometheus_client import Counter
            c = Counter(
                "digiland_fallback_total",
                "Total fallbacks by type",
                ["error_code", "fallback_type"],
            )
            c.labels(error_code=error_code, fallback_type=fallback_type).inc()
        except ImportError:
            pass
        except Exception:
            pass

    def _prometheus_track_recovery(
        self,
        error_code: str,
        recovery_method: str,
        time_to_recovery_ms: Optional[float],
    ) -> None:
        """Increment Prometheus recovery counter."""
        try:
            from prometheus_client import Counter, Histogram
            c = Counter(
                "digiland_recovery_total",
                "Total recoveries",
                ["error_code", "recovery_method"],
            )
            c.labels(
                error_code=error_code, recovery_method=recovery_method
            ).inc()

            if time_to_recovery_ms is not None:
                h = Histogram(
                    "digiland_recovery_time_ms",
                    "Time to recovery in ms",
                    ["error_code"],
                )
                h.labels(error_code=error_code).observe(time_to_recovery_ms)
        except ImportError:
            pass
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Integration: Sentry
    # ------------------------------------------------------------------

    def _sentry_track_error(
        self,
        error_code: str,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send error context to Sentry."""
        try:
            import sentry_sdk
            sentry_sdk.set_tag("error_code", error_code)
            if request_id:
                sentry_sdk.set_tag("request_id", request_id)
            if metadata:
                sentry_sdk.set_context("error_metadata", metadata)
            sentry_sdk.capture_message(
                f"Error tracked: {error_code}",
                level="warning",
            )
        except ImportError:
            pass
        except Exception:
            pass
