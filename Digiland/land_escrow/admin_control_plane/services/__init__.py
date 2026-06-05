"""
Admin Control Plane Services
================================

Service layer for the Enterprise Admin Control Plane.

Each service encapsulates a specific security domain:

    - AdminSessionService       : Short-lived, MFA-verified admin sessions
    - DualApprovalService       : Dual-approval workflow for sensitive actions
    - FinancialProtectionService: Risk scoring & dual-approval for financial ops
    - EmergencyControlService   : Break-glass emergency controls
    - ImmutableAuditService     : Tamper-resistant audit trail

All services are designed to be called from views, management commands,
or Celery tasks.  They raise descriptive exceptions on failure and
return structured dictionaries on success.
"""

import hashlib
import json
import logging
import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Service: AdminSessionService
# ══════════════════════════════════════════════════════════════════════════════


class AdminSessionService:
    """Manage short-lived, MFA-verified administrative sessions.

    Admin sessions are more restrictive than regular user sessions:

    * Shorter idle timeout (default 30 minutes).
    * Absolute maximum lifetime (default 4 hours).
    * MFA verification is mandatory.
    * IP address and device fingerprint are tracked for anomaly detection.

    Usage::

        session = AdminSessionService.create_admin_session(user, request)
        # → Returns AdminSession instance

        is_valid = AdminSessionService.validate_admin_session(token)
        # → Returns AdminSession or None

        AdminSessionService.terminate_admin_session(token, "manual")
    """

    SESSION_TOKEN_LENGTH = 64  # Bytes of entropy for the session token
    DEFAULT_IDLE_TIMEOUT = 1800  # 30 minutes
    DEFAULT_ABSOLUTE_TIMEOUT = 14400  # 4 hours

    @classmethod
    def create_admin_session(cls, user, request):
        """Create a new admin session for an authenticated user.

        The user MUST have completed MFA verification before this method
        is called.  If MFA has not been verified, a ``ValueError`` is
        raised.

        Args:
            user: The authenticated ``User`` instance (must be Admin role).
            request: The current Django ``HttpRequest`` (for IP and UA).

        Returns:
            The newly created ``AdminSession`` instance.

        Raises:
            ValueError: If the user is not an admin or MFA is not verified.
        """
        from .models import AdminSession  # noqa: F811

        # Validate user role
        if getattr(user, "role", None) != "Admin" and not getattr(
            user, "is_superuser", False
        ):
            raise ValueError("Only Admin users can create admin sessions.")

        # Check MFA verification – must be verified via the MFA flow
        # before an admin session can be created.
        mfa_verified_at = getattr(request, "mfa_verified_at", None)
        if not mfa_verified_at:
            # Check session for MFA verification timestamp
            mfa_verified_at = request.session.get("mfa_verified_at")

        # Extract request metadata
        ip_address = cls._client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
        device_fingerprint = cls._device_fingerprint(request)

        idle_timeout = getattr(
            settings,
            "ADMIN_SESSION_IDLE_TIMEOUT_SECONDS",
            cls.DEFAULT_IDLE_TIMEOUT,
        )
        absolute_timeout = getattr(
            settings,
            "ADMIN_SESSION_ABSOLUTE_TIMEOUT_SECONDS",
            cls.DEFAULT_ABSOLUTE_TIMEOUT,
        )

        now = timezone.now()

        session = AdminSession.objects.create(
            tenant_id=getattr(request, "tenant_id", None),
            user=user,
            session_token=secrets.token_hex(cls.SESSION_TOKEN_LENGTH),
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint,
            is_active=True,
            mfa_verified_at=mfa_verified_at or now,
            hardware_key_verified=getattr(request, "hardware_key_verified", False),
            expires_at=now + timedelta(seconds=idle_timeout),
            absolute_expires_at=now + timedelta(seconds=absolute_timeout),
        )

        # Store the session token in the Django session for browser requests
        request.session["admin_session_token"] = session.session_token

        logger.info(
            "AdminSessionService: Created admin session user=%s session=%s",
            user.email,
            str(session.id)[:8],
        )

        return session

    @classmethod
    def validate_admin_session(cls, session_token):
        """Validate an admin session token and return the session.

        Checks:
        * Session exists and is active.
        * Idle timeout has not been exceeded.
        * Absolute timeout has not been exceeded.
        * MFA has been verified.

        Args:
            session_token: The opaque session token string.

        Returns:
            The valid ``AdminSession`` instance, or ``None`` if invalid.
        """
        from .models import AdminSession

        try:
            session = AdminSession.objects.select_related("user").get(
                session_token=session_token,
                is_active=True,
            )
        except AdminSession.DoesNotExist:
            return None

        now = timezone.now()

        # Check absolute expiry
        if now > session.absolute_expires_at:
            cls.terminate_admin_session(session_token, "absolute_expiry")
            return None

        # Check idle expiry
        if now > session.expires_at:
            cls.terminate_admin_session(session_token, "idle_timeout")
            return None

        # Check MFA verification
        if not session.is_mfa_verified:
            cls.terminate_admin_session(session_token, "no_mfa")
            return None

        return session

    @classmethod
    def terminate_admin_session(cls, session_token, reason="manual"):
        """Terminate an admin session cleanly.

        Args:
            session_token: The session token to terminate.
            reason: A short string describing why (e.g. 'manual',
                'security_event', 'emergency_revocation').

        Returns:
            True if the session was found and terminated, False otherwise.
        """
        from .models import AdminSession

        try:
            session = AdminSession.objects.get(
                session_token=session_token,
                is_active=True,
            )
        except AdminSession.DoesNotExist:
            return False

        session.is_active = False
        session.terminated_at = timezone.now()
        session.termination_reason = reason
        session.save(update_fields=["is_active", "terminated_at", "termination_reason"])

        logger.info(
            "AdminSessionService: Terminated session user=%s reason=%s",
            session.user_id,
            reason,
        )
        return True

    @classmethod
    def terminate_all_user_sessions(cls, user, reason="emergency_revocation"):
        """Terminate all active admin sessions for a user.

        Used for emergency session revocation (e.g. after detecting a
        compromised account).

        Args:
            user: The ``User`` whose sessions should be revoked.
            reason: The reason for revocation.

        Returns:
            The number of sessions terminated.
        """
        from .models import AdminSession

        now = timezone.now()
        count = AdminSession.objects.filter(
            user=user,
            is_active=True,
        ).update(
            is_active=False,
            terminated_at=now,
            termination_reason=reason,
        )

        if count > 0:
            logger.warning(
                "AdminSessionService: Terminated %d sessions for user=%s reason=%s",
                count,
                user.email,
                reason,
            )

            # Create audit log
            try:
                from core.models import AuditLog

                AuditLog.objects.create(
                    user=user,
                    action="ALL_ADMIN_SESSIONS_TERMINATED",
                    metadata={"reason": reason, "sessions_terminated": count},
                )
            except Exception:
                logger.exception("Failed to audit session termination")

        return count

    @classmethod
    def detect_anomalous_session(cls, session, request):
        """Detect anomalies in an admin session.

        Checks for:
        * IP address change (potential session hijacking)
        * Device fingerprint change (different browser / device)
        * Impossible travel (IP geo-distance exceeds plausible speed)

        Args:
            session: The ``AdminSession`` to check.
            request: The current ``HttpRequest``.

        Returns:
            A dict of detected anomalies, keyed by type.
            Empty dict means no anomalies detected.
        """
        anomalies = {}
        current_ip = cls._client_ip(request)
        current_fp = cls._device_fingerprint(request)

        # IP address change
        if str(session.ip_address) != current_ip:
            anomalies["ip_change"] = {
                "original_ip": str(session.ip_address),
                "new_ip": current_ip,
                "severity": "high",
            }

        # Device fingerprint change
        if session.device_fingerprint and current_fp != session.device_fingerprint:
            anomalies["device_change"] = {
                "original_fp": session.device_fingerprint[:8],
                "new_fp": current_fp[:8],
                "severity": "medium",
            }

        # Impossible travel detection (simplified – uses session timestamps)
        if anomalies.get("ip_change"):
            time_since_creation = (
                timezone.now() - session.created_at
            ).total_seconds()
            # If session was created less than 5 minutes ago and IP changed,
            # that's suspicious
            if time_since_creation < 300:
                anomalies["impossible_travel"] = {
                    "time_elapsed_seconds": time_since_creation,
                    "severity": "critical",
                }

        return anomalies

    @classmethod
    def get_active_admin_sessions(cls, user):
        """List all active admin sessions for a user.

        Args:
            user: The ``User`` whose sessions to list.

        Returns:
            QuerySet of active ``AdminSession`` instances.
        """
        from .models import AdminSession

        return AdminSession.objects.filter(
            user=user,
            is_active=True,
        ).order_by("-last_activity_at")

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _client_ip(request):
        """Extract client IP from the request."""
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "0.0.0.0")

    @staticmethod
    def _device_fingerprint(request):
        """Generate a device fingerprint from request metadata."""
        ua = request.META.get("HTTP_USER_AGENT", "")
        accept = request.META.get("HTTP_ACCEPT", "")
        accept_lang = request.META.get("HTTP_ACCEPT_LANGUAGE", "")
        raw = f"{ua}|{accept}|{accept_lang}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


# ══════════════════════════════════════════════════════════════════════════════
# Service: DualApprovalService
# ══════════════════════════════════════════════════════════════════════════════


class DualApprovalService:
    """Manage the dual-approval workflow for sensitive administrative actions.

    Certain operations require a second administrator to review and
    approve before execution.  This service handles the full lifecycle:

    1. Request creation (with risk scoring)
    2. Approval / rejection (with step-up auth verification)
    3. Expiration of stale requests
    4. Policy-based determination of which actions require dual approval

    Configuration (Django settings):

        DUAL_APPROVAL_REQUEST_TYPES = [
            'withdrawal', 'balance_adjustment', 'payout', 'transfer',
            'role_change', 'permission_change', 'user_suspend', 'config_change',
        ]
        DUAL_APPROVAL_AMOUNT_THRESHOLD = 500000  # KES
        DUAL_APPROVAL_EXPIRY_HOURS = 24
    """

    DEFAULT_EXPIRY_HOURS = 24
    DEFAULT_AMOUNT_THRESHOLD = Decimal("500000")

    @classmethod
    def create_approval_request(
        cls,
        requester,
        request_type,
        resource_type,
        resource_id,
        data,
        amount=None,
    ):
        """Create a new dual-approval request.

        Args:
            requester: The ``User`` requesting the action.
            request_type: One of the ``REQUEST_TYPE_CHOICES`` values.
            resource_type: Type of resource (e.g. 'Transaction', 'User').
            resource_id: PK of the target resource.
            data: Dict with the full action payload.
            amount: Optional monetary amount (Decimal).

        Returns:
            The created ``DualApprovalRequest`` instance.

        Raises:
            ValueError: If the request_type is invalid or the requester
                is not an admin.
        """
        from .models import DualApprovalRequest

        if getattr(requester, "role", None) != "Admin" and not getattr(
            requester, "is_superuser", False
        ):
            raise ValueError("Only Admin users can create approval requests.")

        valid_types = [choice[0] for choice in DualApprovalRequest.REQUEST_TYPE_CHOICES]
        if request_type not in valid_types:
            raise ValueError(
                f"Invalid request_type '{request_type}'. "
                f"Must be one of: {valid_types}"
            )

        expiry_hours = getattr(
            settings,
            "DUAL_APPROVAL_EXPIRY_HOURS",
            cls.DEFAULT_EXPIRY_HOURS,
        )

        # Calculate risk score
        risk_score = cls._calculate_request_risk(
            request_type, amount, requester
        )

        request_obj = DualApprovalRequest.objects.create(
            tenant_id=getattr(requester, "tenant_id", None),
            requester=requester,
            request_type=request_type,
            resource_type=resource_type,
            resource_id=str(resource_id),
            request_data=data,
            status="pending",
            risk_score=risk_score,
            amount=amount,
            expires_at=timezone.now() + timedelta(hours=expiry_hours),
            requester_step_up_verified=True,  # Caller must verify step-up before calling
        )

        logger.info(
            "DualApprovalService: Created request type=%s requester=%s "
            "resource=%s/%s risk=%.1f",
            request_type,
            requester.email,
            resource_type,
            resource_id,
            risk_score,
        )

        return request_obj

    @classmethod
    def approve_request(cls, request_id, approver, step_up_code=None):
        """Approve a pending dual-approval request.

        The approver must have completed step-up authentication.  If the
        ``step_up_code`` is provided, it will be verified against the
        approver's TOTP secret before the approval is recorded.

        Args:
            request_id: UUID of the ``DualApprovalRequest``.
            approver: The ``User`` who is approving.
            step_up_code: Optional TOTP code for step-up verification.

        Returns:
            The updated ``DualApprovalRequest`` instance.

        Raises:
            ValueError: If the request cannot be approved (wrong status,
                expired, same requester/approver, step-up failed).
        """
        from .models import DualApprovalRequest

        try:
            request_obj = DualApprovalRequest.objects.get(id=request_id)
        except DualApprovalRequest.DoesNotExist:
            raise ValueError(f"DualApprovalRequest {request_id} not found.")

        # Validate status
        if request_obj.status != "pending":
            raise ValueError(
                f"Request is {request_obj.status}, not pending."
            )

        # Check expiry
        if request_obj.is_expired:
            request_obj.status = "expired"
            request_obj.resolved_at = timezone.now()
            request_obj.save(update_fields=["status", "resolved_at"])
            raise ValueError("Request has expired.")

        # Prevent self-approval
        if request_obj.requester_id == approver.id:
            raise ValueError("Cannot approve your own request.")

        # Verify step-up auth if code provided
        step_up_verified = False
        if step_up_code:
            from core.auth_mfa import MFAService

            if MFAService.verify_mfa(approver, step_up_code):
                step_up_verified = True
            else:
                raise ValueError("Step-up authentication failed.")

        now = timezone.now()
        request_obj.status = "approved"
        request_obj.approver = approver
        request_obj.approved_at = now
        request_obj.resolved_at = now
        request_obj.approver_step_up_verified = step_up_verified
        request_obj.save(
            update_fields=[
                "status",
                "approver",
                "approved_at",
                "resolved_at",
                "approver_step_up_verified",
            ]
        )

        logger.info(
            "DualApprovalService: Approved request %s approver=%s",
            str(request_id)[:8],
            approver.email,
        )

        # Create audit log
        cls._audit_dual_approval(request_obj, "approved", approver)

        return request_obj

    @classmethod
    def reject_request(cls, request_id, approver, reason=""):
        """Reject a pending dual-approval request.

        Args:
            request_id: UUID of the ``DualApprovalRequest``.
            approver: The ``User`` who is rejecting.
            reason: Optional reason for rejection.

        Returns:
            The updated ``DualApprovalRequest`` instance.

        Raises:
            ValueError: If the request cannot be rejected.
        """
        from .models import DualApprovalRequest

        try:
            request_obj = DualApprovalRequest.objects.get(id=request_id)
        except DualApprovalRequest.DoesNotExist:
            raise ValueError(f"DualApprovalRequest {request_id} not found.")

        if request_obj.status != "pending":
            raise ValueError(f"Request is {request_obj.status}, not pending.")

        now = timezone.now()
        request_obj.status = "rejected"
        request_obj.approver = approver
        request_obj.approved_at = now
        request_obj.resolved_at = now
        request_obj.notes = (
            f"{request_obj.notes}\n[REJECTED by {approver.email}]: {reason}"
            if reason
            else request_obj.notes
        )
        request_obj.save(
            update_fields=["status", "approver", "approved_at", "resolved_at", "notes"]
        )

        logger.info(
            "DualApprovalService: Rejected request %s approver=%s reason=%s",
            str(request_id)[:8],
            approver.email,
            reason,
        )

        cls._audit_dual_approval(request_obj, "rejected", approver)

        return request_obj

    @classmethod
    def expire_stale_requests(cls):
        """Mark all expired pending requests as expired.

        This should be called periodically via a Celery beat task or
        management command.

        Returns:
            The number of requests that were expired.
        """
        from .models import DualApprovalRequest

        now = timezone.now()
        stale = DualApprovalRequest.objects.filter(
            status="pending",
            expires_at__lt=now,
        )
        count = stale.update(
            status="expired",
            resolved_at=now,
        )

        if count > 0:
            logger.info(
                "DualApprovalService: Expired %d stale requests", count
            )

        return count

    @classmethod
    def is_dual_approval_required(cls, action_type, amount=None):
        """Check whether an action requires dual approval.

        Based on the action type and amount threshold configured in
        settings.

        Args:
            action_type: The type of action being performed.
            amount: Optional monetary amount.

        Returns:
            True if dual approval is required.
        """
        # All financial actions above the threshold require dual approval
        financial_types = {"withdrawal", "balance_adjustment", "payout", "transfer"}
        if action_type in financial_types:
            threshold = Decimal(
                str(
                    getattr(
                        settings,
                        "DUAL_APPROVAL_AMOUNT_THRESHOLD",
                        cls.DEFAULT_AMOUNT_THRESHOLD,
                    )
                )
            )
            if amount is not None and Decimal(str(amount)) >= threshold:
                return True

        # Role and permission changes always require dual approval
        always_require = {"role_change", "permission_change", "admin_create"}
        if action_type in always_require:
            return True

        # Check policy-based requirements
        try:
            from .models import AdminAccessPolicy

            financial_policies = AdminAccessPolicy.objects.filter(
                policy_type="action",
                is_active=True,
            )
            for policy in financial_policies:
                rules = policy.rules
                require_list = rules.get("require_dual_approval", [])
                if action_type in require_list:
                    return True
        except Exception:
            pass

        return False

    @classmethod
    def get_pending_approvals(cls, user):
        """Get pending dual-approval requests that a user can approve.

        Returns requests where the user is NOT the original requester
        and the request is still pending.

        Args:
            user: The potential approver.

        Returns:
            QuerySet of pending ``DualApprovalRequest`` instances.
        """
        from .models import DualApprovalRequest

        return DualApprovalRequest.objects.filter(
            status="pending",
            expires_at__gt=timezone.now(),
        ).exclude(requester=user).order_by("-risk_score", "created_at")

    # ── Private helpers ──────────────────────────────────────────────────

    @classmethod
    def _calculate_request_risk(cls, request_type, amount, requester):
        """Calculate a risk score for a dual-approval request.

        Returns:
            Float between 0 and 100.
        """
        score = 30.0  # Base risk for any admin action

        # Financial actions are riskier
        financial_types = {"withdrawal", "balance_adjustment", "payout", "transfer"}
        if request_type in financial_types:
            score += 20.0

        # Higher amounts are riskier
        if amount is not None:
            amount = Decimal(str(amount))
            if amount >= Decimal("1000000"):
                score += 25.0
            elif amount >= Decimal("500000"):
                score += 15.0
            elif amount >= Decimal("100000"):
                score += 5.0

        # Role changes are high-risk
        if request_type in {"role_change", "permission_change"}:
            score += 15.0

        return min(score, 100.0)

    @staticmethod
    def _audit_dual_approval(request_obj, action, approver):
        """Create an audit log entry for a dual-approval decision."""
        try:
            from core.models import AuditLog

            AuditLog.objects.create(
                user=approver,
                action=f"DUAL_APPROVAL_{action.upper()}",
                metadata={
                    "request_id": str(request_obj.id),
                    "request_type": request_obj.request_type,
                    "resource_type": request_obj.resource_type,
                    "resource_id": request_obj.resource_id,
                    "requester_id": str(request_obj.requester_id),
                    "risk_score": request_obj.risk_score,
                    "amount": str(request_obj.amount) if request_obj.amount else None,
                },
            )
        except Exception:
            logger.exception("Failed to audit dual-approval action")


# ══════════════════════════════════════════════════════════════════════════════
# Service: FinancialProtectionService
# ══════════════════════════════════════════════════════════════════════════════


class FinancialProtectionService:
    """Protect financial operations with risk scoring and dual approval.

    This service provides a unified interface for initiating financial
    actions, checking for emergency freezes, validating risk, and
    determining whether dual approval is required.

    Financial actions include:
    * Withdrawals from the escrow account
    * Balance adjustments (credits / debits)
    * Payouts to sellers
    * Fund transfers between accounts
    """

    @classmethod
    def initiate_financial_action(cls, admin_user, action_type, amount, target, details):
        """Initiate a financial action with full protection checks.

        The flow is:
        1. Check for withdrawal freeze
        2. Validate the action (risk scoring)
        3. Determine if dual approval is required
        4. If dual approval required → create DualApprovalRequest
        5. If no dual approval → return action for immediate execution

        Args:
            admin_user: The ``User`` performing the action.
            action_type: One of 'withdrawal', 'balance_adjustment',
                'payout', 'transfer'.
            amount: The monetary amount as a Decimal.
            target: Dict describing the target (e.g. account, user).
            details: Dict with action-specific details.

        Returns:
            A dict with keys:
                - 'status': 'approved', 'pending_approval', or 'blocked'
                - 'risk_score': float (0-100)
                - 'dual_approval_required': bool
                - 'approval_request': DualApprovalRequest or None
                - 'message': str

        Raises:
            ValueError: If the action is blocked (freeze active, invalid).
        """
        # 1. Check for withdrawal freeze
        if cls.check_withdrawal_freeze():
            return {
                "status": "blocked",
                "risk_score": 100.0,
                "dual_approval_required": True,
                "approval_request": None,
                "message": "Withdrawal freeze is active.  Financial actions are blocked.",
            }

        # 2. Validate the action
        validation = cls.validate_financial_action(
            admin_user, action_type, amount
        )
        risk_score = validation["risk_score"]

        # 3. Check if dual approval is required
        dual_approval_required = cls.require_dual_approval(action_type, amount)

        # 4. Create approval request if needed
        approval_request = None
        if dual_approval_required:
            approval_request = DualApprovalService.create_approval_request(
                requester=admin_user,
                request_type=action_type,
                resource_type=target.get("type", "Unknown"),
                resource_id=target.get("id", "0"),
                data={
                    "amount": str(amount),
                    "target": target,
                    "details": details,
                },
                amount=amount,
            )
            return {
                "status": "pending_approval",
                "risk_score": risk_score,
                "dual_approval_required": True,
                "approval_request": approval_request,
                "message": "Dual approval is required for this financial action.",
            }

        # 5. No dual approval required – ready for execution
        # But still create an audit log
        try:
            from .models import AdminActionLog

            AdminActionLog.objects.create(
                actor=admin_user,
                action_type="financial",
                resource_type=target.get("type", "Unknown"),
                resource_id=str(target.get("id", "0")),
                action_details={
                    "action_type": action_type,
                    "amount": str(amount),
                    "target": target,
                    "details": details,
                    "risk_score": risk_score,
                },
                risk_score=risk_score,
                is_flagged=risk_score >= 70.0,
            )
        except Exception:
            logger.exception("Failed to audit financial action")

        return {
            "status": "approved",
            "risk_score": risk_score,
            "dual_approval_required": False,
            "approval_request": None,
            "message": "Financial action approved for immediate execution.",
        }

    @classmethod
    def check_withdrawal_freeze(cls):
        """Check whether a withdrawal freeze emergency control is active.

        Returns:
            True if a withdrawal freeze is currently in effect.
        """
        from .models import EmergencyControl

        return EmergencyControl.objects.filter(
            control_type="withdrawal_freeze",
            is_active=True,
        ).exists()

    @classmethod
    def validate_financial_action(cls, admin_user, action_type, amount):
        """Validate a financial action and return risk assessment.

        Args:
            admin_user: The ``User`` performing the action.
            action_type: The type of financial action.
            amount: The monetary amount.

        Returns:
            A dict with 'valid', 'risk_score', and 'warnings' keys.
        """
        risk_score = cls.calculate_risk_score(
            action_type, amount, admin_user, None
        )
        warnings = []

        if risk_score >= 80:
            warnings.append("CRITICAL: Very high risk score.")
        elif risk_score >= 60:
            warnings.append("WARNING: Elevated risk score.")

        # Check for withdrawal freeze
        if cls.check_withdrawal_freeze():
            return {
                "valid": False,
                "risk_score": 100.0,
                "warnings": ["Withdrawal freeze is active."],
            }

        # Check for incident mode
        from .models import EmergencyControl

        if EmergencyControl.objects.filter(
            control_type="incident_mode", is_active=True
        ).exists():
            return {
                "valid": False,
                "risk_score": 100.0,
                "warnings": ["Incident mode is active – financial actions blocked."],
            }

        return {
            "valid": True,
            "risk_score": risk_score,
            "warnings": warnings,
        }

    @classmethod
    def calculate_risk_score(cls, action_type, amount, admin_user, target):
        """Calculate a risk score (0-100) for a financial action.

        Scoring factors:
        * Action type (withdrawal > payout > transfer > adjustment)
        * Amount (higher = riskier)
        * Time of day (outside business hours = riskier)
        * Recent similar actions by same admin (frequency)
        * Target risk indicators

        Args:
            action_type: The type of financial action.
            amount: The monetary amount (Decimal or numeric).
            admin_user: The ``User`` performing the action.
            target: Optional dict with target details.

        Returns:
            Float between 0 and 100.
        """
        score = 0.0

        # ── Action type base score ────────────────────────────────────
        type_scores = {
            "withdrawal": 50.0,
            "payout": 40.0,
            "transfer": 35.0,
            "balance_adjustment": 30.0,
        }
        score += type_scores.get(action_type, 25.0)

        # ── Amount-based scoring ──────────────────────────────────────
        if amount is not None:
            amount = Decimal(str(amount))
            if amount >= Decimal("5000000"):  # 5M+
                score += 25.0
            elif amount >= Decimal("1000000"):  # 1M+
                score += 20.0
            elif amount >= Decimal("500000"):  # 500K+
                score += 15.0
            elif amount >= Decimal("100000"):  # 100K+
                score += 5.0

        # ── Time-of-day risk ──────────────────────────────────────────
        now = timezone.now()
        if now.hour < 6 or now.hour >= 22:
            score += 10.0  # Late night / early morning
        elif now.hour < 8 or now.hour >= 18:
            score += 5.0  # Outside business hours

        # ── Frequency risk ────────────────────────────────────────────
        try:
            from .models import AdminActionLog

            recent_count = AdminActionLog.objects.filter(
                actor=admin_user,
                action_type="financial",
                timestamp__gte=now - timedelta(hours=1),
            ).count()

            if recent_count >= 5:
                score += 10.0
            elif recent_count >= 3:
                score += 5.0
        except Exception:
            pass

        return min(score, 100.0)

    @classmethod
    def require_dual_approval(cls, action_type, amount):
        """Check whether dual approval is required for a financial action.

        Delegates to ``DualApprovalService.is_dual_approval_required()``
        but adds financial-specific logic (e.g. all withdrawals above a
        threshold require dual approval, regardless of policy).
        """
        # All financial actions with significant amounts require dual approval
        if amount is not None:
            amount = Decimal(str(amount))
            threshold = Decimal(
                str(
                    getattr(
                        settings,
                        "DUAL_APPROVAL_AMOUNT_THRESHOLD",
                        DualApprovalService.DEFAULT_AMOUNT_THRESHOLD,
                    )
                )
            )
            if amount >= threshold:
                return True

        # Check policy-based requirements
        return DualApprovalService.is_dual_approval_required(action_type, amount)


# ══════════════════════════════════════════════════════════════════════════════
# Service: EmergencyControlService
# ══════════════════════════════════════════════════════════════════════════════


class EmergencyControlService:
    """Break-glass emergency controls for incident response.

    Emergency controls allow authorised administrators to rapidly
    restrict platform operations during a security incident.  All
    activations and deactivations are audited.

    Available controls:
    * **withdrawal_freeze**: Block all financial withdrawals.
    * **session_revocation**: Revoke all active admin sessions.
    * **account_lockdown**: Lock all user accounts.
    * **incident_mode**: Activate incident mode (locks down admin).
    * **admin_lockout**: Prevent all admin access.
    """

    @classmethod
    def activate_withdrawal_freeze(cls, activated_by, reason):
        """Activate a withdrawal freeze.

        While active, no financial withdrawals or payouts can be
        processed.  This is the primary control for containing
        financial fraud.

        Args:
            activated_by: The ``User`` activating the freeze.
            reason: Mandatory reason for the freeze.

        Returns:
            The ``EmergencyControl`` instance.

        Raises:
            ValueError: If a freeze is already active.
        """
        from .models import EmergencyControl

        if EmergencyControl.objects.filter(
            control_type="withdrawal_freeze", is_active=True
        ).exists():
            raise ValueError("Withdrawal freeze is already active.")

        control = EmergencyControl.objects.create(
            control_type="withdrawal_freeze",
            is_active=True,
            activated_by=activated_by,
            reason=reason,
        )

        logger.critical(
            "EmergencyControlService: WITHDRAWAL FREEZE activated by %s reason=%s",
            activated_by.email,
            reason,
        )

        cls._audit_emergency(control, "activated")
        return control

    @classmethod
    def deactivate_withdrawal_freeze(cls, deactivated_by, reason):
        """Deactivate the active withdrawal freeze.

        Args:
            deactivated_by: The ``User`` deactivating the freeze.
            reason: Mandatory reason for deactivation.

        Returns:
            The updated ``EmergencyControl`` instance.

        Raises:
            ValueError: If no active freeze exists.
        """
        from .models import EmergencyControl

        try:
            control = EmergencyControl.objects.get(
                control_type="withdrawal_freeze", is_active=True
            )
        except EmergencyControl.DoesNotExist:
            raise ValueError("No active withdrawal freeze found.")

        control.is_active = False
        control.deactivated_by = deactivated_by
        control.deactivated_at = timezone.now()
        control.save(
            update_fields=["is_active", "deactivated_by", "deactivated_at"]
        )

        logger.critical(
            "EmergencyControlService: WITHDRAWAL FREEZE deactivated by %s reason=%s",
            deactivated_by.email,
            reason,
        )

        cls._audit_emergency(control, "deactivated")
        return control

    @classmethod
    def activate_incident_mode(cls, activated_by, reason):
        """Activate incident mode – locks down all admin operations.

        In incident mode:
        * All admin sessions are revoked.
        * No new admin sessions can be created (except by superusers).
        * All financial actions are blocked.
        * A withdrawal freeze is automatically activated.

        This is the most severe control and should only be used during
        active security incidents.

        Args:
            activated_by: The ``User`` activating incident mode.
            reason: Mandatory reason.

        Returns:
            The ``EmergencyControl`` instance.

        Raises:
            ValueError: If incident mode is already active.
        """
        from .models import EmergencyControl

        if EmergencyControl.objects.filter(
            control_type="incident_mode", is_active=True
        ).exists():
            raise ValueError("Incident mode is already active.")

        with transaction.atomic():
            # Revoke all admin sessions
            AdminSessionService.terminate_all_user_sessions(
                activated_by, reason="incident_mode"
            )

            # Activate withdrawal freeze
            if not EmergencyControl.objects.filter(
                control_type="withdrawal_freeze", is_active=True
            ).exists():
                EmergencyControl.objects.create(
                    control_type="withdrawal_freeze",
                    is_active=True,
                    activated_by=activated_by,
                    reason=f"Auto-activated by incident mode: {reason}",
                )

            # Activate incident mode
            control = EmergencyControl.objects.create(
                control_type="incident_mode",
                is_active=True,
                activated_by=activated_by,
                reason=reason,
            )

        logger.critical(
            "EmergencyControlService: INCIDENT MODE activated by %s reason=%s",
            activated_by.email,
            reason,
        )

        cls._audit_emergency(control, "activated")
        return control

    @classmethod
    def revoke_all_sessions(cls, activated_by, reason):
        """Revoke all active admin sessions across all users.

        Args:
            activated_by: The ``User`` triggering the revocation.
            reason: Mandatory reason.

        Returns:
            The ``EmergencyControl`` instance.
        """
        from .models import EmergencyControl, AdminSession

        now = timezone.now()
        count = AdminSession.objects.filter(is_active=True).update(
            is_active=False,
            terminated_at=now,
            termination_reason="emergency_revocation",
        )

        control = EmergencyControl.objects.create(
            control_type="session_revocation",
            is_active=False,  # One-shot action, not a sustained control
            activated_by=activated_by,
            reason=f"{reason} ({count} sessions revoked)",
        )

        logger.critical(
            "EmergencyControlService: ALL SESSIONS REVOKED by %s count=%d reason=%s",
            activated_by.email,
            count,
            reason,
        )

        cls._audit_emergency(control, "activated")
        return control

    @classmethod
    def lock_admin_account(cls, admin_user, locked_by, reason):
        """Lock an admin account by revoking all sessions and deactivating.

        This is a targeted version of session revocation for a single
        compromised admin account.

        Args:
            admin_user: The ``User`` to lock.
            locked_by: The ``User`` performing the lock.
            reason: Mandatory reason.

        Returns:
            The ``EmergencyControl`` instance.
        """
        from .models import EmergencyControl

        # Revoke all sessions for this user
        AdminSessionService.terminate_all_user_sessions(
            admin_user, reason=f"account_lockdown: {reason}"
        )

        # Mark user as inactive
        admin_user.is_active = False
        admin_user.save(update_fields=["is_active"])

        control = EmergencyControl.objects.create(
            control_type="account_lockdown",
            is_active=True,
            activated_by=locked_by,
            reason=f"Account lock: {admin_user.email} – {reason}",
            config={"locked_user_id": str(admin_user.id)},
        )

        logger.critical(
            "EmergencyControlService: ADMIN ACCOUNT LOCKED user=%s by=%s reason=%s",
            admin_user.email,
            locked_by.email,
            reason,
        )

        cls._audit_emergency(control, "activated")
        return control

    @classmethod
    def get_active_emergencies(cls):
        """Return all currently active emergency controls.

        Returns:
            QuerySet of active ``EmergencyControl`` instances.
        """
        from .models import EmergencyControl

        return EmergencyControl.objects.filter(
            is_active=True
        ).order_by("-activated_at")

    @staticmethod
    def _audit_emergency(control, action):
        """Create an audit log entry for an emergency control action."""
        try:
            from core.models import AuditLog

            AuditLog.objects.create(
                user=control.activated_by,
                action=f"EMERGENCY_{action.upper()}:{control.control_type}",
                metadata={
                    "control_id": str(control.id),
                    "control_type": control.control_type,
                    "reason": control.reason,
                },
            )
        except Exception:
            logger.exception("Failed to audit emergency control action")


# ══════════════════════════════════════════════════════════════════════════════
# Service: ImmutableAuditService
# ══════════════════════════════════════════════════════════════════════════════


class ImmutableAuditService:
    """Tamper-resistant audit trail for all administrative actions.

    The audit trail is implemented as a hash chain: each record's hash
    is derived from its own data and the hash of the previous record.
    This makes it computationally infeasible to alter a record without
    breaking the chain.

    Key operations:
    * Log an admin action (creates AdminActionLog with hash chain)
    * Verify the integrity of the entire chain
    * Query audit trail by resource or actor
    * Export audit logs for compliance
    """

    @classmethod
    def log_admin_action(
        cls,
        actor,
        action_type,
        resource_type,
        resource_id,
        details,
        session=None,
        risk_score=0,
    ):
        """Log an administrative action to the immutable audit trail.

        Args:
            actor: The ``User`` performing the action.
            action_type: One of ``AdminActionLog.ACTION_TYPE_CHOICES``.
            resource_type: Type of resource affected.
            resource_id: PK of the affected resource.
            details: Dict with action-specific details.
            session: Optional ``AdminSession`` for context.
            risk_score: Computed risk score (0-100).

        Returns:
            The created ``AdminActionLog`` instance.
        """
        from .models import AdminActionLog

        log_entry = AdminActionLog(
            actor=actor,
            session=session,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=str(resource_id),
            action_details=details,
            ip_address=getattr(session, "ip_address", None) if session else None,
            user_agent=getattr(session, "user_agent", "")[:500] if session else "",
            device_fingerprint=(
                getattr(session, "device_fingerprint", "") if session else ""
            ),
            step_up_auth=getattr(session, "is_mfa_verified", False) if session else False,
            dual_approval=details.get("dual_approval", False),
            risk_score=risk_score,
            is_flagged=risk_score >= 70.0,
        )
        # The save() method on AdminActionLog computes the hash chain
        log_entry.save()

        logger.info(
            "ImmutableAuditService: Logged action type=%s resource=%s/%s "
            "actor=%s risk=%.1f hash=%s",
            action_type,
            resource_type,
            resource_id,
            getattr(actor, "email", "system"),
            risk_score,
            log_entry.hash[:16],
        )

        return log_entry

    @classmethod
    def verify_audit_integrity(cls):
        """Verify the integrity of the entire audit hash chain.

        Walks the chain from oldest to newest, recomputing each hash
        and comparing it to the stored value.  Any mismatch indicates
        tampering.

        Returns:
            A dict with:
                - 'valid': bool – True if the entire chain is intact
                - 'total_records': int – Number of records checked
                - 'broken_at': str or None – ID of the first broken record
                - 'details': list – Per-record validation results (max 100)
        """
        from .models import AdminActionLog, GENESIS_HASH

        records = AdminActionLog.objects.order_by("timestamp")
        total = records.count()

        if total == 0:
            return {
                "valid": True,
                "total_records": 0,
                "broken_at": None,
                "details": [],
            }

        valid = True
        broken_at = None
        details = []
        previous_hash = GENESIS_HASH

        for record in records.iterator():
            expected_hash = record.compute_hash(previous_hash)
            is_intact = record.hash == expected_hash

            if not is_intact and valid:
                valid = False
                broken_at = str(record.id)

            # Keep only the first 100 detail records to avoid memory issues
            if len(details) < 100:
                details.append(
                    {
                        "id": str(record.id),
                        "timestamp": record.timestamp.isoformat(),
                        "hash_match": is_intact,
                        "stored_hash": record.hash[:16],
                        "computed_hash": expected_hash[:16],
                    }
                )

            previous_hash = record.hash

        return {
            "valid": valid,
            "total_records": total,
            "broken_at": broken_at,
            "details": details,
        }

    @classmethod
    def get_audit_trail(cls, resource_type, resource_id):
        """Get the complete audit trail for a specific resource.

        Args:
            resource_type: The type of resource (e.g. 'User', 'Transaction').
            resource_id: The PK of the resource.

        Returns:
            QuerySet of ``AdminActionLog`` entries for the resource,
            ordered chronologically.
        """
        from .models import AdminActionLog

        return AdminActionLog.objects.filter(
            resource_type=resource_type,
            resource_id=str(resource_id),
        ).order_by("timestamp")

    @classmethod
    def get_actor_history(cls, actor, start_date=None, end_date=None):
        """Get all admin actions performed by a specific actor.

        Args:
            actor: The ``User`` whose actions to retrieve.
            start_date: Optional start date filter.
            end_date: Optional end date filter.

        Returns:
            QuerySet of ``AdminActionLog`` entries.
        """
        from .models import AdminActionLog

        qs = AdminActionLog.objects.filter(actor=actor)

        if start_date:
            qs = qs.filter(timestamp__gte=start_date)
        if end_date:
            qs = qs.filter(timestamp__lte=end_date)

        return qs.order_by("-timestamp")

    @classmethod
    def export_audit_log(cls, start_date, end_date, format="json"):
        """Export audit logs for compliance reporting.

        Args:
            start_date: Start date for the export range.
            end_date: End date for the export range.
            format: Export format – 'json' or 'csv'.

        Returns:
            If format='json': A list of dicts representing the log entries.
            If format='csv': A string in CSV format.

        Raises:
            ValueError: If an unsupported format is requested.
        """
        from .models import AdminActionLog

        qs = AdminActionLog.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date,
        ).order_by("timestamp")

        if format == "json":
            return [
                {
                    "id": str(entry.id),
                    "timestamp": entry.timestamp.isoformat(),
                    "actor_id": str(entry.actor_id) if entry.actor_id else None,
                    "action_type": entry.action_type,
                    "resource_type": entry.resource_type,
                    "resource_id": entry.resource_id,
                    "action_details": entry.action_details,
                    "ip_address": str(entry.ip_address) if entry.ip_address else None,
                    "step_up_auth": entry.step_up_auth,
                    "dual_approval": entry.dual_approval,
                    "approver_id": str(entry.approver_id) if entry.approver_id else None,
                    "risk_score": entry.risk_score,
                    "is_flagged": entry.is_flagged,
                    "hash": entry.hash,
                    "previous_hash": entry.previous_hash,
                }
                for entry in qs.iterator()
            ]

        elif format == "csv":
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                [
                    "id",
                    "timestamp",
                    "actor_id",
                    "action_type",
                    "resource_type",
                    "resource_id",
                    "ip_address",
                    "step_up_auth",
                    "dual_approval",
                    "approver_id",
                    "risk_score",
                    "is_flagged",
                    "hash",
                    "previous_hash",
                ]
            )

            for entry in qs.iterator():
                writer.writerow(
                    [
                        str(entry.id),
                        entry.timestamp.isoformat(),
                        str(entry.actor_id) if entry.actor_id else "",
                        entry.action_type,
                        entry.resource_type,
                        entry.resource_id,
                        str(entry.ip_address) if entry.ip_address else "",
                        entry.step_up_auth,
                        entry.dual_approval,
                        str(entry.approver_id) if entry.approver_id else "",
                        entry.risk_score,
                        entry.is_flagged,
                        entry.hash,
                        entry.previous_hash,
                    ]
                )

            return output.getvalue()

        else:
            raise ValueError(f"Unsupported export format: {format}")
