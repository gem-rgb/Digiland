"""
Secrets Vault for Admin Control Plane
======================================

Manages encrypted secrets with separation of concerns, per-category
encryption keys, access audit logging, and rotation scheduling.

Security Architecture
---------------------
- **AES-256-GCM encryption**: All secret values are encrypted at rest
  using the ``AES256GCMEncryptor`` from the ``encryption`` module.
- **Per-category encryption keys**: Each secret category (ADMIN,
  FINANCIAL, CUSTOMER, SYSTEM, INTEGRATION) has its own encryption
  key, limiting the blast radius if a single key is compromised.
- **Access audit logging**: Every ``get_secret()`` call is logged with
  the caller's identity, IP address, and timestamp.
- **Rate limiting**: Secret access is rate-limited to prevent bulk
  extraction.
- **Soft deletion**: Deleted secrets are marked as deleted but retained
  for audit purposes.

Secret Categories
-----------------
- ``ADMIN``      : Admin credentials, service account keys
- ``FINANCIAL``  : Payment gateway keys, banking credentials
- ``CUSTOMER``   : Customer data encryption keys, PII keys
- ``SYSTEM``     : Database passwords, API tokens
- ``INTEGRATION``: Third-party integration secrets (SMS, email, etc.)

Classes
-------
SecretsVaultService
    Store, retrieve, rotate, and manage encrypted secrets.
"""

import hashlib
import json
import logging
import os
import time
import uuid
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from .encryption import AES256GCMEncryptor
from .services import ImmutableAuditService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATEGORY_CHOICES = [
    ("ADMIN", "Admin"),
    ("FINANCIAL", "Financial"),
    ("CUSTOMER", "Customer"),
    ("SYSTEM", "System"),
    ("INTEGRATION", "Integration"),
]

# Rate limiting: max reads per key per minute
RATE_LIMIT_READS_PER_MINUTE = 30
RATE_LIMIT_READS_PER_HOUR = 200

# Default rotation schedule (days)
DEFAULT_ROTATION_DAYS = {
    "ADMIN": 90,
    "FINANCIAL": 60,
    "CUSTOMER": 365,
    "SYSTEM": 90,
    "INTEGRATION": 120,
}

# Secret strength requirements by category
STRENGTH_REQUIREMENTS = {
    "ADMIN": {"min_length": 20, "require_upper": True, "require_lower": True, "require_digit": True, "require_special": True},
    "FINANCIAL": {"min_length": 24, "require_upper": True, "require_lower": True, "require_digit": True, "require_special": True},
    "CUSTOMER": {"min_length": 16, "require_upper": True, "require_lower": True, "require_digit": True, "require_special": False},
    "SYSTEM": {"min_length": 20, "require_upper": True, "require_lower": True, "require_digit": True, "require_special": True},
    "INTEGRATION": {"min_length": 16, "require_upper": False, "require_lower": False, "require_digit": False, "require_special": False},
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SecretsVaultError(Exception):
    """Base exception for secrets vault operations."""
    pass


class SecretNotFoundError(SecretsVaultError):
    """The requested secret does not exist."""
    pass


class SecretAccessDeniedError(SecretsVaultError):
    """Access to the secret is denied."""
    pass


class SecretRateLimitError(SecretsVaultError):
    """Rate limit exceeded for secret access."""
    pass


class SecretStrengthError(SecretsVaultError):
    """Secret does not meet strength requirements."""
    pass


class SecretRotationError(SecretsVaultError):
    """Error during secret rotation."""
    pass


# ---------------------------------------------------------------------------
# Category Encryption Key Management
# ---------------------------------------------------------------------------

# Cache of per-category encryption keys (derived from a master key)
_category_keys: dict = {}


def _get_master_key() -> bytes:
    """Retrieve the master encryption key for the secrets vault.

    The master key is stored in Django settings as a hex-encoded string.
    If not configured, a key is derived from ``SECRET_KEY`` (not
    recommended for production).

    Returns
    -------
    bytes
        32-byte AES-256 key.
    """
    hex_key = getattr(settings, "SECRETS_VAULT_MASTER_KEY", None)
    if hex_key:
        return bytes.fromhex(hex_key)

    # Fallback: derive from Django SECRET_KEY
    secret = getattr(settings, "SECRET_KEY", "insecure-default-key")
    derived = hashlib.sha256(
        f"secrets-vault-master:{secret}".encode("utf-8")
    ).digest()
    logger.warning(
        "SecretsVault: SECRETS_VAULT_MASTER_KEY not set.  Derived key "
        "from SECRET_KEY — this is NOT recommended for production."
    )
    return derived


def _get_category_key(category: str) -> bytes:
    """Derive a per-category encryption key from the master key.

    Uses HMAC-SHA256 to derive a unique key for each category,
    ensuring that compromising one category's key does not expose
    secrets in other categories.

    Parameters
    ----------
    category : str
        One of ``CATEGORY_CHOICES`` keys.

    Returns
    -------
    bytes
        32-byte AES-256 key unique to this category.
    """
    if category not in _category_keys:
        import hmac as hmac_mod
        master = _get_master_key()
        _category_keys[category] = hmac_mod.new(
            master,
            category.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    return _category_keys[category]


# ---------------------------------------------------------------------------
# Secret Storage
# ---------------------------------------------------------------------------

# In-memory secret store.
# Production deployments MUST use a Django model with encrypted fields.
# Format: {key: SecretRecord}
_secret_store: dict = {}

# Access audit trail
# Format: {key: [{accessor_id, timestamp, ip_address}, ...]}
_access_log: dict = {}

# Rate limit counters
# Format: {key: [(timestamp, accessor_id), ...]}
_rate_limit_counters: dict = {}


class SecretRecord:
    """Stored secret with metadata.

    Attributes
    ----------
    key : str
        Unique identifier for the secret.
    encrypted_value : str
        AES-256-GCM encrypted value (URL-safe base64).
    category : str
        Secret category for key separation.
    rotation_days : int
        Recommended rotation period in days.
    last_rotated_at : str
        ISO-8601 timestamp of last rotation.
    created_at : str
        ISO-8601 timestamp of creation.
    updated_at : str
        ISO-8601 timestamp of last update.
    created_by : str or None
        Admin user ID who created the secret.
    is_deleted : bool
        Soft deletion flag.
    deleted_at : str or None
        ISO-8601 timestamp of deletion.
    version : int
        Incremented on each rotation/update.
    """

    def __init__(
        self,
        key: str,
        encrypted_value: str,
        category: str,
        rotation_days: int,
        created_by: Optional[str] = None,
    ):
        self.key = key
        self.encrypted_value = encrypted_value
        self.category = category
        self.rotation_days = rotation_days
        self.last_rotated_at = timezone.now().isoformat()
        self.created_at = timezone.now().isoformat()
        self.updated_at = self.created_at
        self.created_by = created_by
        self.is_deleted = False
        self.deleted_at = None
        self.version = 1

        _secret_store[key] = self

    def to_dict(self, include_value: bool = False) -> dict:
        """Serialise to a dictionary.

        Parameters
        ----------
        include_value : bool
            If ``True``, include the encrypted value.  Should only be
            ``True`` in internal operations — never expose to API responses.

        Returns
        -------
        dict
            Secret metadata (value excluded by default).
        """
        result = {
            "key": self.key,
            "category": self.category,
            "rotation_days": self.rotation_days,
            "last_rotated_at": self.last_rotated_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at,
            "version": self.version,
            "is_due_for_rotation": self._is_due_for_rotation(),
        }
        if include_value:
            result["encrypted_value"] = self.encrypted_value
        return result

    def _is_due_for_rotation(self) -> bool:
        """Check if the secret is past its rotation schedule."""
        last_rotated = timezone.datetime.fromisoformat(self.last_rotated_at)
        deadline = last_rotated + timedelta(days=self.rotation_days)
        return timezone.now() > deadline


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------

def _check_rate_limit(key: str, accessor_id: str) -> None:
    """Enforce rate limits on secret access.

    Parameters
    ----------
    key : str
        The secret key being accessed.
    accessor_id : str
        The user ID accessing the secret.

    Raises
    ------
    SecretRateLimitError
        If the rate limit is exceeded.
    """
    now = time.time()
    minute_ago = now - 60
    hour_ago = now - 3600

    # Get or create counter list
    if key not in _rate_limit_counters:
        _rate_limit_counters[key] = []

    # Clean old entries
    _rate_limit_counters[key] = [
        (ts, aid) for ts, aid in _rate_limit_counters[key]
        if ts > hour_ago
    ]

    # Count recent accesses
    minute_accesses = sum(
        1 for ts, _ in _rate_limit_counters[key] if ts > minute_ago
    )
    hour_accesses = len(_rate_limit_counters[key])

    if minute_accesses >= RATE_LIMIT_READS_PER_MINUTE:
        raise SecretRateLimitError(
            f"Rate limit exceeded: {RATE_LIMIT_READS_PER_MINUTE} reads "
            f"per minute for secret '{key}'."
        )

    if hour_accesses >= RATE_LIMIT_READS_PER_HOUR:
        raise SecretRateLimitError(
            f"Rate limit exceeded: {RATE_LIMIT_READS_PER_HOUR} reads "
            f"per hour for secret '{key}'."
        )

    # Record this access
    _rate_limit_counters[key].append((now, accessor_id))


# ---------------------------------------------------------------------------
# Secrets Vault Service
# ---------------------------------------------------------------------------

class SecretsVaultService:
    """Store, retrieve, rotate, and manage encrypted secrets.

    All operations are audit-logged.  Secret values are encrypted at
    rest with AES-256-GCM, using separate encryption keys per category.

    Example
    -------
    >>> SecretsVaultService.store_secret(
    ...     key="PAYMENT_GATEWAY_API_KEY",
    ...     value="sk_live_xxx",
    ...     category="FINANCIAL",
    ...     rotation_days=60,
    ...     stored_by=admin_user,
    ... )
    >>> secret_value = SecretsVaultService.get_secret(
    ...     key="PAYMENT_GATEWAY_API_KEY",
    ...     accessed_by=admin_user,
    ... )
    """

    @staticmethod
    def store_secret(
        key: str,
        value: str,
        category: str,
        rotation_days: Optional[int] = None,
        stored_by=None,
        ip_address: str = "",
        user_agent: str = "",
        validate_strength: bool = True,
    ) -> dict:
        """Store an encrypted secret.

        Parameters
        ----------
        key : str
            Unique identifier for the secret.
        value : str
            The plaintext value to encrypt and store.
        category : str
            One of ``CATEGORY_CHOICES`` keys.
        rotation_days : int, optional
            Rotation period in days.  Defaults to category-specific value.
        stored_by : User, optional
            Admin storing the secret.
        ip_address : str
        user_agent : str
        validate_strength : bool
            Whether to validate the secret meets strength requirements.

        Returns
        -------
        dict
            Metadata of the stored secret (never the value).

        Raises
        ------
        SecretsVaultError
            If the key already exists or parameters are invalid.
        SecretStrengthError
            If the value doesn't meet category strength requirements.
        """
        # Validate category
        valid_categories = [c[0] for c in CATEGORY_CHOICES]
        if category not in valid_categories:
            raise SecretsVaultError(
                f"Invalid category '{category}'. "
                f"Valid: {', '.join(valid_categories)}"
            )

        # Check for duplicate key
        if key in _secret_store and not _secret_store[key].is_deleted:
            raise SecretsVaultError(
                f"Secret '{key}' already exists.  Use rotate_secret() "
                f"to update the value."
            )

        # Validate strength
        if validate_strength:
            strength_result = SecretsVaultService.validate_secret_strength(
                key, value, category
            )
            if not strength_result["is_valid"]:
                raise SecretStrengthError(
                    f"Secret does not meet strength requirements: "
                    f"{'; '.join(strength_result['failures'])}"
                )

        # Set default rotation days
        if rotation_days is None:
            rotation_days = DEFAULT_ROTATION_DAYS.get(category, 90)

        # Encrypt with category key
        category_key = _get_category_key(category)
        encrypted_value = AES256GCMEncryptor.encrypt_string(value, category_key)

        # Store
        record = SecretRecord(
            key=key,
            encrypted_value=encrypted_value,
            category=category,
            rotation_days=rotation_days,
            created_by=str(stored_by.id) if stored_by else None,
        )

        # If key was soft-deleted, remove old record
        if key in _secret_store:
            del _secret_store[key]

        # Re-create with new record
        record.key = key
        _secret_store[key] = record

        # Audit log (never log the value)
        ImmutableAuditService.log(
            actor=stored_by,
            action="SECRET_STORED",
            resource_type="VaultSecret",
            resource_id=key,
            metadata={
                "category": category,
                "rotation_days": rotation_days,
                "value_length": len(value),
                "strength_validated": validate_strength,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(
            "SecretsVault: Secret '%s' stored (category=%s, rotation=%dd) by %s",
            key,
            category,
            rotation_days,
            getattr(stored_by, "email", "system"),
        )

        return record.to_dict()

    @staticmethod
    def get_secret(
        key: str,
        accessed_by=None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> str:
        """Retrieve and decrypt a secret value.

        Every access is:
        1. Rate-limited to prevent bulk extraction
        2. Audit-logged with the caller's identity
        3. Verified against the category's encryption key

        Parameters
        ----------
        key : str
            The secret key to retrieve.
        accessed_by : User, optional
            The admin accessing the secret.
        ip_address : str
        user_agent : str

        Returns
        -------
        str
            The decrypted secret value.

        Raises
        ------
        SecretNotFoundError
            If the secret does not exist or is deleted.
        SecretRateLimitError
            If the rate limit is exceeded.
        """
        record = _secret_store.get(key)
        if record is None or record.is_deleted:
            raise SecretNotFoundError(
                f"Secret '{key}' not found."
            )

        # Rate limit check
        accessor_id = str(accessed_by.id) if accessed_by else "anonymous"
        _check_rate_limit(key, accessor_id)

        # Decrypt
        category_key = _get_category_key(record.category)
        try:
            value = AES256GCMEncryptor.decrypt_string(
                record.encrypted_value, category_key
            )
        except Exception as exc:
            logger.error(
                "SecretsVault: Failed to decrypt secret '%s': %s",
                key,
                exc,
            )
            raise SecretsVaultError(
                f"Failed to decrypt secret '{key}'.  Possible key corruption."
            )

        # Access audit log
        if key not in _access_log:
            _access_log[key] = []
        _access_log[key].append({
            "accessor_id": accessor_id,
            "accessor_email": getattr(accessed_by, "email", "anonymous"),
            "timestamp": timezone.now().isoformat(),
            "ip_address": ip_address,
        })

        # Immutable audit log
        ImmutableAuditService.log(
            actor=accessed_by,
            action="SECRET_ACCESSED",
            resource_type="VaultSecret",
            resource_id=key,
            metadata={
                "category": record.category,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return value

    @staticmethod
    def rotate_secret(
        key: str,
        new_value: str,
        rotated_by=None,
        ip_address: str = "",
        user_agent: str = "",
        validate_strength: bool = True,
    ) -> dict:
        """Rotate a secret by replacing its value.

        The old encrypted value is replaced with the new value,
        encrypted with the category key.  The version number is
        incremented.

        Parameters
        ----------
        key : str
            The secret key to rotate.
        new_value : str
            The new plaintext value.
        rotated_by : User, optional
            The admin rotating the secret.
        ip_address : str
        user_agent : str
        validate_strength : bool
            Whether to validate the new value's strength.

        Returns
        -------
        dict
            Updated secret metadata.

        Raises
        ------
        SecretNotFoundError
            If the secret does not exist.
        SecretStrengthError
            If the new value doesn't meet strength requirements.
        """
        record = _secret_store.get(key)
        if record is None or record.is_deleted:
            raise SecretNotFoundError(
                f"Secret '{key}' not found."
            )

        # Validate strength
        if validate_strength:
            strength_result = SecretsVaultService.validate_secret_strength(
                key, new_value, record.category
            )
            if not strength_result["is_valid"]:
                raise SecretStrengthError(
                    f"New value does not meet strength requirements: "
                    f"{'; '.join(strength_result['failures'])}"
                )

        # Encrypt new value
        category_key = _get_category_key(record.category)
        new_encrypted = AES256GCMEncryptor.encrypt_string(new_value, category_key)

        # Update record
        record.encrypted_value = new_encrypted
        record.last_rotated_at = timezone.now().isoformat()
        record.updated_at = record.last_rotated_at
        record.version += 1

        # Audit log
        ImmutableAuditService.log(
            actor=rotated_by,
            action="SECRET_ROTATED",
            resource_type="VaultSecret",
            resource_id=key,
            metadata={
                "category": record.category,
                "new_version": record.version,
                "value_length": len(new_value),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(
            "SecretsVault: Secret '%s' rotated to version %d by %s",
            key,
            record.version,
            getattr(rotated_by, "email", "system"),
        )

        return record.to_dict()

    @staticmethod
    def delete_secret(
        key: str,
        deleted_by=None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict:
        """Mark a secret as deleted (soft deletion).

        The secret value is retained in encrypted form for audit
        purposes but cannot be accessed through ``get_secret()``.

        Parameters
        ----------
        key : str
            The secret key to delete.
        deleted_by : User, optional
            The admin deleting the secret.
        ip_address : str
        user_agent : str

        Returns
        -------
        dict
            Deletion confirmation.

        Raises
        ------
        SecretNotFoundError
            If the secret does not exist.
        """
        record = _secret_store.get(key)
        if record is None:
            raise SecretNotFoundError(
                f"Secret '{key}' not found."
            )

        if record.is_deleted:
            raise SecretsVaultError(
                f"Secret '{key}' is already deleted."
            )

        # Soft delete
        record.is_deleted = True
        record.deleted_at = timezone.now().isoformat()

        # Audit log
        ImmutableAuditService.log(
            actor=deleted_by,
            action="SECRET_DELETED",
            resource_type="VaultSecret",
            resource_id=key,
            metadata={
                "category": record.category,
                "version": record.version,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(
            "SecretsVault: Secret '%s' deleted by %s",
            key,
            getattr(deleted_by, "email", "system"),
        )

        return {"deleted": True, "key": key}

    @staticmethod
    def list_secrets(
        category: Optional[str] = None,
        include_deleted: bool = False,
    ) -> list:
        """List secret metadata (never values).

        Parameters
        ----------
        category : str, optional
            Filter by category.
        include_deleted : bool
            Whether to include soft-deleted secrets.

        Returns
        -------
        list[dict]
            List of secret metadata records.
        """
        results = []
        for record in _secret_store.values():
            # Filter deleted
            if not include_deleted and record.is_deleted:
                continue

            # Filter category
            if category and record.category != category:
                continue

            results.append(record.to_dict())

        # Sort by key name
        results.sort(key=lambda x: x["key"])
        return results

    @staticmethod
    def get_secret_history(key: str, limit: int = 100) -> list:
        """Retrieve the access audit trail for a secret.

        Parameters
        ----------
        key : str
            The secret key.
        limit : int
            Maximum number of entries to return.

        Returns
        -------
        list[dict]
            Access log entries (most recent first).
        """
        entries = _access_log.get(key, [])
        return entries[-limit:][::-1]  # Most recent first

    @staticmethod
    def check_rotation_schedule() -> list:
        """Find secrets that are due for rotation.

        Returns
        -------
        list[dict]
            List of secrets past their rotation deadline.
        """
        due = []
        for record in _secret_store.values():
            if record.is_deleted:
                continue
            if record._is_due_for_rotation():
                due.append({
                    "key": record.key,
                    "category": record.category,
                    "last_rotated_at": record.last_rotated_at,
                    "rotation_days": record.rotation_days,
                    "days_overdue": (
                        timezone.now() - timezone.datetime.fromisoformat(record.last_rotated_at)
                    ).days - record.rotation_days,
                })

        due.sort(key=lambda x: x["days_overdue"], reverse=True)
        return due

    @staticmethod
    def validate_secret_strength(
        key: str,
        value: str,
        category: str,
    ) -> dict:
        """Validate that a secret value meets strength requirements.

        Parameters
        ----------
        key : str
            The secret key (for context in error messages).
        value : str
            The value to validate.
        category : str
            The secret category (determines requirements).

        Returns
        -------
        dict
            ``{"is_valid": bool, "failures": list[str]}``
        """
        failures = []
        requirements = STRENGTH_REQUIREMENTS.get(category, STRENGTH_REQUIREMENTS["SYSTEM"])

        # Length check
        if len(value) < requirements["min_length"]:
            failures.append(
                f"Minimum length is {requirements['min_length']} characters "
                f"(got {len(value)})"
            )

        # Character type checks
        if requirements["require_upper"] and not any(c.isupper() for c in value):
            failures.append("Must contain at least one uppercase letter")

        if requirements["require_lower"] and not any(c.islower() for c in value):
            failures.append("Must contain at least one lowercase letter")

        if requirements["require_digit"] and not any(c.isdigit() for c in value):
            failures.append("Must contain at least one digit")

        if requirements["require_special"]:
            special_chars = set("!@#$%^&*()_+-=[]{}|;':\",./<>?")
            if not any(c in special_chars for c in value):
                failures.append("Must contain at least one special character")

        # Check for common patterns
        common_patterns = ["password", "secret", "admin", "12345", "qwerty"]
        value_lower = value.lower()
        for pattern in common_patterns:
            if pattern in value_lower:
                failures.append(f"Must not contain common pattern '{pattern}'")
                break  # Only report one pattern match

        return {
            "is_valid": len(failures) == 0,
            "failures": failures,
            "requirements": requirements,
        }

    @staticmethod
    def get_secret_metadata(key: str) -> Optional[dict]:
        """Retrieve metadata for a secret without accessing its value.

        Unlike ``get_secret()``, this does NOT:
        - Decrypt the value
        - Rate-limit access
        - Log as a secret access

        Parameters
        ----------
        key : str
            The secret key.

        Returns
        -------
        dict or None
            Secret metadata, or ``None`` if not found.
        """
        record = _secret_store.get(key)
        if record is None or record.is_deleted:
            return None
        return record.to_dict()

    @staticmethod
    def rotate_category_key(
        category: str,
        new_master_key: bytes,
        rotated_by=None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict:
        """Re-encrypt all secrets in a category with a new key.

        This is a maintenance operation that:
        1. Decrypts all secrets in the category with the old key
        2. Re-encrypts them with a new key derived from the new master key
        3. Updates the category key cache

        This is an expensive operation and should be performed during
        maintenance windows.

        Parameters
        ----------
        category : str
            The category whose secrets to re-encrypt.
        new_master_key : bytes
            The new master key (32 bytes).
        rotated_by : User, optional
            The admin performing the rotation.
        ip_address : str
        user_agent : str

        Returns
        -------
        dict
            Rotation result with count of re-encrypted secrets.
        """
        import hmac as hmac_mod

        # Derive old and new category keys
        old_key = _get_category_key(category)
        new_key = hmac_mod.new(
            new_master_key,
            category.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        count = 0
        errors = []

        for record in _secret_store.values():
            if record.category != category or record.is_deleted:
                continue

            try:
                # Decrypt with old key
                plaintext = AES256GCMEncryptor.decrypt_string(
                    record.encrypted_value, old_key
                )
                # Re-encrypt with new key
                record.encrypted_value = AES256GCMEncryptor.encrypt_string(
                    plaintext, new_key
                )
                count += 1
            except Exception as exc:
                errors.append(f"Failed to rotate '{record.key}': {exc}")

        # Update the cached category key
        _category_keys[category] = new_key

        # Audit log
        ImmutableAuditService.log(
            actor=rotated_by,
            action="SECRET_CATEGORY_KEY_ROTATED",
            resource_type="VaultSecret",
            metadata={
                "category": category,
                "secrets_re_encrypted": count,
                "errors_count": len(errors),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.critical(
            "SecretsVault: Category key rotated for '%s' — %d secrets "
            "re-encrypted, %d errors",
            category,
            count,
            len(errors),
        )

        return {
            "category": category,
            "secrets_re_encrypted": count,
            "errors": errors,
        }
