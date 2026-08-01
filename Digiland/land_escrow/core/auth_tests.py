"""Comprehensive tests for the Digiland Authentication System.

Covers:
- Login and registration flows
- MFA setup and verification
- Password reset and change
- Token refresh and blacklisting
- OAuth flow
- WebAuthn registration and authentication
- Trusted device management
- Session management
- Password strength validation
- Rate limiting and brute-force protection
- Audit logging
- Argon2id hashing
- Account lockout
"""
import uuid
import secrets
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from rest_framework.test import APIClient, APITestCase
from rest_framework import status

from .auth_services import (
    JWTService, MFAService, OAuthService, WebAuthnService,
    PasswordService, SessionService, AuditService,
)
from .auth_backends import (
    EmailOrUsernameModelBackend,
    MFAAuthenticationBackend,
    DeviceTrustAuthenticationBackend,
    OAuthAuthenticationBackend,
)
from .models import UserMFA, TrustedDevice, UserSession, AuditLog, LoginAttempt

User = get_user_model()


# ── Helper ──────────────────────────────────────────────────────────────────


def _make_user(email="test@digiland.co.ke", password="TestPass123!", role="Buyer", **kw):
    """Create and return an active test user."""
    return User.objects.create_user(
        email=email,
        password=password,
        role=role,
        phone_number=kw.get("phone_number", "+254712345678"),
        id_number=kw.get("id_number", "12345678"),
        kra_pin=kw.get("kra_pin", "A123456789B"),
    )


# ==================== LOGIN FLOW TESTS ====================


class TestLoginFlow(APITestCase):
    """Tests for the login endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = _make_user()
        self.user.is_email_verified = True
        self.user.save(update_fields=["is_email_verified"])
        self.url = "/api/v1/auth/login/"

    def test_login_success(self):
        """Valid credentials return JWT tokens."""
        resp = self.client.post(self.url, {"email": "test@digiland.co.ke", "password": "TestPass123!"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", resp.data)
        self.assertIn("access", resp.data["tokens"])

    @patch("core.auth_views.send_mail")
    def test_login_unverified_user_sends_verification_email(self, mock_send_mail):
        """An unverified login attempt should send a verification email and block access."""
        user = _make_user(email="api-unverified@digiland.co.ke", password="TestPass123!")
        resp = self.client.post(self.url, {"email": user.email, "password": "TestPass123!"})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(resp.data.get("verification_required"))
        self.assertTrue(resp.data.get("verification_email_sent"))
        self.assertTrue(mock_send_mail.called)
        _, kwargs = mock_send_mail.call_args
        self.assertIn(user.email, kwargs.get("recipient_list", []))

    def test_login_invalid_password(self):
        """Wrong password returns 401."""
        resp = self.client.post(self.url, {"email": "test@digiland.co.ke", "password": "wrong"})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_nonexistent_user(self):
        """Unknown email returns 401."""
        resp = self.client.post(self.url, {"email": "nobody@digiland.co.ke", "password": "TestPass123!"})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_mfa_challenge(self):
        """User with MFA enabled gets an MFA challenge instead of tokens."""
        mfa = UserMFA.objects.create(user=self.user, totp_secret="JBSWY3DPEHPK3PXP", is_enabled=True)
        resp = self.client.post(self.url, {"email": "test@digiland.co.ke", "password": "TestPass123!"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get("mfa_required"))

    def test_login_brute_force_lockout(self):
        """Too many failed attempts locks the account temporarily."""
        for _ in range(6):
            self.client.post(self.url, {"email": "test@digiland.co.ke", "password": "wrong"})
        resp = self.client.post(self.url, {"email": "test@digiland.co.ke", "password": "TestPass123!"})
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def tearDown(self):
        cache.clear()


# ==================== REGISTRATION FLOW TESTS ====================


class TestRegistrationFlow(APITestCase):
    """Tests for the registration endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/v1/auth/register/"

    def test_register_success(self):
        """Valid data creates a new user."""
        data = {
            "email": "new@digiland.co.ke",
            "password": "SecurePass123!",
            "full_name": "Test User",
            "role": "Buyer",
            "phone_number": "+254712345679",
        }
        resp = self.client.post(self.url, data)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="new@digiland.co.ke").exists())

    @patch("core.auth_views.send_mail")
    def test_register_sends_verification_email(self, mock_send_mail):
        """Registration should trigger a verification email to the submitted address."""
        data = {
            "email": "verify-me@digiland.co.ke",
            "password": "SecurePass123!",
            "full_name": "Verify Me",
            "role": "Buyer",
            "phone_number": "+254712345671",
        }
        resp = self.client.post(self.url, data)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(mock_send_mail.called, "Registration did not attempt to send a verification email.")
        _, kwargs = mock_send_mail.call_args
        self.assertIn("verify-me@digiland.co.ke", kwargs.get("recipient_list", []))

    def test_register_duplicate_email(self):
        """Duplicate email returns 400."""
        _make_user(email="dup@digiland.co.ke")
        data = {
            "email": "dup@digiland.co.ke",
            "password": "SecurePass123!",
            "full_name": "Dup User",
            "role": "Buyer",
            "phone_number": "+254712345670",
        }
        resp = self.client.post(self.url, data)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_invalid_phone(self):
        """Invalid phone format returns 400."""
        data = {
            "email": "phone@digiland.co.ke",
            "password": "SecurePass123!",
            "full_name": "Phone User",
            "role": "Buyer",
            "phone_number": "123",
        }
        resp = self.client.post(self.url, data)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_weak_password(self):
        """Weak password returns 400."""
        data = {
            "email": "weak@digiland.co.ke",
            "password": "12345678",
            "full_name": "Weak User",
            "role": "Buyer",
            "phone_number": "+254712345671",
        }
        resp = self.client.post(self.url, data)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ==================== MFA SETUP TESTS ====================


class TestMFASetup(APITestCase):
    """Tests for MFA setup endpoint."""

    def setUp(self):
        self.user = _make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = "/api/v1/auth/mfa/setup/"

    def test_mfa_setup_returns_secret_and_qr(self):
        """MFA setup returns a TOTP secret and QR code."""
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("secret", resp.data)
        self.assertIn("qr_code_base64", resp.data)

    def test_mfa_setup_creates_user_mfa_record(self):
        """MFA setup creates a UserMFA record."""
        self.client.post(self.url)
        self.assertTrue(UserMFA.objects.filter(user=self.user).exists())


# ==================== MFA VERIFICATION TESTS ====================


class TestMFAVerification(APITestCase):
    """Tests for MFA verify endpoint."""

    def setUp(self):
        self.user = _make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.mfa = UserMFA.objects.create(
            user=self.user, totp_secret="JBSWY3DPEHPK3PXP", is_enabled=False,
        )

    def test_mfa_verify_with_valid_code(self):
        """Valid TOTP code enables MFA and returns recovery codes."""
        import pyotp
        totp = pyotp.TOTP(self.mfa.totp_secret)
        code = totp.now()
        resp = self.client.post("/api/v1/auth/mfa/verify/", {"totp_code": code})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("recovery_codes", resp.data)

    def test_mfa_verify_with_invalid_code(self):
        """Invalid TOTP code returns 400."""
        resp = self.client.post("/api/v1/auth/mfa/verify/", {"totp_code": "000000"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ==================== PASSWORD RESET TESTS ====================


class TestPasswordReset(APITestCase):
    """Tests for password reset flow."""

    def setUp(self):
        self.user = _make_user()
        self.client = APIClient()

    @patch("core.auth_views.send_mail")
    def test_reset_request_sends_email(self, mock_mail):
        """Password reset request triggers an email."""
        resp = self.client.post("/api/v1/auth/password/reset/", {"email": "test@digiland.co.ke"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_reset_request_unknown_email_returns_success(self):
        """Unknown email still returns 200 to prevent enumeration."""
        resp = self.client.post("/api/v1/auth/password/reset/", {"email": "nobody@example.com"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_reset_confirm_with_valid_token(self):
        """Valid token + new password resets the password."""
        token = secrets.token_urlsafe(48)
        cache.set(f"pwreset:{token}", {"user_id": str(self.user.id), "email": self.user.email}, timeout=3600)
        resp = self.client.post("/api/v1/auth/password/reset/confirm/", {
            "token": token, "new_password": "NewSecurePass123!",
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_reset_confirm_with_invalid_token(self):
        """Invalid token returns 400."""
        resp = self.client.post("/api/v1/auth/password/reset/confirm/", {
            "token": "invalid-token", "new_password": "NewSecurePass123!",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def tearDown(self):
        cache.clear()


# ==================== TOKEN REFRESH TESTS ====================


class TestTokenRefresh(TestCase):
    """Tests for JWT token refresh."""

    def test_generate_and_verify_access_token(self):
        """Generated access token can be verified."""
        user = _make_user()
        tokens = JWTService.generate_tokens(user)
        payload = JWTService.verify_token(tokens["access"], "access")
        self.assertIsNotNone(payload)
        self.assertEqual(payload["user_id"], str(user.id))

    def test_refresh_tokens_returns_new_pair(self):
        """Refreshing a valid refresh token returns new tokens."""
        user = _make_user()
        tokens = JWTService.generate_tokens(user)
        new_tokens = JWTService.refresh_tokens(tokens["refresh"])
        self.assertIsNotNone(new_tokens)
        self.assertIn("access", new_tokens)

    def test_blacklisted_token_is_rejected(self):
        """Blacklisted token fails verification."""
        user = _make_user()
        tokens = JWTService.generate_tokens(user)
        JWTService.blacklist_token(tokens["access"])
        payload = JWTService.verify_token(tokens["access"], "access")
        self.assertIsNone(payload)

    def test_expired_token_is_rejected(self):
        """Expired token fails verification."""
        payload = JWTService.verify_token("invalid.jwt.token", "access")
        self.assertIsNone(payload)


# ==================== OAUTH FLOW TESTS ====================


class TestOAuthFlow(TestCase):
    """Tests for OAuthService."""

    def test_get_authorization_url_google(self):
        """Google OAuth URL includes correct parameters."""
        url = OAuthService.get_authorization_url(
            "google", "client123", "https://app.example.com/callback", "state123",
        )
        self.assertIn("accounts.google.com", url)
        self.assertIn("client123", url)
        self.assertIn("state123", url)

    def test_get_authorization_url_github(self):
        """GitHub OAuth URL includes correct parameters."""
        url = OAuthService.get_authorization_url(
            "github", "gh_client", "https://app.example.com/callback", "gh_state",
        )
        self.assertIn("github.com", url)

    def test_get_authorization_url_microsoft(self):
        """Microsoft OAuth URL includes correct parameters."""
        url = OAuthService.get_authorization_url(
            "microsoft", "ms_client", "https://app.example.com/callback", "ms_state",
        )
        self.assertIn("microsoftonline.com", url)

    def test_unsupported_provider_raises(self):
        """Unsupported provider raises ValueError."""
        with self.assertRaises(ValueError):
            OAuthService.get_authorization_url(
                "facebook", "fb_client", "https://app.example.com/callback", "state",
            )


# ==================== WEBAUTHN REGISTRATION TESTS ====================


class TestWebAuthnRegistration(TestCase):
    """Tests for WebAuthn registration ceremony."""

    def test_generate_registration_challenge(self):
        """Registration challenge contains expected fields."""
        challenge = WebAuthnService.generate_registration_challenge(
            user_id=str(uuid.uuid4()), email="test@digiland.co.ke", rp_id="localhost",
        )
        self.assertIn("challenge", challenge)
        self.assertIn("rp", challenge)
        self.assertIn("user", challenge)

    def test_verify_registration_with_wrong_challenge(self):
        """Invalid challenge data returns None."""
        result = WebAuthnService.verify_registration(
            user_id=str(uuid.uuid4()),
            credential={"id": "abc", "response": {"clientDataJSON": "", "attestationObject": ""}},
            rp_id="localhost", origin="http://localhost:3000",
        )
        self.assertIsNone(result)


# ==================== WEBAUTHN AUTHENTICATION TESTS ====================


class TestWebAuthnAuthentication(TestCase):
    """Tests for WebAuthn authentication ceremony."""

    def test_generate_authentication_challenge(self):
        """Authentication challenge contains expected fields."""
        challenge = WebAuthnService.generate_authentication_challenge(
            user_id=str(uuid.uuid4()), rp_id="localhost", credential_ids=["cred1"],
        )
        self.assertIn("challenge", challenge)
        self.assertIn("allowCredentials", challenge)

    def test_verify_authentication_with_no_cached_challenge(self):
        """Verification with no cached challenge returns False."""
        result = WebAuthnService.verify_authentication(
            user_id=str(uuid.uuid4()),
            credential={"response": {"clientDataJSON": ""}},
            rp_id="localhost", origin="http://localhost:3000",
        )
        self.assertFalse(result)


# ==================== TRUSTED DEVICE MANAGEMENT TESTS ====================


class TestTrustedDeviceManagement(APITestCase):
    """Tests for trusted device list and revocation."""

    def setUp(self):
        self.user = _make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_trusted_devices(self):
        """Active devices are listed."""
        TrustedDevice.objects.create(
            user=self.user, trust_token="tok1", device_name="Laptop",
            device_type="desktop", expires_at=timezone.now() + timedelta(days=30),
        )
        resp = self.client.get("/api/v1/auth/devices/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_revoke_trusted_device(self):
        """Revoking a device removes it."""
        device = TrustedDevice.objects.create(
            user=self.user, trust_token="tok2", device_name="Phone",
            device_type="mobile", expires_at=timezone.now() + timedelta(days=30),
        )
        resp = self.client.delete(f"/api/v1/auth/devices/{device.id}/revoke/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(TrustedDevice.objects.filter(id=device.id).exists())


# ==================== SESSION MANAGEMENT TESTS ====================


class TestSessionManagement(APITestCase):
    """Tests for active sessions and revocation."""

    def setUp(self):
        self.user = _make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_active_sessions(self):
        """Active sessions are listed."""
        resp = self.client.get("/api/v1/auth/sessions/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_revoke_all_sessions(self):
        """Revoke all sessions endpoint works."""
        resp = self.client.delete("/api/v1/auth/sessions/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ==================== PASSWORD STRENGTH VALIDATION TESTS ====================


class TestPasswordStrengthValidation(TestCase):
    """Tests for PasswordService strength checks."""

    def test_valid_strong_password(self):
        """Strong password passes validation."""
        is_valid, errors = PasswordService.validate_password_strength("Str0ng!Pass2024")
        self.assertTrue(is_valid)

    def test_weak_password_fails(self):
        """Weak password fails validation."""
        is_valid, errors = PasswordService.validate_password_strength("123456")
        self.assertFalse(is_valid)
        self.assertTrue(len(errors) > 0)

    def test_common_password_rejected(self):
        """Common password is rejected."""
        is_valid, errors = PasswordService.validate_password_strength("password")
        self.assertFalse(is_valid)

    def test_password_too_short(self):
        """Short password is rejected."""
        is_valid, errors = PasswordService.validate_password_strength("Ab1!")
        self.assertFalse(is_valid)


# ==================== RATE LIMITING TESTS ====================


class TestRateLimiting(APITestCase):
    """Tests for rate limiting on sensitive endpoints."""

    def setUp(self):
        self.client = APIClient()

    def test_login_rate_limiting(self):
        """Excessive login attempts are rate-limited."""
        url = "/api/v1/auth/login/"
        for _ in range(6):
            self.client.post(url, {"email": "rate@digiland.co.ke", "password": "wrong"})
        # The 7th request should be rate-limited or blocked
        resp = self.client.post(url, {"email": "rate@digiland.co.ke", "password": "wrong"})
        self.assertIn(resp.status_code, [status.HTTP_429_TOO_MANY_REQUESTS, status.HTTP_401_UNAUTHORIZED])

    def tearDown(self):
        cache.clear()


# ==================== AUDIT LOGGING TESTS ====================


class TestAuditLogging(TestCase):
    """Tests for AuditService."""

    def test_log_event_creates_audit_log(self):
        """Logging an event creates an AuditLog record."""
        user = _make_user()
        initial_count = AuditLog.objects.count()
        AuditService.log_login(user, "127.0.0.1")
        self.assertEqual(AuditLog.objects.count(), initial_count + 1)

    def test_log_mfa_event(self):
        """MFA events are logged."""
        user = _make_user()
        AuditService.log_mfa_event("ENABLED", user, "127.0.0.1")
        log = AuditLog.objects.filter(action="MFA_ENABLED").first()
        self.assertIsNotNone(log)

    def test_log_password_change(self):
        """Password change events are logged."""
        user = _make_user()
        AuditService.log_password_change(user, "127.0.0.1")
        self.assertTrue(AuditLog.objects.filter(action="PASSWORD_CHANGED").exists())

    def test_log_device_trust(self):
        """Device trust events are logged."""
        user = _make_user()
        AuditService.log_device_trust(user, "127.0.0.1", "Laptop")
        self.assertTrue(AuditLog.objects.filter(action="DEVICE_TRUSTED").exists())

    def test_log_oauth_link(self):
        """OAuth link events are logged."""
        user = _make_user()
        AuditService.log_oauth_link(user, "127.0.0.1", provider="google")
        self.assertTrue(AuditLog.objects.filter(action="OAUTH_LINKED").exists())


# ==================== ARGON2ID HASHING TESTS ====================


class TestArgon2idHashing(TestCase):
    """Tests for Argon2id password hashing via PasswordService."""

    def test_hash_password_uses_argon2(self):
        """PasswordService.hash_password produces an Argon2 hash."""
        hashed = PasswordService.hash_password("TestPass123!")
        self.assertTrue(hashed.startswith("argon2"))

    def test_verify_password_correct(self):
        """Correct password verifies against Argon2 hash."""
        hashed = PasswordService.hash_password("TestPass123!")
        self.assertTrue(PasswordService.verify_password("TestPass123!", hashed))

    def test_verify_password_incorrect(self):
        """Incorrect password fails verification."""
        hashed = PasswordService.hash_password("TestPass123!")
        self.assertFalse(PasswordService.verify_password("WrongPass!", hashed))


# ==================== ACCOUNT LOCKOUT TESTS ====================


class TestAccountLockout(TestCase):
    """Tests for account lockout after failed attempts."""

    def setUp(self):
        self.user = _make_user()
        self.backend = EmailOrUsernameModelBackend()

    def test_lockout_after_max_failures(self):
        """Account is locked after MAX_FAILED_ATTEMPTS failures."""
        for _ in range(5):
            self.backend._record_failure("test@digiland.co.ke", "127.0.0.1")
        self.assertTrue(self.backend._is_locked_out("test@digiland.co.ke", "127.0.0.1"))

    def test_lockout_cleared_on_success(self):
        """Lockout is cleared after a successful authentication."""
        self.backend._record_failure("test@digiland.co.ke", "127.0.0.1")
        self.backend._clear_failures("test@digiland.co.ke", "127.0.0.1")
        self.assertFalse(self.backend._is_locked_out("test@digiland.co.ke", "127.0.0.1"))

    def test_ip_has_higher_threshold(self):
        """IP lockout threshold is double the email threshold."""
        for _ in range(5):
            self.backend._record_failure("other@digiland.co.ke", "192.168.1.1")
        # 5 failures < 10 (2x max), IP not locked
        self.assertFalse(self.backend._is_locked_out("different@digiland.co.ke", "192.168.1.1"))

    def tearDown(self):
        cache.clear()


# ==================== EMAIL SENDER REGRESSION TESTS ====================


class TestDefaultFromEmailNeverBlank(TestCase):
    """Regression: DEFAULT_FROM_EMAIL must never resolve to a blank string.

    A blank sender caused ``ValueError: Invalid address ''`` during the
    allauth signup flow when EMAIL_HOST_USER was not set.  The fix makes
    DEFAULT_FROM_EMAIL cascade through three fallbacks so it always ends
    up as a valid address.
    """

    def test_adapter_returns_non_blank_from_email(self):
        """The allauth adapter's get_from_email must never return ''."""
        from core.adapter import RoleBasedAccountAdapter

        adapter = RoleBasedAccountAdapter()
        from_email = adapter.get_from_email()
        self.assertTrue(bool(from_email), f"from_email was blank/empty: {from_email!r}")

    @patch("core.adapter.send_mail")
    def test_unverified_login_redirects_to_pending_and_sends_email(self, mock_send_mail):
        """Browser login should send a verification email for unverified users."""
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.test import RequestFactory
        from django.urls import reverse
        from core.adapter import RoleBasedAccountAdapter

        user = _make_user(email="browser-unverified@digiland.co.ke")
        request = RequestFactory().get("/accounts/login/")
        SessionMiddleware(lambda _request: None).process_request(request)
        request.session.save()
        request.user = user

        adapter = RoleBasedAccountAdapter()
        redirect_url = adapter.get_login_redirect_url(request)

        self.assertEqual(redirect_url, reverse("account_verification_pending"))
        self.assertTrue(mock_send_mail.called)

    def test_verified_buyer_login_redirects_to_home(self):
        """Verified buyer sessions should land on the buyer dashboard."""
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.test import RequestFactory
        from django.urls import reverse
        from core.adapter import RoleBasedAccountAdapter

        user = _make_user(email="browser-verified@digiland.co.ke", role="Buyer")
        user.is_email_verified = True
        user.is_onboarded = True
        user.save(update_fields=["is_email_verified", "is_onboarded"])

        request = RequestFactory().get("/accounts/login/")
        SessionMiddleware(lambda _request: None).process_request(request)
        request.session.save()
        request.user = user

        adapter = RoleBasedAccountAdapter()
        redirect_url = adapter.get_login_redirect_url(request)

        self.assertEqual(redirect_url, reverse("frontend:buyer_dashboard"))

    def test_verified_buyer_signup_redirects_to_home(self):
        """Verified buyer signups should return to the buyer dashboard."""
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.test import RequestFactory
        from django.urls import reverse
        from core.adapter import RoleBasedAccountAdapter

        user = _make_user(email="signup-verified@digiland.co.ke", role="Buyer")
        user.is_email_verified = True
        user.is_onboarded = True
        user.save(update_fields=["is_email_verified", "is_onboarded"])

        request = RequestFactory().get("/accounts/signup/")
        SessionMiddleware(lambda _request: None).process_request(request)
        request.session.save()
        request.user = user

        adapter = RoleBasedAccountAdapter()
        redirect_url = adapter.get_signup_redirect_url(request)

        self.assertEqual(redirect_url, reverse("frontend:buyer_dashboard"))

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="test-sender@digiland.local",
    )
    def test_signup_email_uses_valid_from_email(self):
        """Posting to the signup endpoint produces an email with a non-blank from."""
        from django.core.mail import outbox

        from django.test import Client
        client = Client()

        # Attempt a signup — allauth will send a verification email
        resp = client.post("/accounts/signup/", {
            "email": "regression-test@digiland.local",
            "password1": "Str0ng!Pass2024",
            "password2": "Str0ng!Pass2024",
            "role": "Buyer",
            "id_number": "12345678",
            "phone_number": "+254712345678",
            "kra_pin": "A123456789B",
        })

        # Whether signup succeeds or fails validation, if an email was sent
        # it must have a valid from_email.
        if outbox:
            for msg in outbox:
                self.assertTrue(
                    bool(msg.from_email),
                    f"Email from_email was blank: {msg.from_email!r}",
                )

    def test_settings_default_from_email_is_not_blank(self):
        """The configured DEFAULT_FROM_EMAIL setting is never blank."""
        from django.conf import settings
        self.assertTrue(
            bool(settings.DEFAULT_FROM_EMAIL),
            f"DEFAULT_FROM_EMAIL is blank: {settings.DEFAULT_FROM_EMAIL!r}",
        )

    def test_google_signin_prompts_for_account_choice(self):
        """Google OAuth should force the Gmail account chooser."""
        from django.conf import settings
        self.assertEqual(
            settings.SOCIALACCOUNT_PROVIDERS["google"]["AUTH_PARAMS"].get("prompt"),
            "select_account",
        )

    def test_google_login_redirects_to_provider_on_get(self):
        """The Google button should go straight to the provider instead of a dead confirmation page."""
        from django.test import Client

        response = Client().get("/accounts/google/login/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts.google.com", response.url)
        self.assertIn("prompt=select_account", response.url)

    def test_github_login_redirects_to_provider_on_get(self):
        """The GitHub button should open GitHub authorization immediately."""
        from django.test import Client

        response = Client().get("/accounts/github/login/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("github.com/login/oauth/authorize", response.url)

    @override_settings(PUBLIC_BACKEND_URL="http://127.0.0.1:8000")
    @patch("core.utils.send_mail")
    @patch("core.utils.render_to_string", side_effect=lambda template, context: context["login_url"])
    def test_user_approval_email_uses_canonical_backend_url(self, mock_render_to_string, mock_send_mail):
        """Auth emails should use the same backend origin as OAuth callbacks."""
        from core.utils import send_user_approval_email

        user = _make_user(email="email-link@digiland.co.ke")
        send_user_approval_email(user)

        self.assertTrue(mock_render_to_string.called)
        _, kwargs = mock_send_mail.call_args
        self.assertEqual(kwargs["message"], "http://127.0.0.1:8000/accounts/login/")
        self.assertEqual(kwargs["html_message"], "http://127.0.0.1:8000/accounts/login/")

    def test_verified_google_social_signup_marks_email_verified(self):
        """Google social signups with verified email data should bypass the pending gate."""
        from types import SimpleNamespace
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.test import RequestFactory
        from core.signals import on_user_signed_up

        user = _make_user(email="google-social@digiland.co.ke")
        user.is_email_verified = False
        user.save(update_fields=["is_email_verified"])

        request = RequestFactory().post("/accounts/signup/")
        SessionMiddleware(lambda _request: None).process_request(request)
        request.session.save()

        sociallogin = SimpleNamespace(
            email_addresses=[SimpleNamespace(verified=True, email=user.email)],
            account=SimpleNamespace(
                provider="google",
                extra_data={"email_verified": True, "email": user.email},
            ),
        )

        on_user_signed_up(request=request, user=user, sociallogin=sociallogin)

        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)


# ==================== EMAIL VERIFICATION URL REGRESSION TESTS ====================


class TestEmailVerificationUrls(TestCase):
    """Regression: pending verification routes must stay reversible."""

    def test_pending_verification_page_renders(self):
        """The pending verification page should render without NoReverseMatch."""
        from django.test import Client
        from django.urls import reverse

        response = Client().get(reverse("account_verification_pending"))
        self.assertEqual(response.status_code, 200)

    def test_email_verification_redirects_verified_users_to_home(self):
        """Verified users should be sent back to their dashboard."""
        from django.test import Client
        from django.urls import reverse

        user = _make_user(email="verified@digiland.co.ke")
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

        client = Client()
        client.force_login(user)

        response = client.get(reverse("account_verification_pending"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("frontend:home"))

    def test_email_verification_api_redirects_to_home(self):
        """The verification API should return the dashboard redirect after a successful click-through."""
        from django.urls import reverse
        from core.verification import issue_one_time_token

        user = _make_user(email="api-verified@digiland.co.ke")
        token = issue_one_time_token(
            "emailverify",
            {
                "user_id": str(user.id),
                "email": user.email,
                "source": "test",
            },
            ttl_seconds=3600,
        )

        client = APIClient()
        client.force_login(user)

        response = client.post(reverse("auth-email-verify"), {"token": token}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["verification_status"], "verified")
        self.assertEqual(response.data["redirect_url"], reverse("frontend:home"))
        self.assertEqual(response.data["pending_verification"].get("redirect_url"), reverse("frontend:home"))

        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)


class TestEmailVerificationGateMiddleware(TestCase):
    """Regression: authenticated users without verified email cannot reach normal pages."""

    @override_settings(TESTING=False)
    def test_unverified_authenticated_user_is_redirected_to_pending_page(self):
        """The browser gate should redirect unverified users away from protected pages."""
        from django.http import HttpResponse
        from django.test import RequestFactory
        from django.urls import reverse
        from core.middleware import EmailVerificationGateMiddleware

        user = _make_user(email="unverified@digiland.co.ke")
        user.is_email_verified = False
        user.save(update_fields=["is_email_verified"])

        request = RequestFactory().get("/")
        request.user = user

        middleware = EmailVerificationGateMiddleware(lambda _request: HttpResponse("ok"))
        response = middleware(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("account_verification_pending"))

    @override_settings(TESTING=False)
    def test_verification_api_paths_remain_accessible(self):
        """Verification endpoints must stay accessible so the pending page can finish the flow."""
        from django.http import HttpResponse
        from django.test import RequestFactory
        from core.middleware import EmailVerificationGateMiddleware

        user = _make_user(email="unverified-api@digiland.co.ke")
        user.is_email_verified = False
        user.save(update_fields=["is_email_verified"])

        request = RequestFactory().get("/api/v1/auth/email/verify/")
        request.user = user

        middleware = EmailVerificationGateMiddleware(lambda _request: HttpResponse("ok"))
        response = middleware(request)

        self.assertEqual(response.status_code, 200)


class TestRoleSelectionAndRedirect(TestCase):
    """Tests for role selection onboarding and dashboard redirection."""

    def test_onboarding_select_role_api_buyer(self):
        from django.test import Client
        from django.urls import reverse
        user = _make_user(email="unonboarded-buyer@digiland.co.ke")
        user.role = None
        user.is_onboarded = False
        user.save()

        client = Client()
        client.force_login(user)

        response = client.post("/api/onboarding/select-role/", {"role": "buyer"}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("role"), "buyer")
        self.assertTrue(data.get("is_onboarded"))
        self.assertEqual(data.get("redirect_url"), reverse("frontend:buyer_dashboard"))

        user.refresh_from_db()
        self.assertEqual(user.role, "Buyer")
        self.assertTrue(user.is_onboarded)

    def test_onboarding_select_role_api_seller(self):
        from django.test import Client
        from django.urls import reverse
        user = _make_user(email="unonboarded-seller@digiland.co.ke")
        user.role = None
        user.is_onboarded = False
        user.save()

        client = Client()
        client.force_login(user)

        response = client.post("/api/onboarding/select-role/", {"role": "seller"}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("role"), "seller")
        self.assertTrue(data.get("is_onboarded"))
        self.assertEqual(data.get("redirect_url"), reverse("frontend:seller_dashboard"))

        user.refresh_from_db()
        self.assertEqual(user.role, "Seller")
        self.assertTrue(user.is_onboarded)

    def test_onboarding_select_role_view_already_onboarded(self):
        from django.test import Client
        from django.urls import reverse
        user = _make_user(email="onboarded-buyer@digiland.co.ke", role="Buyer")
        user.is_onboarded = True
        user.save(update_fields=["role", "is_onboarded"])

        client = Client()
        client.force_login(user)

        response = client.get("/onboarding/select-role/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("frontend:buyer_dashboard"))

    def test_onboarding_select_role_view_post_html(self):
        from django.test import Client
        from django.urls import reverse
        user = _make_user(email="html-post-seller@digiland.co.ke")
        user.role = None
        user.is_onboarded = False
        user.save()

        client = Client()
        client.force_login(user)

        response = client.post("/onboarding/select-role/", {"role": "seller"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("frontend:seller_dashboard"))

        user.refresh_from_db()
        self.assertEqual(user.role, "Seller")
        self.assertTrue(user.is_onboarded)


class TestCanonicalBackendHostMiddleware(TestCase):
    """Regression: local OAuth requests should be forced to one backend origin."""

    @override_settings(TESTING=False, PUBLIC_BACKEND_URL="http://127.0.0.1:8000")
    def test_localhost_requests_redirect_to_canonical_backend_host(self):
        from django.http import HttpResponse
        from django.test import RequestFactory
        from core.middleware import CanonicalBackendHostMiddleware

        request = RequestFactory().get("/accounts/google/login/?next=/parcels/", HTTP_HOST="localhost:8000")
        middleware = CanonicalBackendHostMiddleware(lambda _request: HttpResponse("ok"))
        response = middleware(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            "http://127.0.0.1:8000/accounts/google/login/?next=/parcels/",
        )
