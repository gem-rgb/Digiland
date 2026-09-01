"""Centralized notification service for Digiland.

Architecture:
    NotificationService (orchestrator)
    ├── EmailProvider (abstract)
    │   └── ResendProvider (Resend API)
    ├── SmsProvider (abstract — stub)
    └── InApp (direct DB)

All external emails flow through this service, never through raw send_mail()
in controllers. The Resend API key lives only on the backend.
"""

import logging
import uuid as _uuid
from abc import ABC, abstractmethod

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Provider Abstractions ─────────────────────────────────────────────────


class EmailProvider(ABC):
    """Abstract email delivery provider."""

    @abstractmethod
    def send(self, *, to, subject, html_body, text_body='',
             from_email=None, from_name=None, reply_to=None,
             idempotency_key=None, tags=None) -> dict:
        """Send an email.

        Returns:
            dict with at least {'provider_message_id': str, 'status': str}
        """

    @abstractmethod
    def verify_webhook(self, payload, headers) -> bool:
        """Verify incoming webhook signature."""


class SmsProvider(ABC):
    """Abstract SMS delivery provider (future implementation)."""

    @abstractmethod
    def send(self, *, to, body, from_number=None) -> dict:
        """Send an SMS."""


# ── Resend Email Provider ─────────────────────────────────────────────────


class ResendEmailProvider(EmailProvider):
    """Email delivery via the Resend API.

    Uses the official `resend` Python SDK. The API key is read from
    settings.RESEND_API_KEY and is never exposed to the frontend.
    """

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import resend
                api_key = getattr(settings, 'RESEND_API_KEY', '')
                if not api_key:
                    raise ValueError("RESEND_API_KEY is not configured")
                resend.api_key = api_key
                self._client = resend
            except ImportError:
                raise ImportError(
                    "The 'resend' package is required. Install it with: pip install resend"
                )
        return self._client

    def send(self, *, to, subject, html_body, text_body='',
             from_email=None, from_name=None, reply_to=None,
             idempotency_key=None, tags=None) -> dict:
        """Send email via Resend API."""
        resend = self.client

        _from_email = from_email or getattr(settings, 'RESEND_FROM_EMAIL', 'noreply@digiland.co.ke')
        _from_name = from_name or getattr(settings, 'RESEND_FROM_NAME', 'Digiland')
        from_addr = f"{_from_name} <{_from_email}>"

        params = {
            "from": from_addr,
            "to": to if isinstance(to, list) else [to],
            "subject": subject,
            "html": html_body,
        }

        if text_body:
            params["text"] = text_body
        if reply_to:
            params["reply_to"] = reply_to if isinstance(reply_to, list) else [reply_to]
        if tags:
            params["tags"] = tags

        # Resend supports idempotency via headers
        headers = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        try:
            response = resend.Emails.send(params)
            msg_id = response.get('id', '') if isinstance(response, dict) else str(response)
            return {
                'provider_message_id': msg_id,
                'status': 'SENT',
            }
        except Exception as exc:
            logger.exception("Resend email send failed: %s", exc)
            return {
                'provider_message_id': '',
                'status': 'FAILED',
                'error': str(exc),
            }

    def verify_webhook(self, payload, headers) -> bool:
        """Verify Resend webhook signature using svix."""
        try:
            from svix.webhooks import Webhook
            webhook_secret = getattr(settings, 'RESEND_WEBHOOK_SECRET', '')
            if not webhook_secret:
                logger.warning("RESEND_WEBHOOK_SECRET not configured; skipping verification")
                return True
            wh = Webhook(webhook_secret)
            wh.verify(payload, headers)
            return True
        except ImportError:
            logger.warning("svix package not installed; webhook verification skipped")
            return True
        except Exception:
            logger.exception("Resend webhook verification failed")
            return False


class StubSmsProvider(SmsProvider):
    """Placeholder SMS provider.

    Digiland's SMS provider has not been selected yet. This stub records
    the intent but does not actually send. Replace with Africa's Talking,
    Twilio, or Safaricom bulk SMS when ready.
    """

    def send(self, *, to, body, from_number=None) -> dict:
        logger.info("SMS stub: would send to %s — %s", to, body[:80])
        return {
            'provider_message_id': '',
            'status': 'QUEUED',
            'error': 'SMS provider not configured',
        }


# ── SMTP Fallback Provider ────────────────────────────────────────────────


class SmtpEmailProvider(EmailProvider):
    """Fallback: use Django's built-in send_mail (SMTP / console backend)."""

    def send(self, *, to, subject, html_body, text_body='',
             from_email=None, from_name=None, reply_to=None,
             idempotency_key=None, tags=None) -> dict:
        from django.core.mail import send_mail as django_send_mail

        _from = from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@digiland.local')
        recipient_list = to if isinstance(to, list) else [to]

        try:
            django_send_mail(
                subject=subject,
                message=text_body or '',
                from_email=_from,
                recipient_list=recipient_list,
                html_message=html_body,
                fail_silently=False,
            )
            return {'provider_message_id': '', 'status': 'SENT'}
        except Exception as exc:
            logger.exception("SMTP email send failed: %s", exc)
            return {'provider_message_id': '', 'status': 'FAILED', 'error': str(exc)}

    def verify_webhook(self, payload, headers) -> bool:
        return False  # SMTP has no webhooks


# ── Notification Service (Orchestrator) ───────────────────────────────────


class NotificationService:
    """Centralized notification dispatch.

    All notification sending — email, SMS, in-app — flows through this service.
    Business logic never calls Resend or send_mail directly.
    """

    _email_provider = None
    _sms_provider = None

    @classmethod
    def get_email_provider(cls) -> EmailProvider:
        if cls._email_provider is None:
            import sys
            provider_name = getattr(settings, 'NOTIFICATION_EMAIL_PROVIDER', 'resend')
            api_key = getattr(settings, 'RESEND_API_KEY', '')
            is_testing = getattr(settings, 'TESTING', False) or ('test' in sys.argv)

            if provider_name == 'resend' and api_key and not is_testing:
                cls._email_provider = ResendEmailProvider()
            else:
                cls._email_provider = SmtpEmailProvider()
                if provider_name == 'resend' and not api_key:
                    logger.warning("RESEND_API_KEY not set; falling back to SMTP")
        return cls._email_provider


    @classmethod
    def get_sms_provider(cls) -> SmsProvider:
        if cls._sms_provider is None:
            cls._sms_provider = StubSmsProvider()
        return cls._sms_provider

    @classmethod
    def send_email(cls, *, user, notification_type, subject, html_body,
                   text_body='', action_url='', idempotency_key=None,
                   metadata=None):
        """Send an email notification and record it in the Notification table.

        Args:
            user: The User model instance to notify
            notification_type: E.g. 'ACCOUNT_ACTIVATION', 'PASSWORD_RESET'
            subject: Email subject line
            html_body: HTML email content
            text_body: Plain text fallback
            action_url: Deep-link URL for the notification
            idempotency_key: Prevents duplicate sends
            metadata: Additional JSON data
        """
        from core.models import Notification

        # Idempotency check
        if idempotency_key:
            existing = Notification.objects.filter(
                idempotency_key=idempotency_key,
                status__in=['SENT', 'DELIVERED', 'QUEUED', 'SENDING'],
            ).first()
            if existing:
                logger.info("Duplicate notification blocked: %s", idempotency_key)
                return existing

        # Create notification record
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            channel='EMAIL',
            status='SENDING',
            title=subject,
            body=text_body or subject,
            action_url=action_url,
            provider='resend' if isinstance(cls.get_email_provider(), ResendEmailProvider) else 'smtp',
            idempotency_key=idempotency_key or '',
            metadata=metadata or {},
        )

        # Send via provider
        provider = cls.get_email_provider()
        result = provider.send(
            to=user.email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            idempotency_key=idempotency_key,
        )

        # Update notification record
        notification.provider_message_id = result.get('provider_message_id', '')
        if result['status'] == 'SENT':
            notification.status = 'SENT'
            notification.sent_at = timezone.now()
        else:
            notification.status = 'FAILED'
            notification.failed_at = timezone.now()
            notification.last_error = result.get('error', 'Unknown error')
        notification.save()

        return notification

    @classmethod
    def send_in_app(cls, *, user, notification_type, title, body,
                    action_url='', metadata=None):
        """Create an in-app notification (no external delivery)."""
        from core.models import Notification

        return Notification.objects.create(
            user=user,
            notification_type=notification_type,
            channel='IN_APP',
            status='DELIVERED',
            title=title,
            body=body,
            action_url=action_url,
            delivered_at=timezone.now(),
            metadata=metadata or {},
        )

    @classmethod
    def send_sms(cls, *, user, notification_type, body, metadata=None):
        """Send an SMS notification (stub — provider not yet configured)."""
        from core.models import Notification

        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            channel='SMS',
            status='QUEUED',
            title='',
            body=body,
            provider='sms_stub',
            metadata=metadata or {},
        )

        provider = cls.get_sms_provider()
        phone = getattr(user, 'phone_number', '')
        if not phone:
            notification.status = 'FAILED'
            notification.last_error = 'No phone number on file'
            notification.failed_at = timezone.now()
            notification.save()
            return notification

        result = provider.send(to=phone, body=body)
        notification.provider_message_id = result.get('provider_message_id', '')
        if result['status'] != 'FAILED':
            notification.status = result['status']
        else:
            notification.status = 'FAILED'
            notification.last_error = result.get('error', '')
            notification.failed_at = timezone.now()
        notification.save()
        return notification

    @classmethod
    def get_unread_in_app_count(cls, user):
        """Count unread in-app notifications for a user."""
        from core.models import Notification
        return Notification.objects.filter(
            user=user, channel='IN_APP', read_at__isnull=True,
        ).count()

    @classmethod
    def get_recent_in_app(cls, user, *, limit=20):
        """Get recent in-app notifications for the notification centre."""
        from core.models import Notification
        return list(Notification.objects.filter(
            user=user, channel='IN_APP',
        ).order_by('-created_at')[:limit])

    @classmethod
    def mark_in_app_read(cls, user, notification_ids):
        """Mark in-app notifications as read."""
        from core.models import Notification
        Notification.objects.filter(
            id__in=notification_ids, user=user, channel='IN_APP',
        ).update(read_at=timezone.now())

    @classmethod
    def update_from_webhook(cls, provider_message_id, status, *, metadata=None):
        """Update a notification's status from a webhook event."""
        from core.models import Notification

        notification = Notification.objects.filter(
            provider_message_id=provider_message_id,
        ).first()
        if not notification:
            logger.warning("Webhook for unknown provider_message_id: %s", provider_message_id)
            return None

        now = timezone.now()
        notification.status = status
        if status == 'DELIVERED':
            notification.delivered_at = now
        elif status in ('BOUNCED', 'FAILED'):
            notification.failed_at = now
        if metadata:
            notification.metadata.update(metadata)
        notification.save()
        return notification
