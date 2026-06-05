"""
Push notification provider adapter for the External Services Layer.

Implements the :class:`~external_services.base.PushNotificationProvider`
interface for:

* **FirebaseAdapter** — Firebase Cloud Messaging (FCM) via the
  ``firebase-admin`` SDK.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Sequence

from django.conf import settings

from external_services.base import (
    HealthCheckResult,
    ProviderResponse,
    PushNotificationProvider,
    ValidationResult,
)
from external_services.exceptions import (
    AuthenticationError,
    ProviderResponseError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)


class FirebaseAdapter(PushNotificationProvider):
    """Firebase Cloud Messaging (FCM) push notification adapter.

    Uses the ``firebase-admin`` SDK for sending push notifications to
    individual devices, multiple devices, and topic subscriptions.

    Configuration (via Django settings):
        ``FIREBASE_CREDENTIALS_PATH`` — Path to the service account JSON file.
        ``FIREBASE_PROJECT_ID``       — Firebase project ID (optional if in credentials).
    """

    PROVIDER_NAME = "firebase"

    def __init__(self, **kwargs: Any)    -> None:
        super().__init__(provider_name=self.PROVIDER_NAME, service_type="push_notification", **kwargs)
        self._credentials_path: str = getattr(settings, "FIREBASE_CREDENTIALS_PATH", "")
        self._app = None

    def _get_app(self):
        """Lazy-initialise the Firebase app."""
        if self._app is None:
            try:
                import firebase_admin
                from firebase_admin import credentials
                if not firebase_admin._apps:
                    if self._credentials_path:
                        cred = credentials.Certificate(self._credentials_path)
                        self._app = firebase_admin.initialize_app(cred)
                    else:
                        # Use application default credentials
                        self._app = firebase_admin.initialize_app()
                else:
                    self._app = firebase_admin.get_app()
            except ImportError as exc:
                raise ProviderUnavailableError(
                    provider_name=self.PROVIDER_NAME,
                    message="firebase-admin package is not installed",
                ) from exc
            except Exception as exc:
                raise ProviderUnavailableError(
                    provider_name=self.PROVIDER_NAME,
                    message=f"Firebase initialisation failed: {exc}",
                ) from exc
        return self._app

    # -- lifecycle --------------------------------------------------------

    def connect(self) -> bool:
        try:
            self._get_app()
            self.is_connected = True
            return True
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME) from exc

    def disconnect(self) -> bool:
        # firebase-admin doesn't support graceful teardown per-app
        self._app = None
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            self._get_app()
            elapsed = (time.monotonic() - start) * 1000
            return HealthCheckResult(
                status="healthy",
                provider=self.PROVIDER_NAME,
                response_time_ms=elapsed,
                details={"project_id": getattr(settings, "FIREBASE_PROJECT_ID", "unknown")},
            )
        except Exception as exc:
            return HealthCheckResult(status="unhealthy", provider=self.PROVIDER_NAME, details={"error": str(exc)})

    def validate_configuration(self) -> ValidationResult:
        errors, warnings = [], []
        if not self._credentials_path:
            warnings.append("FIREBASE_CREDENTIALS_PATH not set; relying on application default credentials")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    # -- push notification operations -------------------------------------

    def send(self, user_id: str, title: str, body: str, **kwargs: Any) -> ProviderResponse:
        """Send a push notification to a single user.

        Looks up the user's device token(s) and sends via FCM.

        Args:
            user_id: Internal user identifier.
            title: Notification title.
            body: Notification body text.
            **kwargs: ``icon``, ``click_action``, ``data`` (dict), ``token`` (override).
        """
        start = time.monotonic()
        try:
            from firebase_admin import messaging
            self._get_app()

            # Use provided token or look up user's device tokens
            token = kwargs.get("token")
            if not token:
                # Try to get from a DeviceToken model or similar
                token = self._get_user_token(user_id)
                if not token:
                    return ProviderResponse(
                        success=False,
                        error=f"No device token found for user {user_id}",
                        provider=self.PROVIDER_NAME,
                        latency_ms=(time.monotonic() - start) * 1000,
                    )

            notification = messaging.Notification(title=title, body=body)
            android = messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    icon=kwargs.get("icon", ""),
                    click_action=kwargs.get("click_action", ""),
                ),
            )
            apns = messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound="default", badge=kwargs.get("badge")),
                ),
            )
            message = messaging.Message(
                token=token,
                notification=notification,
                android=android,
                apns=apns,
                data=kwargs.get("data", {}),
            )

            response = messaging.send(message)
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(
                success=True,
                data={"message_id": response, "user_id": user_id},
                provider=self.PROVIDER_NAME,
                latency_ms=elapsed,
            )
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            return ProviderResponse(
                success=False,
                error=str(exc),
                provider=self.PROVIDER_NAME,
                latency_ms=(time.monotonic() - start) * 1000,
            )

    def send_bulk(self, user_ids: Sequence[str], title: str, body: str, **kwargs: Any) -> ProviderResponse:
        """Send the same push notification to multiple users.

        Uses FCM multicast messaging for efficient batch delivery.

        Args:
            user_ids: List of internal user identifiers.
            title: Notification title.
            body: Notification body text.
            **kwargs: Same options as :meth:`send`.
        """
        start = time.monotonic()
        try:
            from firebase_admin import messaging
            self._get_app()

            # Collect device tokens for all users
            tokens = []
            for uid in user_ids:
                token = kwargs.get(f"token_{uid}") or self._get_user_token(uid)
                if token:
                    tokens.append(token)

            if not tokens:
                return ProviderResponse(
                    success=False,
                    error="No device tokens found for any of the specified users",
                    provider=self.PROVIDER_NAME,
                    latency_ms=(time.monotonic() - start) * 1000,
                )

            notification = messaging.Notification(title=title, body=body)
            message = messaging.MulticastMessage(
                tokens=tokens,
                notification=notification,
                data=kwargs.get("data", {}),
            )

            response = messaging.send_multicast(message)
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(
                success=True,
                data={
                    "success_count": response.success_count,
                    "failure_count": response.failure_count,
                    "total": len(tokens),
                },
                provider=self.PROVIDER_NAME,
                latency_ms=elapsed,
            )
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            return ProviderResponse(
                success=False,
                error=str(exc),
                provider=self.PROVIDER_NAME,
                latency_ms=(time.monotonic() - start) * 1000,
            )

    def send_to_topic(self, topic: str, title: str, body: str, **kwargs: Any) -> ProviderResponse:
        """Send a push notification to a topic/subscription.

        Args:
            topic: Topic name (e.g. ``"parcel_updates"``).
            title: Notification title.
            body: Notification body text.
            **kwargs: Same options as :meth:`send`.
        """
        start = time.monotonic()
        try:
            from firebase_admin import messaging
            self._get_app()

            notification = messaging.Notification(title=title, body=body)
            message = messaging.Message(
                topic=topic,
                notification=notification,
                data=kwargs.get("data", {}),
            )

            response = messaging.send(message)
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(
                success=True,
                data={"message_id": response, "topic": topic},
                provider=self.PROVIDER_NAME,
                latency_ms=elapsed,
            )
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            return ProviderResponse(
                success=False,
                error=str(exc),
                provider=self.PROVIDER_NAME,
                latency_ms=(time.monotonic() - start) * 1000,
            )

    # -- helpers ----------------------------------------------------------

    def _get_user_token(self, user_id: str) -> Optional[str]:
        """Look up a user's FCM device token.

        Override this method or integrate with a ``DeviceToken`` model
        to map user IDs to device tokens.
        """
        try:
            from core.models import User
            user = User.objects.filter(pk=user_id).first()
            if user and hasattr(user, "fcm_token") and user.fcm_token:
                return user.fcm_token
        except Exception:
            pass
        return None
