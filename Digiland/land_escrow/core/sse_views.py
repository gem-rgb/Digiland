"""Server-Sent Events (SSE) views for real-time internal messaging and notifications.

Provides /messages/stream/ endpoint using StreamingHttpResponse.
Listens to Redis pub/sub if available, with resilient fallback to lightweight
database checks, ensuring zero downtime even if Redis is temporarily unreachable.
"""

import json
import logging
import time
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


def _sse_format(event_type: str, data: dict) -> str:
    """Format an SSE message."""
    payload = json.dumps(data)
    return f"event: {event_type}\ndata: {payload}\n\n"


@login_required
def message_stream(request):
    """
    SSE stream delivering real-time messages and notifications to the active user.
    Uses Redis Pub/Sub if available, with an automatic polling fallback.
    """
    user = request.user
    user_id = str(user.id)

    def event_stream():
        # Initial greeting with unread counts
        from core.services.messaging import MessageService
        from core.services.notifications import NotificationService

        unread_msgs = MessageService.get_total_unread_count(user)
        unread_notifs = NotificationService.get_unread_in_app_count(user)

        yield _sse_format("connected", {
            "status": "connected",
            "user_id": user_id,
            "unread_messages": unread_msgs,
            "unread_notifications": unread_notifs,
            "server_time": timezone.now().isoformat(),
        })

        # Try to connect to Redis pub/sub
        redis_pubsub = None
        channel_name = f"digiland:messages:{user_id}"
        notif_channel = f"digiland:notifications:{user_id}"

        try:
            from django.core.cache import cache
            client = getattr(cache, 'client', None)
            if client is None:
                import redis
                redis_url = getattr(settings, 'CACHES', {}).get('default', {}).get('LOCATION', '')
                if redis_url and 'redis' in redis_url:
                    client = redis.from_url(redis_url)
            if client:
                redis_pubsub = client.pubsub()
                redis_pubsub.subscribe(channel_name, notif_channel)
        except Exception:
            redis_pubsub = None

        last_heartbeat = time.time()
        last_check = timezone.now()

        try:
            while True:
                has_event = False

                # 1. Read from Redis pubsub if active
                if redis_pubsub:
                    try:
                        message = redis_pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                        if message and message.get('type') == 'message':
                            raw_data = message.get('data')
                            if isinstance(raw_data, bytes):
                                raw_data = raw_data.decode('utf-8')
                            event_obj = json.loads(raw_data)
                            yield _sse_format(event_obj.get('type', 'message'), event_obj)
                            has_event = True
                    except Exception:
                        redis_pubsub = None

                # 2. Resilient DB fallback if Redis is not connected
                if not redis_pubsub:
                    time.sleep(2.0)
                    from core.models import Message
                    recent_msgs = Message.objects.filter(
                        receiver=user,
                        timestamp__gt=last_check,
                        deleted_at__isnull=True,
                    ).select_related('sender').order_by('timestamp')

                    for msg in recent_msgs:
                        yield _sse_format("new_message", {
                            "message": {
                                "id": str(msg.id),
                                "conversation_id": str(msg.conversation_id) if msg.conversation_id else "",
                                "sender_id": str(msg.sender_id),
                                "sender_email": msg.sender.email,
                                "content": msg.content,
                                "message_type": msg.message_type,
                                "status": msg.status,
                                "timestamp": msg.timestamp.strftime('%b %d, %Y %H:%M'),
                                "client_message_id": msg.client_message_id,
                                "is_self": False,
                            }
                        })
                        last_check = max(last_check, msg.timestamp)
                        has_event = True

                # 3. Heartbeat ping every 20 seconds to prevent connection drops
                now = time.time()
                if now - last_heartbeat > 20:
                    yield _sse_format("ping", {"timestamp": timezone.now().isoformat()})
                    last_heartbeat = now

        except GeneratorExit:
            # Client disconnected
            if redis_pubsub:
                try:
                    redis_pubsub.unsubscribe(channel_name, notif_channel)
                    redis_pubsub.close()
                except Exception:
                    pass
            logger.debug("SSE stream disconnected for user %s", user.email)

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Content-Type'] = 'text/event-stream'
    return response


@login_required
@require_http_methods(["POST"])
def acknowledge_delivery(request):
    """
    Client acknowledges that messages were received/rendered on their screen.
    Updates Message status from SENT -> DELIVERED.
    """
    try:
        data = json.loads(request.body)
        message_ids = data.get('message_ids', [])
        if message_ids:
            from core.services.messaging import MessageService
            MessageService.mark_delivered(request.user, message_ids)
            return JsonResponse({'status': 'ok', 'acknowledged': len(message_ids)})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    return JsonResponse({'status': 'ok', 'acknowledged': 0})
