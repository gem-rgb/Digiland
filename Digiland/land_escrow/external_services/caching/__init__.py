"""
Caching layer for external service responses.

Supports in-memory and distributed caching with TTL policies
tailored to different data types (exchange rates, geocode results,
provider health, etc.).

Usage::

    from external_services.caching import esl_cache

    # Cache a response
    esl_cache.set(
        service_type='payment',
        provider_name='paystack',
        operation='exchange_rate',
        data={'USD_KES': 153.45},
        data_type='exchange_rate',
    )

    # Retrieve a cached response
    rate = esl_cache.get('payment', 'paystack', 'exchange_rate')
    if rate:
        return rate

    # Invalidate a cache entry
    esl_cache.delete('payment', 'paystack', 'exchange_rate')
"""

import hashlib
import json
import logging
from typing import Optional, Dict, Any

from django.core.cache import cache, caches

logger = logging.getLogger('external_services.caching')


class CachePolicy:
    """TTL policies for different data types.

    Each data type has a recommended cache duration based on how
    frequently the underlying data changes:

    * ``provider_health`` — 30 seconds (must be fresh for circuit breakers)
    * ``exchange_rate`` — 5 minutes (rates change frequently)
    * ``geocode_result`` — 24 hours (addresses don't change)
    * ``user_profile`` — 30 minutes (infrequent updates)
    * ``search_results`` — 60 seconds (may change between requests)
    * ``static_data`` — 1 hour (reference data)
    * ``token_cache`` — ~58 minutes (token expiry < 1 hour)
    * ``provider_config`` — 5 minutes (configuration may be updated)
    """

    TTL_POLICIES: Dict[str, int] = {
        'provider_health': 30,
        'exchange_rate': 300,
        'geocode_result': 86400,
        'user_profile': 1800,
        'search_results': 60,
        'static_data': 3600,
        'token_cache': 3500,
        'provider_config': 300,
        'default': 300,
    }

    @classmethod
    def get_ttl(cls, data_type: str) -> int:
        """Get the TTL in seconds for a given data type.

        Args:
            data_type: The type of data being cached.

        Returns:
            TTL in seconds.  Defaults to 300 seconds (5 minutes).
        """
        return cls.TTL_POLICIES.get(data_type, cls.TTL_POLICIES['default'])

    @classmethod
    def set_custom_ttl(cls, data_type: str, ttl_seconds: int) -> None:
        """Override the default TTL for a data type.

        Args:
            data_type: The data type to configure.
            ttl_seconds: New TTL value in seconds.
        """
        cls.TTL_POLICIES[data_type] = ttl_seconds


class ExternalServicesCache:
    """Django-cache-backed caching layer for external service responses.

    Uses a namespaced key scheme to avoid collisions with other
    Django cache users::

        esl:<service_type>:<provider_name>:<operation>[:<param_hash>]

    Supports any Django cache backend (locmem, Redis, Memcached)
    configured in ``settings.CACHES``.
    """

    CACHE_PREFIX = 'esl:'

    def __init__(self, cache_name: str = 'default') -> None:
        """Initialize the cache layer.

        Args:
            cache_name: Name of the Django cache backend to use
                (must exist in ``settings.CACHES``).
        """
        try:
            self._cache = caches[cache_name] if cache_name else cache
        except Exception:
            logger.warning(
                "Cache backend '%s' not found, falling back to default",
                cache_name,
            )
            self._cache = cache

    def get(
        self,
        service_type: str,
        provider_name: str,
        operation: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """Retrieve a cached value.

        Args:
            service_type: Category of service.
            provider_name: Provider identifier.
            operation: Operation name.
            params: Optional parameters used to compute the cache key
                (included when the same operation may produce different
                results for different inputs).

        Returns:
            The cached value, or ``None`` if not found / expired.
        """
        key = self._make_key(service_type, provider_name, operation, params)
        value = self._cache.get(key)
        if value is not None:
            logger.debug(
                "Cache HIT: %s/%s/%s",
                service_type,
                provider_name,
                operation,
            )
        else:
            logger.debug(
                "Cache MISS: %s/%s/%s",
                service_type,
                provider_name,
                operation,
            )
        return value

    def set(
        self,
        service_type: str,
        provider_name: str,
        operation: str,
        data: Any,
        ttl: Optional[int] = None,
        data_type: str = 'default',
    ) -> None:
        """Store a value in the cache.

        Args:
            service_type: Category of service.
            provider_name: Provider identifier.
            operation: Operation name.
            data: The data to cache.
            ttl: Time-to-live in seconds.  If ``None``, the TTL is
                derived from the ``data_type`` via :class:`CachePolicy`.
            data_type: Data type for TTL policy lookup.
        """
        key = self._make_key(service_type, provider_name, operation)
        effective_ttl = ttl or CachePolicy.get_ttl(data_type)
        self._cache.set(key, data, effective_ttl)
        logger.debug(
            "Cache SET: %s/%s/%s (TTL=%ds)",
            service_type,
            provider_name,
            operation,
            effective_ttl,
        )

    def delete(
        self,
        service_type: str,
        provider_name: str,
        operation: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Remove a cached value.

        Args:
            service_type: Category of service.
            provider_name: Provider identifier.
            operation: Operation name.
            params: Parameters used to compute the cache key.
        """
        key = self._make_key(service_type, provider_name, operation, params)
        self._cache.delete(key)
        logger.debug("Cache DELETE: %s/%s/%s", service_type, provider_name, operation)

    def invalidate_provider(self, provider_name: str) -> int:
        """Invalidate all cache entries for a given provider.

        This is a best-effort operation.  For Redis backends, it uses
        ``keys()`` with the provider prefix.  For other backends, it
        is a no-op.

        Args:
            provider_name: Provider whose cache entries to invalidate.

        Returns:
            Number of keys deleted (0 if unsupported).
        """
        pattern = f"{self.CACHE_PREFIX}*:{provider_name}:*"
        try:
            if hasattr(self._cache, 'delete_pattern'):
                return self._cache.delete_pattern(pattern)
            elif hasattr(self._cache, 'keys'):
                keys = self._cache.keys(pattern)
                for key in keys:
                    self._cache.delete(key)
                return len(keys)
        except Exception as e:
            logger.warning("Failed to invalidate provider cache: %s", e)
        return 0

    def _make_key(
        self,
        service_type: str,
        provider_name: str,
        operation: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Construct a namespaced cache key.

        Args:
            service_type: Category of service.
            provider_name: Provider identifier.
            operation: Operation name.
            params: Optional parameters for key differentiation.

        Returns:
            A string cache key with the ``esl:`` prefix.
        """
        base = f"{self.CACHE_PREFIX}{service_type}:{provider_name}:{operation}"
        if params:
            param_hash = hashlib.md5(
                json.dumps(params, sort_keys=True, default=str).encode(),
            ).hexdigest()[:12]
            base = f"{base}:{param_hash}"
        return base


# Module-level singleton
esl_cache = ExternalServicesCache()
