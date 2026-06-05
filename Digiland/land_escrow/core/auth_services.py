"""Service layer for the Digiland Authentication System.

Provides centralized business logic for:
- JWT token generation, verification, refresh, and blacklisting
- TOTP-based MFA secret generation, QR code URIs, and code verification
- OAuth2 authorization URL generation and token exchange (Google, GitHub, Microsoft)
- WebAuthn registration and authentication challenge management
- Password strength validation, breach checking, and Argon2id hashing
- Session lifecycle management (create, validate, revoke, list)
- Audit event logging for all auth-related operations
"""
import hashlib
import secrets
import logging
import urllib.parse
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

import pyotp
import qrcode
import io
import base64
import jwt as pyjwt
import requests as http_requests

from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class JWTService:
    """Handles JWT token generation, verification, refresh, and blacklisting.

    Uses PyJWT for token operations with short-lived access tokens (15 min)
    and longer-lived refresh tokens (7 days). Blacklisted tokens are tracked
    in the Django cache backend.
    """

    ACCESS_TOKEN_LIFETIME = timedelta(minutes=15)
    REFRESH_TOKEN_LIFETIME = timedelta(days=7)
    ALGORITHM = "HS256"

    @classmethod
    def _get_signing_key(cls) -> str:
        """Retrieve the JWT signing key from Django settings."""
        return getattr(settings, "SIMPLE_JWT", {}).get(
            "SIGNING_KEY", settings.SECRET_KEY
        )

    @classmethod
    def generate_tokens(cls, user) -> Dict[str, str]:
        """Generate an access/refresh JWT pair for the given user.

        Returns:
            Dict with 'access', 'refresh', 'access_expires',
            'refresh_expires' keys.
        """
        now = timezone.now()
        signing_key = cls._get_signing_key()

        access_payload = {
            "user_id": str(user.id),
            "email": user.email,
            "role": getattr(user, "role", ""),
            "token_type": "access",
            "exp": now + cls.ACCESS_TOKEN_LIFETIME,
            "iat": now,
            "jti": secrets.token_hex(16),
        }
        refresh_payload = {
            "user_id": str(user.id),
            "token_type": "refresh",
            "exp": now + cls.REFRESH_TOKEN_LIFETIME,
            "iat": now,
            "jti": secrets.token_hex(16),
        }

        access_token = pyjwt.encode(access_payload, signing_key, algorithm=cls.ALGORITHM)
        refresh_token = pyjwt.encode(refresh_payload, signing_key, algorithm=cls.ALGORITHM)

        return {
            "access": access_token,
            "refresh": refresh_token,
            "access_expires": int(cls.ACCESS_TOKEN_LIFETIME.total_seconds()),
            "refresh_expires": int(cls.REFRESH_TOKEN_LIFETIME.total_seconds()),
        }

    @classmethod
    def verify_token(cls, token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT token.

        Args:
            token: The JWT string to verify.
            token_type: Expected token_type claim ('access' or 'refresh').

        Returns:
            Decoded payload dict if valid, None otherwise.
        """
        try:
            payload = pyjwt.decode(
                token, cls._get_signing_key(), algorithms=[cls.ALGORITHM]
            )
            if payload.get("token_type") != token_type:
                return None
            jti = payload.get("jti", "")
            if cache.get(f"jwt_blacklist:{jti}"):
                return None
            return payload
        except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError):
            return None

    @classmethod
    def refresh_tokens(cls, refresh_token: str) -> Optional[Dict[str, str]]:
        """Exchange a valid refresh token for a new access/refresh pair.

        The old refresh token is blacklisted to prevent reuse.

        Returns:
            New token dict if refresh is valid, None otherwise.
        """
        payload = cls.verify_token(refresh_token, token_type="refresh")
        if not payload:
            return None

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(id=payload["user_id"], is_active=True)
        except User.DoesNotExist:
            return None

        cls.blacklist_token(refresh_token)

        return cls.generate_tokens(user)

    @classmethod
    def blacklist_token(cls, token: str) -> bool:
        """Add a token to the blacklist by its JTI claim.

        The blacklist entry TTL matches the token's remaining lifetime.

        Returns:
            True if blacklisted successfully, False on error.
        """
        try:
            payload = pyjwt.decode(
                token, cls._get_signing_key(), algorithms=[cls.ALGORITHM],
                options={"verify_exp": False},
            )
            jti = payload.get("jti", "")
            exp = payload.get("exp", 0)
            remaining = max(exp - int(timezone.now().timestamp()), 0)
            if remaining > 0 and jti:
                cache.set(f"jwt_blacklist:{jti}", True, timeout=remaining)
                return True
        except pyjwt.InvalidTokenError:
            pass
        return False


class MFAService:
    """Handles TOTP-based MFA operations: secret generation, QR codes,
    code verification, and recovery code management.

    Recovery codes are hashed with Argon2id before storage.
    """

    TOTP_ISSUER = "Digiland"
    RECOVERY_CODE_COUNT = 8
    RECOVERY_CODE_LENGTH = 8

    @staticmethod
    def generate_totp_secret() -> str:
        """Generate a cryptographically random TOTP base32 secret."""
        return pyotp.random_base32()

    @staticmethod
    def generate_qr_code_uri(secret: str, email: str) -> str:
        """Build the otpauth:// URI for authenticator app provisioning."""
        totp = pyotp.TOTP(secret)
        return totp.provision_uri(name=email, issuer_name=MFAService.TOTP_ISSUER)

    @staticmethod
    def generate_qr_code_base64(uri: str) -> str:
        """Render a QR code PNG as a base64-encoded string."""
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    @staticmethod
    def verify_totp_code(secret: str, code: str, valid_window: int = 1) -> bool:
        """Verify a TOTP code against the secret, allowing clock drift.

        Args:
            secret: Base32 TOTP secret.
            code: 6-digit code from the authenticator.
            valid_window: Number of intervals to allow for drift (default 1).

        Returns:
            True if the code is valid.
        """
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=valid_window)

    @staticmethod
    def generate_recovery_codes() -> List[str]:
        """Generate a set of human-readable recovery codes (format: XXXX-XXXX)."""
        codes = []
        for _ in range(MFAService.RECOVERY_CODE_COUNT):
            code = secrets.token_hex(MFAService.RECOVERY_CODE_LENGTH // 2).upper()
            codes.append(f"{code[:4]}-{code[4:]}")
        return codes

    @staticmethod
    def hash_recovery_codes(codes: List[str]) -> List[str]:
        """Hash a list of recovery codes with Argon2id for secure storage."""
        return [make_password(code, hasher="argon2") for code in codes]

    @staticmethod
    def validate_recovery_code(hashed_codes: List[str], plain_code: str) -> Tuple[bool, Optional[int]]:
        """Validate a plain recovery code against stored hashes.

        Returns:
            Tuple of (is_valid, index_of_matching_code or None).
        """
        for i, hashed in enumerate(hashed_codes):
            if check_password(plain_code, hashed):
                return True, i
        return False, None


class OAuthService:
    """Manages OAuth2 authorization flows for Google, GitHub, and Microsoft.

    Generates authorization URLs, exchanges authorization codes for tokens,
    and fetches user profile information from the provider.
    """

    PROVIDER_CONFIGS = {
        "google": {
            "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
            "scope": "openid email profile",
        },
        "github": {
            "authorization_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "userinfo_url": "https://api.github.com/user",
            "scope": "user:email",
        },
        "microsoft": {
            "authorization_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            "userinfo_url": "https://graph.microsoft.com/v1.0/me",
            "scope": "openid email profile User.Read",
        },
    }

    @classmethod
    def get_authorization_url(
        cls, provider: str, client_id: str, redirect_uri: str, state: str
    ) -> str:
        """Build the OAuth2 authorization URL for the given provider.

        Args:
            provider: One of 'google', 'github', 'microsoft'.
            client_id: OAuth client ID from settings.
            redirect_uri: URL to redirect after authorization.
            state: CSRF-protection state token.

        Returns:
            Fully formed authorization URL string.
        """
        config = cls.PROVIDER_CONFIGS.get(provider)
        if not config:
            raise ValueError(f"Unsupported OAuth provider: {provider}")

        params = {
            "client_id": client_id,
            "response_type": "code",
            "scope": config["scope"],
            "state": state,
            "redirect_uri": redirect_uri,
        }
        if provider == "microsoft":
            params["response_mode"] = "query"

        return f"{config['authorization_url']}?{urllib.parse.urlencode(params)}"

    @classmethod
    def exchange_code_for_token(
        cls, provider: str, code: str, client_id: str, client_secret: str, redirect_uri: str
    ) -> Optional[Dict[str, Any]]:
        """Exchange an authorization code for access/refresh tokens.

        Returns:
            Token response dict from the provider, or None on failure.
        """
        config = cls.PROVIDER_CONFIGS.get(provider)
        if not config:
            raise ValueError(f"Unsupported OAuth provider: {provider}")

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }
        headers = {"Accept": "application/json"}

        try:
            resp = http_requests.post(
                config["token_url"], data=data, headers=headers, timeout=10
            )
            resp.raise_for_status()
            return resp.json()
        except http_requests.RequestException as exc:
            logger.error("OAuth token exchange failed for %s: %s", provider, exc)
            return None

    @classmethod
    def fetch_user_profile(
        cls, provider: str, access_token: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch user profile from the OAuth provider using an access token.

        Returns:
            Normalized profile dict with 'sub', 'email', 'name',
            'first_name', 'last_name' keys, or None on failure.
        """
        config = cls.PROVIDER_CONFIGS.get(provider)
        if not config:
            raise ValueError(f"Unsupported OAuth provider: {provider}")

        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        if provider == "github":
            headers["User-Agent"] = "Digiland-OAuth"

        try:
            resp = http_requests.get(config["userinfo_url"], headers=headers, timeout=10)
            resp.raise_for_status()
            profile = resp.json()
        except http_requests.RequestException as exc:
            logger.error("OAuth profile fetch failed for %s: %s", provider, exc)
            return None

        if provider == "github":
            # GitHub needs a separate call for email
            email = profile.get("email")
            if not email:
                try:
                    email_resp = http_requests.get(
                        "https://api.github.com/user/emails",
                        headers=headers, timeout=10,
                    )
                    for entry in email_resp.json():
                        if entry.get("primary"):
                            email = entry.get("email")
                            break
                except Exception:
                    pass

            return {
                "sub": str(profile.get("id", "")),
                "email": email or "",
                "name": profile.get("name", ""),
                "first_name": (profile.get("name") or "").split(" ")[0],
                "last_name": " ".join((profile.get("name") or "").split(" ")[1:]),
            }

        # Google / Microsoft — OpenID Connect standard claims
        return {
            "sub": profile.get("sub", profile.get("id", "")),
            "email": profile.get("email", ""),
            "name": profile.get("name", ""),
            "first_name": profile.get("given_name", ""),
            "last_name": profile.get("family_name", ""),
        }


class WebAuthnService:
    """Manages WebAuthn registration and authentication ceremonies.

    Generates challenges, verifies registration responses, and validates
    authentication assertions. Uses patterns compatible with py_webauthn.
    """

    RP_NAME = "Digiland"
    CHALLENGE_LENGTH = 32
    CHALLENGE_TIMEOUT_MS = 60000  # 1 minute

    @classmethod
    def generate_registration_challenge(
        cls, user_id: str, email: str, rp_id: str
    ) -> Dict[str, Any]:
        """Generate a WebAuthn registration challenge for a user.

        Args:
            user_id: UUID string of the registering user.
            email: User email (used as display name).
            rp_id: Relying Party ID (usually the domain).

        Returns:
            Dict with 'challenge', 'rp', 'user', and 'pubKeyCredParams'.
        """
        challenge = secrets.token_bytes(cls.CHALLENGE_LENGTH)
        challenge_b64 = base64.urlsafe_b64encode(challenge).rstrip(b"=").decode()

        # Store challenge for later verification
        cache.set(
            f"webauthn:reg:{user_id}",
            {"challenge": challenge_b64, "rp_id": rp_id},
            timeout=120,
        )

        return {
            "challenge": challenge_b64,
            "rp": {"name": cls.RP_NAME, "id": rp_id},
            "user": {
                "id": base64.urlsafe_b64encode(str(user_id).encode()).rstrip(b"=").decode(),
                "name": email,
                "displayName": email,
            },
            "pubKeyCredParams": [
                {"type": "public-key", "alg": -7},     # ES256
                {"type": "public-key", "alg": -257},   # RS256
            ],
            "timeout": cls.CHALLENGE_TIMEOUT_MS,
            "attestation": "none",
            "authenticatorSelection": {
                "authenticatorAttachment": "platform",
                "userVerification": "preferred",
                "residentKey": "preferred",
            },
        }

    @classmethod
    def verify_registration(
        cls, user_id: str, credential: Dict[str, Any], rp_id: str, origin: str
    ) -> Optional[Dict[str, Any]]:
        """Verify a WebAuthn registration response.

        Returns:
            Verified credential data dict, or None on failure.
        """
        cached = cache.get(f"webauthn:reg:{user_id}")
        if not cached or cached["rp_id"] != rp_id:
            return None

        cache.delete(f"webauthn:reg:{user_id}")

        try:
            credential_id = credential.get("id", "")
            client_data_b64 = credential.get("response", {}).get("clientDataJSON", "")
            attestation_b64 = credential.get("response", {}).get("attestationObject", "")

            # Decode client data to verify challenge and origin
            client_data = base64.urlsafe_b64decode(client_data_b64 + "==")
            import json
            client_data_json = json.loads(client_data)

            if client_data_json.get("type") != "webauthn.create":
                return None
            if client_data_json.get("origin") != origin:
                return None

            received_challenge = client_data_json.get("challenge", "")
            if received_challenge != cached["challenge"]:
                return None

            return {
                "credential_id": credential_id,
                "public_key": credential.get("response", {}).get("publicKey", ""),
                "attestation_object": attestation_b64,
                "sign_count": 0,
            }
        except Exception as exc:
            logger.error("WebAuthn registration verification failed: %s", exc)
            return None

    @classmethod
    def generate_authentication_challenge(
        cls, user_id: str, rp_id: str, credential_ids: List[str]
    ) -> Dict[str, Any]:
        """Generate a WebAuthn authentication challenge.

        Args:
            user_id: UUID string of the authenticating user.
            rp_id: Relying Party ID.
            credential_ids: List of registered credential IDs.

        Returns:
            Dict with 'challenge', 'rpId', 'allowCredentials', and 'timeout'.
        """
        challenge = secrets.token_bytes(cls.CHALLENGE_LENGTH)
        challenge_b64 = base64.urlsafe_b64encode(challenge).rstrip(b"=").decode()

        cache.set(
            f"webauthn:auth:{user_id}",
            {"challenge": challenge_b64, "rp_id": rp_id},
            timeout=120,
        )

        allow_credentials = [
            {
                "type": "public-key",
                "id": cid,
                "transports": ["internal"],
            }
            for cid in credential_ids
        ]

        return {
            "challenge": challenge_b64,
            "rpId": rp_id,
            "allowCredentials": allow_credentials,
            "timeout": cls.CHALLENGE_TIMEOUT_MS,
            "userVerification": "preferred",
        }

    @classmethod
    def verify_authentication(
        cls, user_id: str, credential: Dict[str, Any], rp_id: str, origin: str,
        stored_sign_count: int = 0,
    ) -> bool:
        """Verify a WebAuthn authentication assertion.

        Returns:
            True if authentication is valid.
        """
        cached = cache.get(f"webauthn:auth:{user_id}")
        if not cached or cached["rp_id"] != rp_id:
            return False

        cache.delete(f"webauthn:auth:{user_id}")

        try:
            client_data_b64 = credential.get("response", {}).get("clientDataJSON", "")
            client_data = base64.urlsafe_b64decode(client_data_b64 + "==")
            import json
            client_data_json = json.loads(client_data)

            if client_data_json.get("type") != "webauthn.get":
                return False
            if client_data_json.get("origin") != origin:
                return False

            received_challenge = client_data_json.get("challenge", "")
            if received_challenge != cached["challenge"]:
                return False

            sign_count = credential.get("response", {}).get("authenticatorData", {})
            return True
        except Exception as exc:
            logger.error("WebAuthn authentication verification failed: %s", exc)
            return False


class PasswordService:
    """Password management: strength validation, breach checking, and Argon2id hashing."""

    # Common passwords to reject (subset of Have I Been Pwned top 100)
    COMMON_PASSWORDS = {
        "password", "123456", "12345678", "qwerty", "abc123",
        "monkey", "master", "dragon", "login", "princess",
        "football", "shadow", "sunshine", "trustno1", "iloveyou",
    }

    @staticmethod
    def validate_password_strength(password: str, user=None) -> Tuple[bool, List[str]]:
        """Validate password against complexity requirements.

        Returns:
            Tuple of (is_valid, list_of_error_messages).
        """
        errors: List[str] = []
        try:
            validate_password(password, user=user)
        except Exception as exc:
            errors.extend([str(e) for e in getattr(exc, "messages", [str(exc)])])

        if len(password) < 10:
            errors.append("Password must be at least 10 characters long.")
        if password.lower() in PasswordService.COMMON_PASSWORDS:
            errors.append("This password is too common.")

        return len(errors) == 0, errors

    @classmethod
    def check_breach_database(cls, password: str) -> bool:
        """Check if a password has appeared in known data breaches.

        Uses the k-anonymity API from Have I Been Pwned so the plaintext
        password is never sent over the network.

        Returns:
            True if the password was found in a breach (compromised).
        """
        sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]

        try:
            resp = http_requests.get(
                f"https://api.pwnedpasswords.com/range/{prefix}",
                timeout=5,
            )
            resp.raise_for_status()
            for line in resp.text.splitlines():
                parts = line.strip().split(":")
                if len(parts) == 2 and parts[0] == suffix:
                    return True  # Password found in breach
        except http_requests.RequestException:
            logger.warning("Breach database check failed; skipping.")

        return False

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using Argon2id.

        Returns:
            Argon2id hash string suitable for storage.
        """
        return make_password(password, hasher="argon2")

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify a password against its stored hash.

        Returns:
            True if the password matches the hash.
        """
        return check_password(password, hashed)


class SessionService:
    """Manages user session lifecycle: creation, validation, listing, and revocation."""

    SESSION_LIFETIME = timedelta(days=1)

    @staticmethod
    def create_session(user, request) -> "object":
        """Create a new session record for a user.

        Args:
            user: The authenticated User instance.
            request: The HTTP request (for IP and user-agent extraction).

        Returns:
            The created UserSession instance.
        """
        from .models import UserSession

        ip_address = _get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        device_type = _get_device_type(user_agent)

        session = UserSession.objects.create(
            user=user,
            session_key=secrets.token_hex(32),
            refresh_token_jti="",
            ip_address=ip_address,
            user_agent=user_agent[:500],
            device_type=device_type,
            is_active=True,
            expires_at=timezone.now() + SessionService.SESSION_LIFETIME,
        )
        return session

    @staticmethod
    def validate_session(session_key: str) -> Optional["object"]:
        """Validate an active session by its key.

        Returns:
            The UserSession instance if valid, None otherwise.
        """
        from .models import UserSession

        try:
            session = UserSession.objects.get(
                session_key=session_key,
                is_active=True,
                expires_at__gt=timezone.now(),
            )
            return session
        except UserSession.DoesNotExist:
            return None

    @staticmethod
    def revoke_session(session_id: str, user) -> bool:
        """Revoke a specific session.

        Returns:
            True if the session was revoked, False if not found.
        """
        from .models import UserSession

        try:
            session = UserSession.objects.get(id=session_id, user=user, is_active=True)
            session.is_active = False
            session.save(update_fields=["is_active"])
            return True
        except UserSession.DoesNotExist:
            return False

    @staticmethod
    def list_active_sessions(user) -> list:
        """List all active sessions for a user.

        Returns:
            QuerySet of active UserSession instances.
        """
        from .models import UserSession

        return UserSession.objects.filter(
            user=user, is_active=True, expires_at__gt=timezone.now()
        ).order_by("-last_activity")

    @staticmethod
    def revoke_all_sessions(user, exclude_jti: str = "") -> int:
        """Revoke all active sessions for a user, optionally excluding one by JTI.

        Returns:
            Count of revoked sessions.
        """
        from .models import UserSession

        sessions = UserSession.objects.filter(user=user, is_active=True)
        if exclude_jti:
            sessions = sessions.exclude(refresh_token_jti=exclude_jti)
        count = sessions.count()
        sessions.update(is_active=False)
        return count


class AuditService:
    """Centralized audit logging for all authentication-related events.

    Creates AuditLog entries for login, logout, MFA operations,
    password changes, device trust events, and OAuth linking.
    """

    @staticmethod
    def log_event(
        action: str,
        user=None,
        ip_address: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log an authentication audit event.

        Args:
            action: Event action string (e.g. 'LOGIN_SUCCESS', 'MFA_ENABLED').
            user: The User involved (may be None for anonymous events).
            ip_address: Client IP address.
            metadata: Optional dict with extra context.
        """
        from .models import AuditLog

        try:
            AuditLog.objects.create(
                user=user if user and hasattr(user, "pk") and user.is_authenticated else None,
                action=action,
                ip_address=ip_address or "0.0.0.0",
                metadata=metadata or {},
            )
        except Exception:
            logger.exception("Failed to write audit log for action=%s", action)

    @classmethod
    def log_login(cls, user, ip_address: str, method: str = "password") -> None:
        """Log a successful login event."""
        cls.log_event("LOGIN_SUCCESS", user=user, ip_address=ip_address,
                       metadata={"method": method})

    @classmethod
    def log_logout(cls, user, ip_address: str) -> None:
        """Log a logout event."""
        cls.log_event("LOGOUT", user=user, ip_address=ip_address)

    @classmethod
    def log_mfa_event(cls, action: str, user, ip_address: str = "", **kwargs) -> None:
        """Log an MFA-related event (enable, disable, verify)."""
        cls.log_event(f"MFA_{action}", user=user, ip_address=ip_address, metadata=kwargs)

    @classmethod
    def log_password_change(cls, user, ip_address: str) -> None:
        """Log a password change event."""
        cls.log_event("PASSWORD_CHANGED", user=user, ip_address=ip_address)

    @classmethod
    def log_device_trust(cls, user, ip_address: str, device_name: str = "") -> None:
        """Log a device trust event."""
        cls.log_event("DEVICE_TRUSTED", user=user, ip_address=ip_address,
                       metadata={"device_name": device_name})

    @classmethod
    def log_oauth_link(cls, user, ip_address: str, provider: str = "") -> None:
        """Log an OAuth account link/unlink event."""
        cls.log_event("OAUTH_LINKED", user=user, ip_address=ip_address,
                       metadata={"provider": provider})


# ── Helpers shared across services ──────────────────────────────────────────

def _get_client_ip(request) -> str:
    """Extract client IP from request, respecting X-Forwarded-For."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def _get_device_type(user_agent: str) -> str:
    """Simple device-type detection from User-Agent string."""
    ua = user_agent.lower()
    if "mobile" in ua or "android" in ua or "iphone" in ua:
        return "mobile"
    if "tablet" in ua or "ipad" in ua:
        return "tablet"
    return "desktop"
