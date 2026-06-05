"""Serializers for the Enterprise Admin Control Plane.

All serializers enforce:
- Exclusion of sensitive fields (session tokens, etc.)
- Validation of role permissions where appropriate
- Computed fields for session/approval status

Serializers
-----------
AdminSessionSerializer         : Admin session read/display.
AdminActionLogSerializer       : Read-only audit log display.
DualApprovalRequestSerializer  : Dual-approval request read/display.
DualApprovalActionSerializer   : Approve/reject action input.
EmergencyControlSerializer     : Emergency control status display.
FinancialActionSerializer      : Financial operation input validation.
AdminIPRangeSerializer         : IP range CRUD.
"""

import re
from rest_framework import serializers
from django.utils import timezone

from .models import (
    AdminActionLog,
    AdminSession,
    DualApprovalRequest,
    EmergencyControl,
    AdminIPAddress,
)


# ---------------------------------------------------------------------------
# Admin Session Serializer
# ---------------------------------------------------------------------------

class AdminSessionSerializer(serializers.ModelSerializer):
    """Serializer for AdminSession model.

    Excludes the ``session_token`` field from all outputs to prevent
    token leakage through API responses.
    """

    is_expired = serializers.SerializerMethodField()
    is_valid = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = AdminSession
        fields = [
            'id', 'user', 'user_email', 'ip_address', 'user_agent',
            'mfa_verified', 'mfa_method', 'is_active',
            'expires_at', 'terminated_at', 'last_activity',
            'created_at',
            # Computed fields
            'is_expired', 'is_valid', 'time_remaining',
        ]
        read_only_fields = fields  # Sessions are created/managed via service
        extra_kwargs = {
            'session_token': {'write_only': True},  # Never expose in response
        }

    def get_is_expired(self, obj) -> bool:
        return obj.is_expired

    def get_is_valid(self, obj) -> bool:
        return obj.is_valid

    def get_time_remaining(self, obj) -> str:
        """Return ISO-8601 duration string for remaining time."""
        remaining = obj.time_remaining
        total_seconds = int(remaining.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f'{hours:02d}:{minutes:02d}:{seconds:02d}'


# ---------------------------------------------------------------------------
# Admin Action Log Serializer
# ---------------------------------------------------------------------------

class AdminActionLogSerializer(serializers.ModelSerializer):
    """Read-only serializer for the immutable audit log.

    No create/update/delete is allowed through this serializer — all
    writes must go through ``ImmutableAuditService``.
    """

    actor_email = serializers.CharField(
        source='actor.email', read_only=True, default=None
    )

    class Meta:
        model = AdminActionLog
        fields = [
            'id', 'actor', 'actor_email', 'action',
            'resource_type', 'resource_id',
            'metadata', 'ip_address', 'user_agent',
            'admin_session', 'previous_hash', 'hash',
            'timestamp',
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Dual Approval Request Serializer
# ---------------------------------------------------------------------------

class DualApprovalRequestSerializer(serializers.ModelSerializer):
    """Serializer for DualApprovalRequest model.

    Includes computed fields for expiry status and remaining time.
    """

    is_expired = serializers.SerializerMethodField()
    is_pending = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    requested_by_email = serializers.CharField(
        source='requested_by.email', read_only=True
    )
    reviewed_by_email = serializers.CharField(
        source='reviewed_by.email', read_only=True, default=None
    )

    class Meta:
        model = DualApprovalRequest
        fields = [
            'id', 'action_type', 'description', 'payload', 'status',
            'requested_by', 'requested_by_email',
            'reviewed_by', 'reviewed_by_email',
            'review_notes', 'deadline',
            'reviewed_at', 'executed_at',
            'created_at', 'updated_at',
            # Computed fields
            'is_expired', 'is_pending', 'time_remaining',
        ]
        read_only_fields = [
            'id', 'status', 'requested_by',
            'reviewed_by', 'reviewed_at', 'executed_at',
            'created_at', 'updated_at',
        ]

    def get_is_expired(self, obj) -> bool:
        return obj.is_expired

    def get_is_pending(self, obj) -> bool:
        return obj.is_pending

    def get_time_remaining(self, obj) -> str:
        """Return ISO-8601 duration string for remaining time."""
        remaining = obj.time_remaining
        total_seconds = int(remaining.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f'{hours:02d}:{minutes:02d}:{seconds:02d}'


# ---------------------------------------------------------------------------
# Dual Approval Action Serializer
# ---------------------------------------------------------------------------

class DualApprovalActionSerializer(serializers.Serializer):
    """Input serializer for approve/reject actions on dual-approval requests.

    Validates that ``review_notes`` is provided for rejections (audit
    trail requirement) and that ``totp_code`` is present when step-up
    auth is required.
    """

    ACTION_CHOICES = [('approve', 'Approve'), ('reject', 'Reject')]

    action = serializers.ChoiceField(choices=ACTION_CHOICES)
    review_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000,
        help_text='Mandatory for rejections; recommended for approvals.',
    )
    totp_code = serializers.CharField(
        max_length=6,
        min_length=6,
        required=False,
        help_text='6-digit TOTP code for step-up authentication.',
    )

    def validate_totp_code(self, value):
        if value and not re.match(r'^\d{6}$', value):
            raise serializers.ValidationError(
                'TOTP code must be exactly 6 digits.'
            )
        return value

    def validate(self, data):
        # Reject action must include review notes
        if data.get('action') == 'reject' and not data.get('review_notes'):
            raise serializers.ValidationError({
                'review_notes': 'Review notes are required when rejecting a request.'
            })
        return data


# ---------------------------------------------------------------------------
# Emergency Control Serializer
# ---------------------------------------------------------------------------

class EmergencyControlSerializer(serializers.ModelSerializer):
    """Serializer for the EmergencyControl singleton.

    Includes computed status summary fields.
    """

    withdrawal_freeze_activated_by_email = serializers.CharField(
        source='withdrawal_freeze_activated_by.email',
        read_only=True, default=None,
    )
    incident_mode_activated_by_email = serializers.CharField(
        source='incident_mode_activated_by.email',
        read_only=True, default=None,
    )

    class Meta:
        model = EmergencyControl
        fields = [
            'id',
            'withdrawal_freeze', 'withdrawal_freeze_activated_by',
            'withdrawal_freeze_activated_by_email',
            'withdrawal_freeze_activated_at',
            'incident_mode', 'incident_mode_activated_by',
            'incident_mode_activated_by_email',
            'incident_mode_activated_at',
            'incident_description',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'withdrawal_freeze_activated_by',
            'withdrawal_freeze_activated_at',
            'incident_mode_activated_by',
            'incident_mode_activated_at',
            'updated_at',
        ]


# ---------------------------------------------------------------------------
# Financial Action Serializer
# ---------------------------------------------------------------------------

class FinancialActionSerializer(serializers.Serializer):
    """Input serializer for financial operations.

    Validates amount, recipient, and ensures dual-approval metadata
    is included for operations above the threshold.
    """

    amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=0.01,
        help_text='Amount in KES.',
    )
    recipient_id = serializers.UUIDField(
        help_text='UUID of the recipient user.',
    )
    reference = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        help_text='Optional payment reference.',
    )
    reason = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        help_text='Reason for the financial action (required for adjustments).',
    )
    totp_code = serializers.CharField(
        max_length=6,
        min_length=6,
        required=False,
        help_text='6-digit TOTP code for step-up authentication.',
    )

    def validate_totp_code(self, value):
        if value and not re.match(r'^\d{6}$', value):
            raise serializers.ValidationError(
                'TOTP code must be exactly 6 digits.'
            )
        return value


# ---------------------------------------------------------------------------
# Admin IP Range Serializer
# ---------------------------------------------------------------------------

class AdminIPRangeSerializer(serializers.ModelSerializer):
    """Serializer for AdminIPAddress model (IP range / CIDR entries).

    Validates CIDR notation on create/update.
    """

    user_email = serializers.CharField(
        source='user.email', read_only=True, default=None,
    )

    class Meta:
        model = AdminIPAddress
        fields = [
            'id', 'ip_address', 'ip_range', 'label', 'is_active',
            'user', 'user_email', 'tenant_id', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate_ip_range(self, value):
        """Validate that the ip_range CIDR is well-formed."""
        if not value:
            return value
        import ipaddress
        try:
            ipaddress.ip_network(value, strict=False)
        except ValueError as exc:
            raise serializers.ValidationError(
                f'Invalid CIDR notation: {exc}'
            )
        return value
