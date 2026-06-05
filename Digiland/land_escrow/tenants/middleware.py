"""
Tenant resolution middleware.

On every request this middleware:

1. Reads the tenant_id from the JWT token claims, the ``X-Tenant-ID``
   header, or the user's default organization membership.
2. Sets ``request.tenant`` to the resolved Organization object.
3. Executes ``SELECT set_config('app.current_tenant', ..., false)`` so
   that PostgreSQL Row-Level Security policies can compare against the
   session variable directly — no application-level filtering needed.
4. Clears the session variable on the way out to prevent leakage.
"""
import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponseForbidden

logger = logging.getLogger(__name__)


class TenantMiddleware(MiddlewareMixin):
    """Resolve the current tenant and set the PostgreSQL session variable."""

    def process_request(self, request):
        request.tenant = None
        tenant_id = None

        # 1. Try JWT token claims
        if hasattr(request, 'auth') and request.auth:
            tenant_id = request.auth.get('tenant_id')

        # 2. Try X-Tenant-ID header
        if not tenant_id:
            tenant_id = request.META.get('HTTP_X_TENANT_ID')

        # 3. Try user's default organization
        if not tenant_id and hasattr(request, 'user') and request.user.is_authenticated:
            try:
                from tenants.models import OrganizationMembership
                membership = OrganizationMembership.objects.filter(
                    user=request.user, is_default=True
                ).select_related('organization').first()
                if membership:
                    tenant_id = str(membership.organization_id)
                    request.tenant = membership.organization
            except Exception:
                pass

        # 4. Resolve Organization object if not yet resolved
        if tenant_id and not request.tenant:
            try:
                from tenants.models import Organization
                request.tenant = Organization.objects.get(id=tenant_id, is_active=True)
            except Organization.DoesNotExist:
                logger.warning("Tenant not found or inactive: %s", tenant_id)
                return HttpResponseForbidden("Invalid tenant")

        # 5. Set PostgreSQL session variable for RLS
        if tenant_id:
            self._set_tenant_session_var(tenant_id)

    def process_response(self, request, response):
        """Clear tenant context on response to prevent leakage."""
        self._clear_tenant_session_var()
        return response

    def process_exception(self, request, exception):
        """Ensure tenant context is cleared even on exceptions."""
        self._clear_tenant_session_var()
        return None

    @staticmethod
    def _set_tenant_session_var(tenant_id):
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.current_tenant', %s, false)", [str(tenant_id)])

    @staticmethod
    def _clear_tenant_session_var():
        from django.db import connection
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.current_tenant', '', false)")
        except Exception:
            pass  # Connection may already be closed
