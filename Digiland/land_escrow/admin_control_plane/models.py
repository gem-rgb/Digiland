"""
Admin Control Plane Models
============================

Data models for the Enterprise Admin Control Plane security domain.

These models are intentionally isolated from the core application models.
They implement a defence-in-depth architecture where administrative
operations are protected by additional layers of security beyond what
the customer-facing application requires.

Models:
    - AdminAccessPolicy: Fine-grained access policies for admin operations
    - AdminSession: Short-lived, MFA-verified admin sessions
    - AdminActionLog: Immutable, tamper-resistant audit trail
    - DualApprovalRequest: Dual-approval workflow for sensitive actions
    - EmergencyControl: Break-glass emergency controls
    - AdminIPAddress: IP allow-list for admin network isolation
"""

import uuid
import hashlib
import json
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ── Helpers ──────────────────────────────────────────────────────────────────

def _generate_chain_hash(record_data: str, previous_hash: str) -> str:
    """Compute a SHA-256 chain hash for an audit log record.

    Each record's hash is derived from its own data concatenated with the
    previous record's hash, creating a tamper-evident linked list.  If any
    record is altered, every subsequent hash will be invalid.

    Args:
        record_data: JSON-serialised string of the record payload.
        previous_hash: Hex digest of the previous record's hash, or the
            genesis hash (all zeroes) for the very first record.

    Returns:
        A 64-character lowercase hex string (SHA-256 digest).
    """
    payload = f"{record_data}:{previous_hash}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


GENESIS_HASH = "0" * 64  # Sentinel value for the first audit record


# ══════════════════════════════════════════════════════════════════════════════
# Model: AdminAccessPolicy
# ══════════════════════════════════════════════════════════════════════════════

class AdminAccessPolicy(models.Model):
    """Fine-grained access policy for administrative operations.

    Policies are evaluated in priority order (lowest number = highest
    priority).  Each policy belongs to a category (network, auth, action,
    financial) and carries a JSON rules payload whose schema depends on
    the category.

    Example rule structures by category:

        network:
            {"allowed_cidrs": ["10.0.0.0/8", "172.16.0.0/12"]}

        auth:
            {"require_hardware_key": true, "require_totp": true,
             "step_up_for_financial": true}

        action:
            {"blocked_actions": ["admin_create", "role_change"],
             "require_dual_approval": ["financial", "withdrawal_approve"]}

        financial:
            {"dual_approval_threshold": 500000,
             "max_single_approval": 1000000,
             "withdrawal_freeze": false}
    """

    POLICY_TYPE_CHOICES = [
        ("network", "Network"),
        ("auth", "Authentication"),
        ("action", "Action"),
        ("financial", "Financial"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this policy.",
    )
    tenant_id = models.UUIDField(
        db_index=True,
        null=True,
        blank=True,
        help_text="Organisation tenant ID for row-level security isolation.",
    )
    name = models.CharField(
        max_length=200,
        help_text="Human-readable policy name, e.g. 'Production VPN Only'.",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Detailed description of what this policy enforces.",
    )
    policy_type = models.CharField(
        max_length=20,
        choices=POLICY_TYPE_CHOICES,
        db_index=True,
        help_text="Category of the policy – determines the rule schema.",
    )
    rules = models.JSONField(
        default=dict,
        blank=True,
        help_text="Policy rule payload.  Schema varies by policy_type.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Inactive policies are skipped during evaluation.",
    )
    priority = models.PositiveIntegerField(
        default=100,
        help_text="Evaluation order – lower number = higher priority.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_admin_policies",
        help_text="Administrator who created this policy.",
    )

    class Meta:
        ordering = ["priority", "name"]
        verbose_name = "Admin Access Policy"
        verbose_name_plural = "Admin Access Policies"
        indexes = [
            models.Index(
                fields=["tenant_id", "policy_type", "is_active"],
                name="idx_policy_tenant_type_active",
            ),
            models.Index(
                fields=["tenant_id", "priority"],
                name="idx_policy_tenant_priority",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_policy_type_display()}, priority={self.priority})"


# ══════════════════════════════════════════════════════════════════════════════
# Model: AdminSession
# ══════════════════════════════════════════════════════════════════════════════

class AdminSession(models.Model):
    """A short-lived, MFA-verified session for administrative operations.

    Admin sessions are deliberately more restrictive than regular user
    sessions:

    * They have a short idle timeout (default 30 minutes).
    * They have an absolute maximum lifetime (default 4 hours).
    * They track the IP address and device fingerprint at creation
      time and flag changes as suspicious.
    * MFA verification is mandatory before the session is considered
      valid for admin operations.

    The middleware layer (AdminSessionSecurityMiddleware) validates
    these constraints on every request to an admin path.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    tenant_id = models.UUIDField(
        db_index=True,
        null=True,
        blank=True,
        help_text="Organisation tenant ID for row-level security isolation.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_sessions",
        help_text="The administrator who owns this session.",
    )
    session_token = models.CharField(
        max_length=128,
        unique=True,
        db_index=True,
        help_text="Opaque token identifying this admin session.",
    )
    ip_address = models.GenericIPAddressField(
        help_text="Client IP address at session creation.",
    )
    user_agent = models.TextField(
        blank=True,
        default="",
        help_text="HTTP User-Agent header at session creation.",
    )
    device_fingerprint = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Browser / device fingerprint hash for anomaly detection.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="False once the session is explicitly terminated or expired.",
    )
    mfa_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when MFA was successfully verified for this session.",
    )
    hardware_key_verified = models.BooleanField(
        default=False,
        help_text="Whether a hardware security key (WebAuthn) was used.",
    )
    last_activity_at = models.DateTimeField(
        auto_now=True,
        help_text="Updated on every request – used for idle timeout.",
    )
    expires_at = models.DateTimeField(
        db_index=True,
        help_text="Idle timeout deadline.  Refreshed on each request.",
    )
    absolute_expires_at = models.DateTimeField(
        help_text="Hard ceiling – session cannot be renewed past this time.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    terminated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the session was terminated, if applicable.",
    )
    termination_reason = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text=(
            "Reason for termination: 'idle_timeout', 'absolute_expiry', "
            "'manual', 'security_event', 'emergency_revocation', etc."
        ),
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Admin Session"
        verbose_name_plural = "Admin Sessions"
        indexes = [
            models.Index(
                fields=["user", "is_active"],
                name="idx_admsess_user_active",
            ),
        ]

    def __str__(self):
        status = "active" if self.is_active else "terminated"
        return f"AdminSession {self.session_token[:8]}... ({status}, user={self.user_id})"

    @property
    def is_idle_expired(self):
        """Check whether the session has exceeded the idle timeout."""
        return self.is_active and timezone.now() > self.expires_at

    @property
    def is_absolutely_expired(self):
        """Check whether the session has hit the absolute lifetime ceiling."""
        return timezone.now() > self.absolute_expires_at

    @property
    def is_mfa_verified(self):
        """Check whether MFA has been completed for this session."""
        return self.mfa_verified_at is not None


# ══════════════════════════════════════════════════════════════════════════════
# Model: AdminActionLog (Immutable Audit Trail)
# ══════════════════════════════════════════════════════════════════════════════

class AdminActionLog(models.Model):
    """Immutable, tamper-resistant audit log for administrative actions.

    Every administrative action creates a record here.  Records are linked
    via a SHA-256 hash chain: each record's ``hash`` is derived from its
    own data and the ``previous_hash`` field.  This makes retroactive
    modification detectable – altering a record invalidates every
    subsequent hash in the chain.

    **Immutability contract**: Once written, records MUST NEVER be updated
    or deleted by application code.  Enforce this at the database level
    with triggers or row-level security if possible.
    """

    ACTION_TYPE_CHOICES = [
        ("user_verify", "User Verification"),
        ("kyc_approve", "KYC Approval"),
        ("financial", "Financial Operation"),
        ("withdrawal_approve", "Withdrawal Approval"),
        ("permission_change", "Permission Change"),
        ("role_change", "Role Change"),
        ("admin_create", "Admin Account Creation"),
        ("config_change", "Configuration Change"),
        ("emergency", "Emergency Action"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    tenant_id = models.UUIDField(
        db_index=True,
        null=True,
        blank=True,
        help_text="Organisation tenant ID for row-level security isolation.",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="admin_actions",
        help_text="Administrator who performed the action.",
    )
    session = models.ForeignKey(
        AdminSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="action_logs",
        help_text="Admin session under which the action was performed.",
    )
    action_type = models.CharField(
        max_length=30,
        choices=ACTION_TYPE_CHOICES,
        db_index=True,
        help_text="Category of the administrative action.",
    )
    resource_type = models.CharField(
        max_length=100,
        help_text="Type of resource affected, e.g. 'User', 'Transaction'.",
    )
    resource_id = models.CharField(
        max_length=100,
        help_text="Primary key of the affected resource (string for flexibility).",
    )
    action_details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Arbitrary details about the action for audit purposes.",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Client IP at the time of the action.",
    )
    user_agent = models.TextField(
        blank=True,
        default="",
        help_text="HTTP User-Agent at the time of the action.",
    )
    device_fingerprint = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Device fingerprint at the time of the action.",
    )
    step_up_auth = models.BooleanField(
        default=False,
        help_text="Whether step-up authentication was verified for this action.",
    )
    dual_approval = models.BooleanField(
        default=False,
        help_text="Whether dual approval was obtained for this action.",
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_admin_actions",
        help_text="Second approver for dual-approval actions.",
    )
    risk_score = models.FloatField(
        default=0.0,
        help_text="Calculated risk score (0-100) for this action.",
    )
    is_flagged = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Flagged for review by the risk-scoring engine.",
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the action occurred.",
    )
    hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="SHA-256 hash of this record for tamper detection.",
    )
    previous_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="SHA-256 hash of the preceding record (chain integrity).",
    )

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Admin Action Log"
        verbose_name_plural = "Admin Action Logs"
        indexes = [
            models.Index(
                fields=["actor", "timestamp"],
                name="idx_actlog_actor_ts",
            ),
            models.Index(
                fields=["action_type", "timestamp"],
                name="idx_actlog_type_ts",
            ),
            models.Index(
                fields=["resource_type", "resource_id"],
                name="idx_actlog_res_type_id",
            ),
            models.Index(
                fields=["tenant_id", "timestamp"],
                name="idx_actlog_tenant_ts",
            ),
        ]

    def __str__(self):
        actor_email = getattr(self.actor, "email", "unknown")
        return f"AdminActionLog {self.action_type} by {actor_email} at {self.timestamp}"

    def compute_hash(self, previous_hash: str) -> str:
        """Calculate the chain hash for this record.

        Args:
            previous_hash: The ``hash`` field of the preceding record,
                or ``GENESIS_HASH`` for the first record.

        Returns:
            The computed SHA-256 hex digest.
        """
        record_data = json.dumps(
            {
                "id": str(self.id),
                "tenant_id": str(self.tenant_id) if self.tenant_id else None,
                "actor_id": str(self.actor_id) if self.actor_id else None,
                "session_id": str(self.session_id) if self.session_id else None,
                "action_type": self.action_type,
                "resource_type": self.resource_type,
                "resource_id": self.resource_id,
                "action_details": self.action_details,
                "ip_address": str(self.ip_address) if self.ip_address else None,
                "step_up_auth": self.step_up_auth,
                "dual_approval": self.dual_approval,
                "approver_id": str(self.approver_id) if self.approver_id else None,
                "risk_score": self.risk_score,
                "is_flagged": self.is_flagged,
                "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            },
            sort_keys=True,
            default=str,
        )
        return _generate_chain_hash(record_data, previous_hash)

    def save(self, *args, **kwargs):
        """Override save to enforce immutability.

        Existing records cannot be updated – only new inserts are allowed.
        The hash chain is automatically maintained on creation.
        """
        if self.pk and AdminActionLog.objects.filter(pk=self.pk).exists():
            raise RuntimeError(
                "AdminActionLog records are immutable and cannot be updated."
            )

        # Compute hash chain on first save
        if not self.hash:
            try:
                last_record = AdminActionLog.objects.order_by("-timestamp").first()
                prev = last_record.hash if last_record else GENESIS_HASH
            except Exception:
                prev = GENESIS_HASH
            self.previous_hash = prev
            self.hash = self.compute_hash(prev)

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Prevent deletion of audit records."""
        raise RuntimeError(
            "AdminActionLog records are immutable and cannot be deleted."
        )


# ══════════════════════════════════════════════════════════════════════════════
# Model: DualApprovalRequest
# ══════════════════════════════════════════════════════════════════════════════

class DualApprovalRequest(models.Model):
    """Dual-approval workflow request for sensitive administrative actions.

    Certain high-risk operations (financial transactions above a threshold,
    role changes, permission changes, etc.) require a second administrator
    to explicitly approve the action before it is executed.  This model
    captures the full lifecycle of such a request.

    Both the requester and the approver must have completed step-up
    authentication before the action is considered fully approved.
    """

    REQUEST_TYPE_CHOICES = [
        ("withdrawal", "Withdrawal"),
        ("balance_adjustment", "Balance Adjustment"),
        ("payout", "Payout"),
        ("transfer", "Transfer"),
        ("role_change", "Role Change"),
        ("permission_change", "Permission Change"),
        ("user_suspend", "User Suspension"),
        ("config_change", "Configuration Change"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    tenant_id = models.UUIDField(
        db_index=True,
        null=True,
        blank=True,
        help_text="Organisation tenant ID for row-level security isolation.",
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dual_approval_requests",
        help_text="Administrator who requested the action.",
    )
    request_type = models.CharField(
        max_length=30,
        choices=REQUEST_TYPE_CHOICES,
        db_index=True,
        help_text="Category of the requested action.",
    )
    resource_type = models.CharField(
        max_length=100,
        help_text="Type of resource the action targets.",
    )
    resource_id = models.CharField(
        max_length=100,
        help_text="Primary key of the target resource.",
    )
    request_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Payload describing the requested action.",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
        help_text="Current lifecycle status of the request.",
    )
    risk_score = models.FloatField(
        default=0.0,
        help_text="Calculated risk score (0-100) at the time of request.",
    )
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Monetary value involved, if applicable.",
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_dual_requests",
        help_text="Administrator who approved or rejected the request.",
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the request was approved or rejected.",
    )
    requester_step_up_verified = models.BooleanField(
        default=False,
        help_text="Whether the requester completed step-up authentication.",
    )
    approver_step_up_verified = models.BooleanField(
        default=False,
        help_text="Whether the approver completed step-up authentication.",
    )
    expires_at = models.DateTimeField(
        db_index=True,
        help_text="Deadline by which the request must be approved.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the request reached a terminal state.",
    )
    notes = models.TextField(
        blank=True,
        default="",
        help_text="Optional notes from the requester or approver.",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Dual Approval Request"
        verbose_name_plural = "Dual Approval Requests"
        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="idx_dual_status_created",
            ),
            models.Index(
                fields=["request_type", "status"],
                name="idx_dual_type_status",
            ),
            models.Index(
                fields=["tenant_id", "status"],
                name="idx_dual_tenant_status",
            ),
        ]

    def __str__(self):
        return (
            f"DualApproval({self.request_type}, {self.status}, "
            f"requester={self.requester_id})"
        )

    @property
    def is_expired(self):
        """Check whether the request has passed its expiry deadline."""
        return self.status == "pending" and timezone.now() > self.expires_at

    @property
    def is_pending(self):
        """Check whether the request is still awaiting a decision."""
        return self.status == "pending"


# ══════════════════════════════════════════════════════════════════════════════
# Model: EmergencyControl
# ══════════════════════════════════════════════════════════════════════════════

class EmergencyControl(models.Model):
    """Break-glass emergency control for incident response.

    Emergency controls allow authorised administrators to rapidly
    restrict platform operations during a security incident.  Examples
    include freezing all withdrawals, revoking all admin sessions, or
    locking down the admin panel entirely.

    Only one active control of a given type is allowed at a time.
    Activation and deactivation are both audited.
    """

    CONTROL_TYPE_CHOICES = [
        ("withdrawal_freeze", "Withdrawal Freeze"),
        ("session_revocation", "Session Revocation"),
        ("account_lockdown", "Account Lockdown"),
        ("incident_mode", "Incident Mode"),
        ("admin_lockout", "Admin Lockout"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    tenant_id = models.UUIDField(
        db_index=True,
        null=True,
        blank=True,
        help_text="Organisation tenant ID for row-level security isolation.",
    )
    control_type = models.CharField(
        max_length=30,
        choices=CONTROL_TYPE_CHOICES,
        db_index=True,
        help_text="Type of emergency control.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="True while the control is in effect.",
    )
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="activated_emergency_controls",
        help_text="Administrator who activated the control.",
    )
    activated_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the control was activated.",
    )
    deactivated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deactivated_emergency_controls",
        help_text="Administrator who deactivated the control.",
    )
    deactivated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the control was deactivated.",
    )
    reason = models.TextField(
        help_text="Mandatory reason for activating the emergency control.",
    )
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Optional configuration for the control, e.g. scope filters.",
    )

    class Meta:
        ordering = ["-activated_at"]
        verbose_name = "Emergency Control"
        verbose_name_plural = "Emergency Controls"
        indexes = [
            models.Index(
                fields=["control_type", "is_active"],
                name="idx_emerg_type_active",
            ),
            models.Index(
                fields=["tenant_id", "control_type", "is_active"],
                name="idx_emerg_tenant_type_active",
            ),
        ]

    def __str__(self):
        state = "ACTIVE" if self.is_active else "INACTIVE"
        return f"EmergencyControl({self.control_type}, {state})"


# ══════════════════════════════════════════════════════════════════════════════
# Model: AdminIPAddress
# ══════════════════════════════════════════════════════════════════════════════

class AdminIPAddress(models.Model):
    """IP allow-list entry for admin network isolation.

    Only requests originating from a listed IP or CIDR range are
    permitted to access admin paths.  This provides a network-level
    defence layer that is independent of application-level authentication.

    Entries can be global (no user) or tied to a specific administrator.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    tenant_id = models.UUIDField(
        db_index=True,
        null=True,
        blank=True,
        help_text="Organisation tenant ID for row-level security isolation.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="allowed_admin_ips",
        null=True,
        blank=True,
        help_text=(
            "If set, this entry applies only to the specified user. "
            "If null, it applies globally."
        ),
    )
    ip_address = models.GenericIPAddressField(
        help_text="Individual IP address allowed for admin access.",
    )
    ip_range = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="CIDR notation range, e.g. '10.0.0.0/8'.  Takes precedence over ip_address.",
    )
    label = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Human-readable label, e.g. 'Office VPN', 'Data Center'.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Inactive entries are skipped during IP validation.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Admin IP Address"
        verbose_name_plural = "Admin IP Addresses"
        indexes = [
            models.Index(
                fields=["user", "is_active"],
                name="idx_adminip_user_active",
            ),
            models.Index(
                fields=["tenant_id", "is_active"],
                name="idx_adminip_tenant_active",
            ),
        ]

    def __str__(self):
        target = self.ip_range or str(self.ip_address)
        label = f" ({self.label})" if self.label else ""
        return f"AdminIP {target}{label}"
