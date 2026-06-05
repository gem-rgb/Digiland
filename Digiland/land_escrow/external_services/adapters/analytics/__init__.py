"""
Analytics provider adapter for the External Services Layer.

Implements the :class:`~external_services.base.AnalyticsProvider` interface
for:

* **PostHogAdapter** — PostHog product analytics via the ``posthog``
  Python SDK and REST API.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import requests
from django.conf import settings

from external_services.base import (
    AnalyticsProvider,
    HealthCheckResult,
    ProviderResponse,
    ValidationResult,
)
from external_services.exceptions import (
    AuthenticationError,
    ProviderResponseError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)


class PostHogAdapter(AnalyticsProvider):
    """PostHog analytics adapter.

    Uses the ``posthog`` Python SDK for event capture and the REST API
    for metrics retrieval.

    Configuration (via Django settings):
        ``POSTHOG_API_KEY``     — Project API key for event capture.
        ``POSTHOG_HOST``        — PostHog instance URL (default ``"https://us.i.posthog.com"``).
        ``POSTHOG_PERSONAL_API_KEY`` — Personal API key for metrics queries.
    """

    PROVIDER_NAME = "posthog"
    _DEFAULT_HOST = "https://us.i.posthog.com"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(provider_name=self.PROVIDER_NAME, service_type="analytics", **kwargs)
        self._api_key: str = getattr(settings, "POSTHOG_API_KEY", "")
        self._host: str = getattr(settings, "POSTHOG_HOST", self._DEFAULT_HOST)
        self._personal_api_key: str = getattr(settings, "POSTHOG_PERSONAL_API_KEY", "")
        self._posthog = None

    def _get_sdk(self):
        """Lazy-initialise the PostHog SDK client."""
        if self._posthog is None:
            try:
                import posthog
                posthog.api_key = self._api_key
                posthog.host = self._host
                self._posthog = posthog
            except ImportError as exc:
                raise ProviderUnavailableError(
                    provider_name=self.PROVIDER_NAME,
                    message="posthog package is not installed",
                ) from exc
        return self._posthog

    # -- lifecycle --------------------------------------------------------

    def connect(self) -> bool:
        try:
            self._get_sdk()
            self.is_connected = True
            return True
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME) from exc

    def disconnect(self) -> bool:
        try:
            if self._posthog:
                self._posthog.shutdown()
        except Exception:
            pass
        self._posthog = None
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            if self._personal_api_key:
                resp = requests.get(
                    f"{self._host}/api/users/@me/",
                    headers={"Authorization": f"Bearer {self._personal_api_key}"},
                    timeout=5,
                )
                elapsed = (time.monotonic() - start) * 1000
                return HealthCheckResult(
                    status="healthy" if resp.status_code == 200 else "degraded",
                    provider=self.PROVIDER_NAME,
                    response_time_ms=elapsed,
                )
            # Without personal API key, just confirm SDK is initialised
            return HealthCheckResult(status="healthy", provider=self.PROVIDER_NAME, details={"note": "SDK initialised; no personal API key for deep health check"})
        except Exception:
            return HealthCheckResult(status="unhealthy", provider=self.PROVIDER_NAME)

    def validate_configuration(self) -> ValidationResult:
        errors, warnings = [], []
        if not self._api_key:
            errors.append("POSTHOG_API_KEY is not configured")
        if not self._personal_api_key:
            warnings.append("POSTHOG_PERSONAL_API_KEY not set; metrics queries will be unavailable")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    # -- analytics operations ---------------------------------------------

    def track_event(self, event_name: str, properties: Dict[str, Any], user_id: Optional[str] = None) -> ProviderResponse:
        """Record a custom analytics event via the PostHog SDK.

        Args:
            event_name: Event identifier (e.g. ``"payment_completed"``).
            properties: Event metadata.
            user_id: Optional distinct user identifier.
        """
        start = time.monotonic()
        try:
            ph = self._get_sdk()
            distinct_id = user_id or properties.get("distinct_id", "anonymous")
            ph.capture(distinct_id=distinct_id, event=event_name, properties=properties)
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=True, data={"event": event_name, "distinct_id": distinct_id}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            return ProviderResponse(success=False, error=str(exc), provider=self.PROVIDER_NAME)

    def track_page_view(self, url: str, user_id: Optional[str] = None) -> ProviderResponse:
        """Record a page view event.

        PostHog treats page views as standard ``$pageview`` events.
        """
        start = time.monotonic()
        try:
            ph = self._get_sdk()
            distinct_id = user_id or "anonymous"
            ph.capture(distinct_id=distinct_id, event="$pageview", properties={"$current_url": url})
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=True, data={"event": "$pageview", "url": url}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            return ProviderResponse(success=False, error=str(exc), provider=self.PROVIDER_NAME)

    def identify_user(self, user_id: str, traits: Dict[str, Any]) -> ProviderResponse:
        """Associate traits with a user for analytics segmentation.

        Uses PostHog's ``identify`` call which merges user properties.
        """
        start = time.monotonic()
        try:
            ph = self._get_sdk()
            ph.identify(distinct_id=user_id, properties=traits)
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=True, data={"distinct_id": user_id, "traits_set": list(traits.keys())}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            return ProviderResponse(success=False, error=str(exc), provider=self.PROVIDER_NAME)

    def get_metrics(self, metric_name: str, **kwargs: Any) -> ProviderResponse:
        """Retrieve aggregated metrics from PostHog via the Insights API.

        Requires ``POSTHOG_PERSONAL_API_KEY`` to be configured.

        Args:
            metric_name: Insight type (e.g. ``"Trends"``, ``"Funnels"``).
            **kwargs: ``start_date``, ``end_date``, ``events``, ``filters``.
        """
        start = time.monotonic()
        try:
            if not self._personal_api_key:
                return ProviderResponse(success=False, error="POSTHOG_PERSONAL_API_KEY not configured; cannot query metrics", provider=self.PROVIDER_NAME)

            payload: Dict[str, Any] = {
                "insight": metric_name,
                "date_from": kwargs.get("start_date", "-7d"),
                "date_to": kwargs.get("end_date", "d"),
            }
            if kwargs.get("events"):
                payload["events"] = kwargs["events"]
            if kwargs.get("filters"):
                payload["properties"] = kwargs["filters"]

            resp = requests.post(
                f"{self._host}/api/insights/trend/",
                json=payload,
                headers={"Authorization": f"Bearer {self._personal_api_key}", "Content-Type": "application/json"},
                timeout=30,
            )
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                return ProviderResponse(success=True, data=resp.json(), provider=self.PROVIDER_NAME, latency_ms=elapsed)
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, provider_status=resp.status_code, provider_message=resp.text[:200])
        except ProviderResponseError:
            raise
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc
