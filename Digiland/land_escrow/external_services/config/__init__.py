"""
Configuration Management - Digiland External Services Layer
============================================================

Centralized configuration management for all external service providers.
Handles environment-specific configs, encrypted secrets, secret rotation,
runtime updates, validation, and an audit trail.

Components:
    - **ProviderConfigManager**: Main interface for reading/writing configs
    - **ProviderConfig**: Data class representing a provider's configuration
    - **ConfigValidationError**: Raised when validation fails
    - **SecretRotationRecord**: Audit record for secret rotations

Design choices:
    - Secrets are encrypted at rest using Fernet (symmetric) via
      ``cryptography.fernet.Fernet``.  The encryption key is sourced
      from ``settings.ESL_SECRET_ENCRYPTION_KEY`` or falls back to
      ``settings.SECRET_KEY``.
    - Configuration is persisted to the Django cache (primary) with
      in-memory caching for hot-path reads.
    - Vault / AWS Secrets Manager / Azure Key Vault integration is
      available via pluggable backends.
    - Every write operation is recorded in an audit log stored in the
      Django cache.

Usage::

    from external_services.config import ProviderConfigManager

    mgr = ProviderConfigManager()

    # Set configuration
    mgr.set_config('payment', 'paystack', {
        'base_url': 'https://api.paystack.co',
        'api_key': 'sk_test_...',
        'timeout': 30,
    })

    # Read configuration
    config = mgr.get_config('payment', 'paystack')

    # Access a decrypted secret
    api_key = mgr.get_secret('payment', 'paystack', 'api_key')

    # Rotate a secret
    mgr.rotate_secret(
        'payment', 'paystack', 'api_key',
        new_value='sk_live_...',
        rotated_by='admin@digiland.co.ke',
    )
"""

import base64
import hashlib
import json
import logging
import threading
import time
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "esl:cfg"
_AUDIT_PREFIX = "esl:audit"


# ═══════════════════════════════════════════════════════════════════════════
# Exceptions
# ═══════════════════════════════════════════════════════════════════════════


class ConfigError(Exception):
    """Base exception for configuration errors."""


class ConfigNotFoundError(ConfigError):
    """Raised when a requested configuration does not exist."""

    def __init__(self, service_type: str, provider_name: str):
        self.service_type = service_type
        self.provider_name = provider_name
        super().__init__(
            f"No configuration found for {service_type}:{provider_name}"
        )


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails.

    Attributes:
        errors: List of validation error messages.
    """

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Configuration validation failed: {'; '.join(errors)}")


class SecretEncryptionError(ConfigError):
    """Raised when secret encryption or decryption fails."""


class SecretNotFoundError(ConfigError):
    """Raised when a requested secret key does not exist."""

    def __init__(self, service_type: str, provider_name: str, secret_key: str):
        self.service_type = service_type
        self.provider_name = provider_name
        self.secret_key = secret_key
        super().__init__(
            f"Secret '{secret_key}' not found in "
            f"{service_type}:{provider_name}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ProviderConfig:
    """Full configuration record for a provider.

    Attributes:
        service_type: Service category (e.g. ``'payment'``).
        provider_name: Provider name (e.g. ``'paystack'``).
        config: Non-secret configuration values.
        secrets: Encrypted secret values (stored as ciphertext).
        secret_keys: Set of keys that are treated as secrets.
        environment: Deployment environment tag.
        version: Monotonically increasing version number.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        updated_by: User/system that last updated the config.
    """

    service_type: str
    provider_name: str
    config: dict[str, Any] = field(default_factory=dict)
    secrets: dict[str, str] = field(default_factory=dict)  # encrypted
    secret_keys: set[str] = field(default_factory=set)
    environment: str = "default"
    version: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None


@dataclass
class SecretRotationRecord:
    """Audit record for a secret rotation event.

    Attributes:
        service_type: Service category.
        provider_name: Provider name.
        secret_key: The key that was rotated.
        rotated_by: User/system that initiated the rotation.
        rotated_at: Timestamp of the rotation.
        previous_version: Config version before rotation.
        new_version: Config version after rotation.
    """

    service_type: str
    provider_name: str
    secret_key: str
    rotated_by: Optional[str]
    rotated_at: datetime
    previous_version: int
    new_version: int


# ═══════════════════════════════════════════════════════════════════════════
# Encryption helpers
# ═══════════════════════════════════════════════════════════════════════════


class _Encryptor:
    """Fernet-based symmetric encryption for secret values at rest.

    Derives a Fernet key from ``settings.ESL_SECRET_ENCRYPTION_KEY`` or
    falls back to ``settings.SECRET_KEY``.  The key material is stretched
    via SHA-256 + base64url encoding to satisfy Fernet's 32-byte
    requirement.
    """

    def __init__(self) -> None:
        self._fernet = None
        self._init_error: Optional[Exception] = None
        try:
            from cryptography.fernet import Fernet

            raw_key = getattr(settings, "ESL_SECRET_ENCRYPTION_KEY", None) or getattr(
                settings, "SECRET_KEY", ""
            )
            # Derive a valid 32-byte key
            derived = base64.urlsafe_b64encode(
                hashlib.sha256(raw_key.encode()).digest()
            )
            self._fernet = Fernet(derived)
        except ImportError:
            self._init_error = ImportError(
                "The 'cryptography' package is required for secret encryption. "
                "Install it with: pip install cryptography"
            )
        except Exception as exc:
            self._init_error = exc

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string and return a base64 ciphertext string."""
        if self._fernet is None:
            if self._init_error:
                raise SecretEncryptionError(str(self._init_error))
            raise SecretEncryptionError("Fernet not initialised")
        try:
            return self._fernet.encrypt(plaintext.encode()).decode()
        except Exception as exc:
            raise SecretEncryptionError(f"Encryption failed: {exc}") from exc

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a ciphertext string and return the plaintext."""
        if self._fernet is None:
            if self._init_error:
                raise SecretEncryptionError(str(self._init_error))
            raise SecretEncryptionError("Fernet not initialised")
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except Exception as exc:
            raise SecretEncryptionError(f"Decryption failed: {exc}") from exc

    @property
    def available(self) -> bool:
        """Whether encryption is available (i.e. ``cryptography`` is installed)."""
        return self._fernet is not None


# ═══════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════

# Known required fields per service type (extensible via settings)
_DEFAULT_REQUIRED_FIELDS: dict[str, list[str]] = {
    "payment": ["base_url"],
    "email": ["backend"],
    "sms": ["backend"],
    "storage": ["backend"],
    "ai": ["base_url", "model"],
    "identity": ["client_id", "client_secret"],
}


def _get_required_fields(service_type: str) -> list[str]:
    """Return the list of required config fields for a service type.

    Merges the built-in defaults with any overrides from
    ``settings.ESL_REQUIRED_FIELDS``.
    """
    overrides = getattr(settings, "ESL_REQUIRED_FIELDS", {})
    return overrides.get(service_type, _DEFAULT_REQUIRED_FIELDS.get(service_type, []))


# ═══════════════════════════════════════════════════════════════════════════
# Provider Config Manager
# ═══════════════════════════════════════════════════════════════════════════


class ProviderConfigManager:
    """Centralized configuration management for all external service providers.

    Features:
        - Environment-specific configurations (dev / staging / production)
        - Secret encryption at rest (Fernet symmetric)
        - Secret rotation support with full audit trail
        - Runtime configuration updates without restart
        - Configuration validation against required-field schemas
        - Pluggable secret backends (Vault, AWS SM, Azure KV)
        - Configuration change auditing (every write is logged)

    Example::

        mgr = ProviderConfigManager()
        mgr.set_config('payment', 'paystack', {
            'base_url': 'https://api.paystack.co',
            'timeout': 30,
            'api_key': 'sk_test_...',  # auto-detected as secret
        })

        config = mgr.get_config('payment', 'paystack')
        key = mgr.get_secret('payment', 'paystack', 'api_key')
    """

    _global_instance: Optional["ProviderConfigManager"] = None
    _global_lock = threading.Lock()

    # Keys that are automatically treated as secrets
    _AUTO_SECRET_PATTERNS = {
        "api_key",
        "secret_key",
        "client_secret",
        "password",
        "token",
        "private_key",
        "access_key",
        "auth_token",
        "webhook_secret",
        "encryption_key",
    }

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._configs: dict[str, ProviderConfig] = {}
        self._encryptor = _Encryptor()
        self._secret_backends: dict[str, Any] = {}
        self._environment = getattr(settings, "ESL_ENVIRONMENT", "default")

    @classmethod
    def get_global(cls) -> "ProviderConfigManager":
        """Return the process-wide singleton manager."""
        if cls._global_instance is None:
            with cls._global_lock:
                if cls._global_instance is None:
                    cls._global_instance = cls()
        return cls._global_instance

    @classmethod
    def reset_global(cls) -> None:
        """Reset the global singleton (useful in tests)."""
        with cls._global_lock:
            cls._global_instance = None

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_config(
        self,
        service_type: str,
        provider_name: str,
    ) -> dict[str, Any]:
        """Get configuration for a specific provider.

        Returns a merged dict of non-secret configuration values.
        Secret values are **not** included — use :meth:`get_secret` to
        access individual secrets.

        Args:
            service_type: Service category (e.g. ``'payment'``).
            provider_name: Provider name (e.g. ``'paystack'``).

        Returns:
            A dict of configuration values.

        Raises:
            ConfigNotFoundError: If the provider has no configuration.
        """
        key = self._make_key(service_type, provider_name)
        with self._lock:
            config = self._configs.get(key)
            if config is None:
                # Try to load from cache
                config = self._load_from_cache(key)
                if config is not None:
                    self._configs[key] = config
                else:
                    raise ConfigNotFoundError(service_type, provider_name)
            # Return a deep copy of non-secret config
            return deepcopy(config.config)

    def get_secret(
        self,
        service_type: str,
        provider_name: str,
        secret_key: str,
    ) -> str:
        """Get a decrypted secret value.

        Checks pluggable secret backends first, then falls back to
        locally encrypted secrets.

        Args:
            service_type: Service category.
            provider_name: Provider name.
            secret_key: The key of the secret to retrieve.

        Returns:
            The decrypted secret value as a string.

        Raises:
            ConfigNotFoundError: If the provider has no configuration.
            SecretNotFoundError: If the secret key does not exist.
            SecretEncryptionError: If decryption fails.
        """
        key = self._make_key(service_type, provider_name)

        # Check external backends first
        for backend_name, backend in self._secret_backends.items():
            try:
                value = backend.get_secret(
                    service_type, provider_name, secret_key
                )
                if value is not None:
                    return value
            except Exception:
                logger.debug(
                    "Secret backend '%s' failed for %s/%s",
                    backend_name,
                    service_type,
                    secret_key,
                    exc_info=True,
                )

        with self._lock:
            config = self._configs.get(key)
            if config is None:
                config = self._load_from_cache(key)
                if config is not None:
                    self._configs[key] = config

            if config is None:
                raise ConfigNotFoundError(service_type, provider_name)

            if secret_key not in config.secrets:
                raise SecretNotFoundError(service_type, provider_name, secret_key)

            ciphertext = config.secrets[secret_key]
            return self._encryptor.decrypt(ciphertext)

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def set_config(
        self,
        service_type: str,
        provider_name: str,
        config: dict[str, Any],
        updated_by: Optional[str] = None,
    ) -> None:
        """Set or update provider configuration.

        Values matching known secret patterns (e.g. keys containing
        ``api_key``, ``secret``, ``password``) are automatically
        encrypted and stored separately from non-secret config.

        Args:
            service_type: Service category.
            provider_name: Provider name.
            config: Full configuration dict (may include secrets).
            updated_by: User/system performing the update (for audit).
        """
        key = self._make_key(service_type, provider_name)
        now = datetime.now(timezone.utc)

        with self._lock:
            existing = self._configs.get(key)
            version = (existing.version + 1) if existing else 1
            created_at = existing.created_at if existing else now

            # Separate secrets from plain config
            plain_config: dict[str, Any] = {}
            encrypted_secrets: dict[str, str] = {}
            secret_keys: set[str] = set()

            for k, v in config.items():
                if self._is_secret_key(k):
                    secret_keys.add(k)
                    if self._encryptor.available:
                        encrypted_secrets[k] = self._encryptor.encrypt(str(v))
                    else:
                        # Store as-is if encryption unavailable (dev mode)
                        logger.warning(
                            "ProviderConfigManager: storing secret '%s' "
                            "unencrypted (cryptography not available)",
                            k,
                        )
                        encrypted_secrets[k] = str(v)
                else:
                    plain_config[k] = v

            # Preserve existing secrets not overwritten
            if existing:
                for sk, sv in existing.secrets.items():
                    if sk not in encrypted_secrets:
                        encrypted_secrets[sk] = sv
                        secret_keys.add(sk)

            record = ProviderConfig(
                service_type=service_type,
                provider_name=provider_name,
                config=plain_config,
                secrets=encrypted_secrets,
                secret_keys=secret_keys,
                environment=self._environment,
                version=version,
                created_at=created_at,
                updated_at=now,
                updated_by=updated_by,
            )

            self._configs[key] = record
            self._persist_to_cache(key, record)
            self._audit_log(
                action="set_config",
                service_type=service_type,
                provider_name=provider_name,
                version=version,
                updated_by=updated_by,
            )

    def rotate_secret(
        self,
        service_type: str,
        provider_name: str,
        secret_key: str,
        new_value: str,
        rotated_by: Optional[str] = None,
    ) -> SecretRotationRecord:
        """Rotate a secret value with an audit trail.

        The old value is replaced by *new_value* in the encrypted store.
        The rotation is recorded in the audit log.

        Args:
            service_type: Service category.
            provider_name: Provider name.
            secret_key: The key to rotate.
            new_value: The new plaintext value.
            rotated_by: User/system performing the rotation.

        Returns:
            A :class:`SecretRotationRecord` audit entry.

        Raises:
            ConfigNotFoundError: If the provider has no configuration.
            SecretNotFoundError: If the secret key does not exist.
        """
        key = self._make_key(service_type, provider_name)
        now = datetime.now(timezone.utc)

        with self._lock:
            config = self._configs.get(key)
            if config is None:
                config = self._load_from_cache(key)
                if config is not None:
                    self._configs[key] = config

            if config is None:
                raise ConfigNotFoundError(service_type, provider_name)

            if secret_key not in config.secret_keys:
                raise SecretNotFoundError(service_type, provider_name, secret_key)

            previous_version = config.version

            # Encrypt new value
            if self._encryptor.available:
                config.secrets[secret_key] = self._encryptor.encrypt(new_value)
            else:
                config.secrets[secret_key] = new_value

            config.version += 1
            config.updated_at = now
            config.updated_by = rotated_by

            self._persist_to_cache(key, config)

            record = SecretRotationRecord(
                service_type=service_type,
                provider_name=provider_name,
                secret_key=secret_key,
                rotated_by=rotated_by,
                rotated_at=now,
                previous_version=previous_version,
                new_version=config.version,
            )

            self._audit_log(
                action="rotate_secret",
                service_type=service_type,
                provider_name=provider_name,
                version=config.version,
                updated_by=rotated_by,
                extra={"secret_key": secret_key},
            )

            return record

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_config(
        self,
        service_type: str,
        provider_name: str,
    ) -> list[str]:
        """Validate provider configuration.

        Checks for the presence of required fields defined in
        ``settings.ESL_REQUIRED_FIELDS`` or the built-in defaults.

        Args:
            service_type: Service category.
            provider_name: Provider name.

        Returns:
            A list of validation error strings (empty if valid).

        Raises:
            ConfigNotFoundError: If the provider has no configuration.
        """
        key = self._make_key(service_type, provider_name)

        with self._lock:
            config = self._configs.get(key)
            if config is None:
                config = self._load_from_cache(key)
                if config is not None:
                    self._configs[key] = config

        if config is None:
            raise ConfigNotFoundError(service_type, provider_name)

        errors: list[str] = []
        required = _get_required_fields(service_type)

        all_keys = set(config.config.keys()) | config.secret_keys
        for field_name in required:
            if field_name not in all_keys:
                errors.append(
                    f"Missing required field '{field_name}' "
                    f"for {service_type}:{provider_name}"
                )

        # Check that encrypted secrets can be decrypted
        for sk in config.secret_keys:
            if sk in config.secrets and self._encryptor.available:
                try:
                    self._encryptor.decrypt(config.secrets[sk])
                except SecretEncryptionError:
                    errors.append(
                        f"Secret '{sk}' cannot be decrypted — "
                        f"may have been encrypted with a different key"
                    )

        return errors

    # ------------------------------------------------------------------
    # Reload
    # ------------------------------------------------------------------

    def reload_config(
        self,
        service_type: Optional[str] = None,
        provider_name: Optional[str] = None,
    ) -> int:
        """Reload configuration from persistent storage.

        If both arguments are ``None``, all cached configurations are
        discarded and reloaded on demand.

        Args:
            service_type: Optional service category filter.
            provider_name: Optional provider name filter.

        Returns:
            The number of configurations reloaded.
        """
        with self._lock:
            if service_type and provider_name:
                key = self._make_key(service_type, provider_name)
                self._configs.pop(key, None)
                config = self._load_from_cache(key)
                if config:
                    self._configs[key] = config
                    return 1
                return 0
            else:
                # Reload all from cache
                self._configs.clear()
                return self._load_all_from_cache()

    # ------------------------------------------------------------------
    # Secret backends
    # ------------------------------------------------------------------

    def register_secret_backend(self, name: str, backend: Any) -> None:
        """Register a pluggable secret backend.

        The backend must implement a ``get_secret(service_type,
        provider_name, secret_key) -> str | None`` method.

        Known backends:
            - ``vault``: HashiCorp Vault
            - ``aws_sm``: AWS Secrets Manager
            - ``azure_kv``: Azure Key Vault

        Args:
            name: Backend identifier (e.g. ``'vault'``).
            backend: Backend instance.
        """
        with self._lock:
            self._secret_backends[name] = backend
        logger.info("ProviderConfigManager: registered secret backend '%s'", name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(service_type: str, provider_name: str) -> str:
        return f"{service_type}:{provider_name}"

    @classmethod
    def _is_secret_key(cls, key: str) -> bool:
        """Heuristic: does the key name suggest it holds a secret?"""
        lowered = key.lower()
        return any(pattern in lowered for pattern in cls._AUTO_SECRET_PATTERNS)

    def _persist_to_cache(self, key: str, config: ProviderConfig) -> None:
        """Serialize and persist a ProviderConfig to Django cache."""
        try:
            payload = {
                "service_type": config.service_type,
                "provider_name": config.provider_name,
                "config": config.config,
                "secrets": config.secrets,
                "secret_keys": list(config.secret_keys),
                "environment": config.environment,
                "version": config.version,
                "created_at": (
                    config.created_at.isoformat() if config.created_at else None
                ),
                "updated_at": (
                    config.updated_at.isoformat() if config.updated_at else None
                ),
                "updated_by": config.updated_by,
            }
            cache.set(
                f"{_CACHE_PREFIX}:{key}", payload, timeout=None
            )
        except Exception:
            logger.warning(
                "ProviderConfigManager: cache persist failed for '%s'",
                key,
                exc_info=True,
            )

    def _load_from_cache(self, key: str) -> Optional[ProviderConfig]:
        """Load a ProviderConfig from Django cache."""
        try:
            payload = cache.get(f"{_CACHE_PREFIX}:{key}")
            if payload is None:
                return None
            return ProviderConfig(
                service_type=payload["service_type"],
                provider_name=payload["provider_name"],
                config=payload.get("config", {}),
                secrets=payload.get("secrets", {}),
                secret_keys=set(payload.get("secret_keys", [])),
                environment=payload.get("environment", "default"),
                version=payload.get("version", 1),
                created_at=self._parse_iso(payload.get("created_at")),
                updated_at=self._parse_iso(payload.get("updated_at")),
                updated_by=payload.get("updated_by"),
            )
        except Exception:
            logger.warning(
                "ProviderConfigManager: cache load failed for '%s'",
                key,
                exc_info=True,
            )
            return None

    def _load_all_from_cache(self) -> int:
        """Load all configurations from Django cache (best-effort)."""
        # Django cache doesn't support key listing natively,
        # so we rely on known provider keys stored in a registry set.
        try:
            registry = cache.get(f"{_CACHE_PREFIX}:__registry__", set())
            count = 0
            for key in registry:
                config = self._load_from_cache(key)
                if config:
                    self._configs[key] = config
                    count += 1
            return count
        except Exception:
            return 0

    def _register_key_in_cache(self, key: str) -> None:
        """Add a config key to the cache registry set for enumeration."""
        try:
            registry = cache.get(f"{_CACHE_PREFIX}:__registry__", set())
            if isinstance(registry, list):
                registry = set(registry)
            registry.add(key)
            cache.set(f"{_CACHE_PREFIX}:__registry__", registry, timeout=None)
        except Exception:
            pass

    @staticmethod
    def _parse_iso(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return None

    def _audit_log(
        self,
        action: str,
        service_type: str,
        provider_name: str,
        version: int,
        updated_by: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> None:
        """Write an audit log entry for a configuration change."""
        entry = {
            "action": action,
            "service_type": service_type,
            "provider_name": provider_name,
            "version": version,
            "updated_by": updated_by,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            entry.update(extra)

        try:
            # Append to a list in cache
            audit_key = f"{_AUDIT_PREFIX}:{service_type}:{provider_name}"
            history = cache.get(audit_key, [])
            history.append(entry)
            # Keep last 100 entries
            if len(history) > 100:
                history = history[-100:]
            cache.set(audit_key, history, timeout=None)
        except Exception:
            logger.warning(
                "ProviderConfigManager: audit log write failed", exc_info=True
            )

        logger.info(
            "ProviderConfigManager: %s %s:%s v%d by %s",
            action,
            service_type,
            provider_name,
            version,
            updated_by or "system",
        )


# ═══════════════════════════════════════════════════════════════════════════
# Module exports
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    "ConfigError",
    "ConfigNotFoundError",
    "ConfigValidationError",
    "ProviderConfig",
    "ProviderConfigManager",
    "SecretEncryptionError",
    "SecretNotFoundError",
    "SecretRotationRecord",
]
