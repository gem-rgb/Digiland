"""Partition Isolation & Host Security Middleware for Digiland
============================================================

Enforces strict canonical domain/subdomain partition isolation across the 4 frontends:
1. Marketing (digiland.co.ke / www.digiland.co.ke) -> Landing page & marketing content only
2. App Portal (app.digiland.co.ke) -> Buyers & Sellers dashboards, marketplace, and escrow
3. Staff Portal (staff.digiland.co.ke) -> Agents, Lawyers, Surveyors, Land Officials only
4. Admin Portal (admin.digiland.co.ke) -> Admins / Superusers only

Any non-canonical, malformed, or spoofed hostnames (e.g. app.digiland.staff.co.ke)
are strictly rejected with HTTP 400 Bad Request.
"""

import os
import logging
from django.http import JsonResponse, HttpResponseRedirect, HttpResponseBadRequest, HttpResponseForbidden, Http404
from django.conf import settings

logger = logging.getLogger(__name__)

# Exact canonical hostname mappings (NO WILDCARDS, NO LOOSE PREFIX/SUFFIX MATCHING)
CANONICAL_HOST_PORTAL_MAP = {
    'admin.digiland.co.ke': 'admin',
    'staff.digiland.co.ke': 'staff',
    'app.digiland.co.ke': 'app',
    'digiland.co.ke': 'marketing',
    'www.digiland.co.ke': 'marketing',
}

# Partition definitions & role permissions
PORTAL_ROLE_MAP = {
    'app': {'Buyer', 'Seller'},
    'staff': {'Agent', 'Lawyer', 'Surveyor', 'Land_Official'},
    'admin': {'Admin'},
    'marketing': {'Buyer', 'Seller', 'Agent', 'Lawyer', 'Surveyor', 'Land_Official', 'Admin'},
}

PORTAL_URLS = {
    'app': 'https://app.digiland.co.ke',
    'staff': 'https://staff.digiland.co.ke',
    'admin': 'https://admin.digiland.co.ke',
    'marketing': 'https://www.digiland.co.ke',
}

APP_ONLY_PREFIXES = (
    '/buyer/',
    '/seller/',
    '/parcels/',
    '/transactions/',
    '/messages/',
    '/accounts/login/',
    '/accounts/signup/',
    '/accounts/register/',
    '/checkout/',
    '/joint-groups/',
)

STAFF_ONLY_PREFIXES = (
    '/staff-login/',
    '/staff/login/',
    '/staff/dashboard/',
    '/agent/job-board/',
    '/agent/tasks/',
    '/agent/approvals/',
    '/agent/commission/',
    '/agent/dashboard/',
    '/lawyer/',
    '/surveyor/',
    '/survey/',
    '/survey-assignments/',
)

ADMIN_ONLY_PREFIXES = (
    '/admin/',
    '/auth/admin-login/',
    '/admin/login/',
    '/admin/dashboard/',
    '/api/v1/admin/',
)

DEV_HOSTS = {'localhost', '127.0.0.1', 'testserver', '0.0.0.0'}


def resolve_request_partition(request) -> str:
    """Resolve the partition string strictly from the validated canonical hostname or path."""
    host = request.get_host().split(':')[0].lower().strip()

    if host in CANONICAL_HOST_PORTAL_MAP:
        return CANONICAL_HOST_PORTAL_MAP[host]

    path = request.path

    # In local development or Vercel preview environments, derive strictly from unambiguous path prefixes
    is_local = (
        host in DEV_HOSTS
        or host.startswith('192.168.')
        or host.startswith('10.')
        or host.startswith('172.')
        or getattr(settings, 'DEBUG', False)
    )
    is_vercel = host.endswith('.vercel.app') or bool(os.environ.get('VERCEL'))

    if is_local or is_vercel:
        if any(path.startswith(prefix) for prefix in ADMIN_ONLY_PREFIXES):
            return 'admin'
        elif any(path.startswith(prefix) for prefix in STAFF_ONLY_PREFIXES):
            return 'staff'
        elif any(path.startswith(prefix) for prefix in APP_ONLY_PREFIXES):
            return 'app'
        return 'marketing'

    return 'invalid'


class PartitionIsolationMiddleware:
    """Middleware enforcing strict host validation, subdomain boundary defense, and role isolation."""

    EXEMPT_PATH_PREFIXES = (
        '/static/',
        '/media/',
        '/api/',
        '/health/',
        '/favicon.ico',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        host = request.get_host().split(':')[0].lower().strip()

        # Allow exempt static, media, health check endpoints
        if any(path.startswith(prefix) for prefix in self.EXEMPT_PATH_PREFIXES):
            return self.get_response(request)

        is_local = (
            host in DEV_HOSTS
            or host.startswith('192.168.')
            or host.startswith('10.')
            or host.startswith('172.')
            or getattr(settings, 'DEBUG', False)
        )
        is_vercel = host.endswith('.vercel.app')

        # ── 1. Strict Host Validation: Reject spoofed / malformed hostnames ──
        if not is_local and not is_vercel:
            if host not in CANONICAL_HOST_PORTAL_MAP:
                logger.warning(
                    f"[SECURITY EVENT] Blocked request with non-canonical / spoofed Host header: '{host}' on path '{path}'"
                )
                return HttpResponseBadRequest(
                    """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>400 Bad Request - Digiland Security</title></head>
<body style="font-family:sans-serif;padding:3rem;text-align:center;background:#0f172a;color:#f8fafc;">
  <h1>400 Bad Request</h1>
  <p>The host header provided is not a recognized canonical Digiland portal domain.</p>
  <p style="color:#94a3b8;font-size:0.9rem;">Access via unverified or intermediary subdomains is strictly forbidden.</p>
</body>
</html>""",
                    content_type="text/html",
                )

        portal = resolve_request_partition(request)
        if portal == 'invalid':
            return HttpResponseBadRequest("Invalid request partition.")

        request.digiland_portal = portal

        # ── 2. Production Domain Boundary Enforcement ──
        if not is_local and not is_vercel:
            query_string = request.META.get('QUERY_STRING', '')
            qs_suffix = f"?{query_string}" if query_string else ""

            # Attempting to access STAFF-ONLY endpoints from APP or MARKETING portal
            if portal in ('marketing', 'app') and any(path.startswith(prefix) for prefix in STAFF_ONLY_PREFIXES):
                logger.warning(
                    f"[SECURITY NOTICE] Sensitive staff path '{path}' requested on '{portal}' domain ({host}). Enforcing redirect to canonical staff portal."
                )
                return HttpResponseRedirect(f"{PORTAL_URLS['staff']}/staff/login/{qs_suffix}")

            # Attempting to access ADMIN-ONLY endpoints from APP, MARKETING, or STAFF portal
            if portal != 'admin' and any(path.startswith(prefix) for prefix in ADMIN_ONLY_PREFIXES):
                logger.warning(
                    f"[SECURITY NOTICE] Admin path '{path}' requested on non-admin portal '{portal}' ({host}). Access strictly denied."
                )
                return HttpResponseForbidden("<h1>403 Forbidden</h1><p>Administrative interfaces are only accessible via the dedicated admin portal.</p>")

            # Attempting to access BUYER/SELLER APP endpoints from MARKETING portal
            if portal == 'marketing' and any(path.startswith(prefix) for prefix in APP_ONLY_PREFIXES):
                return HttpResponseRedirect(f"{PORTAL_URLS['app']}{path}{qs_suffix}")

            # Marketing-First Access Gate on app.digiland.co.ke
            if portal == 'app':
                user = getattr(request, 'user', None)
                if not (user and user.is_authenticated):
                    is_auth_route = path.startswith('/accounts/') or path.startswith('/onboarding/') or path.startswith('/auth/')
                    referer = request.META.get('HTTP_REFERER', '')
                    has_marketing_transit = (
                        'digiland.co.ke' in referer
                        or request.GET.get('src') == 'marketing'
                        or request.COOKIES.get('digiland_marketing_passed') == '1'
                    )
                    if path == '/' or (not is_auth_route and not has_marketing_transit):
                        return HttpResponseRedirect(f"{PORTAL_URLS['marketing']}/")

        # ── 3. Authenticated Role-to-Portal Compatibility Enforcement ──
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            user_role = getattr(user, 'role', '') or ('Admin' if user.is_superuser else '')
            allowed_roles = PORTAL_ROLE_MAP.get(portal, set())

            if portal == 'admin':
                is_allowed = user_role == 'Admin' or user.is_superuser
            elif portal in ('app', 'staff'):
                is_allowed = user_role in allowed_roles
            else:
                is_allowed = True

            if not is_allowed:
                correct_portal = (
                    'staff' if user_role in {'Agent', 'Lawyer', 'Surveyor', 'Land_Official'}
                    else ('admin' if (user_role == 'Admin' or user.is_superuser) else 'app')
                )
                target_base = PORTAL_URLS.get(correct_portal, PORTAL_URLS['app'])

                target_path = path
                if path in ('/admin/dashboard/', '/staff/dashboard/', '/agent/dashboard/', '/surveyor/dashboard/'):
                    if correct_portal == 'admin':
                        target_path = '/admin/dashboard/'
                    elif correct_portal == 'staff':
                        target_path = '/staff/dashboard/'
                    else:
                        target_path = '/dashboard/'

                logger.warning(
                    f"[Partition Boundary Enforcement] User {user.email} ({user_role}) on '{portal}' portal redirected to '{correct_portal}' at {target_path}"
                )

                if request.path.startswith('/api/'):
                    return JsonResponse(
                        {
                            'detail': f"Cross-partition access blocked: Role '{user_role}' is not authorized to access the '{portal}' portal.",
                            'error_code': 'PARTITION_ACCESS_DENIED',
                            'user_role': user_role,
                            'current_portal': portal,
                            'required_portal': correct_portal,
                            'target_url': f"{target_base}{target_path}",
                        },
                        status=403,
                    )

                if not is_local and not is_vercel:
                    query_string = request.META.get('QUERY_STRING', '')
                    qs_suffix = f"?{query_string}" if query_string else ""
                    return HttpResponseRedirect(f"{target_base}{target_path}{qs_suffix}")

        response = self.get_response(request)

        # Set transit cookie on marketing visits
        if portal == 'marketing' and not is_local:
            try:
                response.set_cookie(
                    'digiland_marketing_passed',
                    '1',
                    max_age=86400 * 30,
                    domain='.digiland.co.ke',
                    path='/',
                    samesite='Lax',
                    secure=True,
                )
            except Exception:
                pass

        return response
