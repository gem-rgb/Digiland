"""
Django application configuration for the External Services Layer (ESL).

This AppConfig handles automatic provider discovery and registration when
the Django application starts up.  It imports the ``providers`` sub-package
so that every provider module is evaluated (which triggers their
``@register_provider`` decorator), and then calls
:meth:`~external_services.registry.auto_register_providers` to wire up any
providers declared in ``settings.EXTERNAL_SERVICES``.
"""

from django.apps import AppConfig


class ExternalServicesConfig(AppConfig):
    """Django app configuration for the External Services Layer.

    Attributes:
        default_auto_field: Use BigAutoField for any auto-generated PK fields.
        name: Python import path of the app.
        verbose_name: Human-readable name shown in the Django admin.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "external_services"
    verbose_name = "External Services Layer"

    def ready(self) -> None:
        """Execute provider auto-discovery once the app registry is fully populated.

        The import of :mod:`external_services.providers` is performed inside
        ``ready()`` so that Django model references inside provider modules
        resolve correctly.  The ``noqa`` suppresses the "unused import" warning
        because the side-effect of importing the package is intentional.
        """
        from . import providers  # noqa: F401
        from .registry import auto_register_providers

        auto_register_providers()
