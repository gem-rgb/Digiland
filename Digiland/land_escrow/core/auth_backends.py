"""Authentication backends for the Digiland platform.

Provides custom Django authentication backends:
- Argon2id password hasher configured as the default
- EmailOrUsernameModelBackend: authenticate with email OR username
- MFAAuthenticationBackend: verify MFA after initial auth
- DeviceTrustAuthenticationBackend: handle trusted device tokens
- OAuthAuthenticationBackend: handle OAuth provider authentication
- MFABackendMixin: shared MFA verification logic
"""
import logging
from typing import Any, Optional

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

User = get_user_model()


# ── Argon2id Password Hasher Configuration ─────────────────────────────────
# Add to Django settings: PASSWORD_HASHERS = ['core.auth_backends.Argon2idHasher', ...]

class Argon2idHasher:
    """Argon2id password hasher configuration for Digiland.

    This is NOT a Django BasePasswordHasher subclass — it is a
    configuration helper that documents the recommended hasher
    settings. To activate, ensure Django's PASSWORD_HASHERS list
    starts with 'django.contrib.auth.hashers.Argon2PasswordHasher'.

    Recommended settings.py entry::

        PASSWORD_HASHERS = [
            'django.contrib.auth.hashers.Argon2PasswordHasher',
            'django.contrib.auth.hashers.PBKDF2PasswordHasher',
            'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
        ]

    Argon2id parameters (overridable via settings.ARGON2_PARAMS):
        - time_cost:    Number of iterations (default 3)
        - memory_cost:  Memory in KiB (default 65536 = 64 MB)
        - parallelism:  Degree of parallelism (default 4)
    """

    DEFAULT_PARAMS = {
        "time_cost": 3,
        "memory_cost": 65536,
        "parallelism": 4,
    }

    @classmethod
    def get_params(cls) -> dict:
        """Return Argon2id parameters, allowing settings overrides."""
        from django.conf import settings
        return getattr(settings, "ARGON2_PARAMS", cls.DEFAULT_PARAMS)


# ── MFA Backend Mixin ──────────────────────────────────────────────────────


class MFABackendMixin:
    """Shared MFA verification logic for authentication backends.

    Provides methods to check whether a user has MFA enabled and
    verify TOTP codes or recovery codes during the authentication
    pipeline. Subclasses should call ``_verify_mfa()`` after
    successful password verification.
    """

    def _mfa_is_enabled(self, user) -> bool:
        """Check if MFA is enabled for the given user.

        Returns:
            True if the user has an active MFA configuration.
        """
        from .models import UserMFA
        try:
            mfa = UserMFA.objects.get(user=user, is_enabled=True)
            return True
        except UserMFA.DoesNotExist:
            return False

    def _verify_mfa(self, user, mfa_code: str) -> bool:
        """Verify a TOTP or recovery code against the user's MFA config.

        Args:
            user: The User instance.
            mfa_code: 6-digit TOTP code or recovery code string.

        Returns:
            True if verification succeeds.
        """
        from .models import UserMFA
        from .auth_services import MFAService

        try:
            mfa = UserMFA.objects.get(user=user, is_enabled=True)
        except UserMFA.DoesNotExist:
            return False

        # Try TOTP first
        if mfa.totp_secret and len(mfa_code) == 6 and mfa_code.isdigit():
            if MFAService.verify_totp_code(mfa.totp_secret, mfa_code):
                return True

        # Fall back to recovery code
        is_valid, idx = MFAService.validate_recovery_code(mfa.recovery_codes, mfa_code)
        if is_valid and idx is not None:
            mfa.recovery_codes.pop(idx)
            mfa.save()
            logger.info("Recovery code used for user %s", user.email)
            return True

        return False

    def _check_trusted_device(self, user, trust_token: str) -> bool:
        """Check if a device trust token is valid for the user.

        Returns:
            True if the device is trusted and MFA can be skipped.
        """
        from .models import TrustedDevice

        try:
            device = TrustedDevice.objects.get(
                user=user,
                trust_token=trust_token,
                expires_at__gt=timezone.now(),
            )
            device.last_used_at = timezone.now()
            device.save(update_fields=["last_used_at"])
            return True
        except TrustedDevice.DoesNotExist:
            return False


# ── Email or Username Authentication Backend ────────────────────────────────


class EmailOrUsernameModelBackend(ModelBackend):
    """Authenticate users with either their email address or a username.

    The Digiland User model uses email as the primary identifier, but
    this backend also checks a ``username`` field for backward
    compatibility. Brute-force protection is enforced via the cache.
    """

    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_WINDOW_SECONDS = 900  # 15 minutes

    def authenticate(self, request, username=None, password=None, email=None, **kwargs):
        """Attempt to authenticate a user by email, phone, or username + password.

        Args:
            request: The HTTP request (may be None).
            username: Email address, phone number, or username string.
            password: Plaintext password.
            email: Optional email keyword argument.

        Returns:
            The authenticated User, or None.
        """
        identifier = username or email or kwargs.get('email') or kwargs.get('phone_number')
        if not identifier or not password:
            return None

        # Check brute-force lockout
        ip_address = self._get_ip(request)
        if self._is_locked_out(identifier, ip_address):
            logger.warning("Account locked out: %s from IP %s", identifier, ip_address)
            return None

        # Try email/phone lookup first, then username
        user = self._find_user(identifier)
        if user is None:
            self._record_failure(identifier, ip_address)
            return None

        # Verify password
        if not user.check_password(password):
            self._record_failure(identifier, ip_address)
            return None

        # Check is_active
        if not user.is_active:
            return None

        # Clear failed attempts on success
        self._clear_failures(identifier, ip_address)
        return user

    def _find_user(self, identifier: str) -> Optional[User]:
        """Look up a user by email first, phone number, then by username."""
        try:
            return User.objects.get(email__iexact=identifier)
        except User.DoesNotExist:
            pass

        # Try phone lookup if numeric or formatted phone
        phone_clean = identifier.replace(' ', '').replace('-', '').replace('+', '')
        if phone_clean.isdigit():
            phone_tail = phone_clean[-9:] if len(phone_clean) >= 9 else phone_clean
            user = (
                User.objects.filter(phone_number__icontains=phone_tail).first()
                or User.objects.filter(phone_number__icontains=phone_clean).first()
            )
            if user:
                return user

        try:
            return User.objects.get(username__iexact=identifier)
        except (User.DoesNotExist, Exception):
            return None

    @classmethod
    def is_locked_out_check(cls, identifier: str, ip_address: str) -> tuple[bool, str]:
        """Return (is_locked, message) for lockout status."""
        email_key = cls._cache_key("email", identifier.lower().strip() if identifier else "")
        ip_key = cls._cache_key("ip", ip_address or "0.0.0.0")
        email_count = cache.get(email_key, 0)
        ip_count = cache.get(ip_key, 0)
        if email_count >= cls.MAX_FAILED_ATTEMPTS:
            return True, f"Account '{identifier}' is temporarily locked due to too many failed attempts. Try again in 15 minutes."
        if ip_count >= cls.MAX_FAILED_ATTEMPTS * 2:
            return True, "Too many failed attempts from your network. Try again in 15 minutes."
        return False, ""

    @classmethod
    def reset_lockout(cls, identifier: str, ip_address: str = "0.0.0.0") -> None:
        """Manually clear lockout counters for an identifier and IP."""
        if identifier:
            cache.delete(cls._cache_key("email", identifier.lower().strip()))
        if ip_address:
            cache.delete(cls._cache_key("ip", ip_address))

    def _is_locked_out(self, identifier: str, ip_address: str) -> bool:
        """Check if the account or IP is temporarily locked."""
        is_locked, _ = self.is_locked_out_check(identifier, ip_address)
        return is_locked

    def _record_failure(self, identifier: str, ip_address: str) -> None:
        """Increment failed-attempt counters."""
        email_key = self._cache_key("email", identifier.lower().strip())
        ip_key = self._cache_key("ip", ip_address)
        cache.set(email_key, cache.get(email_key, 0) + 1, timeout=self.LOCKOUT_WINDOW_SECONDS)
        cache.set(ip_key, cache.get(ip_key, 0) + 1, timeout=self.LOCKOUT_WINDOW_SECONDS)

    def _clear_failures(self, identifier: str, ip_address: str) -> None:
        """Clear failed-attempt counters after a successful login."""
        self.reset_lockout(identifier, ip_address)

    @staticmethod
    def _cache_key(prefix: str, value: str) -> str:
        return f"auth_fail:{prefix}:{value}"

    @staticmethod
    def _get_ip(request) -> str:
        if not request:
            return "0.0.0.0"
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "0.0.0.0")


# ── MFA Authentication Backend ─────────────────────────────────────────────


class MFAAuthenticationBackend(MFABackendMixin, ModelBackend):
    """Verify MFA after initial authentication.

    This backend is used in the second step of the two-factor
    authentication flow. The user must provide a valid TOTP code
    or recovery code in addition to their session credentials.

    Usage:
        The ``authenticate()`` method expects ``user_id`` and
        ``mfa_code`` keyword arguments.
    """

    def authenticate(self, request, user_id=None, mfa_code=None, **kwargs):
        """Verify MFA code for a previously authenticated user.

        Args:
            request: The HTTP request.
            user_id: UUID of the user requiring MFA verification.
            mfa_code: TOTP code or recovery code string.

        Returns:
            The User if MFA verification succeeds, None otherwise.
        """
        if not user_id or not mfa_code:
            return None

        try:
            user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return None

        if not self._mfa_is_enabled(user):
            return user  # MFA not enabled, pass through

        if self._verify_mfa(user, mfa_code):
            logger.info("MFA verification successful for user %s", user.email)
            return user

        logger.warning("MFA verification failed for user %s", user.email)
        return None


# ── Device Trust Authentication Backend ─────────────────────────────────────


class DeviceTrustAuthenticationBackend(MFABackendMixin, ModelBackend):
    """Handle trusted-device token authentication.

    If a user presents a valid device trust token, MFA can be
    skipped. This backend is intended for the MFA login-verify
    flow where the user opts to trust their device.
    """

    def authenticate(self, request, user_id=None, trust_token=None, **kwargs):
        """Verify a device trust token for a user.

        Args:
            request: The HTTP request.
            user_id: UUID of the user.
            trust_token: The device trust token string.

        Returns:
            The User if the trust token is valid, None otherwise.
        """
        if not user_id or not trust_token:
            return None

        try:
            user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return None

        if self._check_trusted_device(user, trust_token):
            logger.info("Trusted device auth for user %s", user.email)
            return user

        return None


# ── OAuth Authentication Backend ────────────────────────────────────────────


class OAuthAuthenticationBackend(ModelBackend):
    """Handle OAuth provider authentication.

    After the OAuth flow completes, this backend retrieves or creates
    the local User record associated with the OAuth provider account.
    It does NOT handle the OAuth redirect/token exchange — that is
    the responsibility of ``OAuthService`` and ``OAuthCallbackView``.
    """

    def authenticate(self, request, provider=None, provider_user_id=None, **kwargs):
        """Look up a user by their OAuth provider identity.

        Args:
            request: The HTTP request.
            provider: OAuth provider name (e.g. 'google', 'github').
            provider_user_id: User ID on the provider's system.

        Returns:
            The associated User, or None if not found.
        """
        if not provider or not provider_user_id:
            return None

        from .models import OAuthProvider, OAuthAccount

        try:
            oauth_provider = OAuthProvider.objects.get(provider=provider, is_active=True)
            account = OAuthAccount.objects.get(
                provider=oauth_provider,
                provider_user_id=str(provider_user_id),
            )
            user = account.user
            if user.is_active:
                logger.info("OAuth auth for user %s via %s", user.email, provider)
                return user
        except (OAuthProvider.DoesNotExist, OAuthAccount.DoesNotExist):
            pass

        return None
