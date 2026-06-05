"""
Email provider adapters for the External Services Layer.

Implements the :class:`~external_services.base.EmailProvider` interface
for two backends:

* **SMTPAdapter** — Uses Django's built-in SMTP email backend.
* **SendGridAdapter** — Uses the SendGrid v3 REST API with Bearer token auth.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Sequence

import requests
from django.conf import settings
from django.core.mail import EmailMessage, get_connection

from external_services.base import (
    EmailProvider,
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


# ======================================================================
# SMTP Adapter
# ======================================================================


class SMTPAdapter(EmailProvider):
    """SMTP email adapter built on Django's ``django.core.mail``.

    Leverages the ``EMAIL_BACKEND``, ``EMAIL_HOST``, ``EMAIL_PORT``,
    and related settings that Django already provides.  Template emails
    are rendered server-side using Django's template engine before being
    sent as plain HTML.
    """

    PROVIDER_NAME = "smtp"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(provider_name=self.PROVIDER_NAME, service_type="email", **kwargs)

    # -- lifecycle --------------------------------------------------------

    def connect(self) -> bool:
        try:
            connection = get_connection()
            connection.open()
            connection.close()
            self.is_connected = True
            return True
        except Exception as exc:
            raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def disconnect(self) -> bool:
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            connection = get_connection()
            connection.open()
            connection.close()
            return HealthCheckResult(status="healthy", provider=self.PROVIDER_NAME, response_time_ms=(time.monotonic() - start) * 1000)
        except Exception as exc:
            return HealthCheckResult(status="unhealthy", provider=self.PROVIDER_NAME, details={"error": str(exc)})

    def validate_configuration(self) -> ValidationResult:
        errors, warnings = [], []
        if not getattr(settings, "EMAIL_HOST", ""):
            errors.append("EMAIL_HOST is not configured")
        if not getattr(settings, "EMAIL_PORT", 0):
            warnings.append("EMAIL_PORT is not set; using default")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    # -- email operations -------------------------------------------------

    def send(self, to: str, subject: str, body: str, **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            msg = EmailMessage(
                subject=subject,
                body=body,
                from_email=kwargs.get("from_email", settings.DEFAULT_FROM_EMAIL),
                to=[to],
                cc=kwargs.get("cc"),
                bcc=kwargs.get("bcc"),
                reply_to=kwargs.get("reply_to"),
            )
            if kwargs.get("html", False):
                msg.content_subtype = "html"
            sent = msg.send()
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=sent > 0, data={"message_id": msg.extra_headers.get("Message-ID", ""), "recipients": 1}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            return ProviderResponse(success=False, error=str(exc), provider=self.PROVIDER_NAME)

    def send_template(self, to: str, template_id: str, context: Dict[str, Any], **kwargs: Any) -> ProviderResponse:
        """Render a Django template and send as email."""
        start = time.monotonic()
        try:
            from django.template.loader import render_to_string
            html_body = render_to_string(template_id, context)
            return self.send(to=to, subject=kwargs.get("subject", ""), body=html_body, html=True, **kwargs)
        except Exception as exc:
            return ProviderResponse(success=False, error=str(exc), provider=self.PROVIDER_NAME)

    def send_bulk(self, recipients: Sequence[str], subject: str, body: str, **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            connection = get_connection()
            messages = []
            for recipient in recipients:
                msg = EmailMessage(
                    subject=subject, body=body,
                    from_email=kwargs.get("from_email", settings.DEFAULT_FROM_EMAIL),
                    to=[recipient],
                )
                if kwargs.get("html", False):
                    msg.content_subtype = "html"
                messages.append(msg)
            sent_count = connection.send_messages(messages)
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=True, data={"sent_count": sent_count or len(messages)}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            return ProviderResponse(success=False, error=str(exc), provider=self.PROVIDER_NAME)


# ======================================================================
# SendGrid Adapter
# ======================================================================


class SendGridAdapter(EmailProvider):
    """SendGrid v3 API email adapter.

    Uses Bearer-token authentication and SendGrid's REST API.
    Supports template sends (``send_template``) natively via
    SendGrid dynamic templates.

    Configuration (via Django settings):
        ``SENDGRID_API_KEY`` — SendGrid API key.
    """

    PROVIDER_NAME = "sendgrid"
    _BASE_URL = "https://api.sendgrid.com/v3"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(provider_name=self.PROVIDER_NAME, service_type="email", **kwargs)
        self._api_key: str = getattr(settings, "SENDGRID_API_KEY", "")
        self._session: Optional[requests.Session] = None

    # -- lifecycle --------------------------------------------------------

    def connect(self) -> bool:
        try:
            self._session = requests.Session()
            self._session.headers.update({
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            })
            resp = self._session.get(f"{self._BASE_URL}/user/account", timeout=10)
            if resp.status_code == 200:
                self.is_connected = True
                return True
            if resp.status_code == 401:
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
            resp = requests.get(f"{self._BASE_URL}/user/account", headers={"Authorization": f"Bearer {self._api_key}"}, timeout=5)
            elapsed = (time.monotonic() - start) * 1000
            status = "healthy" if resp.status_code == 200 else "degraded"
            return HealthCheckResult(status=status, provider=self.PROVIDER_NAME, response_time_ms=elapsed)
        except Exception:
            return HealthCheckResult(status="unhealthy", provider=self.PROVIDER_NAME)

    def validate_configuration(self) -> ValidationResult:
        errors = []
        if not self._api_key:
            errors.append("SENDGRID_API_KEY is not configured")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    # -- email operations -------------------------------------------------

    def send(self, to: str, subject: str, body: str, **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {
                "personalizations": [{"to": [{"email": to}]}],
                "from": {"email": kwargs.get("from_email", settings.DEFAULT_FROM_EMAIL)},
                "subject": subject,
            }
            if kwargs.get("html", True):
                payload["content"] = [{"type": "text/html", "value": body}]
            else:
                payload["content"] = [{"type": "text/plain", "value": body}]
            resp = self._session.post(f"{self._BASE_URL}/mail/send", json=payload, timeout=30)
            elapsed = (time.monotonic() - start) * 1000
            success = resp.status_code in (200, 202)
            message_id = resp.headers.get("X-Message-Id", "")
            return ProviderResponse(success=success, data={"message_id": message_id}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            return ProviderResponse(success=False, error=str(exc), provider=self.PROVIDER_NAME)

    def send_template(self, to: str, template_id: str, context: Dict[str, Any], **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {
                "personalizations": [{"to": [{"email": to}], "dynamic_template_data": context}],
                "from": {"email": kwargs.get("from_email", settings.DEFAULT_FROM_EMAIL)},
                "template_id": template_id,
            }
            resp = self._session.post(f"{self._BASE_URL}/mail/send", json=payload, timeout=30)
            elapsed = (time.monotonic() - start) * 1000
            success = resp.status_code in (200, 202)
            return ProviderResponse(success=success, data={"message_id": resp.headers.get("X-Message-Id", "")}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            return ProviderResponse(success=False, error=str(exc), provider=self.PROVIDER_NAME)

    def send_bulk(self, recipients: Sequence[str], subject: str, body: str, **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {
                "personalizations": [{"to": [{"email": r}]} for r in recipients],
                "from": {"email": kwargs.get("from_email", settings.DEFAULT_FROM_EMAIL)},
                "subject": subject,
                "content": [{"type": "text/html" if kwargs.get("html", True) else "text/plain", "value": body}],
            }
            resp = self._session.post(f"{self._BASE_URL}/mail/send", json=payload, timeout=60)
            elapsed = (time.monotonic() - start) * 1000
            success = resp.status_code in (200, 202)
            return ProviderResponse(success=success, data={"batch_count": len(recipients)}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            return ProviderResponse(success=False, error=str(exc), provider=self.PROVIDER_NAME)
