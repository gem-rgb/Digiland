"""Partition Isolation Middleware for Digiland
===================================================

Enforces strict domain/subdomain partition isolation across the 4 frontends:
1. Marketing (digiland.co.ke / www.digiland.co.ke)
2. App Portal (app.digiland.co.ke) -> Buyers & Sellers only
3. Staff Portal (staff.digiland.co.ke) -> Agents, Lawyers, Land Officials only
4. Admin Portal (admin.digiland.co.ke) -> Admins / Superusers only
"""

import logging
from django.http import JsonResponse
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

def resolve_request_partition(request) -> str:
    """Resolve the partition string for an incoming request.
    
    Order of precedence:
    1. Header 'X-Digiland-Portal'
    2. Query param 'portal'
    3. HTTP_HOST header matching subdomains
    """
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
    """Middleware enforcing role-based subdomain partition safety."""

    EXEMPT_PATH_PREFIXES = (
        '/static/',
        '/media/',
        '/admin/login/',
        '/api/v1/auth/login/',
        '/api/v1/auth/staff-login/',
        '/api/v1/auth/register/',
        '/api/v1/health/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Allow exempt static and authentication setup endpoints
        if any(path.startswith(prefix) for prefix in self.EXEMPT_PATH_PREFIXES):
            return self.get_response(request)

        portal = resolve_request_partition(request)
        request.digiland_portal = portal

        # If user is authenticated, check role compatibility with requested portal
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            user_role = getattr(user, 'role', '') or ('Admin' if user.is_superuser or user.is_staff else '')
            allowed_roles = PORTAL_ROLE_MAP.get(portal, set())

            # For admin portal, allow if user.is_staff or user.is_superuser
            if portal == 'admin':
                is_allowed = user_role == 'Admin' or user.is_staff or user.is_superuser
            elif portal in ('app', 'staff'):
                is_allowed = user_role in allowed_roles
            else:
                is_allowed = True  # Marketing portal allows public/all

            if not is_allowed:
                correct_portal = 'staff' if user_role in {'Agent', 'Lawyer', 'Land_Official'} else ('admin' if (user_role == 'Admin' or user.is_staff) else 'app')
                target_url = PORTAL_URLS.get(correct_portal, PORTAL_URLS['app'])
                
                logger.warning(
                    f"[Partition Block] User {user.email} (role: {user_role}) attempted to access {portal} portal. Required portal: {correct_portal}"
                )

                if request.path.startswith('/api/'):
                    return JsonResponse(
                        {
                            'detail': f"Cross-partition access blocked: Account role '{user_role}' is not authorized to access the '{portal}' portal.",
                            'error_code': 'PARTITION_ACCESS_DENIED',
                            'user_role': user_role,
                            'current_portal': portal,
                            'required_portal': correct_portal,
                            'target_url': target_url,
                        },
                        status=403,
                    )

        return self.get_response(request)
