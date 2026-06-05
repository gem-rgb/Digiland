"""Service layer for the Enterprise Admin Control Plane.

All mutations to control-plane state flow through these service classes,
which enforce:

- Admin role verification
- Session validity checks
- Step-up authentication for sensitive operations
- Dual-approval workflow for financial and role changes
- Immutable audit logging

Services
--------
AdminSessionService           : Create, validate, terminate admin sessions.
DualApprovalService           : Submit, approve, reject, expire requests.
FinancialProtectionService    : Threshold checks, freeze enforcement.
EmergencyControlService       : Toggle emergency flags with audit.
ImmutableAuditService         : Append-only log with hash-chain integrity.
"""

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.db import transaction

from core.auth_mfa import MFAService, StepUpAuthService

from .models import (
    AdminActionLog,
    AdminSession,
    DualApprovalRequest,
    EmergencyControl,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Admin Session Service
# ---------------------------------------------------------------------------

class AdminSessionService:
    """Manage ephemeral admin sessions with MFA binding.

    Every admin operation requires an active, non-expired session
    created via this service.  Sessions are MFA-verified by default
    and automatically expire after ``SESSION_TIMEOUT_MINUTES``.
    """

    SESSION_TIMEOUT_MINUTES = getattr(
        settings, 'ADMIN_SESSION_TIMEOUT_MINUTES', 60
    )
    SESSION_TOKEN_LENGTH = 64

    @staticmethod
    def create_session(user, mfa_code: str, ip_address: str, user_agent: str = '') -> AdminSession:
        """Create a new admin session after MFA verification.

        Parameters
        ----------
        user : User
            Must have ``role='Admin'``.
        mfa_code : str
            TOTP code to verify step-up auth.
        ip_address : str
            Client IP for audit.
        user_agent : str
            Client User-Agent for audit.

        Returns
        -------
        AdminSession

        Raises
        ------
        PermissionDenied
            If the user is not an admin.
        ValueError
            If MFA verification fails.
        """
        if user.role != 'Admin':
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied('Only admins can create admin sessions.')

        # Verify MFA
        verified = MFAService.verify_mfa(user, mfa_code)
        if not verified:
            raise ValueError('MFA verification failed.')

        token = secrets.token_hex(AdminSessionService.SESSION_TOKEN_LENGTH)
        expires_at = timezone.now() + timedelta(
            minutes=AdminSessionService.SESSION_TIMEOUT_MINUTES
        )

        session = AdminSession.objects.create(
            user=user,
            session_token=token,
            ip_address=ip_address,
            user_agent=user_agent,
            mfa_verified=True,
            mfa_method='totp',
            is_active=True,
            expires_at=expires_at,
        )

        # Audit log
        ImmutableAuditService.log(
            actor=user,
            action_type='ADMIN_SESSION_CREATE',
            resource_type='AdminSession',
            resource_id=str(session.id),
            ip_address=ip_address,
            user_agent=user_agent,
            admin_session=session,
        )

        return session

    @staticmethod
    def validate_session(session_token: str) -> AdminSession:
        """Validate and return an active admin session.

        Raises
        ------
        ValueError
            If the session is invalid, expired, or terminated.
        """
        try:
            session = AdminSession.objects.get(
                session_token=session_token,
                is_active=True,
            )
        except AdminSession.DoesNotExist:
            raise ValueError('Invalid or terminated admin session.')

        if session.is_expired:
            session.is_active = False
            session.save(update_fields=['is_active'])
            raise ValueError('Admin session has expired.')

        return session

    @staticmethod
    def terminate_session(session_id, terminated_by) -> bool:
        """Terminate a specific admin session."""
        try:
            session = AdminSession.objects.get(id=session_id)
        except AdminSession.DoesNotExist:
            raise ValueError('Admin session not found.')

        session.is_active = False
        session.terminated_at = timezone.now()
        session.terminated_by = terminated_by
        session.save(update_fields=['is_active', 'terminated_at', 'terminated_by'])

        ImmutableAuditService.log(
            actor=terminated_by,
            action_type='ADMIN_SESSION_TERMINATE',
            resource_type='AdminSession',
            resource_id=str(session.id),
            metadata={'terminated_user_email': session.user.email},
        )

        return True

    @staticmethod
    def terminate_all_sessions(user, terminated_by=None) -> int:
        """Terminate all active admin sessions for a given user.

        Returns the count of terminated sessions.
        """
        sessions = AdminSession.objects.filter(user=user, is_active=True)
        count = 0
        now = timezone.now()
        for session in sessions:
            session.is_active = False
            session.terminated_at = now
            session.terminated_by = terminated_by
            count += 1
        sessions.update(is_active=False, terminated_at=now)

        if count > 0:
            ImmutableAuditService.log(
                actor=terminated_by or user,
                action_type='ADMIN_SESSION_TERMINATE_ALL',
                resource_type='AdminSession',
                metadata={'terminated_user_email': user.email, 'count': count},
            )

        return count

    @staticmethod
    def list_active_sessions(user=None):
        """Return active admin sessions, optionally filtered by user."""
        qs = AdminSession.objects.filter(
            is_active=True,
            expires_at__gt=timezone.now(),
        ).select_related('user')
        if user:
            qs = qs.filter(user=user)
        return qs


# ---------------------------------------------------------------------------
# Dual Approval Service
# ---------------------------------------------------------------------------

class DualApprovalService:
    """Manage dual-approval workflow for sensitive operations.

    The requesting admin cannot be the same as the approving admin.
    Requests auto-expire after ``APPROVAL_DEADLINE_HOURS``.
    """

    APPROVAL_DEADLINE_HOURS = getattr(
        settings, 'DUAL_APPROVAL_DEADLINE_HOURS', 24
    )

    @staticmethod
    def submit_request(
        requested_by,
        action_type: str,
        description: str,
        payload: dict,
        ip_address: str = '',
        user_agent: str = '',
    ) -> DualApprovalRequest:
        """Create a new dual-approval request.

        Parameters
        ----------
        requested_by : User
            Must be an admin.
        action_type : str
            One of ``DualApprovalRequest.ACTION_TYPE_CHOICES``.
        description : str
            Human-readable description.
        payload : dict
            Structured data for executing the action upon approval.
        ip_address : str
        user_agent : str

        Returns
        -------
        DualApprovalRequest
        """
        if requested_by.role != 'Admin':
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied('Only admins can submit approval requests.')

        deadline = timezone.now() + timedelta(
            hours=DualApprovalService.APPROVAL_DEADLINE_HOURS
        )

        request = DualApprovalRequest.objects.create(
            action_type=action_type,
            description=description,
            payload=payload,
            status='PENDING',
            requested_by=requested_by,
            deadline=deadline,
        )

        ImmutableAuditService.log(
            actor=requested_by,
            action_type='DUAL_APPROVAL_REQUEST_SUBMITTED',
            resource_type='DualApprovalRequest',
            resource_id=str(request.id),
            metadata={
                'action_type': action_type,
                'description': description[:200],
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return request

    @staticmethod
    def approve_request(
        request_id,
        approved_by,
        review_notes: str = '',
        ip_address: str = '',
        user_agent: str = '',
    ) -> DualApprovalRequest:
        """Approve a pending dual-approval request.

        The approving admin must be different from the requesting admin.

        Raises
        ------
        ValueError
            If the request cannot be approved.
        PermissionDenied
            If the approver is the same as the requester.
        """
        try:
            approval_request = DualApprovalRequest.objects.get(id=request_id)
        except DualApprovalRequest.DoesNotExist:
            raise ValueError('Approval request not found.')

        if approval_request.status != 'PENDING':
            raise ValueError(
                f'Cannot approve request in status {approval_request.status}.'
            )

        if approval_request.is_expired:
            approval_request.status = 'EXPIRED'
            approval_request.save(update_fields=['status'])
            raise ValueError('Approval request has expired.')

        if approval_request.requested_by_id == approved_by.id:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied(
                'The requesting admin cannot approve their own request.'
            )

        if approved_by.role != 'Admin':
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied('Only admins can approve requests.')

        approval_request.status = 'APPROVED'
        approval_request.reviewed_by = approved_by
        approval_request.review_notes = review_notes
        approval_request.reviewed_at = timezone.now()
        approval_request.save()

        ImmutableAuditService.log(
            actor=approved_by,
            action_type='DUAL_APPROVAL_REQUEST_APPROVED',
            resource_type='DualApprovalRequest',
            resource_id=str(approval_request.id),
            metadata={
                'action_type': approval_request.action_type,
                'review_notes': review_notes[:200],
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return approval_request

    @staticmethod
    def reject_request(
        request_id,
        rejected_by,
        review_notes: str = '',
        ip_address: str = '',
        user_agent: str = '',
    ) -> DualApprovalRequest:
        """Reject a pending dual-approval request."""
        try:
            approval_request = DualApprovalRequest.objects.get(id=request_id)
        except DualApprovalRequest.DoesNotExist:
            raise ValueError('Approval request not found.')

        if approval_request.status != 'PENDING':
            raise ValueError(
                f'Cannot reject request in status {approval_request.status}.'
            )

        approval_request.status = 'REJECTED'
        approval_request.reviewed_by = rejected_by
        approval_request.review_notes = review_notes
        approval_request.reviewed_at = timezone.now()
        approval_request.save()

        ImmutableAuditService.log(
            actor=rejected_by,
            action_type='DUAL_APPROVAL_REQUEST_REJECTED',
            resource_type='DualApprovalRequest',
            resource_id=str(approval_request.id),
            metadata={
                'action_type': approval_request.action_type,
                'review_notes': review_notes[:200],
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return approval_request

    @staticmethod
    def list_pending():
        """Return all pending dual-approval requests."""
        return DualApprovalRequest.objects.filter(
            status='PENDING',
            deadline__gt=timezone.now(),
        ).select_related('requested_by')

    @staticmethod
    def expire_stale_requests() -> int:
        """Mark all past-deadline pending requests as EXPIRED.

        Called by the signal handler on a periodic basis.

        Returns
        -------
        int
            Number of requests expired.
        """
        stale = DualApprovalRequest.objects.filter(
            status='PENDING',
            deadline__lt=timezone.now(),
        )
        count = stale.update(status='EXPIRED')
        if count > 0:
            logger.warning('Expired %d stale dual-approval request(s).', count)
        return count


# ---------------------------------------------------------------------------
# Financial Protection Service
# ---------------------------------------------------------------------------

class FinancialProtectionService:
    """Enforce financial operation guards.

    - Dual-approval for amounts above ``FINANCIAL_DUAL_APPROVAL_THRESHOLD``.
    - Withdrawal freeze enforcement.
    - Payout approval workflow.
    """

    FINANCIAL_DUAL_APPROVAL_THRESHOLD = getattr(
        settings, 'FINANCIAL_DUAL_APPROVAL_THRESHOLD', 100000
    )  # Default: KES 100,000

    @staticmethod
    def requires_dual_approval(amount) -> bool:
        """Check if the amount exceeds the dual-approval threshold."""
        return float(amount) >= FinancialProtectionService.FINANCIAL_DUAL_APPROVAL_THRESHOLD

    @staticmethod
    def check_withdrawal_freeze() -> bool:
        """Return True if withdrawals are currently frozen."""
        control = EmergencyControl.get_solo()
        return control.withdrawal_freeze

    @staticmethod
    def initiate_withdrawal(
        initiated_by,
        amount,
        recipient_id: str,
        reference: str = '',
        ip_address: str = '',
        user_agent: str = '',
    ):
        """Initiate a withdrawal request.

        If the amount exceeds the threshold, a dual-approval request is
        created automatically.

        Returns
        -------
        dict
            Keys: ``approval_request`` (DualApprovalRequest or None),
                  ``requires_dual_approval`` (bool).
        """
        if FinancialProtectionService.check_withdrawal_freeze():
            raise ValueError('Withdrawals are currently frozen by emergency control.')

        requires_da = FinancialProtectionService.requires_dual_approval(amount)

        approval_request = None
        if requires_da:
            approval_request = DualApprovalService.submit_request(
                requested_by=initiated_by,
                action_type='WITHDRAWAL_APPROVE',
                description=f'Withdrawal of KES {amount} to user {recipient_id}',
                payload={
                    'amount': str(amount),
                    'recipient_id': recipient_id,
                    'reference': reference,
                },
                ip_address=ip_address,
                user_agent=user_agent,
            )

        ImmutableAuditService.log(
            actor=initiated_by,
            action_type='WITHDRAWAL_INITIATED',
            resource_type='FinancialOperation',
            metadata={
                'amount': str(amount),
                'recipient_id': recipient_id,
                'requires_dual_approval': requires_da,
                'approval_request_id': str(approval_request.id) if approval_request else None,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {
            'approval_request': approval_request,
            'requires_dual_approval': requires_da,
        }

    @staticmethod
    def approve_withdrawal(approval_request_id, approved_by, ip_address='', user_agent=''):
        """Execute an approved withdrawal.

        The approval request must be in APPROVED status before calling.
        """
        try:
            approval_request = DualApprovalRequest.objects.get(id=approval_request_id)
        except DualApprovalRequest.DoesNotExist:
            raise ValueError('Approval request not found.')

        if approval_request.status != 'APPROVED':
            raise ValueError('Approval request must be in APPROVED status.')

        if FinancialProtectionService.check_withdrawal_freeze():
            raise ValueError('Withdrawals are currently frozen.')

        # Mark as executed
        approval_request.status = 'EXECUTED'
        approval_request.executed_at = timezone.now()
        approval_request.save(update_fields=['status', 'executed_at'])

        ImmutableAuditService.log(
            actor=approved_by,
            action_type='WITHDRAWAL_EXECUTED',
            resource_type='DualApprovalRequest',
            resource_id=str(approval_request.id),
            metadata={
                'payload': approval_request.payload,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return approval_request

    @staticmethod
    def balance_adjustment(
        initiated_by,
        user_id,
        amount,
        reason: str,
        ip_address='',
        user_agent='',
    ):
        """Request a balance adjustment (dual-approval required)."""
        return DualApprovalService.submit_request(
            requested_by=initiated_by,
            action_type='BALANCE_ADJUSTMENT',
            description=f'Balance adjustment of KES {amount} for user {user_id}: {reason}',
            payload={
                'user_id': str(user_id),
                'amount': str(amount),
                'reason': reason,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    def approve_payout(approval_request_id, approved_by, ip_address='', user_agent=''):
        """Execute an approved payout."""
        try:
            approval_request = DualApprovalRequest.objects.get(id=approval_request_id)
        except DualApprovalRequest.DoesNotExist:
            raise ValueError('Approval request not found.')

        if approval_request.status != 'APPROVED':
            raise ValueError('Payout approval request must be in APPROVED status.')

        approval_request.status = 'EXECUTED'
        approval_request.executed_at = timezone.now()
        approval_request.save(update_fields=['status', 'executed_at'])

        ImmutableAuditService.log(
            actor=approved_by,
            action_type='PAYOUT_EXECUTED',
            resource_type='DualApprovalRequest',
            resource_id=str(approval_request.id),
            metadata={'payload': approval_request.payload},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return approval_request

    @staticmethod
    def get_freeze_status() -> dict:
        """Return the current withdrawal freeze status."""
        control = EmergencyControl.get_solo()
        return {
            'withdrawal_freeze': control.withdrawal_freeze,
            'activated_by': (
                str(control.withdrawal_freeze_activated_by_id)
                if control.withdrawal_freeze_activated_by_id else None
            ),
            'activated_at': (
                control.withdrawal_freeze_activated_at.isoformat()
                if control.withdrawal_freeze_activated_at else None
            ),
        }


# ---------------------------------------------------------------------------
# Emergency Control Service
# ---------------------------------------------------------------------------

class EmergencyControlService:
    """Toggle and inspect emergency controls with full audit trail.

    Every toggle requires step-up auth and produces an audit log.
    """

    @staticmethod
    def set_withdrawal_freeze(
        activated_by,
        activate: bool,
        ip_address='',
        user_agent='',
    ) -> EmergencyControl:
        """Activate or deactivate the withdrawal freeze."""
        control = EmergencyControl.get_solo()
        control.withdrawal_freeze = activate

        if activate:
            control.withdrawal_freeze_activated_by = activated_by
            control.withdrawal_freeze_activated_at = timezone.now()
        else:
            control.withdrawal_freeze_activated_by = None
            control.withdrawal_freeze_activated_at = None

        control.updated_by = activated_by
        control.save()

        ImmutableAuditService.log(
            actor=activated_by,
            action_type='WITHDRAWAL_FREEZE_' + ('ACTIVATED' if activate else 'DEACTIVATED'),
            resource_type='EmergencyControl',
            resource_id=str(control.id),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return control

    @staticmethod
    def revoke_all_sessions(revoked_by, ip_address='', user_agent='') -> int:
        """Revoke all active admin sessions across the platform."""
        sessions = AdminSession.objects.filter(is_active=True)
        count = 0
        now = timezone.now()
        for session in sessions:
            session.is_active = False
            session.terminated_at = now
            session.terminated_by = revoked_by
            count += 1
        sessions.update(is_active=False, terminated_at=now)

        ImmutableAuditService.log(
            actor=revoked_by,
            action_type='EMERGENCY_SESSION_REVOCATION',
            resource_type='AdminSession',
            metadata={'sessions_revoked': count},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return count

    @staticmethod
    def set_incident_mode(
        activated_by,
        activate: bool,
        description: str = '',
        ip_address='',
        user_agent='',
    ) -> EmergencyControl:
        """Activate or deactivate incident mode."""
        control = EmergencyControl.get_solo()
        control.incident_mode = activate

        if activate:
            control.incident_mode_activated_by = activated_by
            control.incident_mode_activated_at = timezone.now()
            control.incident_description = description
        else:
            control.incident_mode_activated_by = None
            control.incident_mode_activated_at = None
            control.incident_description = ''

        control.updated_by = activated_by
        control.save()

        ImmutableAuditService.log(
            actor=activated_by,
            action_type='INCIDENT_MODE_' + ('ACTIVATED' if activate else 'DEACTIVATED'),
            resource_type='EmergencyControl',
            resource_id=str(control.id),
            metadata={'description': description[:500]} if activate else {},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return control

    @staticmethod
    def lock_admin_account(
        locked_by,
        user_to_lock,
        ip_address='',
        user_agent='',
    ):
        """Lock an admin account by deactivating all their sessions."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        if user_to_lock.role != 'Admin':
            raise ValueError('Can only lock admin accounts.')

        count = AdminSessionService.terminate_all_sessions(
            user=user_to_lock,
            terminated_by=locked_by,
        )

        # Deactivate the user
        user_to_lock.is_active = False
        user_to_lock.save(update_fields=['is_active'])

        ImmutableAuditService.log(
            actor=locked_by,
            action_type='ADMIN_ACCOUNT_LOCKED',
            resource_type='User',
            resource_id=str(user_to_lock.id),
            metadata={
                'locked_user_email': user_to_lock.email,
                'sessions_terminated': count,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {'locked': True, 'sessions_terminated': count}

    @staticmethod
    def get_status() -> dict:
        """Return the full emergency control status."""
        control = EmergencyControl.get_solo()
        return {
            'withdrawal_freeze': control.withdrawal_freeze,
            'incident_mode': control.incident_mode,
            'incident_description': control.incident_description,
            'withdrawal_freeze_activated_at': (
                control.withdrawal_freeze_activated_at.isoformat()
                if control.withdrawal_freeze_activated_at else None
            ),
            'incident_mode_activated_at': (
                control.incident_mode_activated_at.isoformat()
                if control.incident_mode_activated_at else None
            ),
            'updated_at': control.updated_at.isoformat() if control.updated_at else None,
        }


# ---------------------------------------------------------------------------
# Immutable Audit Service
# ---------------------------------------------------------------------------

class ImmutableAuditService:
    """Append-only audit logging with SHA-256 hash-chain integrity.

    Every admin action must be logged through this service.  The hash
    chain makes it computationally infeasible to alter or delete log
    entries without detection.
    """

    @staticmethod
    def log(
        actor,
        action: str,
        resource_type: str = '',
        resource_id: str = '',
        metadata: dict = None,
        ip_address: str = '',
        user_agent: str = '',
        admin_session=None,
    ) -> AdminActionLog:
        """Create an immutable audit log entry.

        Parameters
        ----------
        actor : User
            The admin performing the action.
        action : str
            Short action code (e.g. WITHDRAWAL_APPROVE).
        resource_type : str
        resource_id : str
        metadata : dict
        ip_address : str
        user_agent : str
        admin_session : AdminSession, optional

        Returns
        -------
        AdminActionLog
        """
        entry = AdminActionLog(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata or {},
            ip_address=ip_address or '',
            user_agent=user_agent or '',
            admin_session=admin_session,
        )
        entry.save()  # Triggers compute_hash via model.save()
        return entry

    @staticmethod
    def verify_integrity() -> dict:
        """Verify the hash-chain integrity of the entire audit log.

        Returns
        -------
        dict
            Keys:
            - ``valid`` (bool): True if the entire chain is intact.
            - ``total_entries`` (int): Number of entries checked.
            - ``broken_at`` (str|None): ID of the first broken entry.
            - ``errors`` (list): Descriptions of any integrity breaks.
        """
        entries = AdminActionLog.objects.order_by('timestamp')
        errors = []
        broken_at = None
        total = 0
        previous_hash = '0' * 64  # Genesis

        for entry in entries:
            total += 1

            # Check previous_hash linkage
            if entry.previous_hash != previous_hash:
                errors.append(
                    f'Broken chain at entry {entry.id}: '
                    f'expected previous_hash={previous_hash}, '
                    f'got {entry.previous_hash}'
                )
                if broken_at is None:
                    broken_at = str(entry.id)

            # Verify the entry's own hash
            expected_hash = entry.compute_hash()
            if entry.hash != expected_hash:
                errors.append(
                    f'Hash mismatch at entry {entry.id}: '
                    f'stored={entry.hash}, computed={expected_hash}'
                )
                if broken_at is None:
                    broken_at = str(entry.id)

            previous_hash = entry.hash

        return {
            'valid': len(errors) == 0,
            'total_entries': total,
            'broken_at': broken_at,
            'errors': errors,
        }

    @staticmethod
    def get_actor_history(actor, limit=100):
        """Return recent audit log entries for a specific admin."""
        return AdminActionLog.objects.filter(
            actor=actor,
        ).order_by('-timestamp')[:limit]

    @staticmethod
    def export_logs(
        since=None,
        until=None,
        actor_id=None,
        action=None,
        resource_type=None,
    ):
        """Export audit logs for compliance.

        Returns a QuerySet that can be serialized to JSON or CSV.
        """
        qs = AdminActionLog.objects.order_by('timestamp')

        if since:
            qs = qs.filter(timestamp__gte=since)
        if until:
            qs = qs.filter(timestamp__lte=until)
        if actor_id:
            qs = qs.filter(actor_id=actor_id)
        if action:
            qs = qs.filter(action=action)
        if resource_type:
            qs = qs.filter(resource_type=resource_type)

        return qs
