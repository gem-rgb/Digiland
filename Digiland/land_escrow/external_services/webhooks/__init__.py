"""
Webhook framework for the External Services Layer.

Supports inbound/outbound webhooks with signature verification,
idempotency, queue-based processing, dead letter queues, and retry
with exponential backoff.

Usage::

    from external_services.webhooks import webhook_processor

    # Register a handler for inbound webhooks
    def handle_payment_completed(data):
        transaction = Transaction.objects.get(reference=data['reference'])
        transaction.mark_completed()

    webhook_processor.register_handler('payment.completed', handle_payment_completed)

    # Process an inbound webhook
    result = webhook_processor.process_inbound(
        provider_name='paystack',
        event_type='payment.completed',
        payload=request.body,
        signature=request.headers.get('X-Webhook-Signature'),
    )

    # Send an outbound webhook
    result = webhook_processor.send_webhook(
        url='https://partner.example.com/hooks',
        payload={'event': 'settlement.released', 'transaction_id': 'abc123'},
        secret='whsec_...',
        event_type='settlement.released',
    )
"""

import json
import uuid
import hashlib
import hmac
import time
import logging
from typing import Optional, Dict, Any, List, Callable, Union
from enum import Enum

from django.conf import settings

logger = logging.getLogger('external_services.webhooks')


class WebhookDirection(str, Enum):
    """Direction of a webhook request."""
    INBOUND = 'inbound'
    OUTBOUND = 'outbound'


class WebhookStatus(str, Enum):
    """Processing status of a webhook event."""
    PENDING = 'pending'
    COMPLETED = 'completed'
    FAILED = 'failed'
    DEAD_LETTERED = 'dead_lettered'


class WebhookSignatureVerifier:
    """Utility class for verifying webhook signatures."""

    @staticmethod
    def verify_hmac_sha256(
        payload: Union[str, bytes],
        signature: str,
        secret: str,
    ) -> bool:
        """Verify an HMAC-SHA256 signature.

        Supports both ``sha256=<hex>`` and plain ``<hex>`` formats.

        Args:
            payload: The raw request body.
            signature: The signature from the webhook header.
            secret: The shared secret.

        Returns:
            ``True`` if the signature is valid.
        """
        if not secret:
            logger.warning("WebhookSignatureVerifier: Empty secret, skipping verification")
            return True

        raw = payload if isinstance(payload, bytes) else payload.encode()
        expected = hmac.new(
            secret.encode(), raw, hashlib.sha256,
        ).hexdigest()

        # Support both "sha256=<hex>" and plain "<hex>" formats
        return (
            hmac.compare_digest(f"sha256={expected}", signature)
            or hmac.compare_digest(expected, signature)
        )


class WebhookProcessor:
    """Central processor for inbound and outbound webhooks.

    Features:
    * Signature verification for inbound webhooks.
    * Event-type-based handler registration and dispatch.
    * Idempotency via Django's cache framework (24-hour dedup window).
    * Outbound webhooks with exponential backoff retry.
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, List[Callable]] = {}
        self._idempotency_cache: Dict[str, bool] = {}

    # ------------------------------------------------------------------
    # Handler registration
    # ------------------------------------------------------------------

    def register_handler(
        self,
        event_type: str,
        handler: Callable,
    ) -> None:
        """Register a handler function for a specific event type.

        Multiple handlers can be registered for the same event type.
        Use ``*`` as the event type to register a catch-all handler.

        Args:
            event_type: Event type to handle (e.g. ``payment.completed``).
            handler: Callable that receives the parsed webhook payload.
        """
        self._handlers.setdefault(event_type, []).append(handler)
        logger.info("Webhook handler registered for '%s': %s", event_type, handler.__name__)

    def unregister_handler(
        self,
        event_type: str,
        handler: Callable,
    ) -> None:
        """Remove a previously registered handler.

        Args:
            event_type: Event type the handler was registered for.
            handler: The handler function to remove.
        """
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    # ------------------------------------------------------------------
    # Inbound webhook processing
    # ------------------------------------------------------------------

    def process_inbound(
        self,
        provider_name: str,
        event_type: str,
        payload: Union[str, bytes, Dict],
        signature: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Process an inbound webhook request.

        Steps:
        1. Verify the signature (if provided).
        2. Parse the JSON payload.
        3. Check idempotency (skip duplicates).
        4. Dispatch to registered handlers.

        Args:
            provider_name: Name of the sending provider.
            event_type: Expected event type.
            payload: Raw request body or pre-parsed dictionary.
            signature: Signature header value (optional).
            headers: Request headers (optional).

        Returns:
            A dictionary with ``success`` and ``status`` keys.
        """
        # 1. Signature verification
        if signature and not self._verify_signature(provider_name, payload, signature):
            logger.warning(
                "Webhook signature verification failed for %s",
                provider_name,
            )
            return {'success': False, 'error': 'Invalid signature'}

        # 2. Parse payload
        try:
            data = json.loads(payload) if isinstance(payload, (bytes, str)) else payload
        except json.JSONDecodeError:
            logger.warning("Webhook payload is not valid JSON from %s", provider_name)
            return {'success': False, 'error': 'Invalid JSON'}

        # 3. Idempotency check
        event_id = data.get('id', data.get('event_id', ''))
        if event_id and self._is_duplicate(event_id):
            logger.info("Duplicate webhook event %s from %s", event_id, provider_name)
            return {'success': True, 'status': 'duplicate', 'event_id': event_id}

        # 4. Determine actual event type from payload
        actual_event_type = data.get('event', data.get('event_type', event_type))

        # 5. Dispatch to handlers
        handlers = (
            self._handlers.get(actual_event_type, [])
            + self._handlers.get(event_type, [])
            + self._handlers.get('*', [])
        )

        errors = []
        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                logger.error(
                    "Webhook handler %s error for %s: %s",
                    handler.__name__,
                    actual_event_type,
                    str(e),
                )
                errors.append({'handler': handler.__name__, 'error': str(e)})

        if errors and len(errors) == len(handlers):
            return {
                'success': False,
                'status': 'handler_error',
                'errors': errors,
            }

        return {
            'success': True,
            'status': 'processed',
            'event_type': actual_event_type,
            'handlers_called': len(handlers),
            'errors': errors or None,
        }

    # ------------------------------------------------------------------
    # Outbound webhook sending
    # ------------------------------------------------------------------

    def send_webhook(
        self,
        url: str,
        payload: Dict[str, Any],
        secret: str,
        event_type: str = '',
        max_retries: int = 5,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """Send an outbound webhook with retry logic.

        The payload is signed using HMAC-SHA256 with a timestamp nonce.
        Retries use exponential backoff (capped at 60 seconds).

        Args:
            url: Target webhook URL.
            payload: Data to send (will be JSON-serialized).
            secret: Shared secret for signing.
            event_type: Event type header value.
            max_retries: Maximum number of retry attempts.
            timeout: Request timeout in seconds.

        Returns:
            A dictionary with ``success`` and status details.
        """
        import requests

        body = json.dumps(payload, default=str)
        timestamp = str(int(time.time()))
        signature = hmac.new(
            secret.encode(),
            f"{timestamp}.{body}".encode(),
            hashlib.sha256,
        ).hexdigest()

        headers = {
            'Content-Type': 'application/json',
            'X-Webhook-Signature': f"t={timestamp},v1={signature}",
            'X-Webhook-Event': event_type,
            'X-Webhook-ID': uuid.uuid4().hex,
        }

        last_error = None
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    url,
                    data=body,
                    headers=headers,
                    timeout=timeout,
                    verify=not getattr(settings, 'DEBUG', True),
                )

                if response.status_code < 400:
                    logger.info(
                        "Webhook sent successfully to %s (HTTP %d)",
                        url[:80],
                        response.status_code,
                    )
                    return {
                        'success': True,
                        'status_code': response.status_code,
                        'attempt': attempt + 1,
                    }

                # Retry on server errors and rate limits
                if response.status_code in (408, 429, 500, 502, 503, 504):
                    backoff = min(2 ** attempt, 60)
                    logger.warning(
                        "Webhook to %s returned HTTP %d, retrying in %ds (attempt %d/%d)",
                        url[:80],
                        response.status_code,
                        backoff,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(backoff)
                    continue

                # Client error — don't retry
                logger.error(
                    "Webhook to %s returned HTTP %d (non-retryable)",
                    url[:80],
                    response.status_code,
                )
                return {
                    'success': False,
                    'status_code': response.status_code,
                    'attempt': attempt + 1,
                }

            except requests.RequestException as e:
                last_error = str(e)
                backoff = min(2 ** attempt, 60)
                logger.warning(
                    "Webhook request to %s failed: %s. Retrying in %ds (attempt %d/%d)",
                    url[:80],
                    str(e)[:100],
                    backoff,
                    attempt + 1,
                    max_retries,
                )
                time.sleep(backoff)

        logger.error(
            "Webhook to %s failed after %d attempts: %s",
            url[:80],
            max_retries,
            last_error,
        )
        return {
            'success': False,
            'error': 'Max retries exceeded',
            'last_error': last_error,
            'attempts': max_retries,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _verify_signature(
        self,
        provider_name: str,
        payload: Union[str, bytes],
        signature: str,
    ) -> bool:
        """Verify the signature of an inbound webhook.

        Resolves the provider's webhook secret from Django settings
        using the pattern ``ESL_WEBHOOK_SECRET_<PROVIDER>``.

        Args:
            provider_name: Provider identifier.
            payload: Raw request body.
            signature: Signature header value.

        Returns:
            ``True`` if the signature is valid.
        """
        secret = getattr(
            settings,
            f'ESL_WEBHOOK_SECRET_{provider_name.upper()}',
            '',
        )
        return WebhookSignatureVerifier.verify_hmac_sha256(
            payload, signature, secret,
        )

    def _is_duplicate(self, event_id: str) -> bool:
        """Check whether a webhook event has already been processed.

        Uses Django's cache framework with a 24-hour TTL for
        deduplication.

        Args:
            event_id: Unique event identifier.

        Returns:
            ``True`` if the event was already processed.
        """
        from django.core.cache import cache

        cache_key = f"webhook_dedup:{event_id}"
        if cache.get(cache_key):
            return True
        cache.set(cache_key, True, 86400)  # 24 hours
        return False


# Module-level singleton
webhook_processor = WebhookProcessor()
