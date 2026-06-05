"""
Tenant-aware query manager.

Automatically filters querysets by the current tenant context set via
TenantMiddleware.  Use `unscoped()` to bypass tenant filtering for
admin/superuser access.
"""
from django.db import models


class TenantManager(models.Manager):
    """
    Custom manager that auto-filters by tenant_id when a tenant context
    is active on the current DB connection.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        tenant_id = self._get_current_tenant_id()
        if tenant_id is not None:
            return qs.filter(tenant_id=tenant_id)
        return qs

    def unscoped(self):
        """Return the unfiltered queryset (bypasses tenant isolation).

        Use sparingly — only for admin dashboards, superuser operations,
        and cross-tenant reports.
        """
        return super().get_queryset()

    def for_tenant(self, tenant_id):
        """Explicitly filter by a specific tenant_id."""
        return super().get_queryset().filter(tenant_id=tenant_id)

    @staticmethod
    def _get_current_tenant_id():
        """Read the current tenant ID from PostgreSQL session state."""
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_tenant', true)")
            value = cursor.fetchone()[0]
            if value and value != '':
                from uuid import UUID
                try:
                    return str(UUID(value))
                except ValueError:
                    return value
        return None
