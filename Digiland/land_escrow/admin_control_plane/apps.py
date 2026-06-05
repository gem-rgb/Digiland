"""Django app configuration for the admin_control_plane module."""

from django.apps import AppConfig


class AdminControlPlaneConfig(AppConfig):
    """App config for admin_control_plane.

    Registers signals on ready to ensure auto-termination of sessions,
    audit trail integrity, suspicious-behaviour alerting, and dual-approval
    expiry all function without manual wiring.
    """

    default_auto_field = 'django.db.models.UUIDField'
    name = 'admin_control_plane'
    verbose_name = 'Admin Control Plane'

    def ready(self):
        """Import signals when the app is fully loaded."""
        import admin_control_plane.signals  # noqa: F401
