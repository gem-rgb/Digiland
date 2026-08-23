import sys
import time
import logging
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.core.cache import cache
from django.http import JsonResponse


class ExceptionLoggerMiddleware:
    """Catch unhandled view/middleware exceptions and output the traceback."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        import traceback
        from django.http import HttpResponse
        tb = traceback.format_exc()
        return HttpResponse(f"<h1>Application Exception</h1><pre style='background:#111;color:#ff6b6b;padding:1.5rem;border-radius:8px;font-size:13px;line-height:1.5;overflow:auto;'>{tb}</pre>", status=500, content_type="text/html")


class LegacyBrowseRedirectMiddleware:
    """Redirect the old /browse alias to the marketplace page."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.rstrip('/') == '/browse':
            return redirect('/parcels/')
        return self.get_response(request)


logger = logging.getLogger(__name__)


class CanonicalBackendHostMiddleware:
    """Normalize local browser requests to the configured backend origin.

    allauth builds OAuth callback URLs from the active request host. If the
    app is reached through both ``localhost`` and ``127.0.0.1`` during local
    development, Google sees different redirect URIs and rejects the login.
    """

    LOCAL_HOST_ALIASES = {"localhost", "127.0.0.1", "[::1]"}

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _split_host_port(host: str) -> str:
        host = (host or "").strip().lower()
        if host.startswith("[") and "]" in host:
            return host.split("]", 1)[0] + "]"
        return host.split(":", 1)[0]

    def __call__(self, request):
        backend_url = getattr(settings, "PUBLIC_BACKEND_URL", "").strip()
        if not backend_url:
            return self.get_response(request)

        parsed = urlsplit(backend_url)
        if not parsed.scheme or not parsed.netloc:
            return self.get_response(request)

        current_host = self._split_host_port(request.get_host())
        canonical_host = self._split_host_port(parsed.netloc)
        current_scheme = "https" if request.is_secure() else "http"

        if current_host == canonical_host and current_scheme == parsed.scheme:
            return self.get_response(request)

        if current_host not in self.LOCAL_HOST_ALIASES and current_host != canonical_host:
            return self.get_response(request)

        target = urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                request.path,
                request.META.get("QUERY_STRING", ""),
                "",
            )
        )
        return redirect(target)

EMAIL_VERIFICATION_EXEMPT_PREFIXES = (
    '/static/',
    '/media/',
    '/accounts/',
    '/api/v1/auth/',
)

EMAIL_VERIFICATION_EXEMPT_PATHS = {
    '/favicon.ico',
    '/robots.txt',
}


class EmailVerificationGateMiddleware:
    """Block authenticated users who have not yet verified their email."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "TESTING", False):
            return self.get_response(request)

        path = request.path
        if path in EMAIL_VERIFICATION_EXEMPT_PATHS or any(path.startswith(prefix) for prefix in EMAIL_VERIFICATION_EXEMPT_PREFIXES):
            return self.get_response(request)

        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return self.get_response(request)

        if getattr(user, "role", None) == "Admin" or getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            return self.get_response(request)

        if getattr(user, "is_email_verified", True):
            return self.get_response(request)

        return redirect(reverse("account_verification_pending"))

# ── Path prefixes that are ALWAYS accessible to Agent users ──────────────────
# Phase 1 (unverified): only KYC, onboarding, auth, and static paths
AGENT_UNVERIFIED_EXEMPT = {
    '/agent/kyc/',
    '/kyc/',
    '/api/kyc/',
    '/agent/onboarding/',
    '/staff/login/',
    '/accounts/logout/',
    '/accounts/login/',
    '/accounts/signup/',
    '/admin/',
}

# Phase 2 (verified): all operational work pages the agent needs
AGENT_VERIFIED_EXEMPT = {
    # Auth & onboarding
    '/agent/kyc/',
    '/agent/onboarding/',
    '/staff/login/',
    '/accounts/logout/',
    '/accounts/login/',
    '/accounts/signup/',
    '/admin/',
    # Agent command-centre and work views
    '/agent/dashboard/',
    '/agent/tasks/',
    '/agent/applications/',
    '/agent/users/',
    '/agent/approvals/',
    '/agent/send-message/',
    '/agent/assign-task/',
    '/agent/unassign-task/',
    '/agent/rate/',
    '/agent/parcel/',
    '/agent/transaction/',
    '/agent/signup-complete/',
    # Core operational pages
    '/parcels/',
    '/transactions/',
    '/messages/',
    '/support/',
    '/recommendations/',
    '/price-prediction/',
    # Informational pages
    '/about/',
    '/architecture/',
    '/investors/',
    '/terms/',
    '/privacy/',
    '/escrow-acts/',
    # Home page
    '/',
}


class AgentKYCGateMiddleware:
    """
    Enforces the two-phase Agent flow on every request:

    Phase 1 — Unverified Agent (KYC not yet approved):
      • No KYC submitted yet  → /agent/kyc/
      • KYC submitted, awaiting admin review → /agent/onboarding/

    Phase 2 — Verified (approved) Agent accessing site via public session
               without staff authentication:
      • Redirect to /agent/onboarding/ which shows the
        "You're approved — use Staff Login" message.
      • All agent operational paths (parcels, transactions, approvals,
        messaging, etc.) are whitelisted so the dashboard is functional
        once the agent is logged in through the staff portal.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user

        if user.is_authenticated and getattr(user, 'role', None) == 'Agent':
            path = request.path

            # Always let static / media through
            if path.startswith('/static/') or path.startswith('/media/'):
                return self.get_response(request)

            if user.is_identity_verified:
                # Verified agent — allow all operational paths
                is_exempt = any(path.startswith(p) for p in AGENT_VERIFIED_EXEMPT)
                # Also allow the exact home path '/'
                if path == '/':
                    is_exempt = True
                if not is_exempt:
                    return redirect(reverse('frontend:agent_onboarding'))

            else:
                # Unverified agent — strict KYC gate
                is_exempt = any(path.startswith(p) for p in AGENT_UNVERIFIED_EXEMPT)
                if not is_exempt:
                    try:
                        from core.models import AgentKYCApplication
                        app = AgentKYCApplication.objects.get(agent=user)
                        if app.kyc_submitted:
                            return redirect(reverse('frontend:agent_onboarding'))
                        return redirect(reverse('frontend:agent_kyc'))
                    except Exception:
                        return redirect(reverse('frontend:agent_kyc'))

        return self.get_response(request)


def get_client_ip(request) -> str:
    """Extract client IP address, prioritizing Cloudflare's CF-Connecting-IP header.

    Falls back to X-Forwarded-For (client IP) and REMOTE_ADDR.
    """
    cf_ip = request.META.get("HTTP_CF_CONNECTING_IP")
    if cf_ip:
        return cf_ip.strip()

    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        # First IP in X-Forwarded-For is the originating client IP
        return xff.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR", "0.0.0.0")


# ── Rate Limiting Middleware ──────────────────────────────────────────────────


class RateLimitMiddleware:
    """
    IP-based rate limiting middleware.

    Limits the number of requests a single IP can make within a rolling
    time window.  Uses the configured Django cache backend (Redis in
    production, locmem in development).

    Configure via Django settings:

        RATE_LIMIT_DEFAULT = "100/60"          # 100 requests per 60 seconds
        RATE_LIMIT_PER_PATH = {                 # optional per-path overrides
            "/api/": "300/60",
            "/api/auth/": "20/60",
        }
    """

    DEFAULT_RATE = "100/60"  # 100 requests per 60 seconds

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "TESTING", False) or "test" in sys.argv:
            return self.get_response(request)

        # Skip for static / media / admin paths
        path = request.path
        if path.startswith("/static/") or path.startswith("/media/"):
            return self.get_response(request)

        # Skip for superusers / staff
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False) and (user.is_superuser or user.is_staff):
            return self.get_response(request)

        # Only apply in production or when explicitly enabled
        if not getattr(settings, "RATE_LIMIT_ENABLED", not settings.DEBUG):
            return self.get_response(request)

        rate_str = self._get_rate_limit(path)
        limit, window_seconds = self._parse_rate(rate_str)

        key = self._cache_key(request)
        now = time.time()

        try:
            from django.core.cache import cache

            window_data = cache.get(key)
            if window_data is None:
                cache.set(key, {"count": 1, "window_start": now}, timeout=window_seconds)
                return self.get_response(request)

            # Check if window expired
            if now - window_data["window_start"] > window_seconds:
                cache.set(key, {"count": 1, "window_start": now}, timeout=window_seconds)
                return self.get_response(request)

            if window_data["count"] < limit:
                window_data["count"] += 1
                cache.set(
                    key,
                    window_data,
                    timeout=int(window_seconds - (now - window_data["window_start"])),
                )
                return self.get_response(request)

            # Limit reached
            logger.warning(
                "Rate limit exceeded for IP %s on %s (%d requests in %ds)",
                self._client_ip(request),
                path,
                window_data["count"],
                window_seconds,
            )
            return JsonResponse(
                {
                    "detail": "Rate limit exceeded. Please try again later.",
                    "retry_after": int(window_seconds - (now - window_data["window_start"])),
                },
                status=429,
            )
        except Exception as e:
            # Cache failure must never block requests
            logger.error("Rate limit check failed: %s", e)
            return self.get_response(request)

    # ── helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _client_ip(request):
        return get_client_ip(request)

    @staticmethod
    def _cache_key(request):
        ip = RateLimitMiddleware._client_ip(request)
        return f"rl:{ip}"

    @staticmethod
    def _parse_rate(rate_str):
        """Parse 'count/seconds' string, e.g. '100/60' -> (100, 60)."""
        parts = rate_str.split("/")
        return int(parts[0]), int(parts[1])

    @staticmethod
    def _get_rate_limit(path):
        """Resolve the rate limit for a given request path."""
        from django.conf import settings

        per_path = getattr(settings, "RATE_LIMIT_PER_PATH", {})
        for prefix, rate in per_path.items():
            if path.startswith(prefix):
                return rate
        return getattr(settings, "RATE_LIMIT_DEFAULT", RateLimitMiddleware.DEFAULT_RATE)


# ── Role-Based Access Control Middleware ──────────────────────────────────────


class RBACMiddleware:
    """
    Lightweight role-based access control middleware.

    Enforces URL -> role mappings defined in Django settings:

        RBAC_RULES = {
            "/api/admin/":     ["Admin"],
            "/api/agent/":     ["Agent", "Admin"],
            "/api/seller/":    ["Seller", "Admin"],
            "/api/buyer/":     ["Buyer", "Admin"],
        }

    Unauthenticated users are blocked on all RBAC-protected paths.
    Paths not listed in RBAC_RULES are unrestricted (handled by
    individual view permissions).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Skip non-API / static paths
        if path.startswith("/static/") or path.startswith("/media/"):
            return self.get_response(request)

        from django.conf import settings

        rbac_rules = getattr(settings, "RBAC_RULES", {})
        required_roles = self._match_roles(path, rbac_rules)

        if required_roles is None:
            # No RBAC rule for this path — allow through
            return self.get_response(request)

        user = request.user

        if not getattr(user, "is_authenticated", False):
            return JsonResponse(
                {"detail": "Authentication required."},
                status=401,
            )

        user_role = getattr(user, "role", None)

        if user_role not in required_roles:
            # Superusers bypass RBAC
            if getattr(user, "is_superuser", False):
                return self.get_response(request)

            logger.warning(
                "RBACMiddleware: user %s (role=%s) denied access to %s — requires %s",
                user.email,
                user_role,
                path,
                required_roles,
            )
            return JsonResponse(
                {"detail": "You do not have permission to access this resource."},
                status=403,
            )

        return self.get_response(request)

    @staticmethod
    def _match_roles(path, rbac_rules):
        """
        Find the first matching rule prefix and return its required roles.
        Returns None if no rule matches (meaning the path is unrestricted).
        """
        for prefix, roles in rbac_rules.items():
            if path.startswith(prefix):
                return roles
        return None


# ── Security Headers Middleware ──────────────────────────────────────────────


class SecurityHeadersMiddleware:
    """
    Adds security-related HTTP headers to every response.

    Headers added:
    - Content-Security-Policy: Prevents XSS by restricting resource loading
    - X-Content-Type-Options: Prevents MIME-type sniffing
    - X-Frame-Options: Prevents clickjacking
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Restricts browser features
    - Strict-Transport-Security: Enforces HTTPS (production only)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Content Security Policy
        # Default: restrict to same origin; allow Cloudinary for media
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  # Needed for React SPA
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data: https://res.cloudinary.com https://*.cloudinary.com",
            "connect-src 'self' https://api.paystack.co https://api.stripe.com",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
        response['Content-Security-Policy'] = '; '.join(csp_directives)

        # Prevent MIME-type sniffing
        response['X-Content-Type-Options'] = 'nosniff'

        # Prevent clickjacking
        response['X-Frame-Options'] = 'DENY'

        # Control referrer information
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Restrict browser features
        response['Permissions-Policy'] = (
            'camera=(), microphone=(), geolocation=(self), '
            'payment=(self), usb=(), magnetometer=(), gyroscope=()'
        )

        # XSS Protection (legacy, but still useful for older browsers)
        response['X-XSS-Protection'] = '1; mode=block'

        # Cache control for API responses
        if request.path.startswith('/api/'):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'

        return response


# ── Security Audit Middleware ────────────────────────────────────────────────


class SecurityAuditMiddleware:
    """
    Logs security-relevant events for audit purposes.

    Tracks:
    - Authentication events (login success/failure)
    - Authorization failures
    - Admin actions
    - Payment-related operations
    - Suspicious activity patterns

    NEVER logs: passwords, tokens, secrets, or PII in plaintext.
    """

    # Paths that trigger enhanced audit logging
    SENSITIVE_PATHS = {
        '/api/v1/auth/login': 'AUTH_LOGIN',
        '/api/v1/auth/register': 'AUTH_REGISTER',
        '/api/v1/payments/': 'PAYMENT_OPERATION',
        '/api/v1/mpesa/': 'MPESA_OPERATION',
        '/api/v1/admin/': 'ADMIN_OPERATION',
        '/api/v1/verification/': 'VERIFICATION_OPERATION',
        '/admin/': 'DJANGO_ADMIN',
    }

    # Status codes that indicate security events
    SECURITY_STATUS_CODES = {401, 403, 405, 429}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Determine if this request should be audited
        path = request.path
        event_type = self._classify_event(path)
        status_code = response.status_code

        should_log = (
            event_type is not None
            or status_code in self.SECURITY_STATUS_CODES
            or (request.user.is_authenticated and getattr(request.user, 'role', None) == 'Admin')
        )

        if should_log:
            self._log_security_event(request, response, event_type)

        return response

    def _classify_event(self, path):
        """Classify the request path into a security event type."""
        for prefix, event_type in self.SENSITIVE_PATHS.items():
            if path.startswith(prefix):
                return event_type
        return None

    def _log_security_event(self, request, response, event_type):
        """Log a security event with sanitized details."""
        user = request.user
        user_info = (
            f"user={user.email}, role={getattr(user, 'role', 'anon')}"
            if hasattr(user, 'email') and user.is_authenticated
            else "user=anonymous"
        )

        # Sanitize: never log passwords, tokens, or sensitive headers
        safe_method = request.method
        safe_path = request.path
        safe_status = response.status_code
        client_ip = self._client_ip(request)

        # Determine event category
        if response.status_code == 401:
            category = "AUTH_FAILURE"
        elif response.status_code == 403:
            category = "ACCESS_DENIED"
        elif response.status_code == 429:
            category = "RATE_LIMITED"
        elif event_type:
            category = event_type
        else:
            category = "SECURITY_EVENT"

        logger.warning(
            "SECURITY_AUDIT: category=%s %s %s status=%d ip=%s %s",
            category,
            safe_method,
            safe_path,
            safe_status,
            client_ip,
            user_info,
        )

        # For critical events, also create an AuditLog entry
        if category in ('AUTH_FAILURE', 'ACCESS_DENIED', 'PAYMENT_OPERATION', 'ADMIN_OPERATION'):
            try:
                from core.models import AuditLog
                AuditLog.objects.create(
                    user=user if hasattr(user, 'pk') and user.is_authenticated else None,
                    action=f"SECURITY: {category} {safe_method} {safe_path}",
                    ip_address=client_ip,
                    metadata={
                        'category': category,
                        'method': safe_method,
                        'path': safe_path,
                        'status_code': safe_status,
                        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
                    },
                )
            except Exception:
                # Don't let audit logging failures break the request
                pass

    @staticmethod
    def _client_ip(request):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[-1].strip()
        return request.META.get("REMOTE_ADDR", "0.0.0.0")


ONBOARDING_EXEMPT_PREFIXES = (
    '/static/',
    '/media/',
    '/accounts/',
    '/api/v1/auth/',
    '/onboarding/select-role/',
    '/api/onboarding/select-role/',
    '/api/auth/me/',
)

ONBOARDING_EXEMPT_PATHS = {
    '/favicon.ico',
    '/robots.txt',
}


class OnboardingGateMiddleware:
    """Block authenticated users who have not yet completed onboarding/role selection."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "TESTING", False):
            return self.get_response(request)

        path = request.path
        if path in ONBOARDING_EXEMPT_PATHS or any(path.startswith(prefix) for prefix in ONBOARDING_EXEMPT_PREFIXES):
            return self.get_response(request)

        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return self.get_response(request)

        # Allow superusers, staff, admins, and agents to bypass onboarding redirect
        if getattr(user, "is_superuser", False) or user.role in ['Admin', 'Agent', 'Lawyer']:
            return self.get_response(request)

        # If role is not assigned, or role is Buyer/Seller but is_onboarded is False
        if not user.role or not getattr(user, 'is_onboarded', False):
            # If it's an API request, return JSON so that React page knows it needs redirection or onboarding
            if path.startswith('/api/'):
                return JsonResponse(
                    {
                        "detail": "Onboarding role selection required.",
                        "redirect_to": "/onboarding/select-role/"
                    },
                    status=403
                )
            return redirect('/onboarding/select-role/')

        return self.get_response(request)
