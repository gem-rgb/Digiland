"""Partition Isolation Middleware for Digiland
===================================================

Enforces strict domain/subdomain partition isolation across the 4 frontends:
1. Marketing (digiland.co.ke / www.digiland.co.ke) -> Landing page & marketing content only
2. App Portal (app.digiland.co.ke) -> Buyers & Sellers dashboards, marketplace, and escrow
3. Staff Portal (staff.digiland.co.ke) -> Agents, Lawyers, Land Officials only
4. Admin Portal (admin.digiland.co.ke) -> Admins / Superusers only
"""

import logging
from django.http import JsonResponse, HttpResponseRedirect
from django.conf import settings

logger = logging.getLogger(__name__)

# Partition definitions & role permissions
PORTAL_ROLE_MAP = {
    'app': {'Buyer', 'Seller'},
    'staff': {'Agent', 'Lawyer', 'Land_Official'},
    'admin': {'Admin'},
    'marketing': {'Buyer', 'Seller', 'Agent', 'Lawyer', 'Land_Official', 'Admin'},
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
    '/agent/job-board/',
    '/agent/tasks/',
    '/agent/approvals/',
    '/agent/commission/',
    '/lawyer/',
)

ADMIN_ONLY_PREFIXES = (
    '/admin/',
    '/api/v1/admin/',
)

def resolve_request_partition(request) -> str:
    """Resolve the partition string for an incoming request."""
    header_portal = request.META.get('HTTP_X_DIGILAND_PORTAL')
    if header_portal and header_portal.lower() in PORTAL_ROLE_MAP:
        return header_portal.lower()

    query_portal = request.GET.get('portal')
    if query_portal and query_portal.lower() in PORTAL_ROLE_MAP:
        return query_portal.lower()

    host = request.get_host().split(':')[0].lower()
    if host.startswith('admin.'):
        return 'admin'
    elif host.startswith('staff.'):
        return 'staff'
    elif host.startswith('app.'):
        return 'app'
    
    return 'marketing'

class PartitionIsolationMiddleware:
    """Middleware enforcing strict role-based subdomain partition safety and domain redirection."""

    EXEMPT_PATH_PREFIXES = (
        '/static/',
        '/media/',
        '/api/',
        '/admin/api/',
        '/health/',
        '/favicon.ico',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Allow exempt static and API endpoints
        if any(path.startswith(prefix) for prefix in self.EXEMPT_PATH_PREFIXES):
            return self.get_response(request)

        portal = resolve_request_partition(request)
        request.digiland_portal = portal
        host = request.get_host().split(':')[0].lower()
        is_local = host in {'localhost', '127.0.0.1'}

        # In production, redirect routes hitting the wrong portal domain
        if not is_local:
            query_string = request.META.get('QUERY_STRING', '')
            qs_suffix = f"?{query_string}" if query_string else ""

            if portal == 'marketing':
                if any(path.startswith(prefix) for prefix in APP_ONLY_PREFIXES):
                    return HttpResponseRedirect(f"{PORTAL_URLS['app']}{path}{qs_suffix}")
                elif any(path.startswith(prefix) for prefix in STAFF_ONLY_PREFIXES):
                    return HttpResponseRedirect(f"{PORTAL_URLS['staff']}{path}{qs_suffix}")
                elif any(path.startswith(prefix) for prefix in ADMIN_ONLY_PREFIXES):
                    return HttpResponseRedirect(f"{PORTAL_URLS['admin']}{path}{qs_suffix}")

            elif portal == 'admin':
                if any(path.startswith(prefix) for prefix in STAFF_ONLY_PREFIXES):
                    return HttpResponseRedirect(f"{PORTAL_URLS['admin']}/admin/login/{qs_suffix}")
                user = getattr(request, 'user', None)
                if not (user and user.is_authenticated):
                    if not path.startswith('/admin/login') and not path.startswith('/auth/admin-login'):
                        return HttpResponseRedirect(f"{PORTAL_URLS['admin']}/admin/login/{qs_suffix}")

            elif portal == 'staff':
                if any(path.startswith(prefix) for prefix in ADMIN_ONLY_PREFIXES):
                    return HttpResponseRedirect(f"{PORTAL_URLS['admin']}{path}{qs_suffix}")
                user = getattr(request, 'user', None)
                if not (user and user.is_authenticated):
                    if not path.startswith('/staff/login'):
                        return HttpResponseRedirect(f"{PORTAL_URLS['staff']}/staff/login/{qs_suffix}")

            elif portal == 'app':
                if any(path.startswith(prefix) for prefix in STAFF_ONLY_PREFIXES):
                    return HttpResponseRedirect(f"{PORTAL_URLS['staff']}{path}{qs_suffix}")
                elif any(path.startswith(prefix) for prefix in ADMIN_ONLY_PREFIXES):
                    return HttpResponseRedirect(f"{PORTAL_URLS['admin']}{path}{qs_suffix}")

                # Marketing-First Access Gate: Direct unauthenticated visits to app.digiland.co.ke must pass through marketing
                user = getattr(request, 'user', None)
                if not (user and user.is_authenticated):
                    is_auth_route = path.startswith('/accounts/') or path.startswith('/onboarding/') or path.startswith('/auth/')
                    referer = request.META.get('HTTP_REFERER', '')
                    has_marketing_transit = (
                        'digiland.co.ke' in referer
                        or request.GET.get('src') == 'marketing'
                        or request.COOKIES.get('digiland_marketing_passed') == '1'
                    )

                    # Direct cold access to root / or deep app pages without session or marketing referrer
                    if path == '/' or (not is_auth_route and not has_marketing_transit):
                        return HttpResponseRedirect(f"{PORTAL_URLS['marketing']}/")

        # If user is authenticated, check role compatibility with requested portal
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            user_role = getattr(user, 'role', '') or ('Admin' if user.is_superuser or user.is_staff else '')
            allowed_roles = PORTAL_ROLE_MAP.get(portal, set())

            if portal == 'admin':
                is_allowed = user_role == 'Admin' or user.is_staff or user.is_superuser
            elif portal in ('app', 'staff'):
                is_allowed = user_role in allowed_roles
            else:
                is_allowed = True

            if not is_allowed:
                correct_portal = 'staff' if user_role in {'Agent', 'Lawyer', 'Land_Official'} else ('admin' if (user_role == 'Admin' or user.is_staff or user.is_superuser) else 'app')
                target_base = PORTAL_URLS.get(correct_portal, PORTAL_URLS['app'])
                
                logger.warning(
                    f"[Partition Redirect] User {user.email} (role: {user_role}) on {portal} portal redirected to {correct_portal}"
                )

                if request.path.startswith('/api/'):
                    return JsonResponse(
                        {
                            'detail': f"Cross-partition access blocked: Account role '{user_role}' is not authorized to access the '{portal}' portal.",
                            'error_code': 'PARTITION_ACCESS_DENIED',
                            'user_role': user_role,
                            'current_portal': portal,
                            'required_portal': correct_portal,
                            'target_url': f"{target_base}{path}",
                        },
                        status=403,
                    )
                
                if not is_local:
                    query_string = request.META.get('QUERY_STRING', '')
                    qs_suffix = f"?{query_string}" if query_string else ""
                    return HttpResponseRedirect(f"{target_base}{path}{qs_suffix}")

        response = self.get_response(request)

        # Set transit cookie when user visits marketing site to unlock app access
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
