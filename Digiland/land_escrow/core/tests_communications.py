"""Test suite for Digiland Communications Architecture.

Covers:
1. ConversationService & MessageService (internal messaging)
2. NotificationService & Resend Provider
3. SecurityEvent auditing & security alert thresholds
4. Real-time delivery acknowledgments and Webhook processing
"""

import json
from unittest.mock import patch
from django.test import TestCase, Client
from django.utils import timezone
from django.core.cache import cache

from core.models import (
    User,
    Conversation,
    ConversationParticipant,
    Message,
    Notification,
    SecurityEvent,
)
from core.services.messaging import ConversationService, MessageService
from core.services.notifications import (
    NotificationService,
    ResendEmailProvider,
)


class InternalMessagingTests(TestCase):
    """Verify internal messaging logic, conversation threading, and status tracking."""

    def setUp(self):
        cache.clear()
        self.user_a = User.objects.create_user(
            email='alice@example.com',
            password='TestPassword123!',
            role='Buyer',
            is_email_verified=True,
        )
        self.user_b = User.objects.create_user(
            email='bob@example.com',
            password='TestPassword123!',
            role='Seller',
            is_email_verified=True,
        )

    def test_get_or_create_direct_conversation(self):
        conv1, created1 = ConversationService.get_or_create_direct_conversation(self.user_a, self.user_b)
        self.assertTrue(created1)
        self.assertEqual(conv1.conversation_type, 'DIRECT')
        self.assertEqual(conv1.participants.count(), 2)

        # Calling again between same users should return existing conversation
        conv2, created2 = ConversationService.get_or_create_direct_conversation(self.user_b, self.user_a)
        self.assertFalse(created2)
        self.assertEqual(conv1.id, conv2.id)

    def test_send_message_updates_timestamps_and_status(self):
        conv, _ = ConversationService.get_or_create_direct_conversation(self.user_a, self.user_b)
        msg = MessageService.send_message(
            sender=self.user_a,
            conversation_id=conv.id,
            content="Hello Bob, inquiring about the parcel.",
            client_message_id="msg-uuid-1",
        )

        self.assertEqual(msg.status, 'SENT')
        self.assertEqual(msg.content, "Hello Bob, inquiring about the parcel.")
        self.assertEqual(msg.receiver, self.user_b)
        self.assertEqual(msg.client_message_id, "msg-uuid-1")

        conv.refresh_from_db()
        self.assertIsNotNone(conv.last_message_at)

    def test_send_message_idempotency(self):
        conv, _ = ConversationService.get_or_create_direct_conversation(self.user_a, self.user_b)
        msg1 = MessageService.send_message(
            sender=self.user_a,
            conversation_id=conv.id,
            content="Duplicate check",
            client_message_id="idem-key-100",
        )
        msg2 = MessageService.send_message(
            sender=self.user_a,
            conversation_id=conv.id,
            content="Duplicate check",
            client_message_id="idem-key-100",
        )
        self.assertEqual(msg1.id, msg2.id)
        self.assertEqual(Message.objects.filter(client_message_id="idem-key-100").count(), 1)

    def test_mark_delivered_and_read(self):
        conv, _ = ConversationService.get_or_create_direct_conversation(self.user_a, self.user_b)
        msg = MessageService.send_message(
            sender=self.user_a,
            conversation_id=conv.id,
            content="Test read receipt",
        )
        self.assertEqual(msg.status, 'SENT')

        # Bob receives the message
        MessageService.mark_delivered(self.user_b, [msg.id])
        msg.refresh_from_db()
        self.assertEqual(msg.status, 'DELIVERED')
        self.assertIsNotNone(msg.delivered_at)

        # Bob reads the message
        MessageService.mark_read(self.user_b, conv.id)
        msg.refresh_from_db()
        self.assertEqual(msg.status, 'READ')
        self.assertTrue(msg.is_read)
        self.assertIsNotNone(msg.read_at)

    def test_unread_count_for_conversation(self):
        conv, _ = ConversationService.get_or_create_direct_conversation(self.user_a, self.user_b)
        MessageService.send_message(self.user_a, conv.id, "Message 1")
        MessageService.send_message(self.user_a, conv.id, "Message 2")

        # Bob should have 2 unread
        self.assertEqual(ConversationService.get_unread_count_for_conversation(self.user_b, conv), 2)
        # Alice should have 0 unread (she sent them)
        self.assertEqual(ConversationService.get_unread_count_for_conversation(self.user_a, conv), 0)

        # Mark read for Bob
        MessageService.mark_read(self.user_b, conv.id)
        self.assertEqual(ConversationService.get_unread_count_for_conversation(self.user_b, conv), 0)


class NotificationServiceTests(TestCase):
    """Verify external email delivery through NotificationService."""

    def setUp(self):
        cache.clear()
        NotificationService._email_provider = ResendEmailProvider()
        self.user = User.objects.create_user(
            email='carol@example.com',
            password='TestPassword123!',
            role='Buyer',
        )

    def tearDown(self):
        NotificationService._email_provider = None


    def test_send_email_creates_notification_record(self):
        with patch.object(ResendEmailProvider, 'send', return_value={'provider_message_id': 'resend_msg_123', 'status': 'SENT'}):
            notif = NotificationService.send_email(
                user=self.user,
                notification_type='ACCOUNT_ACTIVATION',
                subject='Verify Your Email',
                html_body='<p>Click here to verify</p>',
                text_body='Click here to verify',
                idempotency_key='activation_carol_1',
            )

            self.assertEqual(notif.status, 'SENT')
            self.assertEqual(notif.provider_message_id, 'resend_msg_123')
            self.assertEqual(notif.notification_type, 'ACCOUNT_ACTIVATION')
            self.assertEqual(notif.channel, 'EMAIL')

    def test_notification_idempotency_prevents_duplicate_send(self):
        with patch.object(ResendEmailProvider, 'send', return_value={'provider_message_id': 'msg_1', 'status': 'SENT'}) as mock_send:
            n1 = NotificationService.send_email(
                user=self.user,
                notification_type='SECURITY_ALERT_FAILED_LOGINS',
                subject='Security Alert',
                html_body='<p>Alert</p>',
                idempotency_key='alert_key_unique',
            )
            n2 = NotificationService.send_email(
                user=self.user,
                notification_type='SECURITY_ALERT_FAILED_LOGINS',
                subject='Security Alert',
                html_body='<p>Alert</p>',
                idempotency_key='alert_key_unique',
            )
            self.assertEqual(n1.id, n2.id)
            # Only sent once to provider
            self.assertEqual(mock_send.call_count, 1)

    def test_webhook_updates_notification_status(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type='OFFER_RECEIVED',
            channel='EMAIL',
            status='SENT',
            provider_message_id='resend_test_webhook_id',
        )

        updated = NotificationService.update_from_webhook(
            provider_message_id='resend_test_webhook_id',
            status='DELIVERED',
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, 'DELIVERED')
        self.assertIsNotNone(updated.delivered_at)


class SecurityAlertAndAuthTests(TestCase):
    """Verify security event audit logging and brute-force alert emails."""

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = User.objects.create_user(
            email='target@example.com',
            password='CorrectPassword123!',
            is_email_verified=True,
        )

    def test_failed_login_logs_security_event(self):
        self.client.post(
            '/api/v1/auth/login/',
            data=json.dumps({'email': 'target@example.com', 'password': 'WrongPassword'}),
            content_type='application/json',
        )

        event = SecurityEvent.objects.filter(email='target@example.com', event_type='LOGIN_FAILED').first()
        self.assertIsNotNone(event)
        self.assertEqual(event.user, self.user)

    def test_failed_login_threshold_triggers_alert(self):
        with patch('core.services.notifications.NotificationService.send_email') as mock_send_email:
            # Simulate 5 consecutive failed login attempts
            for _ in range(5):
                self.client.post(
                    '/api/v1/auth/login/',
                    data=json.dumps({'email': 'target@example.com', 'password': 'WrongPassword'}),
                    content_type='application/json',
                )

            # Security alert email should have been sent
            self.assertTrue(mock_send_email.called)
            args, kwargs = mock_send_email.call_args
            self.assertEqual(kwargs['notification_type'], 'SECURITY_ALERT_FAILED_LOGINS')
            self.assertIn('Digiland Security Alert', kwargs['subject'])

            # Suspicious login security event logged
            suspicious = SecurityEvent.objects.filter(
                email='target@example.com', event_type='SUSPICIOUS_LOGIN'
            ).first()
            self.assertIsNotNone(suspicious)


class ApiEndpointsTests(TestCase):
    """Verify HTTP endpoints for SSE delivery acknowledgment and Resend webhooks."""

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = User.objects.create_user(
            email='dan@example.com',
            password='TestPassword123!',
            is_email_verified=True,
        )
        self.client.force_login(self.user)

    def test_acknowledge_delivery_endpoint(self):
        other = User.objects.create_user(email='other@example.com', password='pw')
        conv, _ = ConversationService.get_or_create_direct_conversation(other, self.user)
        msg = MessageService.send_message(sender=other, conversation_id=conv.id, content='Hi Dan')

        resp = self.client.post(
            '/messages/acknowledge/',
            data=json.dumps({'message_ids': [str(msg.id)]}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['acknowledged'], 1)

        msg.refresh_from_db()
        self.assertEqual(msg.status, 'DELIVERED')

    def test_resend_webhook_endpoint(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type='ACCOUNT_ACTIVATION',
            channel='EMAIL',
            status='SENT',
            provider_message_id='wh_test_email_id_99',
        )

        resp = self.client.post(
            '/api/v1/webhooks/resend/',
            data=json.dumps({
                'type': 'email.delivered',
                'data': {'email_id': 'wh_test_email_id_99'},
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)

        notif.refresh_from_db()
        self.assertEqual(notif.status, 'DELIVERED')
