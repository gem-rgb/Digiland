"""Django admin configuration for the Enterprise Admin Control Plane.

Customisations
--------------
- ``AdminActionLog`` is displayed as **read-only** — no add, change,
  or delete permissions are granted through the admin.
- ``AdminSession`` supports inline termination via a custom action.
- ``DualApprovalRequest`` shows a filtered list of pending items and
  provides approve/reject actions.
- ``EmergencyControl`` provides one-click emergency toggle actions.
- ``AdminIPAddress`` is a simple CRUD model.

Custom Admin Actions
--------------------
- ``activate_withdrawal_freeze`` : Toggle withdrawal freeze on.
- ``deactivate_withdrawal_freeze`` : Toggle withdrawal freeze off.
- ``activate_incident_mode`` : Toggle incident mode on.
- ``terminate_selected_sessions`` : Terminate selected admin sessions.
- ``expire_selected_approvals`` : Mark selected approvals as expired.
"""

import logging

from django.contrib import admin, messages
from django.utils import timezone

from .models import (
    AdminActionLog,
    AdminSession,
    DualApprovalRequest,
    EmergencyControl,
    AdminIPAddress,
)
from .services import (
    EmergencyControlService,
    ImmutableAuditService,
)

logger = logging.getLogger(__name__)


# ===========================================================================
# Admin Action Log — strictly read-only
# ===========================================================================

@admin.register(AdminActionLog)
class AdminActionLogAdmin(admin.ModelAdmin):
    """Read-only admin for the immutable audit log.

    No add, change, or delete operations are permitted through the
    Django admin.  All writes must flow through ``ImmutableAuditService``.
    """

    list_display = [
        'timestamp', 'actor_email', 'action_type', 'resource_type',
        'resource_id', 'ip_address', 'hash_short',
    ]
    list_filter = ['action_type', 'resource_type', 'timestamp']
    search_fields = ['action_type', 'resource_id', 'ip_address']
    readonly_fields = [
        'id', 'actor', 'action_type', 'resource_type', 'resource_id',
        'action_details', 'ip_address', 'user_agent', 'device_fingerprint',
        'session', 'previous_hash', 'hash', 'timestamp',
        'step_up_auth', 'dual_approval', 'approver', 'risk_score', 'is_flagged',
    ]
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']

    # Disable all write operations
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    # Display helpers
    @admin.display(description='Actor', ordering='actor')
    def actor_email(self, obj):
        return obj.actor.email if obj.actor else '(system)'

    @admin.display(description='Hash (short)')
    def hash_short(self, obj):
        return obj.hash[:16] + '...' if obj.hash else '-'


# ===========================================================================
# Admin Session
# ===========================================================================

@admin.register(AdminSession)
class AdminSessionAdmin(admin.ModelAdmin):
    """Admin for admin session management with termination action."""

    list_display = [
        'id_short', 'user_email', 'ip_address', 'mfa_verified_display',
        'is_active', 'is_expired_display', 'expires_at', 'created_at',
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__email', 'ip_address', 'session_token']
    readonly_fields = [
        'id', 'user', 'session_token', 'ip_address', 'user_agent',
        'device_fingerprint', 'mfa_verified_at', 'hardware_key_verified',
        'is_active', 'expires_at', 'absolute_expires_at',
        'created_at', 'last_activity_at',
        'terminated_at', 'termination_reason',
    ]
    actions = ['terminate_selected_sessions']

    def has_add_permission(self, request):
        return False  # Sessions are created via service layer

    @admin.display(description='Session ID (short)', ordering='id')
    def id_short(self, obj):
        return str(obj.id)[:8] + '...'

    @admin.display(description='User', ordering='user')
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description='MFA Verified?')
    def mfa_verified_display(self, obj):
        return obj.is_mfa_verified
    mfa_verified_display.boolean = True

    @admin.display(description='Expired?')
    def is_expired_display(self, obj):
        return obj.is_expired
    is_expired_display.boolean = True

    @admin.action(description='Terminate selected sessions')
    def terminate_selected_sessions(self, request, queryset):
        count = 0
        for session in queryset.filter(is_active=True):
            session.is_active = False
            session.terminated_at = timezone.now()
            session.termination_reason = 'admin_bulk_terminate'
            session.save(update_fields=['is_active', 'terminated_at', 'termination_reason'])
            count += 1

        messages.success(
            request,
            f'{count} admin session(s) terminated.',
        )

        ImmutableAuditService.log(
            actor=request.user,
            action_type='ADMIN_SESSIONS_BULK_TERMINATED',
            resource_type='AdminSession',
            metadata={'count': count},
            ip_address=request.META.get('REMOTE_ADDR', ''),
        )


# ===========================================================================
# Dual Approval Request
# ===========================================================================

@admin.register(DualApprovalRequest)
class DualApprovalRequestAdmin(admin.ModelAdmin):
    """Admin for dual-approval request management."""

    list_display = [
        'id_short', 'request_type', 'status', 'requester_email',
        'approver_email', 'expires_at', 'created_at',
    ]
    list_filter = ['request_type', 'status', 'created_at']
    search_fields = ['notes', 'requester__email', 'approver__email']
    readonly_fields = [
        'id', 'request_type', 'resource_type', 'resource_id',
        'request_data', 'status', 'requester', 'approver',
        'notes', 'amount', 'risk_score',
        'requester_step_up_verified', 'approver_step_up_verified',
        'expires_at', 'approved_at', 'resolved_at',
        'created_at',
    ]
    actions = ['expire_selected_approvals']

    def has_add_permission(self, request):
        return False  # Requests are created via service layer

    @admin.display(description='ID (short)', ordering='id')
    def id_short(self, obj):
        return str(obj.id)[:8] + '...'

    @admin.display(description='Requester', ordering='requester')
    def requester_email(self, obj):
        return obj.requester.email

    @admin.display(description='Approver', ordering='approver')
    def approver_email(self, obj):
        return obj.approver.email if obj.approver else '-'

    @admin.action(description='Mark selected requests as expired')
    def expire_selected_approvals(self, request, queryset):
        count = queryset.filter(status='pending').update(status='expired')
        messages.success(
            request,
            f'{count} pending approval request(s) marked as expired.',
        )

        ImmutableAuditService.log(
            actor=request.user,
            action_type='DUAL_APPROVALS_BULK_EXPIRED',
            resource_type='DualApprovalRequest',
            metadata={'count': count},
            ip_address=request.META.get('REMOTE_ADDR', ''),
        )


# ===========================================================================
# Emergency Control
# ===========================================================================

@admin.register(EmergencyControl)
class EmergencyControlAdmin(admin.ModelAdmin):
    """Admin for the EmergencyControl singleton with emergency actions."""

    list_display = [
        'id_short', 'control_type', 'is_active',
        'reason_short', 'activated_at',
    ]
    readonly_fields = [
        'id',
        'activated_by',
        'activated_at',
        'deactivated_by',
        'deactivated_at',
    ]
    fieldsets = (
        ('Control Details', {
            'fields': (
                'control_type',
                'is_active',
                'reason',
                'config',
            ),
        }),
        ('Activation', {
            'fields': (
                'activated_by',
                'activated_at',
            ),
        }),
        ('Deactivation', {
            'fields': (
                'deactivated_by',
                'deactivated_at',
            ),
        }),
        ('Metadata', {
            'fields': ('id',),
        }),
    )
    actions = [
        'activate_withdrawal_freeze',
        'deactivate_withdrawal_freeze',
        'activate_incident_mode',
        'deactivate_incident_mode',
    ]

    def has_add_permission(self, request):
        return True  # Emergency controls can be created via admin

    def has_delete_permission(self, request, obj=None):
        return False  # Never allow deletion of the singleton

    @admin.display(description='ID (short)')
    def id_short(self, obj):
        return str(obj.id)[:8] + '...'

    @admin.display(description='Reason (short)')
    def reason_short(self, obj):
        if obj.reason:
            return obj.reason[:50] + '...'
        return '-'

    @admin.action(description='Activate withdrawal freeze')
    def activate_withdrawal_freeze(self, request, queryset):
        for control in queryset:
            EmergencyControlService.set_withdrawal_freeze(
                activated_by=request.user,
                activate=True,
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
        messages.warning(request, 'Withdrawal freeze ACTIVATED.')

    @admin.action(description='Deactivate withdrawal freeze')
    def deactivate_withdrawal_freeze(self, request, queryset):
        for control in queryset:
            EmergencyControlService.set_withdrawal_freeze(
                activated_by=request.user,
                activate=False,
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
        messages.success(request, 'Withdrawal freeze DEACTIVATED.')

    @admin.action(description='Activate incident mode')
    def activate_incident_mode(self, request, queryset):
        for control in queryset:
            EmergencyControlService.set_incident_mode(
                activated_by=request.user,
                activate=True,
                description='Activated via Django admin action.',
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
        messages.warning(request, 'Incident mode ACTIVATED.')

    @admin.action(description='Deactivate incident mode')
    def deactivate_incident_mode(self, request, queryset):
        for control in queryset:
            EmergencyControlService.set_incident_mode(
                activated_by=request.user,
                activate=False,
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
        messages.success(request, 'Incident mode DEACTIVATED.')


# ===========================================================================
# Admin IP Range
# ===========================================================================

@admin.register(AdminIPAddress)
class AdminIPAddressAdmin(admin.ModelAdmin):
    """Simple CRUD admin for IP allow-list management."""

    list_display = ['ip_address', 'ip_range', 'label', 'is_active', 'user_email', 'created_at']
    list_filter = ['is_active']
    search_fields = ['ip_address', 'ip_range', 'label']
    readonly_fields = ['id', 'created_at']

    @admin.display(description='User', ordering='user')
    def user_email(self, obj):
        return obj.user.email if obj.user else '(global)'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
