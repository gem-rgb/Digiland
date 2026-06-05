"""
Event-driven integration framework for the External Services Layer.

Supports Redis Pub/Sub, Celery, and local (in-process) event backends.
Enables loose coupling between service components by publishing and
subscribing to integration events.

Usage::

    from external_services.events import event_publisher

    # Subscribe to events
    def on_payment_completed(event):
        transaction = Transaction.objects.get(id=event.data['transaction_id'])
        transaction.mark_completed()

    event_publisher.subscribe('payment.completed', on_payment_completed)

    # Publish an event
    event = IntegrationEvent(
        event_type='payment.completed',
        source='paystack',
        data={'transaction_id': 'abc123', 'amount': 50000},
        correlation_id='trace-123',
    )
    event_publisher.publish(event)
"""

import json
import uuid
import logging
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger('external_services.events')


@dataclass
class IntegrationEvent:
    """Represents an event in the External Services Layer.

    Events carry information about something that happened in the
    system — a payment was completed, a webhook was received, a
    provider went down, etc.

    Attributes:
        event_id: Unique identifier for this event instance.
        event_type: Type of event (e.g. ``payment.completed``).
        source: Origin of the event (e.g. ``paystack``).
        data: Event-specific payload.
        metadata: Optional metadata (correlation IDs, tracing info).
        timestamp: ISO 8601 timestamp when the event was created.
        correlation_id: Links events across service boundaries.
        tenant_id: Tenant context for multi-tenant deployments.
    """

    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    event_type: str = ''
    source: str = ''
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    correlation_id: Optional[str] = None
    tenant_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the event to a dictionary.

        Returns:
            A JSON-serializable dictionary representation.
        """
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'source': self.source,
            'data': self.data,
            'metadata': self.metadata,
            'timestamp': self.timestamp,
            'correlation_id': self.correlation_id,
            'tenant_id': self.tenant_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IntegrationEvent':
        """Deserialize an event from a dictionary.

        Args:
            data: Dictionary representation of an event.

        Returns:
            An :class:`IntegrationEvent` instance.
        """
        return cls(
            event_id=data.get('event_id', uuid.uuid4().hex),
            event_type=data.get('event_type', ''),
            source=data.get('source', ''),
            data=data.get('data', {}),
            metadata=data.get('metadata', {}),
            timestamp=data.get('timestamp', datetime.utcnow().isoformat()),
            correlation_id=data.get('correlation_id'),
            tenant_id=data.get('tenant_id'),
        )


class EventPublisher:
    """Publishes and dispatches integration events.

    Supports multiple backends:

    * ``redis`` — Publishes to Redis Pub/Sub channels (production).
    * ``celery`` — Dispatches events as Celery tasks (async processing).
    * ``local`` — Synchronous in-process dispatch (testing / fallback).

    Subscribers register handlers for specific event types.  A
    catch-all handler can be registered for the ``*`` event type.
    """

    def __init__(self, backend: Optional[str] = None) -> None:
        """Initialize the event publisher.

        Args:
            backend: Event backend to use.  If ``None``, reads from
                ``settings.ESL_EVENT_BACKEND`` (default: ``redis``).
        """
        from django.conf import settings

        self._backend = backend or getattr(
            settings, 'ESL_EVENT_BACKEND', 'redis',
        )
        self._subscribers: Dict[str, List[Callable]] = {}

    def publish(self, event: IntegrationEvent) -> None:
        """Publish an integration event.

        The event is dispatched through the configured backend.  If the
        backend is unavailable, falls back to local dispatch.

        Args:
            event: The event to publish.
        """
        payload = json.dumps(event.to_dict(), default=str)
        try:
            if self._backend == 'celery':
                self._publish_celery(event, payload)
            elif self._backend == 'redis':
                self._publish_redis(event, payload)
            else:
                self._dispatch_local(event)

            logger.info(
                "Event published: %s [%s]",
                event.event_type,
                event.event_id,
            )
        except Exception as e:
            logger.error(
                "Event publish failed: %s - %s",
                event.event_type,
                str(e),
            )

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Register a handler for a specific event type.

        Args:
            event_type: Event type to subscribe to (``*`` for all).
            handler: Callable that receives an :class:`IntegrationEvent`.
        """
        self._subscribers.setdefault(event_type, []).append(handler)
        logger.info(
            "Event subscriber registered: '%s' → %s",
            event_type,
            handler.__name__,
        )

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """Remove a previously registered handler.

        Args:
            event_type: Event type the handler was subscribed to.
            handler: The handler to remove.
        """
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    # ------------------------------------------------------------------
    # Backend implementations
    # ------------------------------------------------------------------

    def _dispatch_local(self, event: IntegrationEvent) -> None:
        """Dispatch an event synchronously to all matching handlers.

        This is the fallback backend and is also used for testing.

        Args:
            event: The event to dispatch.
        """
        handlers = (
            self._subscribers.get(event.event_type, [])
            + self._subscribers.get('*', [])
        )

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    "Event handler error for %s: %s",
                    event.event_type,
                    str(e),
                )

    def _publish_redis(self, event: IntegrationEvent, payload: str) -> None:
        """Publish an event to a Redis Pub/Sub channel.

        The channel name follows the pattern ``esl:events:<event_type>``.

        Args:
            event: The event to publish.
            payload: JSON-serialized event data.
        """
        try:
            import redis
            from django.conf import settings as django_settings

            client = redis.from_url(
                getattr(django_settings, 'REDIS_URL', 'redis://localhost:6379/0'),
            )
            channel = f"esl:events:{event.event_type}"
            client.publish(channel, payload)

            # Also dispatch locally for same-process subscribers
            self._dispatch_local(event)
        except Exception as e:
            logger.warning(
                "Redis publish failed, falling back to local: %s",
                str(e),
            )
            self._dispatch_local(event)

    def _publish_celery(
        self,
        event: IntegrationEvent,
        payload: str,
    ) -> None:
        """Publish an event as a Celery task.

        Falls back to local dispatch if Celery is not available.

        Args:
            event: The event to publish.
            payload: JSON-serialized event data.
        """
        try:
            from core.tasks import process_esl_event

            process_esl_event.delay(event.to_dict())
            # Also dispatch locally for immediate processing
            self._dispatch_local(event)
        except ImportError:
            logger.debug("Celery task not found, using local dispatch")
            self._dispatch_local(event)
        except Exception as e:
            logger.warning(
                "Celery dispatch failed, falling back to local: %s",
                str(e),
            )
            self._dispatch_local(event)


# Module-level singleton
event_publisher = EventPublisher()
