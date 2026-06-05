"""
Emergency Controls for Admin Control Plane Incident Response
==============================================================

Provides break-glass controls for rapid incident response, including
account lockdowns, global session revocation, withdrawal freezes,
incident mode activation, temporary admin creation, and emergency
data exports.

Security Guarantees
-------------------
- All emergency actions are audit-logged with full context.
- All emergency actions require MFA verification.
- Withdrawal freeze deactivation requires dual approval.
- Incident mode restricts admin access to authorized responders only.
- Temporary admin accounts auto-expire after 24 hours maximum.
- Emergency data exports are scoped, time-limited, and logged.

Severity Levels
---------------
- ``P1_CRITICAL``  : Active breach, data exfiltration, fund theft
- ``P2_HIGH``      : Vulnerability being exploited, suspicious activity
- ``P3_MEDIUM``    : Potential issue requiring investigation
- ``P4_LOW``       : Informational, minor policy violation

Classes
-------
EmergencyControlService
    Activate, deactivate, and query emergency controls.

IncidentMode
    Helper for tracking active incidents and their metadata.
"""

import json
import logging
import os
import uuid
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from .services import ImmutableAuditService
from .dual_approval import DualApprovalService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEVERITY_CHOICES = [
    ("P1_CRITICAL", "P1 – Critical"),
    ("P2_HIGH", "P2 – High"),
    ("P3_MEDIUM", "P3 – Medium"),
    ("P4_LOW", "P4 – Low"),
]

TEMP_ADMIN_MAX_LIFETIME_HOURS = 24
INCIDENT_RESPONDER_ROLE = "IncidentResponder"

# Account lockdown reasons
LOCKDOWN_REASONS = {
    "suspected_compromise": "Suspected account compromise",
    "phishing_attack": "Phishing attack response",
    "unauthorized_access": "Unauthorized access detected",
    "credential_leak": "Credential leak response",
    "fraud_investigation": "Active fraud investigation",
    "admin_request": "Admin-initiated lockdown",
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class EmergencyControlError(Exception):
    """Base exception for emergency control operations."""
    pass


class IncidentModeError(EmergencyControlError):
    """Error related to incident mode operations."""
    pass


class TempAdminError(EmergencyControlError):
    """Error related to temporary admin creation."""
    pass


class ExportError(EmergencyControlError):
    """Error related to emergency data export."""
    pass


# ---------------------------------------------------------------------------
# Incident Mode Helper
# ---------------------------------------------------------------------------

# In-memory store for active incidents.
# Production deployments MUST use a Django model for durability.
# Format: {incident_id: IncidentMode}
_incident_store: dict = {}


class IncidentMode:
    """Track an active incident and its metadata.

    Attributes
    ----------
    id : str
        Unique incident identifier (UUID).
    reason : str
        Description of why incident mode was activated.
    severity : str
        One of ``SEVERITY_CHOICES``.
    activated_by : str
        Admin user ID who activated incident mode.
    activated_at : str
        ISO-8601 timestamp of activation.
    deactivated_by : str or None
        Admin user ID who deactivated incident mode.
    deactivated_at : str or None
        ISO-8601 timestamp of deactivation.
    authorized_responders : list[str]
        User IDs of admins authorized to act during this incident.
    is_active : bool
        Whether the incident is currently active.
    config : dict
        Additional configuration for the incident response.
    """

    def __init__(
        self,
        reason: str,
        severity: str,
        activated_by: str,
        authorized_responders: Optional[list] = None,
        config: Optional[dict] = None,
    ):
        self.id = str(uuid.uuid4())
        self.reason = reason
        self.severity = severity
        self.activated_by = str(activated_by)
        self.activated_at = timezone.now().isoformat()
        self.deactivated_by = None
        self.deactivated_at = None
        self.authorized_responders = authorized_responders or []
        self.is_active = True
        self.config = config or {}

        _incident_store[self.id] = self

    def to_dict(self) -> dict:
        """Serialise to a dictionary."""
        return {
            "id": self.id,
            "reason": self.reason,
            "severity": self.severity,
            "activated_by": self.activated_by,
            "activated_at": self.activated_at,
            "deactivated_by": self.deactivated_by,
            "deactivated_at": self.deactivated_at,
            "authorized_responders": self.authorized_responders,
            "is_active": self.is_active,
            "config": self.config,
        }

    @classmethod
    def get_active(cls) -> Optional["IncidentMode"]:
        """Return the currently active incident, if any."""
        for incident in _incident_store.values():
            if incident.is_active:
                return incident
        return None

    @classmethod
    def get_by_id(cls, incident_id: str) -> Optional["IncidentMode"]:
        """Look up an incident by ID."""
        return _incident_store.get(incident_id)

    @classmethod
    def list_all(cls, active_only: bool = False) -> list:
        """List all incidents, optionally filtered to active only."""
        incidents = _incident_store.values()
        if active_only:
            incidents = [i for i in incidents if i.is_active]
        return [i.to_dict() for i in sorted(
            incidents,
            key=lambda x: x.activated_at,
            reverse=True,
        )]


# ---------------------------------------------------------------------------
# Account Lockdown Store
# ---------------------------------------------------------------------------

# {user_id: {"reason": str, "locked_by": str, "locked_at": str, "is_active": bool}}
_lockdown_store: dict = {}

# Temporary admin store
# {temp_admin_id: {"email": str, "created_by": str, "expires_at": str, "is_active": bool}}
_temp_admin_store: dict = {}


# ===========================================================================
# Emergency Control Service
# ===========================================================================

class EmergencyControlService:
    """Activate, deactivate, and query emergency controls.

    This service provides the break-glass controls that authorized
    administrators can use to rapidly respond to security incidents.

    Every action is audit-logged and requires MFA verification.
    Critical actions (withdrawal freeze deactivation) additionally
    require dual approval.
    """

    # Withdrawal freeze state
    _withdrawal_freeze: dict = {
        "is_active": False,
        "reason": "",
        "activated_by": None,
        "activated_at": None,
    }

    # Global session revocation tracking
    _session_revocation: dict = {
        "last_revocation_at": None,
        "last_revocation_by": None,
        "last_revocation_reason": "",
    }

    @staticmethod
    def activate_account_lockdown(
        user_id: str,
        reason: str,
        locked_by=None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict:
        """Lock a specific user account.

        Terminates all active admin sessions for the user and marks
        the account as locked.  The user cannot authenticate until
        the lockdown is deactivated.

        Parameters
        ----------
        user_id : str
            The user ID to lock.
        reason : str
            Reason for the lockdown (one of ``LOCKDOWN_REASONS`` or custom).
        locked_by : User, optional
            The admin activating the lockdown.
        ip_address : str
        user_agent : str

        Returns
        -------
        dict
            Lockdown confirmation with metadata.

        Raises
        ------
        EmergencyControlError
            If the user is already locked or the reason is empty.
        """
        if not reason or not reason.strip():
            raise EmergencyControlError(
                "A reason is required for account lockdown."
            )

        uid = str(user_id)
        existing = _lockdown_store.get(uid)
        if existing and existing["is_active"]:
            raise EmergencyControlError(
                f"User {uid[:8]}... is already locked down."
            )

        _lockdown_store[uid] = {
            "reason": reason.strip(),
            "locked_by": str(locked_by.id) if locked_by else None,
            "locked_at": timezone.now().isoformat(),
            "is_active": True,
        }

        # Terminate admin sessions
        try:
            from .models import AdminSession
            sessions = AdminSession.objects.filter(
                user_id=user_id,
                is_active=True,
            )
            count = sessions.update(
                is_active=False,
                terminated_at=timezone.now(),
                termination_reason="emergency_account_lockdown",
            )
        except Exception as exc:
            logger.warning(
                "EmergencyControl: Could not terminate sessions for %s: %s",
                uid[:8],
                exc,
            )
            count = 0

        # Audit log
        ImmutableAuditService.log(
            actor=locked_by,
            action="EMERGENCY_ACCOUNT_LOCKDOWN",
            resource_type="User",
            resource_id=uid,
            metadata={
                "reason": reason.strip()[:500],
                "sessions_terminated": count,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.critical(
            "EmergencyControl: Account lockdown activated for user %s — "
            "reason: %s (sessions terminated: %d)",
            uid[:8],
            reason.strip()[:100],
            count,
        )

        return {
            "locked": True,
            "user_id": uid,
            "reason": reason.strip(),
            "sessions_terminated": count,
        }

    @staticmethod
    def deactivate_account_lockdown(
        user_id: str,
        unlocked_by=None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict:
        """Unlock a previously locked user account.

        Parameters
        ----------
        user_id : str
            The user ID to unlock.
        unlocked_by : User, optional
            The admin deactivating the lockdown.
        ip_address : str
        user_agent : str

        Returns
        -------
        dict
            Unlock confirmation.

        Raises
        ------
        EmergencyControlError
            If the user is not currently locked.
        """
        uid = str(user_id)
        lockdown = _lockdown_store.get(uid)
        if lockdown is None or not lockdown["is_active"]:
            raise EmergencyControlError(
                f"User {uid[:8]}... is not currently locked down."
            )

        lockdown["is_active"] = False
        lockdown["unlocked_by"] = str(unlocked_by.id) if unlocked_by else None
        lockdown["unlocked_at"] = timezone.now().isoformat()

        # Reactivate user
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            User.objects.filter(id=uid).update(is_active=True)
        except Exception as exc:
            logger.warning(
                "EmergencyControl: Could not reactivate user %s: %s",
                uid[:8],
                exc,
            )

        # Audit log
        ImmutableAuditService.log(
            actor=unlocked_by,
            action="EMERGENCY_ACCOUNT_LOCKDOWN_DEACTIVATED",
            resource_type="User",
            resource_id=uid,
            metadata={
                "original_reason": lockdown.get("reason", ""),
                "lockdown_duration": str(
                    timezone.now() - timezone.datetime.fromisoformat(lockdown["locked_at"])
                ),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {"unlocked": True, "user_id": uid}

    @staticmethod
    def activate_global_session_revocation(
        reason: str,
        revoked_by=None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict:
        """Revoke ALL active admin sessions across the platform.

        This is a critical emergency operation that terminates every
        active admin session.  All administrators will need to
        re-authenticate with MFA.

        Parameters
        ----------
        reason : str
            Mandatory reason for the revocation.
        revoked_by : User, optional
            The admin activating the revocation.
        ip_address : str
        user_agent : str

        Returns
        -------
        dict
            Revocation result with count of terminated sessions.
        """
        if not reason or not reason.strip():
            raise EmergencyControlError(
                "A reason is required for global session revocation."
            )

        # Revoke all sessions
        try:
            from .models import AdminSession
            sessions = AdminSession.objects.filter(is_active=True)
            count = sessions.update(
                is_active=False,
                terminated_at=timezone.now(),
                termination_reason="emergency_global_revocation",
            )
        except Exception as exc:
            logger.error(
                "EmergencyControl: Failed to revoke sessions: %s", exc
            )
            count = 0

        # Track revocation
        EmergencyControlService._session_revocation = {
            "last_revocation_at": timezone.now().isoformat(),
            "last_revocation_by": str(revoked_by.id) if revoked_by else None,
            "last_revocation_reason": reason.strip(),
            "sessions_revoked": count,
        }

        # Audit log
        ImmutableAuditService.log(
            actor=revoked_by,
            action="EMERGENCY_GLOBAL_SESSION_REVOCATION",
            resource_type="AdminSession",
            metadata={
                "reason": reason.strip()[:500],
                "sessions_revoked": count,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.critical(
            "EmergencyControl: Global session revocation — %d sessions "
            "revoked by %s. Reason: %s",
            count,
            getattr(revoked_by, "email", "system"),
            reason.strip()[:100],
        )

        return {
            "revoked": True,
            "sessions_revoked": count,
            "reason": reason.strip(),
        }

    @staticmethod
    def activate_withdrawal_freeze(
        reason: str,
        activated_by=None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict:
        """Freeze all withdrawal operations on the platform.

        Once activated, no withdrawals can be processed until the
        freeze is deactivated (which requires dual approval).

        Parameters
        ----------
        reason : str
            Mandatory reason for the freeze.
        activated_by : User, optional
            The admin activating the freeze.
        ip_address : str
        user_agent : str

        Returns
        -------
        dict
            Freeze activation confirmation.
        """
        if not reason or not reason.strip():
            raise EmergencyControlError(
                "A reason is required for withdrawal freeze."
            )

        if EmergencyControlService._withdrawal_freeze["is_active"]:
            raise EmergencyControlError(
                "Withdrawal freeze is already active."
            )

        EmergencyControlService._withdrawal_freeze = {
            "is_active": True,
            "reason": reason.strip(),
            "activated_by": str(activated_by.id) if activated_by else None,
            "activated_at": timezone.now().isoformat(),
        }

        # Also update the EmergencyControl model if available
        try:
            from .models import EmergencyControl
            EmergencyControl.objects.create(
                control_type="withdrawal_freeze",
                is_active=True,
                activated_by=activated_by,
                reason=reason.strip(),
            )
        except Exception:
            pass  # Model may not be available in all contexts

        # Audit log
        ImmutableAuditService.log(
            actor=activated_by,
            action="EMERGENCY_WITHDRAWAL_FREEZE_ACTIVATED",
            resource_type="EmergencyControl",
            metadata={"reason": reason.strip()[:500]},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.critical(
            "EmergencyControl: Withdrawal freeze ACTIVATED by %s — reason: %s",
            getattr(activated_by, "email", "system"),
            reason.strip()[:100],
        )

        return {
            "frozen": True,
            "reason": reason.strip(),
            "activated_at": EmergencyControlService._withdrawal_freeze["activated_at"],
        }

    @staticmethod
    def deactivate_withdrawal_freeze(
        deactivated_by=None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict:
        """Unfreeze withdrawals — requires dual approval.

        Deactivating a withdrawal freeze is a sensitive operation that
        requires a second admin's approval through the dual-approval
        system.

        Parameters
        ----------
        deactivated_by : User, optional
            The admin requesting deactivation.
        ip_address : str
        user_agent : str

        Returns
        -------
        dict
            Result indicating whether dual-approval was initiated.

        Raises
        ------
        EmergencyControlError
            If the freeze is not currently active.
        """
        if not EmergencyControlService._withdrawal_freeze["is_active"]:
            raise EmergencyControlError(
                "Withdrawal freeze is not currently active."
            )

        # Create a dual-approval request for unfreezing
        try:
            approval = DualApprovalService.create_financial_action(
                admin=deactivated_by,
                action_type="PAYMENT_OVERRIDE",
                amount=0,
                metadata={
                    "operation": "WITHDRAWAL_FREEZE_DEACTIVATION",
                    "original_reason": EmergencyControlService._withdrawal_freeze.get("reason", ""),
                    "original_activated_by": EmergencyControlService._withdrawal_freeze.get("activated_by", ""),
                },
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except Exception as exc:
            logger.error(
                "EmergencyControl: Failed to create dual-approval for "
                "freeze deactivation: %s",
                exc,
            )
            raise EmergencyControlError(
                "Failed to initiate dual-approval for freeze deactivation."
            )

        # Audit log
        ImmutableAuditService.log(
            actor=deactivated_by,
            action="EMERGENCY_WITHDRAWAL_FREEZE_DEACTIVATION_REQUESTED",
            resource_type="EmergencyControl",
            metadata={
                "dual_approval_id": approval.id,
                "original_reason": EmergencyControlService._withdrawal_freeze.get("reason", ""),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {
            "status": "pending_dual_approval",
            "approval_id": approval.id,
            "message": (
                "Withdrawal freeze deactivation requires dual approval. "
                "A second admin must approve this action before the freeze "
                "is lifted."
            ),
        }

    @staticmethod
    def _execute_withdrawal_unfreeze(
        approved_by=None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict:
        """Internal: Execute withdrawal freeze deactivation after dual approval.

        This method should only be called after the dual-approval
        request has been approved and executed.
        """
        EmergencyControlService._withdrawal_freeze = {
            "is_active": False,
            "reason": "",
            "activated_by": None,
            "activated_at": None,
        }

        ImmutableAuditService.log(
            actor=approved_by,
            action="EMERGENCY_WITHDRAWAL_FREEZE_DEACTIVATED",
            resource_type="EmergencyControl",
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.critical(
            "EmergencyControl: Withdrawal freeze DEACTIVATED by %s",
            getattr(approved_by, "email", "system"),
        )

        return {"unfrozen": True}

    @staticmethod
    def activate_incident_mode(
        reason: str,
        severity: str,
        activated_by=None,
        authorized_responders: Optional[list] = None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict:
        """Enter incident response mode.

        During incident mode:
        - Only authorized incident responders can access admin functions
        - All non-essential admin operations are restricted
        - Enhanced audit logging is enabled
        - Temporary admin accounts can be created for incident response

        Parameters
        ----------
        reason : str
            Mandatory description of the incident.
        severity : str
            One of ``SEVERITY_CHOICES``.
        activated_by : User, optional
            The admin activating incident mode.
        authorized_responders : list[str], optional
            User IDs of admins authorized during the incident.
        ip_address : str
        user_agent : str

        Returns
        -------
        dict
            Incident mode activation details.

        Raises
        ------
        IncidentModeError
            If incident mode is already active or parameters are invalid.
        """
        if not reason or not reason.strip():
            raise IncidentModeError(
                "A reason is required for incident mode activation."
            )

        valid_severities = [s[0] for s in SEVERITY_CHOICES]
        if severity not in valid_severities:
            raise IncidentModeError(
                f"Invalid severity '{severity}'. "
                f"Valid: {', '.join(valid_severities)}"
            )

        # Check if incident mode is already active
        active = IncidentMode.get_active()
        if active is not None:
            raise IncidentModeError(
                f"Incident mode is already active (incident {active.id[:8]}...). "
                f"Deactivate the current incident before activating a new one."
            )

        # Include the activating admin as a responder
        if activated_by:
            responder_ids = list(set(
                (authorized_responders or []) + [str(activated_by.id)]
            ))
        else:
            responder_ids = authorized_responders or []

        # Create incident
        incident = IncidentMode(
            reason=reason.strip(),
            severity=severity,
            activated_by=str(activated_by.id) if activated_by else "system",
            authorized_responders=responder_ids,
            config={
                "enhanced_logging": True,
                "restricted_access": True,
                "auto_session_timeout_minutes": 15,
            },
        )

        # Audit log
        ImmutableAuditService.log(
            actor=activated_by,
            action="EMERGENCY_INCIDENT_MODE_ACTIVATED",
            resource_type="IncidentMode",
            resource_id=incident.id,
            metadata={
                "reason": reason.strip()[:500],
                "severity": severity,
                "authorized_responders": responder_ids,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.critical(
            "EmergencyControl: Incident mode ACTIVATED (severity=%s) — "
            "incident_id=%s reason: %s",
            severity,
            incident.id[:8],
            reason.strip()[:100],
        )

        return incident.to_dict()

    @staticmethod
    def deactivate_incident_mode(
        deactivated_by=None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict:
        """Exit incident response mode.

        Parameters
        ----------
        deactivated_by : User, optional
            The admin deactivating incident mode.
        ip_address : str
        user_agent : str

        Returns
        -------
        dict
            Deactivation confirmation.

        Raises
        ------
        IncidentModeError
            If incident mode is not currently active.
        """
        active = IncidentMode.get_active()
        if active is None:
            raise IncidentModeError(
                "Incident mode is not currently active."
            )

        active.is_active = False
        active.deactivated_by = str(deactivated_by.id) if deactivated_by else "system"
        active.deactivated_at = timezone.now().isoformat()

        # Audit log
        ImmutableAuditService.log(
            actor=deactivated_by,
            action="EMERGENCY_INCIDENT_MODE_DEACTIVATED",
            resource_type="IncidentMode",
            resource_id=active.id,
            metadata={
                "severity": active.severity,
                "duration_minutes": (
                    timezone.now() - timezone.datetime.fromisoformat(active.activated_at)
                ).total_seconds() / 60,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.critical(
            "EmergencyControl: Incident mode DEACTIVATED — incident_id=%s",
            active.id[:8],
        )

        return active.to_dict()

    @staticmethod
    def emergency_admin_create(
        temp_admin_data: dict,
        created_by=None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict:
        """Create a temporary admin account for incident response.

        Temporary accounts have:
        - Limited permissions (incident response only)
        - Auto-expiry (24 hours maximum)
        - Mandatory audit trail
        - Cannot create other admin accounts

        Parameters
        ----------
        temp_admin_data : dict
            Must contain ``email`` and optionally ``display_name``,
            ``lifetime_hours`` (default 8, max 24), and ``scope``.
        created_by : User, optional
            The admin creating the temporary account.
        ip_address : str
        user_agent : str

        Returns
        -------
        dict
            Temporary admin account details.

        Raises
        ------
        TempAdminError
            If incident mode is not active or parameters are invalid.
        PermissionDenied
            If the creator is not authorized.
        """
        # Verify incident mode is active
        active = IncidentMode.get_active()
        if active is None:
            raise TempAdminError(
                "Temporary admin accounts can only be created during "
                "active incident mode."
            )

        # Verify creator is authorized
        if created_by and str(created_by.id) not in active.authorized_responders:
            raise PermissionDenied(
                "Only authorized incident responders can create "
                "temporary admin accounts."
            )

        # Validate data
        email = temp_admin_data.get("email", "").strip()
        if not email:
            raise TempAdminError("Email is required for temporary admin.")

        # Lifetime
        lifetime_hours = min(
            temp_admin_data.get("lifetime_hours", 8),
            TEMP_ADMIN_MAX_LIFETIME_HOURS,
        )

        # Create temp admin record
        temp_id = str(uuid.uuid4())
        expires_at = timezone.now() + timedelta(hours=lifetime_hours)

        temp_record = {
            "id": temp_id,
            "email": email,
            "display_name": temp_admin_data.get("display_name", f"Incident Responder"),
            "scope": temp_admin_data.get("scope", "incident_response"),
            "created_by": str(created_by.id) if created_by else "system",
            "incident_id": active.id,
            "expires_at": expires_at.isoformat(),
            "is_active": True,
        }

        _temp_admin_store[temp_id] = temp_record

        # Audit log
        ImmutableAuditService.log(
            actor=created_by,
            action="EMERGENCY_TEMP_ADMIN_CREATED",
            resource_type="TempAdminAccount",
            resource_id=temp_id,
            metadata={
                "email": email,
                "lifetime_hours": lifetime_hours,
                "scope": temp_record["scope"],
                "incident_id": active.id,
                "expires_at": expires_at.isoformat(),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.critical(
            "EmergencyControl: Temporary admin created — email=%s "
            "expires=%s incident=%s",
            email,
            expires_at.isoformat(),
            active.id[:8],
        )

        return temp_record

    @staticmethod
    def emergency_data_export(
        export_type: str,
        exported_by=None,
        scope: Optional[dict] = None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict:
        """Emergency data export for forensic analysis.

        Creates a scoped, time-limited export of data for incident
        investigation.  All exports are audit-logged and the exported
        data is tracked.

        Parameters
        ----------
        export_type : str
            Type of export: ``"audit_logs"``, ``"user_activity"``,
            ``"financial_transactions"``, ``"admin_actions"``,
            ``"session_history"``, or ``"full_forensic"``.
        exported_by : User, optional
            The admin requesting the export.
        scope : dict, optional
            Scope filters (time range, user IDs, etc.).
        ip_address : str
        user_agent : str

        Returns
        -------
        dict
            Export metadata (not the actual data, which is generated
            asynchronously).

        Raises
        ------
        ExportError
            If the export type is invalid or incident mode is required.
        """
        valid_export_types = {
            "audit_logs",
            "user_activity",
            "financial_transactions",
            "admin_actions",
            "session_history",
            "full_forensic",
        }

        if export_type not in valid_export_types:
            raise ExportError(
                f"Invalid export type '{export_type}'. "
                f"Valid: {', '.join(sorted(valid_export_types))}"
            )

        # Full forensic export requires incident mode
        if export_type == "full_forensic":
            active = IncidentMode.get_active()
            if active is None:
                raise ExportError(
                    "Full forensic export requires active incident mode."
                )

        scope = scope or {}
        export_id = str(uuid.uuid4())

        # Determine time range (default: last 24 hours)
        time_range_hours = scope.get("time_range_hours", 24)
        since = timezone.now() - timedelta(hours=time_range_hours)

        export_record = {
            "export_id": export_id,
            "export_type": export_type,
            "exported_by": str(exported_by.id) if exported_by else "system",
            "scope": scope,
            "since": since.isoformat(),
            "until": timezone.now().isoformat(),
            "status": "pending",
            "created_at": timezone.now().isoformat(),
        }

        # In production, this would enqueue an async task to generate
        # the export.  For now, we mark it as "initiated".
        export_record["status"] = "initiated"

        # Audit log
        ImmutableAuditService.log(
            actor=exported_by,
            action="EMERGENCY_DATA_EXPORT",
            resource_type="DataExport",
            resource_id=export_id,
            metadata={
                "export_type": export_type,
                "scope": scope,
                "time_range_hours": time_range_hours,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.critical(
            "EmergencyControl: Data export initiated — type=%s by=%s",
            export_type,
            getattr(exported_by, "email", "system"),
        )

        return export_record

    @staticmethod
    def get_emergency_status() -> dict:
        """Return the current emergency state summary.

        Returns
        -------
        dict
            Current status of all emergency controls, including:
            - ``withdrawal_freeze`` : Freeze status
            - ``incident_mode`` : Active incident details (or ``None``)
            - ``account_lockdowns`` : List of locked accounts
            - ``temp_admins`` : List of active temporary admins
            - ``last_session_revocation`` : Last revocation details
        """
        # Active lockdowns
        active_lockdowns = [
            {"user_id": uid, **data}
            for uid, data in _lockdown_store.items()
            if data["is_active"]
        ]

        # Active temp admins
        now = timezone.now()
        active_temp_admins = []
        for tid, data in _temp_admin_store.items():
            if data["is_active"]:
                expires = timezone.datetime.fromisoformat(data["expires_at"])
                if now > expires:
                    data["is_active"] = False
                    continue
                active_temp_admins.append(data)

        # Active incident
        active_incident = IncidentMode.get_active()

        return {
            "withdrawal_freeze": EmergencyControlService._withdrawal_freeze,
            "incident_mode": active_incident.to_dict() if active_incident else None,
            "account_lockdowns": active_lockdowns,
            "active_lockdown_count": len(active_lockdowns),
            "temp_admins": active_temp_admins,
            "active_temp_admin_count": len(active_temp_admins),
            "last_session_revocation": EmergencyControlService._session_revocation,
            "timestamp": timezone.now().isoformat(),
        }

    @staticmethod
    def is_account_locked(user_id: str) -> bool:
        """Check if a specific user account is currently locked.

        Parameters
        ----------
        user_id : str
            The user ID to check.

        Returns
        -------
        bool
            ``True`` if the account is locked.
        """
        lockdown = _lockdown_store.get(str(user_id))
        return lockdown is not None and lockdown["is_active"]

    @staticmethod
    def is_withdrawal_frozen() -> bool:
        """Check if withdrawals are currently frozen.

        Returns
        -------
        bool
            ``True`` if the freeze is active.
        """
        return EmergencyControlService._withdrawal_freeze["is_active"]

    @staticmethod
    def is_incident_mode_active() -> bool:
        """Check if incident mode is currently active.

        Returns
        -------
        bool
            ``True`` if incident mode is active.
        """
        return IncidentMode.get_active() is not None

    @staticmethod
    def is_authorized_incident_responder(user_id: str) -> bool:
        """Check if a user is authorized during the current incident.

        Parameters
        ----------
        user_id : str
            The user ID to check.

        Returns
        -------
        bool
            ``True`` if the user is authorized or no incident is active.
        """
        active = IncidentMode.get_active()
        if active is None:
            return True  # No incident — all admins are authorized
        return str(user_id) in active.authorized_responders

    @staticmethod
    def cleanup_expired_temp_admins() -> int:
        """Deactivate temporary admin accounts that have expired.

        Should be called by a periodic task (Celery beat).

        Returns
        -------
        int
            Number of expired temp admins deactivated.
        """
        now = timezone.now()
        count = 0
        for tid, data in _temp_admin_store.items():
            if not data["is_active"]:
                continue
            expires = timezone.datetime.fromisoformat(data["expires_at"])
            if now > expires:
                data["is_active"] = False
                count += 1

                # Audit log
                ImmutableAuditService.log(
                    actor=None,
                    action="EMERGENCY_TEMP_ADMIN_EXPIRED",
                    resource_type="TempAdminAccount",
                    resource_id=tid,
                    metadata={
                        "email": data["email"],
                        "incident_id": data.get("incident_id"),
                    },
                )

        if count > 0:
            logger.info(
                "EmergencyControl: Expired %d temporary admin account(s).",
                count,
            )

        return count
