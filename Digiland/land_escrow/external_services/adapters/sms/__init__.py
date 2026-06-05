"""
SMS provider adapter for the External Services Layer.

Implements the :class:`~external_services.base.SmsProvider` interface
for:

* **AfricasTalkingAdapter** — Africa's Talking SMS API, the primary SMS
  gateway for the East-African market.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Sequence

import requests
from django.conf import settings

from external_services.base import (
    HealthCheckResult,
    ProviderResponse,
    SmsProvider,
    ValidationResult,
)
from external_services.exceptions import (
    AuthenticationError,
    ProviderResponseError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)


class AfricasTalkingAdapter(SmsProvider):
    """Africa's Talking SMS adapter.

    Uses the Africa's Talking REST API with API-key authentication.
    Supports single sends, bulk sends, and delivery-status queries.

    Configuration (via Django settings):
        ``AFRICAS_TALKING_API_KEY``    — API key.
        ``AFRICAS_TALKING_USERNAME``   — Username (use ``"sandbox"`` for testing).
        ``AFRICAS_TALKING_SENDER_ID``  — Optional alphanumeric sender ID.
        ``AFRICAS_TALKING_BASE_URL``   — Defaults to ``https://api.africastalking.com/v1``.
    """

    PROVIDER_NAME = "africas_talking"
    _SANDBOX_URL = "https://api.sandbox.africastalking.com/v1"
    _PRODUCTION_URL = "https://api.africastalking.com/v1"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(provider_name=self.PROVIDER_NAME, service_type="sms", **kwargs)
        self._api_key: str = getattr(settings, "AFRICAS_TALKING_API_KEY", "")
        self._username: str = getattr(settings, "AFRICAS_TALKING_USERNAME", "sandbox")
        self._sender_id: str = getattr(settings, "AFRICAS_TALKING_SENDER_ID", "")
        self._sandbox: bool = self._username.lower() == "sandbox"
        self._base_url: str = self._SANDBOX_URL if self._sandbox else self._PRODUCTION_URL
        self._session: Optional[requests.Session] = None

    # -- lifecycle --------------------------------------------------------

    def connect(self) -> bool:
        try:
            self._session = requests.Session()
            self._session.headers.update({
                "apiKey": self._api_key,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            })
            # Verify credentials by fetching user data
            resp = self._session.get(f"{self._base_url}/user", timeout=10)
            if resp.status_code == 200:
                self.is_connected = True
                return True
            if resp.status_code in (401, 403):
                raise AuthenticationError(provider_name=self.PROVIDER_NAME)
            raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME)
        except (AuthenticationError, ProviderUnavailableError):
            raise
        except Exception as exc:
            raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME) from exc

    def disconnect(self) -> bool:
        if self._session:
            self._session.close()
            self._session = None
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            resp = requests.get(
                f"{self._base_url}/user",
                headers={"apiKey": self._api_key, "Accept": "application/json"},
                timeout=5,
            )
            elapsed = (time.monotonic() - start) * 1000
            return HealthCheckResult(
                status="healthy" if resp.status_code == 200 else "degraded",
                provider=self.PROVIDER_NAME,
                response_time_ms=elapsed,
            )
        except Exception:
            return HealthCheckResult(status="unhealthy", provider=self.PROVIDER_NAME)

    def validate_configuration(self) -> ValidationResult:
        errors, warnings = [], []
        if not self._api_key:
            errors.append("AFRICAS_TALKING_API_KEY is not configured")
        if not self._username:
            errors.append("AFRICAS_TALKING_USERNAME is not configured")
        if self._sandbox:
            warnings.append("Using sandbox mode; switch AFRICAS_TALKING_USERNAME for production")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    # -- sms operations ---------------------------------------------------

    def send(self, to: str, message: str, **kwargs: Any) -> ProviderResponse:
        """Send a single SMS message.

        Args:
            to: Recipient phone number in international format (e.g. ``+254712345678``).
            message: SMS body text (max 160 chars for single SMS).
            **kwargs: ``sender_id`` override, ``enqueue`` flag.
        """
        start = time.monotonic()
        try:
            payload = {
                "username": self._username,
                "to": to,
                "message": message,
            }
            sender = kwargs.get("sender_id", self._sender_id)
            if sender:
                payload["from"] = sender
            resp = self._session.post(f"{self._base_url}/messaging", data=payload, timeout=30)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code == 201 and data.get("SMSMessageData", {}).get("Recipients"):
                recipients = data["SMSMessageData"]["Recipients"]
                msg_id = recipients[0].get("messageId", "") if recipients else ""
                return ProviderResponse(
                    success=True,
                    data={"message_id": msg_id, "cost": data["SMSMessageData"].get("Message", "")},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            return ProviderResponse(
                success=False,
                error=data.get("SMSMessageData", {}).get("Message", "Send failed"),
                data=data,
                provider=self.PROVIDER_NAME,
                latency_ms=elapsed,
            )
        except requests.Timeout:
            from external_services.exceptions import TimeoutError as ESLTimeoutError
            raise ESLTimeoutError(provider_name=self.PROVIDER_NAME, timeout_seconds=30)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def send_bulk(self, recipients: Sequence[str], message: str, **kwargs: Any) -> ProviderResponse:
        """Send the same SMS to multiple recipients.

        Africa's Talking accepts comma-separated phone numbers in a
        single API call, which is more efficient than individual sends.
        """
        start = time.monotonic()
        try:
            payload = {
                "username": self._username,
                "to": ",".join(recipients),
                "message": message,
            }
            sender = kwargs.get("sender_id", self._sender_id)
            if sender:
                payload["from"] = sender
            resp = self._session.post(f"{self._base_url}/messaging", data=payload, timeout=60)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            recipient_list = data.get("SMSMessageData", {}).get("Recipients", [])
            return ProviderResponse(
                success=resp.status_code == 201,
                data={"sent_count": len(recipient_list), "recipients": recipient_list},
                provider=self.PROVIDER_NAME,
                latency_ms=elapsed,
            )
        except requests.Timeout:
            from external_services.exceptions import TimeoutError as ESLTimeoutError
            raise ESLTimeoutError(provider_name=self.PROVIDER_NAME, timeout_seconds=60)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def get_delivery_status(self, message_id: str) -> ProviderResponse:
        """Query delivery status of a previously sent message.

        Uses the Africa's Talking messaging subscription callback or
        the delivery-reports endpoint when available.
        """
        start = time.monotonic()
        try:
            # Africa's Talking doesn't have a direct "check status" endpoint
            # for arbitrary message IDs. In production, delivery reports
            # are pushed via webhook callbacks. We simulate a check here.
            logger.info("Delivery status check for message_id=%s — in production, use webhook callbacks", message_id)
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(
                success=True,
                data={"message_id": message_id, "status": "unknown", "note": "Use webhook callbacks for real-time delivery status"},
                provider=self.PROVIDER_NAME,
                latency_ms=elapsed,
            )
        except Exception as exc:
            return ProviderResponse(success=False, error=str(exc), provider=self.PROVIDER_NAME)
