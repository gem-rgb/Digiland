"""
Service Registry for the External Services Layer (ESL).

The :class:`ServiceRegistry` is the central point where providers are
registered, resolved, and accessed.  It supports:

* **Lazy initialization** — provider instances are created on first access,
  not at registration time.
* **Default providers** — each service type has a default provider, so
  callers can omit the ``provider_name`` argument.
* **Fallback chains** — if a provider is unhealthy, the registry can
  automatically fall back to the next provider in the chain.
* **Thread safety** — all mutations are protected by a
  :class:`threading.RLock`.
* **Health checking** — :meth:`health_check` can probe one service type or
  all registered providers.
* **Auto-registration** — :func:`auto_register_providers` reads
  ``settings.EXTERNAL_SERVICES`` and registers everything declared there.

Typical usage::

    from external_services import get_service

    payment = get_service("payment")          # uses default provider
    result = payment.initialize_payment(...)

    stripe = get_service("payment", "stripe") # explicit provider
    result = stripe.initialize_payment(...)
"""

from __future__ import annotations

import importlib
import logging
import threading
from typing import Any, Dict, List, Optional, Sequence, Type

from django.conf import settings

from .exceptions import (
    CircuitBreakerOpenError,
    ConfigurationError,
    ExternalServiceError,
    ProviderUnavailableError,
)

logger = logging.getLogger("external_services.registry")

# Type alias for provider classes
ProviderClass = Type[Any]


class _ProviderEntry:
    """Internal bookkeeping for a single registered provider.

    Attributes:
        provider_class: The class to instantiate (lazy).
        config: Configuration dict passed to the constructor.
        instance: The cached provider instance (``None`` until first access).
        is_default: Whether this is the default provider for its service type.
        priority: Lower values are tried first in fallback chains.
    """

    __slots__ = ("provider_class", "config", "instance", "is_default", "priority")

    def __init__(
        self,
        provider_class: ProviderClass,
        config: Optional[Dict[str, Any]] = None,
        is_default: bool = False,
        priority: int = 0,
    ) -> None:
        self.provider_class = provider_class
        self.config = config or {}
        self.instance: Optional[Any] = None
        self.is_default = is_default
        self.priority = priority

    @property
    def is_initialized(self) -> bool:
        return self.instance is not None

    def get_instance(self) -> Any:
        """Return the provider instance, creating it on first access (lazy init).

        Returns:
            The initialised provider instance.

        Raises:
            ConfigurationError: If the provider cannot be instantiated.
        """
        if self.instance is None:
            try:
                self.instance = self.provider_class(**self.config)
            except Exception as exc:
                provider_name = getattr(self.provider_class, "__name__", str(self.provider_class))
                raise ConfigurationError(
                    provider_name=provider_name,
                    message=f"Failed to initialise provider '{provider_name}': {exc}",
                    cause=exc,
                ) from exc
        return self.instance


class ServiceRegistry:
    """Thread-safe registry of external service providers.

    The registry maps ``(service_type, provider_name)`` pairs to provider
    classes.  Each service type (e.g. ``"payment"``, ``"email"``) can have
    multiple providers (e.g. ``"paystack"``, ``"stripe"``), one of which is
    designated as the **default**.

    A **fallback chain** is an ordered list of provider names for a given
    service type.  When :meth:`get_service` is called without a specific
    provider, the chain is walked until a healthy provider is found.
    """

    def __init__(self) -> None:
        self._providers: Dict[str, Dict[str, _ProviderEntry]] = {}
        self._defaults: Dict[str, str] = {}
        self._fallback_chains: Dict[str, List[str]] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        service_type: str,
        provider_name: str,
        provider_class: ProviderClass,
        config: Optional[Dict[str, Any]] = None,
        is_default: bool = False,
        priority: int = 0,
    ) -> None:
        """Register a provider class for a service type.

        Args:
            service_type: Category identifier (e.g. ``"payment"``).
            provider_name: Specific provider identifier (e.g. ``"paystack"``).
            provider_class: The class that implements the provider interface.
            config: Configuration dict forwarded to the constructor.
            is_default: Mark this provider as the default for the service type.
            priority: Ordering hint for fallback chains (lower = tried first).

        Raises:
            ValueError: If ``service_type`` or ``provider_name`` is empty.
        """
        if not service_type or not isinstance(service_type, str):
            raise ValueError("service_type must be a non-empty string")
        if not provider_name or not isinstance(provider_name, str):
            raise ValueError("provider_name must be a non-empty string")

        entry = _ProviderEntry(
            provider_class=provider_class,
            config=config,
            is_default=is_default,
            priority=priority,
        )

        with self._lock:
            if service_type not in self._providers:
                self._providers[service_type] = {}

            self._providers[service_type][provider_name] = entry

            # Auto-set default if this is the first provider for the type
            if is_default or service_type not in self._defaults:
                self._defaults[service_type] = provider_name

            # Rebuild the fallback chain sorted by priority
            self._rebuild_fallback_chain(service_type)

        logger.info(
            "Registered provider %s/%s (default=%s, priority=%d)",
            service_type,
            provider_name,
            is_default,
            priority,
        )

    def unregister(self, service_type: str, provider_name: str) -> None:
        """Remove a previously registered provider.

        If the removed provider was the default for the service type, the
        first remaining provider (sorted by priority) becomes the new default.

        Args:
            service_type: Category identifier.
            provider_name: Provider to remove.

        Raises:
            ExternalServiceError: If the provider is not registered.
        """
        with self._lock:
            if service_type not in self._providers or provider_name not in self._providers[service_type]:
                raise ExternalServiceError(
                    message=f"Provider '{provider_name}' is not registered for service '{service_type}'",
                    service_type=service_type,
                    provider_name=provider_name,
                )

            del self._providers[service_type][provider_name]

            # Clean up empty service types
            if not self._providers[service_type]:
                del self._providers[service_type]
                self._defaults.pop(service_type, None)
                self._fallback_chains.pop(service_type, None)
                return

            # Reassign default if the removed provider was the default
            if self._defaults.get(service_type) == provider_name:
                remaining = self._providers[service_type]
                sorted_providers = sorted(
                    remaining.items(), key=lambda item: item[1].priority
                )
                self._defaults[service_type] = sorted_providers[0][0]

            self._rebuild_fallback_chain(service_type)

        logger.info("Unregistered provider %s/%s", service_type, provider_name)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_service(
        self,
        service_type: str,
        provider_name: Optional[str] = None,
        use_fallback: bool = True,
    ) -> Any:
        """Get a provider instance for the given service type.

        When ``provider_name`` is ``None`` the default provider is returned.
        If ``use_fallback`` is ``True`` and the resolved provider is
        unhealthy (circuit breaker open), the fallback chain is walked.

        Args:
            service_type: Category identifier (e.g. ``"payment"``).
            provider_name: Optional specific provider (e.g. ``"stripe"``).
            use_fallback: Walk the fallback chain if the primary is unhealthy.

        Returns:
            An initialised provider instance.

        Raises:
            ExternalServiceError: If the service type is not registered.
            ProviderUnavailableError: If no healthy provider is found.
        """
        with self._lock:
            if service_type not in self._providers:
                raise ExternalServiceError(
                    message=f"No providers registered for service type '{service_type}'",
                    service_type=service_type,
                )

            # Resolve the target provider name
            target = provider_name or self._defaults.get(service_type)
            if target is None:
                raise ExternalServiceError(
                    message=f"No default provider set for service type '{service_type}'",
                    service_type=service_type,
                )

            if target not in self._providers[service_type]:
                available = list(self._providers[service_type].keys())
                raise ExternalServiceError(
                    message=(
                        f"Provider '{target}' not registered for service '{service_type}'. "
                        f"Available: {available}"
                    ),
                    service_type=service_type,
                    provider_name=target,
                )

            # Try the primary provider first
            entry = self._providers[service_type][target]
            try:
                instance = entry.get_instance()
                if self._is_healthy(instance):
                    return instance
            except ConfigurationError:
                if not use_fallback:
                    raise

            if not use_fallback:
                # Re-raise a generic unavailable error for the non-fallback case
                raise ProviderUnavailableError(
                    provider_name=target,
                    service_type=service_type,
                )

            # Walk the fallback chain
            chain = self._fallback_chains.get(service_type, [target])
            for fallback_name in chain:
                if fallback_name == target:
                    continue  # already tried
                fallback_entry = self._providers[service_type].get(fallback_name)
                if fallback_entry is None:
                    continue
                try:
                    fallback_instance = fallback_entry.get_instance()
                    if self._is_healthy(fallback_instance):
                        logger.warning(
                            "Falling back from %s to %s for service %s",
                            target,
                            fallback_name,
                            service_type,
                        )
                        return fallback_instance
                except ConfigurationError:
                    continue

            # All fallbacks exhausted
            raise ProviderUnavailableError(
                provider_name=target,
                service_type=service_type,
                message=(
                    f"All providers for service '{service_type}' are unhealthy. "
                    f"Attempted fallback chain: {chain}"
                ),
            )

    def get_provider(self, service_type: str, provider_name: str) -> Any:
        """Get a specific provider instance (no fallback logic).

        This is a convenience shortcut for :meth:`get_service` with
        ``use_fallback=False``.

        Args:
            service_type: Category identifier.
            provider_name: Specific provider identifier.

        Returns:
            The provider instance.

        Raises:
            ExternalServiceError: If the provider is not registered.
        """
        return self.get_service(service_type, provider_name, use_fallback=False)

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_services(self) -> List[str]:
        """Return a sorted list of all registered service types.

        Returns:
            E.g. ``["ai", "email", "payment", "sms"]``
        """
        with self._lock:
            return sorted(self._providers.keys())

    def list_providers(self, service_type: str) -> List[Dict[str, Any]]:
        """Return metadata about all providers for a service type.

        Args:
            service_type: Category identifier.

        Returns:
            A list of dicts, each containing ``name``, ``class``,
            ``is_default``, ``priority``, and ``is_initialized``.

        Raises:
            ExternalServiceError: If the service type is not registered.
        """
        with self._lock:
            if service_type not in self._providers:
                raise ExternalServiceError(
                    message=f"No providers registered for service type '{service_type}'",
                    service_type=service_type,
                )

            default_name = self._defaults.get(service_type)
            result: List[Dict[str, Any]] = []
            for name, entry in sorted(
                self._providers[service_type].items(), key=lambda item: item[1].priority
            ):
                result.append({
                    "name": name,
                    "class": entry.provider_class.__name__,
                    "is_default": name == default_name,
                    "priority": entry.priority,
                    "is_initialized": entry.is_initialized,
                })
            return result

    # ------------------------------------------------------------------
    # Defaults & Fallbacks
    # ------------------------------------------------------------------

    def set_default(self, service_type: str, provider_name: str) -> None:
        """Set the default provider for a service type.

        Args:
            service_type: Category identifier.
            provider_name: Provider to mark as default.

        Raises:
            ExternalServiceError: If the provider is not registered.
        """
        with self._lock:
            if service_type not in self._providers or provider_name not in self._providers[service_type]:
                raise ExternalServiceError(
                    message=f"Provider '{provider_name}' is not registered for service '{service_type}'",
                    service_type=service_type,
                    provider_name=provider_name,
                )

            # Clear old default flag
            old_default = self._defaults.get(service_type)
            if old_default and old_default in self._providers[service_type]:
                self._providers[service_type][old_default].is_default = False

            self._providers[service_type][provider_name].is_default = True
            self._defaults[service_type] = provider_name

            self._rebuild_fallback_chain(service_type)

        logger.info("Default provider for %s set to %s", service_type, provider_name)

    def set_fallback_chain(self, service_type: str, chain: Sequence[str]) -> None:
        """Manually set the fallback chain for a service type.

        Args:
            service_type: Category identifier.
            chain: Ordered list of provider names to try on failure.

        Raises:
            ExternalServiceError: If any provider in the chain is not registered.
        """
        with self._lock:
            if service_type not in self._providers:
                raise ExternalServiceError(
                    message=f"No providers registered for service type '{service_type}'",
                    service_type=service_type,
                )

            registered = set(self._providers[service_type].keys())
            unknown = [p for p in chain if p not in registered]
            if unknown:
                raise ExternalServiceError(
                    message=(
                        f"Unknown providers in fallback chain for '{service_type}': {unknown}. "
                        f"Registered: {sorted(registered)}"
                    ),
                    service_type=service_type,
                )

            self._fallback_chains[service_type] = list(chain)

        logger.info("Fallback chain for %s set to %s", service_type, chain)

    # ------------------------------------------------------------------
    # Health Check
    # ------------------------------------------------------------------

    def health_check(self, service_type: Optional[str] = None) -> Dict[str, Any]:
        """Check the health of registered providers.

        Args:
            service_type: If provided, check only this service type.
                If ``None``, check all registered providers.

        Returns:
            A dict mapping service types to provider health results.
            Each provider entry contains ``status``, ``response_time_ms``,
            and ``details``.
        """
        results: Dict[str, Any] = {}

        with self._lock:
            types_to_check = (
                {service_type: self._providers[service_type]}
                if service_type
                else self._providers
            )

            for stype, providers in types_to_check.items():
                if stype not in self._providers:
                    results[stype] = {"error": f"Service type '{stype}' not registered"}
                    continue

                stype_results: Dict[str, Any] = {}
                for pname, entry in providers.items():
                    try:
                        instance = entry.get_instance()
                        hc = instance.health_check()
                        stype_results[pname] = {
                            "status": hc.status,
                            "response_time_ms": hc.response_time_ms,
                            "details": hc.details,
                            "checked_at": hc.checked_at.isoformat() if hc.checked_at else None,
                        }
                    except Exception as exc:
                        stype_results[pname] = {
                            "status": "unhealthy",
                            "error": str(exc),
                        }

                results[stype] = stype_results

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rebuild_fallback_chain(self, service_type: str) -> None:
        """Rebuild the fallback chain for *service_type* sorted by priority.

        Must be called while holding ``self._lock``.
        """
        providers = self._providers.get(service_type, {})
        sorted_names = [
            name
            for name, _entry in sorted(providers.items(), key=lambda item: item[1].priority)
        ]
        self._fallback_chains[service_type] = sorted_names

    @staticmethod
    def _is_healthy(instance: Any) -> bool:
        """Quick health probe — does not make a network call.

        Checks for a ``circuit_breaker_open`` attribute or property first.
        Falls back to calling ``instance.health_check()`` only when the
        attribute is absent.

        Returns:
            ``True`` if the instance appears healthy, ``False`` otherwise.
        """
        # Fast path: check circuit breaker state without a network call
        cb_open = getattr(instance, "circuit_breaker_open", None)
        if cb_open is True:
            return False

        # If the provider exposes an is_healthy property, trust it
        is_healthy = getattr(instance, "is_healthy", None)
        if isinstance(is_healthy, bool):
            return is_healthy

        # Default to healthy — the full health_check is an explicit operation
        return True

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        with self._lock:
            counts = {st: len(provs) for st, provs in self._providers.items()}
        return f"ServiceRegistry(providers={counts})"


# ======================================================================
# Module-level helpers
# ======================================================================

# Global singleton — also referenced by external_services.__init__
_registry_instance: Optional[ServiceRegistry] = None
_registry_lock = threading.Lock()


def get_registry() -> ServiceRegistry:
    """Return the global :class:`ServiceRegistry` singleton.

    This function is thread-safe and lazily creates the registry on first
    call.
    """
    global _registry_instance
    if _registry_instance is None:
        with _registry_lock:
            if _registry_instance is None:
                _registry_instance = ServiceRegistry()
    return _registry_instance


def auto_register_providers() -> None:
    """Discover and register all providers declared in Django settings.

    The expected settings format is::

        EXTERNAL_SERVICES = {
            "payment": {
                "default": "paystack",
                "providers": {
                    "paystack": {
                        "class": "external_services.providers.payment.PaystackProvider",
                        "config": {"api_key": "..."},
                        "priority": 1,
                    },
                    "stripe": {
                        "class": "external_services.providers.payment.StripeProvider",
                        "config": {"api_key": "..."},
                        "priority": 2,
                    },
                },
            },
        }

    Each provider entry must have a ``class`` key with the fully-qualified
    Python path to the provider class.  ``config`` and ``priority`` are
    optional.
    """
    registry = get_registry()
    services_config = getattr(settings, "EXTERNAL_SERVICES", {})

    if not services_config:
        logger.debug("No EXTERNAL_SERVICES configuration found in Django settings.")
        return

    for service_type, service_config in services_config.items():
        if not isinstance(service_config, dict):
            logger.warning(
                "Skipping invalid EXTERNAL_SERVICES entry for '%s' — expected dict, got %s",
                service_type,
                type(service_config).__name__,
            )
            continue

        default_provider = service_config.get("default")
        providers_config = service_config.get("providers", {})

        for provider_name, provider_config in providers_config.items():
            class_path = provider_config.get("class")
            if not class_path:
                logger.warning(
                    "Skipping provider %s/%s — missing 'class' key",
                    service_type,
                    provider_name,
                )
                continue

            try:
                provider_class = _import_class(class_path)
            except (ImportError, AttributeError) as exc:
                logger.error(
                    "Failed to import provider class '%s' for %s/%s: %s",
                    class_path,
                    service_type,
                    provider_name,
                    exc,
                )
                continue

            config = provider_config.get("config", {})
            priority = provider_config.get("priority", 0)
            is_default = provider_name == default_provider

            registry.register(
                service_type=service_type,
                provider_name=provider_name,
                provider_class=provider_class,
                config=config,
                is_default=is_default,
                priority=priority,
            )

    logger.info(
        "Auto-registered %d service types from settings",
        len(services_config),
    )


def _import_class(dotted_path: str) -> ProviderClass:
    """Import a class from a dotted module path.

    Args:
        dotted_path: e.g. ``"external_services.providers.payment.PaystackProvider"``

    Returns:
        The imported class.

    Raises:
        ImportError: If the module cannot be imported.
        AttributeError: If the class is not found in the module.
    """
    module_path, _, class_name = dotted_path.rpartition(".")
    module = importlib.import_module(module_path)
    return getattr(module, class_name)
