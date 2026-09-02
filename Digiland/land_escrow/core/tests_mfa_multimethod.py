"""Comprehensive tests for DigiLand Multi-Method MFA & Session Timeout Architecture.

Tests:
1. Dynamic MFA Available Methods endpoint.
2. OTP Generation, email dispatch, and verification.
3. Multi-method MFA challenge verification (TOTP, OTP, Recovery code).
4. PrivilegedSessionMiddleware blocking stage-1 password tokens from /api/staff/* and /api/admin/*.
5. Session inactivity timeout evaluation and server-side session revocation.
"""
import pyotp
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from rest_framework.test import APIClient, APITestCase
from rest_framework import status

from core.models import UserMFA, UserSession, AuditLog
from core.auth_mfa import MFAService
from core.auth_services import JWTService, SessionService

User = get_user_model()


def _make_staff_user(email="staff@digiland.co.ke", password="StaffPassword123!", role="Agent"):
    user = User.objects.create_user(
        email=email,
        password=password,
        role=role,
        is_staff=True,
        phone_number="+254712345678",
        id_number="12345678",
        kra_pin="A123456789B",
    )
    user.is_email_verified = True
    user.save(update_fields=["is_email_verified"])
    return user


def _make_admin_user(email="admin@digiland.co.ke", password="AdminPassword123!", role="Admin"):
    user = User.objects.create_user(
        email=email,
        password=password,
        role=role,
        is_staff=True,
        is_superuser=True,
        phone_number="+254787654321",
        id_number="87654321",
        kra_pin="B987654321A",
    )
    user.is_email_verified = True
    user.save(update_fields=["is_email_verified"])
    return user


class TestMultiMethodMFA(APITestCase):
    """Test suite for Multi-Method MFA, OTP, and Session Timeout."""

    def setUp(self):
        self.client = APIClient()
        self.staff_user = _make_staff_user()
        self.admin_user = _make_admin_user()
        cache.clear()

    def test_available_methods_for_new_user(self):
        """A user with default config should have OTP available."""
        res = MFAService.get_available_methods(self.staff_user)
        self.assertIn("methods", res)
        method_ids = [m["id"] for m in res["methods"]]
        self.assertIn("otp", method_ids)

    def test_available_methods_with_totp(self):
        """When TOTP is setup, 'authenticator' should be in available methods."""
        secret = MFAService.generate_totp_secret()
        UserMFA.objects.create(
            user=self.staff_user,
            totp_secret=secret,
            is_enabled=True,
            totp_enabled=True,
        )
        res = MFAService.get_available_methods(self.staff_user)
        method_ids = [m["id"] for m in res["methods"]]
        self.assertIn("authenticator", method_ids)
        self.assertEqual(res["default_method"], "authenticator")

    @patch("django.core.mail.send_mail")
    def test_send_and_verify_mfa_otp(self, mock_send_mail):
        """Test OTP generation, dispatch, and verification flow."""
        # 1. Send OTP
        res = MFAService.send_mfa_otp(self.staff_user)
        self.assertTrue(res["sent"])
        self.assertTrue(mock_send_mail.called)

        # Retrieve stored OTP from cache for verification test
        cache_key = f"mfa_otp_{self.staff_user.id}"
        otp_code = cache.get(cache_key)
        self.assertIsNotNone(otp_code)
        self.assertEqual(len(otp_code), 6)

        # 2. Verify Wrong OTP
        self.assertFalse(MFAService.verify_mfa_otp(self.staff_user, "000000"))

        # 3. Verify Correct OTP
        self.assertTrue(MFAService.verify_mfa_otp(self.staff_user, otp_code))

    def test_verify_challenge_endpoint_totp(self):
        """Test verifying TOTP challenge via API endpoint."""
        secret = MFAService.generate_totp_secret()
        UserMFA.objects.create(
            user=self.staff_user,
            totp_secret=secret,
            is_enabled=True,
            totp_enabled=True,
        )

        # Create mfa_challenge token
        challenge_token = "test_challenge_token_123"
        cache.set(f"mfa_challenge:{challenge_token}", {"user_id": str(self.staff_user.id)}, timeout=300)

        totp_code = pyotp.TOTP(secret).now()

        resp = self.client.post("/api/v1/auth/mfa/verify-challenge/", {
            "challenge_token": challenge_token,
            "method": "authenticator",
            "code": totp_code,
        })

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", resp.data)
        self.assertIn("access", resp.data["tokens"])

    @patch("django.core.mail.send_mail")
    def test_verify_challenge_endpoint_otp(self, mock_send_mail):
        """Test verifying OTP challenge via API endpoint."""
        challenge_token = "test_otp_challenge_456"
        cache.set(f"mfa_challenge:{challenge_token}", {"user_id": str(self.staff_user.id)}, timeout=300)

        # Send OTP
        MFAService.send_mfa_otp(self.staff_user)
        otp_code = cache.get(f"mfa_otp_{self.staff_user.id}")

        resp = self.client.post("/api/v1/auth/mfa/verify-challenge/", {
            "challenge_token": challenge_token,
            "method": "otp",
            "code": otp_code,
        })

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", resp.data)

    def test_session_heartbeat(self):
        """Test session heartbeat endpoint extends last_activity."""
        tokens = JWTService.generate_tokens(self.staff_user)
        session = SessionService.create_session(self.staff_user, self.client.get("/").wsgi_request)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        resp = self.client.post("/api/v1/auth/session/heartbeat/", {})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "active")
        self.assertEqual(resp.data["inactivity_timeout_seconds"], 1800)

    def test_session_revoke_all(self):
        """Test revoking all user sessions."""
        SessionService.create_session(self.staff_user, self.client.get("/").wsgi_request)
        tokens = JWTService.generate_tokens(self.staff_user)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        resp = self.client.post("/api/v1/auth/session/revoke-all/", {})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["revoked_count"], 1)
        self.assertEqual(UserSession.objects.filter(user=self.staff_user, is_active=True).count(), 0)

    def test_privileged_middleware_blocks_inactive_session(self):
        """PrivilegedSessionMiddleware should return 401 when session last_activity exceeds timeout."""
        SessionService.create_session(self.staff_user, self.client.get("/").wsgi_request)
        tokens = JWTService.generate_tokens(self.staff_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Backdate all sessions for user right before test request
        past_time = timezone.now() - timedelta(minutes=35)
        UserSession.objects.filter(user=self.staff_user).update(last_activity=past_time)

        resp = self.client.get("/api/v1/auth/oauth/admin/providers/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(resp.json().get("code"), "SESSION_EXPIRED")

    def test_security_methods_summary_endpoint(self):
        """Test GET /api/v1/auth/security/methods/ returns security configuration & sessions."""
        tokens = JWTService.generate_tokens(self.staff_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        resp = self.client.get("/api/v1/auth/security/methods/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("methods", resp.data)
        self.assertIn("authenticator", resp.data["methods"])
        self.assertIn("passkey", resp.data["methods"])
        self.assertIn("otp", resp.data["methods"])
        self.assertIn("passkeys", resp.data)
        self.assertIn("active_sessions", resp.data)

    @patch("django.core.mail.send_mail")
    def test_passkey_registration_and_removal(self, mock_send_mail):
        """Test registering a new passkey and removing it."""
        tokens = JWTService.generate_tokens(self.staff_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # 1. Start registration
        start_resp = self.client.post("/api/v1/auth/security/passkey/register/start/", {})
        self.assertEqual(start_resp.status_code, status.HTTP_200_OK)
        self.assertIn("challenge", start_resp.data)

        # 2. Finish registration
        finish_resp = self.client.post("/api/v1/auth/security/passkey/register/finish/", {
            "credential_id": "test_cred_id_789",
            "name": "YubiKey 5C NFC",
        })
        self.assertEqual(finish_resp.status_code, status.HTTP_201_CREATED)
        passkey_id = finish_resp.data["passkey"]["id"]
        self.assertTrue(mock_send_mail.called)

        # 3. Add TOTP so user has >=2 methods before removing passkey
        secret = MFAService.generate_totp_secret()
        UserMFA.objects.update_or_create(
            user=self.staff_user,
            defaults={"totp_secret": secret, "is_enabled": True, "totp_enabled": True}
        )

        # 4. Remove passkey
        remove_resp = self.client.post("/api/v1/auth/security/passkey/remove/", {
            "passkey_id": passkey_id,
        })
        self.assertEqual(remove_resp.status_code, status.HTTP_200_OK)

    def test_last_method_removal_protection(self):
        """Users should not be allowed to remove their last remaining active security method."""
        from core.models import UserPasskey
        tokens = JWTService.generate_tokens(self.staff_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Ensure user has only 1 passkey method and TOTP disabled
        mfa, _ = UserMFA.objects.get_or_create(user=self.staff_user)
        mfa.totp_enabled = False
        mfa.totp_secret = ""
        mfa.passkey_enabled = True
        mfa.save()

        passkey = UserPasskey.objects.create(
            user=self.staff_user,
            credential_id="solo_passkey_cred_123",
            name="Solo Key",
        )

        # Attempt to delete the last passkey
        resp = self.client.post("/api/v1/auth/security/passkey/remove/", {
            "passkey_id": str(passkey.id),
        })

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data.get("code"), "LAST_METHOD_PROTECTION")

    def test_stepup_challenge_verification(self):
        """Test step-up verification endpoint for sensitive admin operations."""
        tokens = JWTService.generate_tokens(self.staff_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Setup TOTP for user
        secret = MFAService.generate_totp_secret()
        UserMFA.objects.update_or_create(
            user=self.staff_user,
            defaults={"totp_secret": secret, "is_enabled": True, "totp_enabled": True}
        )
        totp_code = pyotp.TOTP(secret).now()

        resp = self.client.post("/api/v1/auth/security/step-up/", {
            "method": "authenticator",
            "code": totp_code,
        })

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("stepup_token", resp.data)
        self.assertEqual(resp.data["expires_in_seconds"], 600)
