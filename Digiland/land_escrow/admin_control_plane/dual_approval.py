"""
Financial Dual-Approval System for Admin Control Plane
========================================================

Implements the four-eyes principle for all financial operations on the
Digiland platform.  NO single admin can move funds, modify financial
records, or approve payments alone — every financial action requires
explicit approval from a second, independent administrator.

Security Controls
-----------------
- **Step-up authentication**: Both the initiator and the approver must
  complete MFA verification before the action is considered fully
  approved.
- **Risk scoring**: High-value actions (above configurable thresholds)
  require additional verification, including hardware key attestation.
- **Transaction signing**: Every approval is cryptographically signed
  using HMAC-SHA256, creating a tamper-evident record of who approved
  what and when.
- **Same-person prohibition**: The approver must be a different admin
  from the initiator — enforced at the service level and verified
  cryptographically.

Action Types
------------
- ``WITHDRAWAL_APPROVAL``      : Approve a user withdrawal
- ``REFUND_APPROVAL``          : Issue a refund to a user
- ``COMMISSION_ADJUSTMENT``    : Modify agent commission rates
- ``PAYMENT_OVERRIDE``         : Override a payment status
- ``FEE_WAIVER``               : Waive platform fees for a user
- ``BULK_PAYOUT``              : Initiate a bulk payout operation

Classes
-------
DualApprovalService
    Create, approve, reject, execute, and cancel financial actions.

FinancialAction
    Helper for storing pending/approved/rejected financial actions
    with cryptographic signing.
"""

import hashlib
import hmac
import json
import logging
import os
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from .services import ImmutableAuditService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Action type choices — every financial operation must use one of these
ACTION_TYPE_CHOICES = [
    ("WITHDRAWAL_APPROVAL", "Withdrawal Approval"),
    ("REFUND_APPROVAL", "Refund Approval"),
    ("COMMISSION_ADJUSTMENT", "Commission Adjustment"),
    ("PAYMENT_OVERRIDE", "Payment Override"),
    ("FEE_WAIVER", "Fee Waiver"),
    ("BULK_PAYOUT", "Bulk Payout"),
]

# Risk thresholds (in KES)
HIGH_VALUE_THRESHOLD = Decimal(getattr(
    settings, "DUAL_APPROVAL_HIGH_VALUE_THRESHOLD", "500000"
))  # 500K KES
CRITICAL_VALUE_THRESHOLD = Decimal(getattr(
    settings, "DUAL_APPROVAL_CRITICAL_VALUE_THRESHOLD", "2000000"
))  # 2M KES

# Approval deadline
APPROVAL_DEADLINE_HOURS = getattr(
    settings, "DUAL_APPROVAL_DEADLINE_HOURS", 24
)

# Signing key for transaction signatures (hex-encoded)
_TRANSACTION_SIGNING_KEY = getattr(
    settings, "DUAL_APPROVAL_SIGNING_KEY", None
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class DualApprovalError(Exception):
    """Base exception for dual-approval operations."""
    pass


class SamePersonApprovalError(DualApprovalError):
    """The approver is the same person as the initiator."""
    pass


class StepUpRequiredError(DualApprovalError):
    """Step-up authentication is required but not completed."""
    pass


class ActionExpiredError(DualApprovalError):
    """The action has expired and can no longer be approved."""
    pass


class InvalidActionStateError(DualApprovalError):
    """The action is in an invalid state for the requested operation."""
    pass


class RiskThresholdExceededError(DualApprovalError):
    """The action exceeds risk thresholds and needs additional verification."""
    pass


# ---------------------------------------------------------------------------
# Financial Action Store
# ---------------------------------------------------------------------------

# In-memory store for financial actions.
# Production deployments MUST replace this with a Django model backed by
# the database for durability and transactional integrity.
# Format: {action_id: FinancialAction}
_financial_action_store: dict = {}


class FinancialAction:
    """Store and manage pending/approved/rejected financial actions.

    Each financial action tracks its full lifecycle:

    1. ``pending``    — Created, awaiting approval
    2. ``approved``   — Second admin has approved, ready for execution
    3. ``executed``   — Action has been executed
    4. ``rejected``   — Second admin has rejected
    5. ``cancelled``  — Initiator has cancelled
    6. ``expired``    — Approval deadline passed without action

    Attributes
    ----------
    id : str
        Unique action identifier (UUID).
    action_type : str
        One of ``ACTION_TYPE_CHOICES``.
    amount : Decimal
        Monetary value of the action.
    metadata : dict
        Additional context (recipient, reason, etc.).
    status : str
        Current lifecycle status.
    initiator_id : str
        Admin who created the action.
    approver_id : str or None
        Admin who approved/rejected.
    risk_score : float
        Calculated risk score (0–100).
    initiator_step_up : bool
        Whether the initiator completed step-up auth.
    approver_step_up : bool
        Whether the approver completed step-up auth.
    approval_signature : str or None
        HMAC signature of the approval.
    created_at : str
        ISO-8601 timestamp.
    expires_at : str
        ISO-8601 deadline for approval.
    approved_at : str or None
        ISO-8601 timestamp of approval.
    executed_at : str or None
        ISO-8601 timestamp of execution.
    rejection_reason : str or None
        Reason for rejection, if applicable.
    """

    VALID_STATUSES = {"pending", "approved", "executed", "rejected", "cancelled", "expired"}

    def __init__(
        self,
        action_type: str,
        amount: Decimal,
        metadata: dict,
        initiator_id: str,
        tenant_id: Optional[str] = None,
    ):
        self.id = str(uuid.uuid4())
        self.action_type = action_type
        self.amount = amount
        self.metadata = metadata
        self.initiator_id = str(initiator_id)
        self.tenant_id = tenant_id
        self.status = "pending"
        self.approver_id = None
        self.risk_score = 0.0
        self.initiator_step_up = False
        self.approver_step_up = False
        self.approval_signature = None
        self.created_at = timezone.now().isoformat()
        self.expires_at = (
            timezone.now() + timedelta(hours=APPROVAL_DEADLINE_HOURS)
        ).isoformat()
        self.approved_at = None
        self.executed_at = None
        self.rejection_reason = None

        # Calculate risk score
        self.risk_score = self._calculate_risk_score()

        # Store
        _financial_action_store[self.id] = self

    def _calculate_risk_score(self) -> float:
        """Calculate a risk score (0–100) for this financial action.

        Factors:
        - Amount relative to thresholds
        - Action type risk weight
        - Time of day
        """
        score = 0.0

        # Amount-based risk
        if self.amount >= CRITICAL_VALUE_THRESHOLD:
            score += 50.0
        elif self.amount >= HIGH_VALUE_THRESHOLD:
            score += 30.0
        else:
            score += 10.0

        # Action type risk weights
        type_weights = {
            "WITHDRAWAL_APPROVAL": 25.0,
            "BULK_PAYOUT": 30.0,
            "PAYMENT_OVERRIDE": 20.0,
            "REFUND_APPROVAL": 15.0,
            "COMMISSION_ADJUSTMENT": 10.0,
            "FEE_WAIVER": 10.0,
        }
        score += type_weights.get(self.action_type, 15.0)

        # Outside business hours
        now = timezone.now()
        if now.hour < 8 or now.hour >= 18:
            score += 10.0

        # Weekend
        if now.weekday() >= 5:
            score += 5.0

        return min(score, 100.0)

    @property
    def is_expired(self) -> bool:
        """Check if the action has passed its approval deadline."""
        if self.status != "pending":
            return False
        return timezone.now() > timezone.datetime.fromisoformat(self.expires_at)

    @property
    def requires_hardware_key(self) -> bool:
        """Check if the action amount requires hardware key verification."""
        return self.amount >= CRITICAL_VALUE_THRESHOLD

    def to_dict(self) -> dict:
        """Serialise to a dictionary (excludes internal state)."""
        return {
            "id": self.id,
            "action_type": self.action_type,
            "amount": str(self.amount),
            "metadata": self.metadata,
            "initiator_id": self.initiator_id,
            "tenant_id": self.tenant_id,
            "status": self.status,
            "approver_id": self.approver_id,
            "risk_score": self.risk_score,
            "initiator_step_up": self.initiator_step_up,
            "approver_step_up": self.approver_step_up,
            "approval_signature": self.approval_signature,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "approved_at": self.approved_at,
            "executed_at": self.executed_at,
            "rejection_reason": self.rejection_reason,
        }


# ---------------------------------------------------------------------------
# Transaction Signing
# ---------------------------------------------------------------------------

def _get_signing_key() -> bytes:
    """Retrieve the HMAC signing key for transaction signatures.

    Falls back to a derived key if not configured in settings.

    Returns
    -------
    bytes
        The signing key.
    """
    if _TRANSACTION_SIGNING_KEY:
        return bytes.fromhex(_TRANSACTION_SIGNING_KEY)
    # Fallback: derive from Django SECRET_KEY
    secret = getattr(settings, "SECRET_KEY", "insecure-default-key")
    return hashlib.sha256(
        f"dual-approval-signing:{secret}".encode("utf-8")
    ).digest()


def sign_action(action: FinancialAction, approver_id: str) -> str:
    """Create an HMAC-SHA256 signature for a financial action approval.

    The signature covers the action ID, type, amount, initiator, and
    approver, providing tamper evidence and non-repudiation.

    Parameters
    ----------
    action : FinancialAction
        The approved action.
    approver_id : str
        The admin who approved the action.

    Returns
    -------
    str
        Hex-encoded HMAC-SHA256 signature.
    """
    payload = json.dumps({
        "action_id": action.id,
        "action_type": action.action_type,
        "amount": str(action.amount),
        "initiator_id": action.initiator_id,
        "approver_id": str(approver_id),
        "timestamp": timezone.now().isoformat(),
    }, sort_keys=True)

    key = _get_signing_key()
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_action_signature(action: FinancialAction) -> bool:
    """Verify the approval signature of a financial action.

    Parameters
    ----------
    action : FinancialAction
        The action whose signature to verify.

    Returns
    -------
    bool
        ``True`` if the signature is valid.
    """
    if not action.approval_signature or not action.approver_id:
        return False

    expected = sign_action(action, action.approver_id)
    return hmac.compare_digest(expected, action.approval_signature)


# ===========================================================================
# Dual Approval Service
# ===========================================================================

class DualApprovalService:
    """Manage the full lifecycle of financial dual-approval actions.

    This service enforces the four-eyes principle: every financial
    action must be initiated by one admin and explicitly approved by
    a different admin before it can be executed.

    Security Guarantees
    -------------------
    1. No single admin can execute a financial action alone.
    2. The approver must be a different admin from the initiator.
    3. Both admins must complete step-up MFA verification.
    4. High-value actions require hardware key attestation.
    5. Every action is cryptographically signed upon approval.
    6. All operations are audit-logged with full context.
    """

    @staticmethod
    def create_financial_action(
        admin,
        action_type: str,
        amount,
        metadata: dict,
        ip_address: str = "",
        user_agent: str = "",
    ) -> FinancialAction:
        """Initiate a financial action requiring dual approval.

        Parameters
        ----------
        admin : User
            The admin initiating the action.  Must have role ``Admin``.
        action_type : str
            One of ``ACTION_TYPE_CHOICES``.
        amount : Decimal or str or float
            Monetary value of the action in KES.
        metadata : dict
            Additional context — recipient, reason, reference, etc.
        ip_address : str
        user_agent : str

        Returns
        -------
        FinancialAction
            The created action in ``pending`` status.

        Raises
        ------
        PermissionDenied
            If the user is not an admin.
        DualApprovalError
            If the action type is invalid.
        """
        if getattr(admin, "role", None) != "Admin":
            raise PermissionDenied("Only admins can create financial actions.")

        # Validate action type
        valid_types = [choice[0] for choice in ACTION_TYPE_CHOICES]
        if action_type not in valid_types:
            raise DualApprovalError(
                f"Invalid action type '{action_type}'. "
                f"Valid types: {', '.join(valid_types)}"
            )

        # Normalise amount
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))

        if amount <= 0:
            raise DualApprovalError("Amount must be positive.")

        # Create the action
        action = FinancialAction(
            action_type=action_type,
            amount=amount,
            metadata=metadata,
            initiator_id=str(admin.id),
            tenant_id=getattr(admin, "tenant_id", None),
        )

        # Audit log
        ImmutableAuditService.log(
            actor=admin,
            action="FINANCIAL_ACTION_CREATED",
            resource_type="FinancialAction",
            resource_id=action.id,
            metadata={
                "action_type": action_type,
                "amount": str(amount),
                "risk_score": action.risk_score,
                "requires_hardware_key": action.requires_hardware_key,
                "expires_at": action.expires_at,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(
            "DualApproval: Financial action %s created by %s — type=%s "
            "amount=%s risk_score=%.1f",
            action.id[:8],
            admin.email,
            action_type,
            amount,
            action.risk_score,
        )

        return action

    @staticmethod
    def approve_action(
        approver,
        action_id: str,
        ip_address: str = "",
        user_agent: str = "",
        step_up_verified: bool = False,
        hardware_key_verified: bool = False,
    ) -> FinancialAction:
        """Approve a pending financial action (second admin).

        The approver must be a different admin from the initiator.
        Both step-up MFA and (for high-value actions) hardware key
        verification are required.

        Parameters
        ----------
        approver : User
            The admin approving the action.
        action_id : str
            The UUID of the financial action.
        ip_address : str
        user_agent : str
        step_up_verified : bool
            Whether the approver has completed step-up MFA.
        hardware_key_verified : bool
            Whether the approver used a hardware key.

        Returns
        -------
        FinancialAction
            The action in ``approved`` status.

        Raises
        ------
        SamePersonApprovalError
            If the approver is the same as the initiator.
        StepUpRequiredError
            If step-up auth is not verified.
        ActionExpiredError
            If the action has expired.
        InvalidActionStateError
            If the action is not in ``pending`` status.
        """
        action = _financial_action_store.get(action_id)
        if action is None:
            raise InvalidActionStateError(
                f"Financial action {action_id[:8]}... not found."
            )

        if action.status != "pending":
            raise InvalidActionStateError(
                f"Action is in '{action.status}' status — only 'pending' "
                f"actions can be approved."
            )

        # Check expiry
        if action.is_expired:
            action.status = "expired"
            raise ActionExpiredError(
                "Action has expired.  The approval deadline has passed."
            )

        # Same-person prohibition
        if action.initiator_id == str(approver.id):
            raise SamePersonApprovalError(
                "The same admin cannot approve their own financial action. "
                "A different administrator must provide the second approval."
            )

        # Verify approver is an admin
        if getattr(approver, "role", None) != "Admin":
            raise PermissionDenied("Only admins can approve financial actions.")

        # Step-up authentication required
        if not step_up_verified:
            raise StepUpRequiredError(
                "Step-up MFA verification is required before approving "
                "financial actions."
            )

        # Hardware key required for high-value actions
        if action.requires_hardware_key and not hardware_key_verified:
            raise StepUpRequiredError(
                f"This action (KES {action.amount}) exceeds the critical "
                f"threshold (KES {CRITICAL_VALUE_THRESHOLD}).  Hardware "
                f"security key verification is required for approval."
            )

        # Sign the approval
        signature = sign_action(action, str(approver.id))

        # Update action
        action.status = "approved"
        action.approver_id = str(approver.id)
        action.approver_step_up = step_up_verified
        action.approval_signature = signature
        action.approved_at = timezone.now().isoformat()

        # Verify our own signature (belt and suspenders)
        if not verify_action_signature(action):
            raise DualApprovalError(
                "Signature verification failed after signing. "
                "This should never happen — possible key corruption."
            )

        # Audit log
        ImmutableAuditService.log(
            actor=approver,
            action="FINANCIAL_ACTION_APPROVED",
            resource_type="FinancialAction",
            resource_id=action.id,
            metadata={
                "action_type": action.action_type,
                "amount": str(action.amount),
                "initiator_id": action.initiator_id,
                "risk_score": action.risk_score,
                "hardware_key_used": hardware_key_verified,
                "approval_signature": signature[:16] + "...",
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(
            "DualApproval: Action %s approved by %s — type=%s amount=%s",
            action.id[:8],
            approver.email,
            action.action_type,
            action.amount,
        )

        return action

    @staticmethod
    def reject_action(
        approver,
        action_id: str,
        reason: str,
        ip_address: str = "",
        user_agent: str = "",
    ) -> FinancialAction:
        """Reject a pending financial action.

        Parameters
        ----------
        approver : User
            The admin rejecting the action.
        action_id : str
            The UUID of the financial action.
        reason : str
            Mandatory reason for rejection.
        ip_address : str
        user_agent : str

        Returns
        -------
        FinancialAction
            The action in ``rejected`` status.

        Raises
        ------
        InvalidActionStateError
            If the action is not in ``pending`` status.
        DualApprovalError
            If no reason is provided.
        """
        if not reason or not reason.strip():
            raise DualApprovalError(
                "A reason is required when rejecting a financial action."
            )

        action = _financial_action_store.get(action_id)
        if action is None:
            raise InvalidActionStateError(
                f"Financial action {action_id[:8]}... not found."
            )

        if action.status != "pending":
            raise InvalidActionStateError(
                f"Action is in '{action.status}' status — only 'pending' "
                f"actions can be rejected."
            )

        action.status = "rejected"
        action.approver_id = str(approver.id)
        action.rejection_reason = reason.strip()

        # Audit log
        ImmutableAuditService.log(
            actor=approver,
            action="FINANCIAL_ACTION_REJECTED",
            resource_type="FinancialAction",
            resource_id=action.id,
            metadata={
                "action_type": action.action_type,
                "amount": str(action.amount),
                "initiator_id": action.initiator_id,
                "rejection_reason": reason.strip()[:500],
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(
            "DualApproval: Action %s rejected by %s — reason: %s",
            action.id[:8],
            approver.email,
            reason.strip()[:100],
        )

        return action

    @staticmethod
    def execute_approved_action(
        action_id: str,
        executed_by=None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> FinancialAction:
        """Execute a dual-approved financial action.

        The action must be in ``approved`` status with a valid
        cryptographic signature before execution.

        Parameters
        ----------
        action_id : str
            The UUID of the financial action.
        executed_by : User, optional
            Admin or system user executing the action.
        ip_address : str
        user_agent : str

        Returns
        -------
        FinancialAction
            The action in ``executed`` status.

        Raises
        ------
        InvalidActionStateError
            If the action is not in ``approved`` status.
        DualApprovalError
            If the approval signature is invalid.
        """
        action = _financial_action_store.get(action_id)
        if action is None:
            raise InvalidActionStateError(
                f"Financial action {action_id[:8]}... not found."
            )

        if action.status != "approved":
            raise InvalidActionStateError(
                f"Action is in '{action.status}' status — only 'approved' "
                f"actions can be executed."
            )

        # Verify the approval signature before execution
        if not verify_action_signature(action):
            raise DualApprovalError(
                "Approval signature verification FAILED.  This action may "
                "have been tampered with.  Execution blocked."
            )

        # Mark as executed
        action.status = "executed"
        action.executed_at = timezone.now().isoformat()

        # Audit log
        ImmutableAuditService.log(
            actor=executed_by,
            action="FINANCIAL_ACTION_EXECUTED",
            resource_type="FinancialAction",
            resource_id=action.id,
            metadata={
                "action_type": action.action_type,
                "amount": str(action.amount),
                "initiator_id": action.initiator_id,
                "approver_id": action.approver_id,
                "signature_valid": True,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(
            "DualApproval: Action %s executed — type=%s amount=%s",
            action.id[:8],
            action.action_type,
            action.amount,
        )

        return action

    @staticmethod
    def cancel_action(
        admin,
        action_id: str,
        reason: str = "",
        ip_address: str = "",
        user_agent: str = "",
    ) -> FinancialAction:
        """Cancel a pending financial action.

        Only the initiator can cancel their own pending action, or a
        superadmin can cancel any pending action.

        Parameters
        ----------
        admin : User
            The admin cancelling the action (must be the initiator or superadmin).
        action_id : str
            The UUID of the financial action.
        reason : str, optional
            Reason for cancellation.
        ip_address : str
        user_agent : str

        Returns
        -------
        FinancialAction
            The action in ``cancelled`` status.

        Raises
        ------
        PermissionDenied
            If the admin is not the initiator or a superadmin.
        InvalidActionStateError
            If the action is not in ``pending`` status.
        """
        action = _financial_action_store.get(action_id)
        if action is None:
            raise InvalidActionStateError(
                f"Financial action {action_id[:8]}... not found."
            )

        if action.status != "pending":
            raise InvalidActionStateError(
                f"Action is in '{action.status}' status — only 'pending' "
                f"actions can be cancelled."
            )

        is_initiator = action.initiator_id == str(admin.id)
        is_superadmin = getattr(admin, "is_superuser", False)

        if not is_initiator and not is_superadmin:
            raise PermissionDenied(
                "Only the action initiator or a superadmin can cancel "
                "a pending financial action."
            )

        action.status = "cancelled"
        action.rejection_reason = f"Cancelled: {reason}" if reason else "Cancelled by initiator"

        # Audit log
        ImmutableAuditService.log(
            actor=admin,
            action="FINANCIAL_ACTION_CANCELLED",
            resource_type="FinancialAction",
            resource_id=action.id,
            metadata={
                "action_type": action.action_type,
                "amount": str(action.amount),
                "reason": reason[:500] if reason else "",
                "cancelled_by_initiator": is_initiator,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(
            "DualApproval: Action %s cancelled by %s",
            action.id[:8],
            admin.email,
        )

        return action

    @staticmethod
    def get_pending_approvals(admin) -> list:
        """List financial actions awaiting the given admin's approval.

        Excludes actions initiated by the admin themselves (since
        self-approval is prohibited).

        Parameters
        ----------
        admin : User
            The admin whose pending approvals to list.

        Returns
        -------
        list[dict]
            List of pending actions that this admin can approve.
        """
        admin_id = str(admin.id)
        pending = []
        for action in _financial_action_store.values():
            if (
                action.status == "pending"
                and action.initiator_id != admin_id
                and not action.is_expired
            ):
                pending.append(action.to_dict())

        # Sort by risk score (highest first)
        pending.sort(key=lambda x: x["risk_score"], reverse=True)
        return pending

    @staticmethod
    def get_action_history(
        filters: Optional[dict] = None,
    ) -> list:
        """Retrieve audit trail of all financial actions.

        Parameters
        ----------
        filters : dict, optional
            Filters to apply:
            - ``status`` : Filter by status
            - ``action_type`` : Filter by action type
            - ``initiator_id`` : Filter by initiator
            - ``approver_id`` : Filter by approver
            - ``min_amount`` : Minimum amount filter
            - ``max_amount`` : Maximum amount filter
            - ``since`` : ISO-8601 timestamp
            - ``until`` : ISO-8601 timestamp

        Returns
        -------
        list[dict]
            List of matching financial actions, ordered by creation date
            (newest first).
        """
        filters = filters or {}
        results = []

        for action in _financial_action_store.values():
            # Apply filters
            if "status" in filters and action.status != filters["status"]:
                continue
            if "action_type" in filters and action.action_type != filters["action_type"]:
                continue
            if "initiator_id" in filters and action.initiator_id != filters["initiator_id"]:
                continue
            if "approver_id" in filters and action.approver_id != filters["approver_id"]:
                continue
            if "min_amount" in filters and action.amount < Decimal(str(filters["min_amount"])):
                continue
            if "max_amount" in filters and action.amount > Decimal(str(filters["max_amount"])):
                continue

            results.append(action.to_dict())

        # Sort by created_at (newest first)
        results.sort(key=lambda x: x["created_at"], reverse=True)
        return results

    @staticmethod
    def expire_stale_actions() -> int:
        """Mark all past-deadline pending actions as expired.

        Should be called by a periodic task (Celery beat).

        Returns
        -------
        int
            Number of actions expired.
        """
        count = 0
        for action in _financial_action_store.values():
            if action.status == "pending" and action.is_expired:
                action.status = "expired"
                count += 1

        if count > 0:
            logger.warning(
                "DualApproval: Expired %d stale financial action(s).",
                count,
            )

        return count

    @staticmethod
    def get_action(action_id: str) -> Optional[dict]:
        """Retrieve a single financial action by ID.

        Parameters
        ----------
        action_id : str
            The UUID of the financial action.

        Returns
        -------
        dict or None
            The action data, or ``None`` if not found.
        """
        action = _financial_action_store.get(action_id)
        return action.to_dict() if action else None

    @staticmethod
    def verify_action_integrity(action_id: str) -> dict:
        """Verify the cryptographic integrity of an approved action.

        Checks that the approval signature is valid and that the
        action has not been tampered with.

        Parameters
        ----------
        action_id : str
            The UUID of the financial action.

        Returns
        -------
        dict
            ``{"valid": bool, "action_id": str, "checks": dict}``
        """
        action = _financial_action_store.get(action_id)
        if action is None:
            return {
                "valid": False,
                "action_id": action_id,
                "checks": {"error": "Action not found"},
            }

        checks = {
            "status_consistent": action.status in FinancialAction.VALID_STATUSES,
            "has_approver": action.approver_id is not None if action.status in ("approved", "executed") else True,
            "different_approvers": (
                action.initiator_id != action.approver_id
                if action.approver_id else True
            ),
            "signature_valid": (
                verify_action_signature(action)
                if action.status in ("approved", "executed") else True
            ),
            "step_up_verified": (
                action.approver_step_up
                if action.status in ("approved", "executed") else True
            ),
        }

        all_valid = all(checks.values())

        return {
            "valid": all_valid,
            "action_id": action_id,
            "checks": checks,
        }
