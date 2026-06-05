"""
Fraud detection provider adapter for the External Services Layer.

Implements the :class:`~external_services.base.FraudDetectionProvider`
interface for:

* **InternalFraudAdapter** — Wraps the existing
  ``core.services.fraud_detection.FraudDetectionService`` so that it
  can be used through the ESL like any other provider.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from django.conf import settings

from external_services.base import (
    FraudDetectionProvider,
    HealthCheckResult,
    ProviderResponse,
    ValidationResult,
)
from external_services.exceptions import ProviderResponseError

logger = logging.getLogger(__name__)


class InternalFraudAdapter(FraudDetectionProvider):
    """Internal fraud detection adapter wrapping the core service.

    Delegates to :class:`core.services.fraud_detection.FraudDetectionService`
    for risk evaluation and scoring.  This adapter does **not** make
    external API calls — all computation is local to the Django process.

    The adapter exists so that the fraud-detection subsystem is
    accessible through the same ESL interface used for third-party
    providers, making it swappable with Sift, Signifyd, etc. without
    any changes to calling code.
    """

    PROVIDER_NAME = "internal"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(provider_name=self.PROVIDER_NAME, service_type="fraud_detection", **kwargs)
        self._fraud_service = None

    def _get_service(self):
        """Lazy-import the fraud detection service."""
        if self._fraud_service is None:
            from core.services.fraud_detection import FraudDetectionService
            self._fraud_service = FraudDetectionService
        return self._fraud_service

    # -- lifecycle --------------------------------------------------------

    def connect(self) -> bool:
        """No external connection needed; always succeeds."""
        self._get_service()
        self.is_connected = True
        return True

    def disconnect(self) -> bool:
        self._fraud_service = None
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        """Internal service is always healthy if the module imports."""
        try:
            self._get_service()
            return HealthCheckResult(status="healthy", provider=self.PROVIDER_NAME, response_time_ms=0.0)
        except Exception as exc:
            return HealthCheckResult(status="unhealthy", provider=self.PROVIDER_NAME, details={"error": str(exc)})

    def validate_configuration(self) -> ValidationResult:
        """Internal service has no configuration requirements."""
        try:
            self._get_service()
            return ValidationResult(is_valid=True)
        except Exception as exc:
            return ValidationResult(is_valid=False, errors=[str(exc)])

    # -- fraud detection operations ---------------------------------------

    def evaluate_risk(self, event: str, user_id: str, **kwargs: Any) -> ProviderResponse:
        """Evaluate the risk level of a transaction or user action.

        Maps to ``FraudDetectionService.calculate_user_fraud_score`` for
        payment events, or performs targeted checks for other events.

        Args:
            event: Event type (e.g. ``"payment"``, ``"login"``).
            user_id: Internal user identifier.
            **kwargs: ``amount``, ``ip_address``, ``device_fingerprint``, etc.
        """
        start = time.monotonic()
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            service = self._get_service()

            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return ProviderResponse(
                    success=False,
                    error=f"User {user_id} not found",
                    provider=self.PROVIDER_NAME,
                    latency_ms=(time.monotonic() - start) * 1000,
                )

            # Calculate comprehensive fraud score
            fraud_score = service.calculate_user_fraud_score(user)

            # Determine recommendation based on score
            score_value = fraud_score.score
            if score_value >= 75:
                recommendation = "block"
            elif score_value >= 50:
                recommendation = "manual_review"
            elif score_value >= 25:
                recommendation = "flag"
            else:
                recommendation = "allow"

            # Additional event-specific checks
            risk_factors = list(fraud_score.risk_factors) if fraud_score.risk_factors else []
            if event == "payment" and kwargs.get("amount"):
                amount = float(kwargs["amount"])
                if amount > 500000:  # > 500K KES
                    risk_factors.append(f"High-value transaction: KES {amount:,.0f}")
                    score_value = min(score_value + 10, 100)

            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(
                success=True,
                data={
                    "risk_score": score_value,
                    "recommendation": recommendation,
                    "risk_factors": risk_factors,
                    "event": event,
                    "user_id": user_id,
                },
                provider=self.PROVIDER_NAME,
                latency_ms=elapsed,
            )
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def get_risk_score(self, user_id: str) -> ProviderResponse:
        """Retrieve the current aggregate risk score for a user.

        Args:
            user_id: Internal user identifier.
        """
        start = time.monotonic()
        try:
            from django.contrib.auth import get_user_model
            from core.models import FraudScore
            User = get_user_model()

            try:
                fraud_score = FraudScore.objects.select_related("user").get(user_id=user_id)
                elapsed = (time.monotonic() - start) * 1000
                return ProviderResponse(
                    success=True,
                    data={
                        "risk_score": fraud_score.score,
                        "risk_factors": list(fraud_score.risk_factors) if fraud_score.risk_factors else [],
                        "flagged_for_review": fraud_score.flagged_for_review,
                        "last_calculated": fraud_score.last_calculated.isoformat() if fraud_score.last_calculated else None,
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            except FraudScore.DoesNotExist:
                elapsed = (time.monotonic() - start) * 1000
                return ProviderResponse(
                    success=True,
                    data={"risk_score": 0, "risk_factors": [], "flagged_for_review": False, "note": "No fraud score calculated yet"},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def flag_event(self, event_id: str, reason: str) -> ProviderResponse:
        """Manually flag an event for fraud review.

        Uses ``FraudDetectionService.flag_for_manual_review`` to flag
        the associated user.

        Args:
            event_id: Identifier of the event (typically a user ID or
                transaction reference).
            reason: Human-readable explanation for the flag.
        """
        start = time.monotonic()
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            service = self._get_service()

            try:
                user = User.objects.get(pk=event_id)
                service.flag_for_manual_review(user, reason)
                elapsed = (time.monotonic() - start) * 1000
                return ProviderResponse(
                    success=True,
                    data={"event_id": event_id, "flagged": True, "reason": reason},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            except User.DoesNotExist:
                # If event_id is not a user PK, log the flag anyway
                logger.warning("Flag event for non-user ID %s: %s", event_id, reason)
                elapsed = (time.monotonic() - start) * 1000
                return ProviderResponse(
                    success=True,
                    data={"event_id": event_id, "flagged": True, "reason": reason, "note": "Logged but not linked to a user record"},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc
