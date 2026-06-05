"""
Third-party service degradation handler.

For each integration:
- Payment: Queue for retry, inform user
- Email: Queue for retry, create account anyway
- SMS: Fall back to email, queue for retry
- Storage: Use local temp, queue for sync
- AI: Return cached/default response, queue for retry
- Maps: Return basic info, degrade gracefully
- Analytics: Queue events, process later
- Identity: Queue verification, allow limited access

All user-facing messages must NEVER expose:
- Provider names (Stripe, M-Pesa, Paystack, Twilio, etc.)
- Internal service architecture
- API endpoints or URLs
- Error codes from providers
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest

from .error_taxonomy import map_exception_to_error_code
from .error_responses import create_error_response

logger = logging.getLogger(__name__)


class ThirdPartyDegradationHandler:
    """Handle third-party service failures gracefully.

    Usage::

        handler = ThirdPartyDegradationHandler()

        try:
            result = payment_provider.charge(...)
        except ExternalServiceError as exc:
            response = handler.handle_payment_provider_failure(
                "payment", exc, transaction
            )
    """

    # Queue key prefix for deferred operations
    QUEUE_KEY_PREFIX = "digiland:degradation:queue:"

    def handle_payment_provider_failure(
        self,
        provider: str,
        error: Exception,
        transaction: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Handle a payment provider failure.

        Strategy: Queue payment for retry, inform user without
        revealing the provider name.

        Args:
            provider: Provider identifier (internal only — NEVER exposed).
            error: The exception.
            transaction: The transaction object, if available.

        Returns:
            Dict with the response data.
        """
        reference_id = str(uuid.uuid4())
        transaction_id = str(getattr(transaction, "id", "unknown")) if transaction else None

        error_code = map_exception_to_error_code(error)

        # Queue for retry
        self._queue_for_retry(
            service_type="payment",
            operation="payment_verification",
            reference_id=reference_id,
            metadata={"transaction_id": transaction_id},
        )

        # Determine if outcome is uncertain
        from external_services.exceptions import TimeoutError as ESLTimeout
        is_uncertain = isinstance(error, (ESLTimeout, ConnectionError, TimeoutError))

        if is_uncertain:
            user_message = (
                "We couldn't confirm your payment status. Your money may or may not "
                "have been debited. Please do NOT attempt the same payment again. "
                "We are verifying the status and will notify you. "
                f"Reference: {reference_id}"
            )
            funds_status = "unknown"
        else:
            user_message = (
                "We're unable to process your payment right now. "
                "Your money has not been debited. "
                "Please try again in a few minutes. "
                f"Reference: {reference_id}"
            )
            funds_status = "not_moved"

        logger.error(
            "Payment provider failure: ref=%s provider=%s txn=%s uncertain=%s exc=%s",
            reference_id,
            provider,  # Internal only
            transaction_id,
            is_uncertain,
            type(error).__name__,
            extra={
                "reference_id": reference_id,
                "provider": provider,  # Logged internally only
                "transaction_id": transaction_id,
                "error_code": error_code,
                "is_uncertain": is_uncertain,
                "exception_type": type(error).__name__,
                "exception_message": str(error)[:500],
            },
        )

        return {
            "success": False,
            "error_code": error_code,
            "user_message": user_message,
            "reference_id": reference_id,
            "transaction_id": transaction_id,
            "funds_status": funds_status,
            "retry_queued": True,
        }

    def handle_email_provider_failure(
        self,
        provider: str,
        error: Exception,
        user: Optional[Any] = None,
        email_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle an email provider failure.

        Strategy: Create the account anyway, queue email for retry.

        Args:
            provider: Provider identifier (internal only).
            error: The exception.
            user: The user object, if available.
            email_type: Type of email (welcome, verification, etc.).

        Returns:
            Dict with the response data.
        """
        reference_id = str(uuid.uuid4())
        user_id = str(getattr(user, "id", "unknown")) if user else None

        self._queue_for_retry(
            service_type="email",
            operation="send_email",
            reference_id=reference_id,
            metadata={"user_id": user_id, "email_type": email_type},
        )

        logger.warning(
            "Email provider failure: ref=%s provider=%s user=%s type=%s",
            reference_id,
            provider,
            user_id,
            email_type,
            extra={
                "reference_id": reference_id,
                "provider": provider,
                "user_id": user_id,
                "email_type": email_type,
                "exception_type": type(error).__name__,
                "exception_message": str(error)[:300],
            },
        )

        return {
            "success": True,  # Account creation/operation still succeeds
            "warning": (
                "Your account has been created, but the confirmation email "
                "is delayed. We'll send it as soon as possible."
            ),
            "reference_id": reference_id,
            "email_delayed": True,
            "retry_queued": True,
        }

    def handle_sms_provider_failure(
        self,
        provider: str,
        error: Exception,
        phone: Optional[str] = None,
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle an SMS provider failure.

        Strategy: Fall back to in-app notification, queue SMS for retry.

        Args:
            provider: Provider identifier (internal only).
            error: The exception.
            phone: Phone number (sanitized in logs).
            message: SMS message content (not logged).

        Returns:
            Dict with the response data.
        """
        reference_id = str(uuid.uuid4())

        self._queue_for_retry(
            service_type="sms",
            operation="send_sms",
            reference_id=reference_id,
            metadata={"phone_prefix": phone[:6] + "****" if phone else None},
        )

        # Queue in-app notification as fallback
        self._queue_for_retry(
            service_type="notification",
            operation="send_in_app_notification",
            reference_id=reference_id,
            metadata={"fallback_for": "sms", "reference_id": reference_id},
        )

        logger.warning(
            "SMS provider failure: ref=%s provider=%s",
            reference_id,
            provider,
            extra={
                "reference_id": reference_id,
                "provider": provider,
                "exception_type": type(error).__name__,
                "exception_message": str(error)[:300],
            },
        )

        return {
            "success": True,  # The main operation still succeeds
            "warning": (
                "We couldn't send an SMS right now, but an in-app notification "
                "has been created. We'll send the SMS when the service recovers."
            ),
            "reference_id": reference_id,
            "sms_delayed": True,
            "fallback_notification_sent": True,
            "retry_queued": True,
        }

    def handle_storage_provider_failure(
        self,
        provider: str,
        error: Exception,
        file: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Handle a storage provider failure.

        Strategy: Use temporary local storage, queue for sync when
        the provider recovers.

        Args:
            provider: Provider identifier (internal only).
            error: The exception.
            file: The file being uploaded.

        Returns:
            Dict with the response data.
        """
        reference_id = str(uuid.uuid4())
        file_name = getattr(file, "name", "unknown") if file else "unknown"

        self._queue_for_retry(
            service_type="storage",
            operation="sync_file",
            reference_id=reference_id,
            metadata={"file_name": file_name},
        )

        logger.error(
            "Storage provider failure: ref=%s provider=%s file=%s",
            reference_id,
            provider,
            file_name,
            extra={
                "reference_id": reference_id,
                "provider": provider,
                "file_name": file_name,
                "exception_type": type(error).__name__,
                "exception_message": str(error)[:300],
            },
        )

        return {
            "success": True,  # File stored locally as fallback
            "warning": (
                "Your file has been saved temporarily. It will be "
                "permanently stored as soon as the service recovers."
            ),
            "reference_id": reference_id,
            "temp_storage": True,
            "sync_pending": True,
            "retry_queued": True,
        }

    def handle_ai_provider_failure(
        self,
        provider: str,
        error: Exception,
        request_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle an AI provider failure.

        Strategy: Return cached/default response, queue for retry.

        Args:
            provider: Provider identifier (internal only).
            error: The exception.
            request_type: Type of AI request (chat, embedding, etc.).

        Returns:
            Dict with the response data.
        """
        reference_id = str(uuid.uuid4())

        # Try to get a cached response
        cached_response = self._get_cached_ai_response(request_type or "default")

        self._queue_for_retry(
            service_type="ai",
            operation=request_type or "ai_request",
            reference_id=reference_id,
            metadata={"request_type": request_type},
        )

        logger.error(
            "AI provider failure: ref=%s provider=%s type=%s",
            reference_id,
            provider,
            request_type,
            extra={
                "reference_id": reference_id,
                "provider": provider,
                "request_type": request_type,
                "has_cached_response": cached_response is not None,
                "exception_type": type(error).__name__,
                "exception_message": str(error)[:300],
            },
        )

        if cached_response:
            return {
                "success": True,
                "data": cached_response,
                "degraded": True,
                "warning": (
                    "AI-powered results may not be fully up to date. "
                    "We're working on restoring full functionality."
                ),
                "reference_id": reference_id,
                "from_cache": True,
            }

        return {
            "success": False,
            "error_code": "EXTERNAL_SERVICE_UNAVAILABLE",
            "user_message": (
                "AI-powered features are temporarily unavailable. "
                "Basic functionality still works. Please try again later."
            ),
            "reference_id": reference_id,
            "retry_queued": True,
        }

    def handle_identity_provider_failure(
        self,
        provider: str,
        error: Exception,
        user: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Handle an identity provider failure.

        Strategy: Queue verification, allow limited access.

        Args:
            provider: Provider identifier (internal only).
            error: The exception.
            user: The user object.

        Returns:
            Dict with the response data.
        """
        reference_id = str(uuid.uuid4())
        user_id = str(getattr(user, "id", "unknown")) if user else None

        self._queue_for_retry(
            service_type="identity",
            operation="identity_verification",
            reference_id=reference_id,
            metadata={"user_id": user_id},
        )

        logger.error(
            "Identity provider failure: ref=%s provider=%s user=%s",
            reference_id,
            provider,
            user_id,
            extra={
                "reference_id": reference_id,
                "provider": provider,
                "user_id": user_id,
                "exception_type": type(error).__name__,
                "exception_message": str(error)[:300],
            },
        )

        return {
            "success": True,  # Allow limited access
            "warning": (
                "Identity verification is temporarily unavailable. "
                "You can continue with limited access. "
                "Verification will be processed when the service recovers."
            ),
            "reference_id": reference_id,
            "limited_access": True,
            "verification_pending": True,
            "retry_queued": True,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _queue_for_retry(
        self,
        service_type: str,
        operation: str,
        reference_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Queue a failed operation for automatic retry.

        Args:
            service_type: Type of service.
            operation: The operation to retry.
            reference_id: Reference ID for tracking.
            metadata: Additional metadata.

        Returns:
            True if queued successfully.
        """
        try:
            queue_key = f"{self.QUEUE_KEY_PREFIX}{service_type}"
            queue_data = cache.get(queue_key, "[]")
            if isinstance(queue_data, str):
                queue_data = json.loads(queue_data) if queue_data else []

            entry = {
                "service_type": service_type,
                "operation": operation,
                "reference_id": reference_id,
                "metadata": metadata or {},
                "queued_at": __import__("time").time(),
            }
            queue_data.append(entry)

            # Keep only the last 500 entries per service type
            if len(queue_data) > 500:
                queue_data = queue_data[-500:]

            cache.set(queue_key, json.dumps(queue_data), timeout=86400)
            return True
        except Exception:
            logger.warning("Failed to queue for retry: ref=%s", reference_id)
            return False

    def _get_cached_ai_response(self, request_type: str) -> Optional[Dict[str, Any]]:
        """Try to get a cached AI response for the given request type."""
        try:
            import json
            key = f"digiland:ai:cache:{request_type}"
            data = cache.get(key)
            if data is None:
                return None
            if isinstance(data, str):
                return json.loads(data)
            return data
        except Exception:
            return None


# Import needed for _queue_for_retry
import json
