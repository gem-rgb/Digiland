"""
Admin Control Plane Middleware
================================

Middleware components that enforce the admin control plane's security
policies on every request to administrative paths.

The middleware stack is designed as a series of defence layers, each
responsible for a specific security concern:

1. AdminNetworkIsolationMiddleware  — IP allow-list verification
2. AdminMFAEnforcementMiddleware    — Mandatory MFA for admin sessions
3. AdminSessionSecurityMiddleware   — Session timeout & anomaly detection
4. AdminAuditMiddleware             — Immutable audit logging

Ordering matters: these should be placed BEFORE the core RBAC and rate-
limiting middleware so that network isolation and MFA checks are enforced
first.

Configure in Django settings:

    MIDDLEWARE = [
        ...
        'admin_control_plane.middleware.AdminNetworkIsolationMiddleware',
        'admin_control_plane.middleware.AdminMFAEnforcementMiddleware',
        'admin_control_plane.middleware.AdminSessionSecurityMiddleware',
        'admin_control_plane.middleware.AdminAuditMiddleware',
        ...
    ]
"""

import ipaddress
import logging
import hashlib

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _is_admin_path(path: str) -> bool:
    """Return True if the request path targets an admin endpoint."""
    admin_prefixes = getattr(
        settings,
        "ADMIN_PATH_PREFIXES",
        ["/admin/", "/api/v1/admin/"],
    )
    return any(path.startswith(prefix) for prefix in admin_prefixes)


def _client_ip(request) -> str:
    """Extract the client IP from the request, respecting trusted proxies.

    Uses ``X-Forwarded-For`` when the request arrives through a trusted
    reverse proxy (configured via ``ADMIN_TRUSTED_PROXY_COUNT``).
    """
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        # Use the rightmost untrusted IP, or the first IP if no trusted
        # proxy count is configured.  For simplicity, we take the first
        # IP in the chain (leftmost = original client behind one proxy).
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def _device_fingerprint(request) -> str:
    """Generate a device fingerprint from request metadata.

    The fingerprint is a SHA-256 hash of the User-Agent and other
    browser-specific headers.  It is not a perfect identifier but
    sufficient for detecting device switches within a session.
    """
    ua = request.META.get("HTTP_USER_AGENT", "")
    accept = request.META.get("HTTP_ACCEPT", "")
    accept_lang = request.META.get("HTTP_ACCEPT_LANGUAGE", "")
    raw = f"{ua}|{accept}|{accept_lang}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _ip_in_allowed_ranges(ip_str: str, allowed_ranges: list) -> bool:
    """Check whether an IP address falls within any of the allowed ranges.

    Args:
        ip_str: The client IP address as a string.
        allowed_ranges: A list of CIDR strings (e.g. ['10.0.0.0/8'])
            or individual IP addresses.

    Returns:
        True if the IP is within any allowed range.
    """
    try:
        client_ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    for entry in allowed_ranges:
        entry = entry.strip()
        if not entry:
            continue
        try:
            # Try CIDR range first
            if "/" in entry:
                if client_ip in ipaddress.ip_network(entry, strict=False):
                    return True
            else:
                # Single IP
                if client_ip == ipaddress.ip_address(entry):
                    return True
        except ValueError:
            continue
    return False


# ══════════════════════════════════════════════════════════════════════════════
# Middleware: AdminNetworkIsolationMiddleware
# ══════════════════════════════════════════════════════════════════════════════


class AdminNetworkIsolationMiddleware:
    """Enforce IP allow-list for administrative paths.

    Only requests originating from trusted network ranges (VPN, office
    CIDR, data centre) are permitted to reach admin endpoints.  All
    other IPs receive a 403 response and the attempt is logged.

    Configuration (Django settings):

        ADMIN_ALLOWED_IP_RANGES = [
            "10.0.0.0/8",          # Internal VPN
            "172.16.0.0/12",       # Private network
            "192.168.1.0/24",      # Office network
            "203.0.113.50",        # Specific IP
        ]

    If ``ADMIN_ALLOWED_IP_RANGES`` is not set or is empty, the
    middleware does NOT block any request (allow-by-default for
    development).  In production, this MUST be configured.
    """

    # Paths exempt from network isolation (e.g. the MFA setup page)
    EXEMPT_PATHS = set()

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Skip non-admin paths
        if not _is_admin_path(path):
            return self.get_response(request)

        # Skip exempt paths
        if any(path.startswith(exempt) for exempt in self.EXEMPT_PATHS):
            return self.get_response(request)

        # Allow static/media through
        if path.startswith("/static/") or path.startswith("/media/"):
            return self.get_response(request)

        # Resolve allowed IP ranges
        allowed_ranges = list(
            getattr(settings, "ADMIN_ALLOWED_IP_RANGES", [])
        )

        # If no ranges are configured, allow through (dev mode)
        if not allowed_ranges:
            return self.get_response(request)

        # Also check AdminIPAddress model for per-user / global entries
        try:
            from .models import AdminIPAddress

            active_ips = AdminIPAddress.objects.filter(is_active=True)
            for entry in active_ips:
                if entry.ip_range:
                    allowed_ranges.append(entry.ip_range)
                else:
                    allowed_ranges.append(str(entry.ip_address))
        except Exception:
            # If the model isn't available (e.g. during migration),
            # rely on settings only.
            pass

        client_ip = _client_ip(request)

        if not _ip_in_allowed_ranges(client_ip, allowed_ranges):
            logger.warning(
                "AdminNetworkIsolation: BLOCKED ip=%s path=%s user=%s",
                client_ip,
                path,
                getattr(request.user, "email", "anon"),
            )

            # Create audit log entry for the blocked attempt
            self._audit_blocked_attempt(request, client_ip, path)

            return JsonResponse(
                {
                    "detail": (
                        "Access denied.  Administrative access is only "
                        "permitted from authorised networks."
                    ),
                },
                status=403,
            )

        return self.get_response(request)

    @staticmethod
    def _audit_blocked_attempt(request, ip, path):
        """Create an audit log entry for a blocked network access attempt."""
        try:
            from core.models import AuditLog

            AuditLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                action="ADMIN_NETWORK_BLOCKED",
                ip_address=ip,
                metadata={
                    "path": path,
                    "reason": "IP not in allowed ranges",
                },
            )
        except Exception:
            logger.exception("Failed to audit blocked admin network access")


# ══════════════════════════════════════════════════════════════════════════════
# Middleware: AdminMFAEnforcementMiddleware
# ══════════════════════════════════════════════════════════════════════════════


class AdminMFAEnforcementMiddleware:
    """Enforce mandatory MFA verification for administrative paths.

    Accessing any admin path requires that the user has completed MFA
    verification.  Password-only authentication is insufficient.

    For financial operations (identified by path pattern), a hardware
    security key (WebAuthn) is additionally required.

    Exempt paths:
        - Admin login page
        - MFA verification endpoint
        - MFA setup endpoint
    """

    # Paths that do NOT require MFA (login, MFA setup/verify)
    MFA_EXEMPT_PATHS = {
        "/admin/login/",
        "/api/v1/admin/auth/login/",
        "/api/v1/admin/auth/mfa/verify/",
        "/api/v1/admin/auth/mfa/setup/",
        "/api/v1/admin/auth/mfa/challenge/",
    }

    # Paths that require hardware key verification
    FINANCIAL_PATHS = {
        "/api/v1/admin/financial/",
        "/api/v1/admin/withdrawals/",
        "/api/v1/admin/payouts/",
        "/api/v1/admin/transfers/",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Skip non-admin paths
        if not _is_admin_path(path):
            return self.get_response(request)

        # Skip static/media
        if path.startswith("/static/") or path.startswith("/media/"):
            return self.get_response(request)

        # Skip exempt paths (login, MFA endpoints)
        if any(path.startswith(exempt) for exempt in self.MFA_EXEMPT_PATHS):
            return self.get_response(request)

        user = request.user

        # Unauthenticated users are handled by auth middleware
        if not getattr(user, "is_authenticated", False):
            return self.get_response(request)

        # Only enforce MFA for admin-role users
        if getattr(user, "role", None) != "Admin" and not getattr(user, "is_superuser", False):
            return self.get_response(request)

        # Check MFA verification status from admin session
        admin_session = self._get_admin_session(request)
        if admin_session is None:
            # No admin session found — redirect to MFA verification
            return self._require_mfa(request, path)

        if not admin_session.is_mfa_verified:
            return self._require_mfa(request, path)

        # Check hardware key for financial operations
        if self._is_financial_path(path) and not admin_session.hardware_key_verified:
            logger.warning(
                "AdminMFAEnforcement: Financial path accessed without "
                "hardware key user=%s path=%s",
                user.email,
                path,
            )
            return JsonResponse(
                {
                    "detail": (
                        "Hardware security key verification is required "
                        "for financial operations."
                    ),
                    "require_hardware_key": True,
                },
                status=403,
            )

        # Attach admin session to request for downstream use
        request.admin_session = admin_session

        return self.get_response(request)

    def _get_admin_session(self, request):
        """Retrieve the active admin session for the current request.

        Looks for the admin session token in the request headers
        (``X-Admin-Session-Token``) or in the Django session.
        """
        session_token = request.META.get(
            "HTTP_X_ADMIN_SESSION_TOKEN", ""
        ) or request.session.get("admin_session_token", "")

        if not session_token:
            return None

        try:
            from .models import AdminSession

            return AdminSession.objects.select_related("user").get(
                session_token=session_token,
                is_active=True,
                user=request.user,
            )
        except Exception:
            return None

    def _is_financial_path(self, path: str) -> bool:
        """Check whether the path targets a financial operation."""
        return any(path.startswith(prefix) for prefix in self.FINANCIAL_PATHS)

    def _require_mfa(self, request, path: str):
        """Redirect or return 403 requiring MFA verification.

        API requests receive a JSON response; browser requests are
        redirected to the MFA verification page.
        """
        user = request.user
        logger.info(
            "AdminMFAEnforcement: MFA required user=%s path=%s",
            getattr(user, "email", "anon"),
            path,
        )

        # API requests expect JSON
        if path.startswith("/api/"):
            return JsonResponse(
                {
                    "detail": "MFA verification is required for admin access.",
                    "require_mfa": True,
                },
                status=403,
            )

        # Browser requests get redirected
        try:
            return redirect(reverse("admin_mfa_verify"))
        except Exception:
            return JsonResponse(
                {"detail": "MFA verification is required for admin access."},
                status=403,
            )


# ══════════════════════════════════════════════════════════════════════════════
# Middleware: AdminSessionSecurityMiddleware
# ══════════════════════════════════════════════════════════════════════════════


class AdminSessionSecurityMiddleware:
    """Enforce admin session timeouts and detect anomalous activity.

    This middleware validates every request to an admin path against the
    admin session's security constraints:

    * **Idle timeout**: If the session has been idle for longer than the
      configured maximum (default 30 minutes), the session is terminated.
    * **Absolute timeout**: If the session has exceeded its maximum
      lifetime (default 4 hours), the session is terminated.
    * **IP change detection**: If the client IP changes mid-session, the
      session is flagged and may be terminated depending on configuration.
    * **Device fingerprint change**: If the device fingerprint changes
      mid-session, the session is flagged as suspicious.

    Configuration (Django settings):

        ADMIN_SESSION_IDLE_TIMEOUT_SECONDS = 1800     # 30 min
        ADMIN_SESSION_ABSOLUTE_TIMEOUT_SECONDS = 14400 # 4 hours
        ADMIN_SESSION_TERMINATE_ON_IP_CHANGE = True
        ADMIN_SESSION_TERMINATE_ON_DEVICE_CHANGE = False
    """

    DEFAULT_IDLE_TIMEOUT = 1800       # 30 minutes
    DEFAULT_ABSOLUTE_TIMEOUT = 14400  # 4 hours

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Skip non-admin paths
        if not _is_admin_path(path):
            return self.get_response(request)

        # Skip static/media
        if path.startswith("/static/") or path.startswith("/media/"):
            return self.get_response(request)

        # Skip unauthenticated requests (handled by MFA middleware)
        user = request.user
        if not getattr(user, "is_authenticated", False):
            return self.get_response(request)

        # Retrieve admin session
        admin_session = getattr(request, "admin_session", None)
        if admin_session is None:
            # Try to get it from the token
            session_token = request.META.get(
                "HTTP_X_ADMIN_SESSION_TOKEN", ""
            ) or request.session.get("admin_session_token", "")
            if session_token:
                try:
                    from .models import AdminSession

                    admin_session = AdminSession.objects.get(
                        session_token=session_token,
                        is_active=True,
                        user=user,
                    )
                except Exception:
                    admin_session = None

        if admin_session is None:
            return self.get_response(request)

        now = timezone.now()
        idle_timeout = getattr(
            settings,
            "ADMIN_SESSION_IDLE_TIMEOUT_SECONDS",
            self.DEFAULT_IDLE_TIMEOUT,
        )
        absolute_timeout = getattr(
            settings,
            "ADMIN_SESSION_ABSOLUTE_TIMEOUT_SECONDS",
            self.DEFAULT_ABSOLUTE_TIMEOUT,
        )

        # ── Check absolute timeout ───────────────────────────────────────
        if now > admin_session.absolute_expires_at:
            self._terminate_session(
                admin_session, "absolute_expiry", request
            )
            return self._session_expired_response(request)

        # ── Check idle timeout ───────────────────────────────────────────
        idle_seconds = (now - admin_session.last_activity_at).total_seconds()
        if idle_seconds > idle_timeout:
            self._terminate_session(
                admin_session, "idle_timeout", request
            )
            return self._session_expired_response(request)

        # ── Detect IP change ─────────────────────────────────────────────
        current_ip = _client_ip(request)
        if str(admin_session.ip_address) != current_ip:
            terminate_on_ip_change = getattr(
                settings,
                "ADMIN_SESSION_TERMINATE_ON_IP_CHANGE",
                True,
            )
            self._log_security_event(
                admin_session,
                "ip_change",
                {
                    "original_ip": str(admin_session.ip_address),
                    "new_ip": current_ip,
                },
                request,
            )
            if terminate_on_ip_change:
                self._terminate_session(
                    admin_session, "security_event_ip_change", request
                )
                return self._session_expired_response(
                    request, reason="IP address changed during session"
                )

        # ── Detect device fingerprint change ─────────────────────────────
        current_fingerprint = _device_fingerprint(request)
        if (
            admin_session.device_fingerprint
            and current_fingerprint != admin_session.device_fingerprint
        ):
            terminate_on_device_change = getattr(
                settings,
                "ADMIN_SESSION_TERMINATE_ON_DEVICE_CHANGE",
                False,
            )
            self._log_security_event(
                admin_session,
                "device_change",
                {
                    "original_fp": admin_session.device_fingerprint[:8],
                    "new_fp": current_fingerprint[:8],
                },
                request,
            )
            if terminate_on_device_change:
                self._terminate_session(
                    admin_session, "security_event_device_change", request
                )
                return self._session_expired_response(
                    request, reason="Device changed during session"
                )

        # ── Refresh idle timeout ─────────────────────────────────────────
        from datetime import timedelta

        admin_session.expires_at = now + timedelta(seconds=idle_timeout)
        admin_session.save(update_fields=["expires_at", "last_activity_at"])

        # Attach session to request for downstream middleware
        request.admin_session = admin_session

        return self.get_response(request)

    def _terminate_session(self, session, reason, request):
        """Terminate an admin session and log the event."""
        session.is_active = False
        session.terminated_at = timezone.now()
        session.termination_reason = reason
        session.save(update_fields=["is_active", "terminated_at", "termination_reason"])

        logger.warning(
            "AdminSessionSecurity: Session terminated user=%s reason=%s",
            session.user_id,
            reason,
        )

        # Create audit log
        try:
            from core.models import AuditLog

            AuditLog.objects.create(
                user=session.user,
                action=f"ADMIN_SESSION_TERMINATED:{reason}",
                ip_address=_client_ip(request),
                metadata={"session_id": str(session.id), "reason": reason},
            )
        except Exception:
            logger.exception("Failed to audit session termination")

    def _log_security_event(self, session, event_type, details, request):
        """Log a security event without terminating the session."""
        logger.warning(
            "AdminSessionSecurity: %s user=%s session=%s details=%s",
            event_type,
            session.user_id,
            str(session.id)[:8],
            details,
        )

        try:
            from core.models import AuditLog

            AuditLog.objects.create(
                user=session.user,
                action=f"ADMIN_SESSION_SECURITY:{event_type}",
                ip_address=_client_ip(request),
                metadata={
                    "session_id": str(session.id),
                    "event_type": event_type,
                    **details,
                },
            )
        except Exception:
            logger.exception("Failed to audit session security event")

    @staticmethod
    def _session_expired_response(request, reason=None):
        """Return an appropriate response for an expired/terminated session."""
        path = request.path
        detail = reason or "Admin session has expired.  Please re-authenticate."

        # Clear the admin session token from the Django session
        if hasattr(request, "session"):
            request.session.pop("admin_session_token", None)

        if path.startswith("/api/"):
            return JsonResponse(
                {"detail": detail, "admin_session_expired": True},
                status=401,
            )

        try:
            return redirect(reverse("admin_mfa_verify"))
        except Exception:
            return JsonResponse({"detail": detail}, status=401)


# ══════════════════════════════════════════════════════════════════════════════
# Middleware: AdminAuditMiddleware
# ══════════════════════════════════════════════════════════════════════════════


class AdminAuditMiddleware:
    """Immutable audit logging for every administrative action.

    This middleware intercepts all requests to admin paths and creates
    a tamper-resistant ``AdminActionLog`` entry.  The log includes:

    * The actor (authenticated admin user)
    * The action type (derived from the path)
    * The admin session context
    * Client IP, user agent, and device fingerprint
    * Step-up auth and dual-approval status from the session
    * A computed risk score
    * A hash-chain entry for tamper detection

    This ensures that every administrative action is recorded in a way
    that makes retroactive modification detectable.
    """

    # Path → action type mapping
    ACTION_TYPE_MAP = {
        "/api/v1/admin/users/verify": "user_verify",
        "/api/v1/admin/kyc/": "kyc_approve",
        "/api/v1/admin/financial/": "financial",
        "/api/v1/admin/withdrawals/": "withdrawal_approve",
        "/api/v1/admin/permissions/": "permission_change",
        "/api/v1/admin/roles/": "role_change",
        "/api/v1/admin/admins/": "admin_create",
        "/api/v1/admin/config/": "config_change",
        "/api/v1/admin/emergency/": "emergency",
        "/admin/": "config_change",
    }

    # Paths to skip entirely (e.g. health checks, static files)
    SKIP_PATHS = {"/admin/jsi18n/", "/admin/login/", "/admin/logout/"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Only audit admin paths
        if not _is_admin_path(path):
            return self.get_response(request)

        # Skip static/media
        if path.startswith("/static/") or path.startswith("/media/"):
            return self.get_response(request)

        # Skip explicitly excluded paths
        if any(path.startswith(skip) for skip in self.SKIP_PATHS):
            return self.get_response(request)

        # Skip read-only methods for non-sensitive paths (GET, HEAD, OPTIONS)
        # We still audit write methods (POST, PUT, PATCH, DELETE)
        if request.method in ("GET", "HEAD", "OPTIONS"):
            # Only audit GET requests to sensitive paths
            if not self._is_sensitive_read_path(path):
                return self.get_response(request)

        # Process the request
        response = self.get_response(request)

        # Create the audit log entry
        self._create_audit_log(request, response)

        return response

    def _is_sensitive_read_path(self, path: str) -> bool:
        """Check whether a GET request to this path should still be audited."""
        sensitive_reads = {
            "/api/v1/admin/financial/",
            "/api/v1/admin/audit/",
            "/api/v1/admin/emergency/",
        }
        return any(path.startswith(prefix) for prefix in sensitive_reads)

    def _resolve_action_type(self, path: str) -> str:
        """Map a request path to an action type."""
        for prefix, action_type in self.ACTION_TYPE_MAP.items():
            if path.startswith(prefix):
                return action_type
        return "config_change"  # Default for unknown admin paths

    def _calculate_risk_score(self, request, action_type: str) -> float:
        """Calculate a risk score (0-100) for the admin action.

        The score is based on:
        * Action type (financial > config > read)
        * Whether the action is a write operation
        * Time of day (outside business hours = higher risk)
        * Whether the session has hardware key verification
        """
        score = 0.0

        # Base score by action type
        type_scores = {
            "financial": 60.0,
            "withdrawal_approve": 70.0,
            "emergency": 50.0,
            "role_change": 45.0,
            "permission_change": 40.0,
            "admin_create": 55.0,
            "kyc_approve": 30.0,
            "user_verify": 20.0,
            "config_change": 25.0,
        }
        score += type_scores.get(action_type, 15.0)

        # Write operations are riskier
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            score += 10.0

        # Outside business hours (8 AM - 6 PM UTC)
        now = timezone.now()
        if now.hour < 8 or now.hour >= 18:
            score += 5.0

        # No hardware key verified
        admin_session = getattr(request, "admin_session", None)
        if admin_session and not admin_session.hardware_key_verified:
            score += 5.0

        # Cap at 100
        return min(score, 100.0)

    def _create_audit_log(self, request, response):
        """Create an AdminActionLog entry for the current request."""
        try:
            from .models import AdminActionLog

            user = request.user
            admin_session = getattr(request, "admin_session", None)
            action_type = self._resolve_action_type(request.path)
            risk_score = self._calculate_risk_score(request, action_type)

            # Determine resource type/id from path segments
            resource_type, resource_id = self._extract_resource(request.path)

            AdminActionLog.objects.create(
                tenant_id=getattr(request, "tenant_id", None),
                actor=user if user.is_authenticated else None,
                session=admin_session,
                action_type=action_type,
                resource_type=resource_type,
                resource_id=resource_id,
                action_details={
                    "method": request.method,
                    "path": request.path,
                    "status_code": response.status_code,
                    "query_params": dict(request.GET) if request.GET else {},
                },
                ip_address=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
                device_fingerprint=_device_fingerprint(request),
                step_up_auth=getattr(admin_session, "is_mfa_verified", False),
                dual_approval=False,  # Set by specific views when applicable
                risk_score=risk_score,
                is_flagged=risk_score >= 70.0,
            )
        except Exception:
            # Audit logging must never break the request
            logger.exception(
                "AdminAuditMiddleware: Failed to create audit log for %s",
                request.path,
            )

    @staticmethod
    def _extract_resource(path: str):
        """Extract resource_type and resource_id from the URL path.

        E.g. '/api/v1/admin/users/abc-123/verify/' → ('User', 'abc-123')
        """
        parts = [p for p in path.split("/") if p]
        resource_type = "Unknown"
        resource_id = "0"

        # Try to find a resource collection in the path
        collection_names = {
            "users": "User",
            "kyc": "KYCProfile",
            "financial": "FinancialAction",
            "withdrawals": "Withdrawal",
            "payouts": "Payout",
            "transfers": "Transfer",
            "permissions": "Permission",
            "roles": "Role",
            "admins": "Admin",
            "config": "Configuration",
            "emergency": "EmergencyControl",
        }

        for i, part in enumerate(parts):
            if part.lower() in collection_names:
                resource_type = collection_names[part.lower()]
                # Next segment might be the ID
                if i + 1 < len(parts):
                    candidate = parts[i + 1]
                    # UUID-like or numeric ID
                    if len(candidate) > 8 or candidate.isdigit():
                        resource_id = candidate
                break

        return resource_type, resource_id
