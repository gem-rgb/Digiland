"""Messaging services for Digiland internal communication.

Provides MessageService and ConversationService for thread-based messaging
with proper persistence, delivery tracking, and permission checks.
"""

import logging
import uuid as _uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Count, Max, Subquery, OuterRef, Exists
from django.utils import timezone

logger = logging.getLogger(__name__)


class ConversationService:
    """Manages conversations and participant membership."""

    @staticmethod
    def get_or_create_direct_conversation(user_a, user_b, *, tenant_id=None):
        """Find or create a DIRECT conversation between exactly two users.

        Returns (conversation, created) tuple.
        """
        from core.models import Conversation, ConversationParticipant

        # Look for an existing DIRECT conversation containing both users
        existing = Conversation.objects.filter(
            conversation_type='DIRECT',
            is_active=True,
            deleted_at__isnull=True,
        ).filter(
            participants__user=user_a,
            participants__is_active=True,
        ).filter(
            pk__in=Conversation.objects.filter(
                participants__user=user_b,
                participants__is_active=True,
            ).values('pk'),
        ).first()

        if existing:
            return existing, False

        with transaction.atomic():
            conv = Conversation.objects.create(
                conversation_type='DIRECT',
                tenant_id=tenant_id,
            )
            ConversationParticipant.objects.create(
                conversation=conv, user=user_a, role='MEMBER',
            )
            ConversationParticipant.objects.create(
                conversation=conv, user=user_b, role='MEMBER',
            )
            return conv, True

    @staticmethod
    def create_group_conversation(creator, participants, *, conversation_type='GROUP',
                                  title='', transaction_obj=None, parcel=None, tenant_id=None):
        """Create a multi-participant conversation."""
        from core.models import Conversation, ConversationParticipant

        with transaction.atomic():
            conv = Conversation.objects.create(
                conversation_type=conversation_type,
                title=title,
                transaction=transaction_obj,
                parcel=parcel,
                tenant_id=tenant_id,
            )
            ConversationParticipant.objects.create(
                conversation=conv, user=creator, role='ADMIN',
            )
            for user in participants:
                if user.id != creator.id:
                    ConversationParticipant.objects.create(
                        conversation=conv, user=user, role='MEMBER',
                    )
            return conv

    @staticmethod
    def get_user_conversations(user, *, limit=50, offset=0):
        """Return conversations the user participates in, ordered by last activity.

        Includes unread message count for each conversation.
        """
        from core.models import Conversation, ConversationParticipant, Message

        participant_convs = ConversationParticipant.objects.filter(
            user=user, is_active=True,
        ).values_list('conversation_id', flat=True)

        conversations = Conversation.objects.filter(
            id__in=participant_convs,
            is_active=True,
            deleted_at__isnull=True,
        ).prefetch_related(
            'participants__user',
        ).order_by('-last_message_at', '-created_at')[offset:offset + limit]

        return conversations

    @staticmethod
    def get_unread_count_for_conversation(user, conversation):
        """Count unread messages in a conversation for a given user."""
        from core.models import ConversationParticipant, Message

        participant = ConversationParticipant.objects.filter(
            conversation=conversation, user=user, is_active=True,
        ).first()
        if not participant:
            return 0

        qs = Message.objects.filter(
            conversation=conversation,
            deleted_at__isnull=True,
        ).exclude(sender=user)

        if participant.last_read_message_id:
            # Count messages created after the last read message
            last_read_msg = Message.objects.filter(id=participant.last_read_message_id).values('timestamp').first()
            if last_read_msg:
                qs = qs.filter(timestamp__gt=last_read_msg['timestamp'])
        elif participant.last_read_at:
            qs = qs.filter(timestamp__gt=participant.last_read_at)
        else:
            # Never read — all messages are unread
            pass

        return qs.count()

    @staticmethod
    def is_participant(user, conversation_id):
        """Check if user is an active participant of a conversation."""
        from core.models import ConversationParticipant
        return ConversationParticipant.objects.filter(
            conversation_id=conversation_id, user=user, is_active=True,
        ).exists()

    @staticmethod
    def get_conversation_partner(user, conversation):
        """For DIRECT conversations, return the other participant."""
        from core.models import ConversationParticipant
        participant = ConversationParticipant.objects.filter(
            conversation=conversation, is_active=True,
        ).exclude(user=user).select_related('user').first()
        return participant.user if participant else None


class MessageService:
    """Handles message creation, persistence, delivery, and retrieval."""

    @staticmethod
    def send_message(sender, conversation_id, content, *,
                     client_message_id='', message_type='TEXT',
                     reply_to_id=None, metadata=None):
        """Persist a message and publish a real-time event.

        Flow:
        1. Validate sender is a participant
        2. Deduplicate via client_message_id
        3. Create Message record (status=SENT)
        4. Update conversation.last_message_at
        5. Publish real-time event via Redis
        """
        from core.models import Conversation, Message

        # Validate sender membership
        if not ConversationService.is_participant(sender, conversation_id):
            raise PermissionError("You are not a participant of this conversation.")

        conversation = Conversation.objects.get(id=conversation_id)

        # Idempotency check
        if client_message_id:
            existing = Message.objects.filter(
                client_message_id=client_message_id,
                sender=sender,
                conversation=conversation,
            ).first()
            if existing:
                return existing

        # Determine receiver for backward compat (DIRECT conversations)
        receiver = None
        if conversation.conversation_type == 'DIRECT':
            receiver = ConversationService.get_conversation_partner(sender, conversation)

        with transaction.atomic():
            msg = Message.objects.create(
                conversation=conversation,
                sender=sender,
                receiver=receiver,
                content=content,
                message_type=message_type,
                status='SENT',
                client_message_id=client_message_id,
                reply_to_id=reply_to_id,
                metadata=metadata or {},
                tenant_id=conversation.tenant_id,
            )
            # Update conversation timestamp
            Conversation.objects.filter(id=conversation_id).update(
                last_message_at=msg.timestamp,
            )

        # Publish real-time event (best-effort, does not block persistence)
        try:
            _publish_message_event(msg, conversation)
        except Exception:
            logger.exception("Failed to publish real-time event for message %s", msg.id)

        return msg

    @staticmethod
    def send_legacy_message(sender, receiver, content, *, transaction_obj=None):
        """Send a message using the legacy sender/receiver pattern.

        Auto-creates a DIRECT conversation if one doesn't exist.
        This ensures backward compatibility with existing code.
        """
        conv, _ = ConversationService.get_or_create_direct_conversation(sender, receiver)

        return MessageService.send_message(
            sender, conv.id, content,
            client_message_id=str(_uuid.uuid4()),
        )

    @staticmethod
    def get_conversation_messages(user, conversation_id, *, limit=50, before_id=None):
        """Paginated message retrieval — newest first, cursor-based.

        Returns messages before `before_id` for infinite scroll.
        """
        from core.models import Message

        if not ConversationService.is_participant(user, conversation_id):
            raise PermissionError("You are not a participant of this conversation.")

        qs = Message.objects.filter(
            conversation_id=conversation_id,
            deleted_at__isnull=True,
        ).select_related('sender', 'receiver').order_by('-timestamp')

        if before_id:
            cursor_msg = Message.objects.filter(id=before_id).values('timestamp').first()
            if cursor_msg:
                qs = qs.filter(timestamp__lt=cursor_msg['timestamp'])

        return list(qs[:limit])

    @staticmethod
    def mark_delivered(user, message_ids):
        """Mark messages as delivered for a recipient."""
        from core.models import Message
        now = timezone.now()
        Message.objects.filter(
            id__in=message_ids,
            status__in=['SENT'],
            deleted_at__isnull=True,
        ).exclude(sender=user).update(
            status='DELIVERED',
            delivered_at=now,
        )

    @staticmethod
    def mark_read(user, conversation_id):
        """Mark all messages in a conversation as read for a user."""
        from core.models import Message, ConversationParticipant

        if not ConversationService.is_participant(user, conversation_id):
            return

        now = timezone.now()
        # Update messages
        updated = Message.objects.filter(
            conversation_id=conversation_id,
            deleted_at__isnull=True,
        ).exclude(sender=user).filter(
            Q(status__in=['SENT', 'DELIVERED']) | Q(is_read=False),
        ).update(
            is_read=True,
            read_at=now,
            status='READ',
        )

        # Update participant's last read state
        last_msg = Message.objects.filter(
            conversation_id=conversation_id,
            deleted_at__isnull=True,
        ).order_by('-timestamp').values('id').first()

        if last_msg:
            ConversationParticipant.objects.filter(
                conversation_id=conversation_id, user=user,
            ).update(
                last_read_message_id=last_msg['id'],
                last_read_at=now,
            )

        return updated

    @staticmethod
    def get_total_unread_count(user):
        """Get total unread message count across all conversations."""
        from core.models import ConversationParticipant, Message

        total = 0
        memberships = ConversationParticipant.objects.filter(
            user=user, is_active=True,
        ).select_related('conversation')

        for membership in memberships:
            qs = Message.objects.filter(
                conversation=membership.conversation,
                deleted_at__isnull=True,
            ).exclude(sender=user)

            if membership.last_read_at:
                qs = qs.filter(timestamp__gt=membership.last_read_at)
            elif membership.last_read_message_id:
                last_msg = Message.objects.filter(id=membership.last_read_message_id).values('timestamp').first()
                if last_msg:
                    qs = qs.filter(timestamp__gt=last_msg['timestamp'])

            total += qs.count()

        return total


def migrate_orphan_messages(user):
    """Auto-migrate legacy Message records (without conversation) into conversations.

    Called lazily when a user accesses their messages.
    """
    from core.models import Message

    orphans = Message.objects.filter(
        conversation__isnull=True,
        deleted_at__isnull=True,
    ).filter(Q(sender=user) | Q(receiver=user)).select_related('sender', 'receiver')

    if not orphans.exists():
        return

    partner_map = {}
    for msg in orphans:
        partner = msg.receiver if msg.sender == user else msg.sender
        if partner and partner.id not in partner_map:
            partner_map[partner.id] = partner

    for partner in partner_map.values():
        conv, _ = ConversationService.get_or_create_direct_conversation(user, partner)

        # Assign orphan messages to the conversation
        Message.objects.filter(
            conversation__isnull=True,
            deleted_at__isnull=True,
        ).filter(
            Q(sender=user, receiver=partner) | Q(sender=partner, receiver=user),
        ).update(conversation=conv)

        # Update conversation last_message_at
        last_msg = Message.objects.filter(conversation=conv).order_by('-timestamp').values('timestamp').first()
        if last_msg:
            Conversation.objects.filter(id=conv.id).update(last_message_at=last_msg['timestamp'])

    logger.info("Migrated orphan messages for user %s into %d conversations", user.email, len(partner_map))


def _publish_message_event(message, conversation):
    """Publish a new-message event via Redis pub/sub for SSE delivery."""
    import json
    try:
        from django.core.cache import cache
        # Use Redis pub/sub via the cache backend
        redis_client = getattr(cache, 'client', None)
        if redis_client is None:
            # Try to get raw Redis connection
            try:
                import redis as _redis
                redis_url = getattr(settings, 'CACHES', {}).get('default', {}).get('LOCATION', '')
                if redis_url:
                    redis_client = _redis.from_url(redis_url)
            except Exception:
                pass

        if redis_client is None:
            return

        from core.models import ConversationParticipant
        participants = ConversationParticipant.objects.filter(
            conversation=conversation, is_active=True,
        ).exclude(user=message.sender).values_list('user_id', flat=True)

        event_data = json.dumps({
            'type': 'new_message',
            'message': {
                'id': str(message.id),
                'conversation_id': str(conversation.id),
                'sender_id': str(message.sender_id),
                'sender_email': message.sender.email,
                'content': message.content,
                'message_type': message.message_type,
                'status': message.status,
                'timestamp': message.timestamp.isoformat(),
                'client_message_id': message.client_message_id,
            },
        })

        for user_id in participants:
            channel = f"digiland:messages:{user_id}"
            try:
                redis_client.publish(channel, event_data)
            except Exception:
                logger.debug("Failed to publish to channel %s", channel)

    except Exception:
        logger.exception("Redis pub/sub publish failed for message %s", message.id)
