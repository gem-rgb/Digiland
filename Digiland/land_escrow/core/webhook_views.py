"""Webhook handlers for external providers (Resend).

Provides /api/v1/webhooks/resend/ to ingest email delivery events
(sent, delivered, bounced, complained) and update Notification records.
"""

import json
import logging

from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def resend_webhook(request):
    """
    Handle Resend email event webhooks.
    Verifies the Svix signature if RESEND_WEBHOOK_SECRET is set.
    """
    payload = request.body
    headers = {
        "svix-id": request.headers.get("svix-id", ""),
        "svix-timestamp": request.headers.get("svix-timestamp", ""),
        "svix-signature": request.headers.get("svix-signature", ""),
    }

    # Verify signature if secret is configured
    secret = getattr(settings, "RESEND_WEBHOOK_SECRET", "")
    if secret:
        try:
            from svix.webhooks import Webhook
            wh = Webhook(secret)
            wh.verify(payload, headers)
        except Exception as exc:
            logger.warning("Resend webhook signature verification failed: %s", exc)
            return JsonResponse({"error": "Invalid webhook signature"}, status=401)

    try:
        data = json.loads(payload)
    except Exception:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    event_type = data.get("type", "")
    event_data = data.get("data", {})

    logger.info("Resend webhook received: %s", event_type)

    # Dispatch to Celery task if running async, or process directly
    try:
        from core.tasks import process_resend_webhook_task
        process_resend_webhook_task.delay(event_type, event_data)
    except Exception:
        # Fallback to synchronous processing if Celery is not available
        from core.services.notifications import NotificationService
        email_id = event_data.get("email_id") or event_data.get("id")
        if email_id:
            status_map = {
                "email.sent": "SENT",
                "email.delivered": "DELIVERED",
                "email.bounced": "BOUNCED",
                "email.complained": "BOUNCED",
            }
            mapped_status = status_map.get(event_type)
            if mapped_status:
                NotificationService.update_from_webhook(
                    provider_message_id=email_id,
                    status=mapped_status,
                    metadata={"webhook_event": event_type},
                )

    return JsonResponse({"status": "ok", "received": event_type})
