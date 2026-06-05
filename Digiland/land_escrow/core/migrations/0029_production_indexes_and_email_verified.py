# Migration 0029: Production indexes and email verification field
#
# This migration addresses findings from the production readiness audit:
#
# 1. Adds `is_email_verified` to User — email verification is now a separate
#    concern from identity verification (KRA PIN / ID).
#
# 2. Adds missing database indexes for high-frequency query patterns:
#    - User.role                — role-based access control filters
#    - AuditLog.user            — FK (no db_index by default on SET_NULL)
#    - AuditLog.action          — admin dashboard filtering
#    - AuditLog.timestamp       — chronological log queries
#    - AuditLog (user, action, timestamp) — composite for audit trail lookups
#    - Message.sender           — FK reverse lookup (sent messages)
#    - Message.receiver         — FK reverse lookup (received messages)
#    - Message.is_read          — unread message filter
#    - Message (receiver, is_read) — composite for unread inbox queries
#    - SupportTicket.user       — FK (user's tickets)
#    - SupportTicket.status     — admin queue filtering
#    - JointPaymentContribution.checkout_request_id — M-Pesa callback (CRITICAL)
#    - JointPaymentContribution.status — payment status queries
#    - JointPaymentContribution.transaction — FK lookup
#    - UserFavorite.saved_at    — chronological favorites (ordering ≠ index)

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0028_enable_rls'),
    ]

    operations = [
        # ── New field ───────────────────────────────────────────────────
        migrations.AddField(
            model_name='user',
            name='is_email_verified',
            field=models.BooleanField(
                default=False,
                help_text='Whether the user has verified their email address '
                          '(distinct from identity verification via KRA PIN/ID)',
            ),
        ),

        # ── User indexes ────────────────────────────────────────────────
        migrations.AddIndex(
            model_name='user',
            index=models.Index(fields=['role'], name='idx_user_role'),
        ),

        # ── AuditLog indexes ────────────────────────────────────────────
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['user'], name='idx_auditlog_user'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['action'], name='idx_auditlog_action'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['timestamp'], name='idx_auditlog_timestamp'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(
                fields=['user', 'action', 'timestamp'],
                name='idx_auditlog_user_action_ts',
            ),
        ),

        # ── Message indexes ─────────────────────────────────────────────
        migrations.AddIndex(
            model_name='message',
            index=models.Index(fields=['sender'], name='idx_message_sender'),
        ),
        migrations.AddIndex(
            model_name='message',
            index=models.Index(fields=['receiver'], name='idx_message_receiver'),
        ),
        migrations.AddIndex(
            model_name='message',
            index=models.Index(fields=['is_read'], name='idx_message_is_read'),
        ),
        migrations.AddIndex(
            model_name='message',
            index=models.Index(
                fields=['receiver', 'is_read'],
                name='idx_message_receiver_unread',
            ),
        ),

        # ── SupportTicket indexes ───────────────────────────────────────
        migrations.AddIndex(
            model_name='supportticket',
            index=models.Index(fields=['user'], name='idx_supportticket_user'),
        ),
        migrations.AddIndex(
            model_name='supportticket',
            index=models.Index(fields=['status'], name='idx_supportticket_status'),
        ),

        # ── JointPaymentContribution indexes ────────────────────────────
        migrations.AddIndex(
            model_name='jointpaymentcontribution',
            index=models.Index(
                fields=['checkout_request_id'],
                name='idx_jpc_checkout_request_id',
            ),
        ),
        migrations.AddIndex(
            model_name='jointpaymentcontribution',
            index=models.Index(fields=['status'], name='idx_jpc_status'),
        ),
        migrations.AddIndex(
            model_name='jointpaymentcontribution',
            index=models.Index(fields=['transaction'], name='idx_jpc_transaction'),
        ),

        # ── UserFavorite indexes ────────────────────────────────────────
        migrations.AddIndex(
            model_name='userfavorite',
            index=models.Index(fields=['saved_at'], name='idx_userfavorite_saved_at'),
        ),
    ]
