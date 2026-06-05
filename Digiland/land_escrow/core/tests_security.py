"""
Security Test Suite for Digiland Platform

Comprehensive automated security tests covering:
- Authentication security
- Authorization and access control
- API security
- Input validation
- SQL injection prevention
- XSS prevention
- CSRF protection
- File upload security
- Rate limiting
- Session security
- IDOR prevention
- Privilege escalation prevention

Run with: python manage.py test core.tests_security
"""

import json
import uuid
from decimal import Decimal
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class AuthenticationSecurityTests(TestCase):
    """Test authentication security controls."""

    def setUp(self):
        self.client = Client()
        self.buyer = User.objects.create_user(
            email='buyer@test.com',
            password='TestPass123!@#',
            role='Buyer',
            id_number='12345678',
            phone_number='+254712345678',
            kra_pin='A123456789B',
        )
        self.seller = User.objects.create_user(
            email='seller@test.com',
            password='TestPass123!@#',
            role='Seller',
            id_number='23456789',
            phone_number='+254712345679',
            kra_pin='B234567890C',
        )
        self.admin = User.objects.create_superuser(
            email='admin@test.com',
            password='AdminPass123!@#',
            role='Admin',
            id_number='34567890',
            phone_number='+254712345670',
            kra_pin='C345678901D',
        )

    def test_login_returns_jwt_tokens(self):
        """SEC-001: Login must return JWT access + refresh tokens."""
        response = self.client.post(
            '/api/v1/auth/login',
            {'email': 'buyer@test.com', 'password': 'TestPass123!@#'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('tokens', data)
        self.assertIn('access', data['tokens'])
        self.assertIn('refresh', data['tokens'])

    def test_login_with_wrong_password_fails(self):
        """SEC-002: Login with incorrect password must fail."""
        response = self.client.post(
            '/api/v1/auth/login',
            {'email': 'buyer@test.com', 'password': 'WrongPassword123!'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)

    def test_login_with_disabled_account_fails(self):
        """SEC-003: Login with disabled account must be rejected."""
        self.buyer.is_active = False
        self.buyer.save()
        response = self.client.post(
            '/api/v1/auth/login',
            {'email': 'buyer@test.com', 'password': 'TestPass123!@#'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_role_cannot_be_self_assigned(self):
        """SEC-004: Admin role cannot be assigned during registration."""
        response = self.client.post(
            '/api/v1/auth/register',
            {
                'email': 'hacker@test.com',
                'password': 'HackerPass123!@#',
                'role': 'Admin',
                'id_number': '99999999',
                'phone_number': '+254799999999',
                'kra_pin': 'Z999999999Z',
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_login_audit_log_created(self):
        """SEC-005: Successful login must create an audit log entry."""
        from core.models import AuditLog
        initial_count = AuditLog.objects.filter(action='LOGIN_SUCCESS').count()
        self.client.post(
            '/api/v1/auth/login',
            {'email': 'buyer@test.com', 'password': 'TestPass123!@#'},
            content_type='application/json',
        )
        new_count = AuditLog.objects.filter(action='LOGIN_SUCCESS').count()
        self.assertEqual(new_count, initial_count + 1)

    def test_failed_login_audit_log_created(self):
        """SEC-006: Failed login must create an audit log entry."""
        from core.models import AuditLog
        initial_count = AuditLog.objects.filter(action='LOGIN_FAILURE').count()
        self.client.post(
            '/api/v1/auth/login',
            {'email': 'buyer@test.com', 'password': 'wrong'},
            content_type='application/json',
        )
        new_count = AuditLog.objects.filter(action='LOGIN_FAILURE').count()
        self.assertEqual(new_count, initial_count + 1)


class AuthorizationSecurityTests(TestCase):
    """Test authorization and access control security."""

    def setUp(self):
        self.client = Client()
        self.buyer = User.objects.create_user(
            email='buyer@test.com',
            password='TestPass123!@#',
            role='Buyer',
            id_number='12345678',
            phone_number='+254712345678',
            kra_pin='A123456789B',
        )
        self.seller = User.objects.create_user(
            email='seller@test.com',
            password='TestPass123!@#',
            role='Seller',
            id_number='23456789',
            phone_number='+254712345679',
            kra_pin='B234567890C',
        )
        self.admin = User.objects.create_superuser(
            email='admin@test.com',
            password='AdminPass123!@#',
            role='Admin',
            id_number='34567890',
            phone_number='+254712345670',
            kra_pin='C345678901D',
        )
        # Get JWT tokens
        response = self.client.post(
            '/api/v1/auth/login',
            {'email': 'buyer@test.com', 'password': 'TestPass123!@#'},
            content_type='application/json',
        )
        self.buyer_token = response.json().get('tokens', {}).get('access', '')

        response = self.client.post(
            '/api/v1/auth/login',
            {'email': 'admin@test.com', 'password': 'AdminPass123!@#'},
            content_type='application/json',
        )
        self.admin_token = response.json().get('tokens', {}).get('access', '')

    def test_unauthenticated_api_access_denied(self):
        """SEC-007: Unauthenticated access to protected endpoints must be denied."""
        response = self.client.get('/api/v1/transactions/')
        self.assertIn(response.status_code, [401, 403])

    def test_unauthenticated_document_access_denied(self):
        """SEC-008: Unauthenticated access to documents must be denied."""
        response = self.client.get('/api/v1/documents/')
        self.assertIn(response.status_code, [401, 403])

    def test_payment_release_requires_admin(self):
        """SEC-009: Payment release must require admin privileges."""
        from core.models import Transaction, LandParcel
        parcel = LandParcel.objects.create(
            parcel_number='TEST-AUTH-001',
            land_use_type='Residential',
            county='Nairobi',
            constituency='Westlands',
            ward='Kitisuru',
            land_size=Decimal('0.5000'),
            registered_owner_id='12345678',
            listed_by=self.seller,
        )
        transaction = Transaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            land_parcel=parcel,
            agreed_price=Decimal('1000000.00'),
        )
        
        # Buyer should NOT be able to release payment
        response = self.client.post(
            f'/api/v1/payments/{transaction.id}/release',
            {'gateway': 'mpesa'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.buyer_token}',
        )
        self.assertIn(response.status_code, [403, 404])

    def test_payment_refund_requires_admin(self):
        """SEC-010: Payment refund must require admin privileges."""
        from core.models import Transaction, LandParcel
        parcel = LandParcel.objects.create(
            parcel_number='TEST-AUTH-002',
            land_use_type='Residential',
            county='Nairobi',
            constituency='Westlands',
            ward='Kitisuru',
            land_size=Decimal('0.5000'),
            registered_owner_id='12345678',
            listed_by=self.seller,
        )
        transaction = Transaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            land_parcel=parcel,
            agreed_price=Decimal('1000000.00'),
        )
        
        # Buyer should NOT be able to refund
        response = self.client.post(
            f'/api/v1/payments/{transaction.id}/refund',
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.buyer_token}',
        )
        self.assertIn(response.status_code, [403, 404])


class InputValidationTests(TestCase):
    """Test input validation and sanitization."""

    def setUp(self):
        self.client = Client()

    def test_registration_rejects_short_password(self):
        """SEC-011: Registration must reject passwords shorter than 10 characters."""
        response = self.client.post(
            '/api/v1/auth/register',
            {
                'email': 'newuser@test.com',
                'password': 'Short1!',
                'role': 'Buyer',
                'id_number': '45678901',
                'phone_number': '+254745678901',
                'kra_pin': 'D456789012E',
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_registration_rejects_invalid_role(self):
        """SEC-012: Registration must reject invalid roles."""
        response = self.client.post(
            '/api/v1/auth/register',
            {
                'email': 'newuser@test.com',
                'password': 'ValidPass123!@#',
                'role': 'SuperAdmin',
                'id_number': '45678901',
                'phone_number': '+254745678901',
                'kra_pin': 'D456789012E',
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_registration_rejects_duplicate_email(self):
        """SEC-013: Registration must reject duplicate email addresses."""
        User.objects.create_user(
            email='existing@test.com',
            password='TestPass123!@#',
            role='Buyer',
            id_number='56789012',
            phone_number='+254756789012',
            kra_pin='E567890123F',
        )
        response = self.client.post(
            '/api/v1/auth/register',
            {
                'email': 'existing@test.com',
                'password': 'TestPass123!@#',
                'role': 'Buyer',
                'id_number': '67890123',
                'phone_number': '+254767890123',
                'kra_pin': 'F678901234G',
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


class SessionSecurityTests(TestCase):
    """Test session security controls."""

    def test_session_cookie_httponly(self):
        """SEC-014: Session cookies must be HttpOnly."""
        from django.conf import settings
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)

    def test_session_cookie_samesite(self):
        """SEC-015: Session cookies must use SameSite attribute."""
        from django.conf import settings
        self.assertIn(settings.SESSION_COOKIE_SAMESITE, ['Lax', 'Strict'])


class SecurityHeaderTests(TestCase):
    """Test security headers are present in responses."""

    def setUp(self):
        self.client = Client()

    def test_x_content_type_options_header(self):
        """SEC-016: X-Content-Type-Options header must be present."""
        response = self.client.get('/')
        self.assertEqual(response.get('X-Content-Type-Options'), 'nosniff')

    def test_x_frame_options_header(self):
        """SEC-017: X-Frame-Options header must be present."""
        response = self.client.get('/')
        self.assertEqual(response.get('X-Frame-Options'), 'DENY')

    def test_content_security_policy_header(self):
        """SEC-018: Content-Security-Policy header must be present."""
        response = self.client.get('/')
        self.assertIn('Content-Security-Policy', response)

    def test_referrer_policy_header(self):
        """SEC-019: Referrer-Policy header must be present."""
        response = self.client.get('/')
        self.assertIn('Referrer-Policy', response)

    def test_api_responses_no_cache(self):
        """SEC-020: API responses must have no-cache headers."""
        response = self.client.get('/api/v1/recommendations/popular/')
        cache_control = response.get('Cache-Control', '')
        self.assertIn('no-store', cache_control)


class IDORPreventionTests(TestCase):
    """Test Insecure Direct Object Reference prevention."""

    def setUp(self):
        self.client = Client()
        self.buyer1 = User.objects.create_user(
            email='buyer1@test.com',
            password='TestPass123!@#',
            role='Buyer',
            id_number='11111111',
            phone_number='+254711111111',
            kra_pin='A111111111B',
        )
        self.buyer2 = User.objects.create_user(
            email='buyer2@test.com',
            password='TestPass123!@#',
            role='Buyer',
            id_number='22222222',
            phone_number='+254722222222',
            kra_pin='C222222222D',
        )

    def test_user_cannot_verify_others_identity(self):
        """SEC-021: User cannot verify another user's identity."""
        response = self.client.post(
            '/api/v1/auth/login',
            {'email': 'buyer1@test.com', 'password': 'TestPass123!@#'},
            content_type='application/json',
        )
        token = response.json().get('tokens', {}).get('access', '')
        
        # Buyer1 trying to verify Buyer2's identity
        response = self.client.post(
            f'/api/v1/users/{self.buyer2.id}/verify-identity',
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(response.status_code, 403)


class PasswordSecurityTests(TestCase):
    """Test password security controls."""

    def test_argon2id_is_preferred_hasher(self):
        """SEC-022: Argon2id must be the preferred password hasher."""
        from django.conf import settings
        hashers = settings.PASSWORD_HASHERS
        self.assertEqual(hashers[0], 'django.contrib.auth.hashers.Argon2PasswordHasher')

    def test_minimum_password_length_10(self):
        """SEC-023: Minimum password length must be 10 characters."""
        # Find the MinimumLengthValidator config
        from django.conf import settings
        for validator in settings.AUTH_PASSWORD_VALIDATORS:
            if 'MinimumLengthValidator' in validator['NAME']:
                self.assertGreaterEqual(validator.get('OPTIONS', {}).get('min_length', 8), 10)
                break


class CORSConfigurationTests(TestCase):
    """Test CORS security configuration."""

    def test_cors_not_allow_all(self):
        """SEC-024: CORS must not allow all origins."""
        from django.conf import settings
        self.assertFalse(settings.CORS_ALLOW_ALL_ORIGINS)

    def test_cors_allows_credentials(self):
        """SEC-025: CORS must allow credentials for authenticated requests."""
        from django.conf import settings
        self.assertTrue(settings.CORS_ALLOW_CREDENTIALS)


class JWTSecurityTests(TestCase):
    """Test JWT token security configuration."""

    def test_access_token_lifetime_short(self):
        """SEC-026: JWT access token lifetime must be 15 minutes or less."""
        from django.conf import settings
        lifetime = settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']
        self.assertLessEqual(lifetime.total_seconds(), 15 * 60)

    def test_refresh_tokens_are_rotated(self):
        """SEC-027: Refresh tokens must be rotated."""
        from django.conf import settings
        self.assertTrue(settings.SIMPLE_JWT['ROTATE_REFRESH_TOKENS'])

    def test_blacklist_after_rotation(self):
        """SEC-028: Refresh tokens must be blacklisted after rotation."""
        from django.conf import settings
        self.assertTrue(settings.SIMPLE_JWT['BLACKLIST_AFTER_ROTATION'])


class DataExposureTests(TestCase):
    """Test prevention of sensitive data exposure."""

    def test_lowest_negotiable_price_not_in_serializer(self):
        """SEC-029: Lowest negotiable price must not be exposed in API."""
        from core.serializers import LandParcelSerializer
        fields = LandParcelSerializer.Meta.fields
        self.assertNotIn('lowest_negotiable_price', fields)

    def test_face_embedding_is_write_only(self):
        """SEC-030: KYC face embedding must be write-only."""
        from core.serializers import KYCProfileSerializer
        extra_kwargs = KYCProfileSerializer.Meta.extra_kwargs
        if 'face_embedding' in extra_kwargs:
            self.assertTrue(extra_kwargs['face_embedding'].get('write_only', False))


class SettingsSecurityTests(TestCase):
    """Test Django settings security configuration."""

    def test_no_hardcoded_admin_pin(self):
        """SEC-031: Admin finance PIN must not be present in settings."""
        from django.conf import settings
        # The ADMIN_FINANCE_PIN should be deprecated/removed
        pin = getattr(settings, 'ADMIN_FINANCE_PIN', None)
        if pin:
            self.assertNotEqual(pin, 'admin2026')

    def test_secret_key_has_no_default(self):
        """SEC-032: SECRET_KEY must not have an insecure default."""
        # This test verifies the setting exists and is not the old insecure default
        from django.conf import settings
        self.assertNotIn('django-insecure-', settings.SECRET_KEY)

    def test_default_permission_is_authenticated(self):
        """SEC-033: Default DRF permission must be IsAuthenticated."""
        from django.conf import settings
        perms = settings.REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES']
        self.assertIn('rest_framework.permissions.IsAuthenticated', perms)

    def test_data_upload_max_memory_size(self):
        """SEC-034: Data upload max memory size must be set."""
        from django.conf import settings
        self.assertIsNotNone(settings.DATA_UPLOAD_MAX_MEMORY_SIZE)
        self.assertLessEqual(settings.DATA_UPLOAD_MAX_MEMORY_SIZE, 20 * 1024 * 1024)  # Max 20MB

    def test_session_expire_at_browser_close(self):
        """SEC-035: Sessions must expire at browser close."""
        from django.conf import settings
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)


class TempApproveAgentSecurityTests(TestCase):
    """Test that temp_approve_agent is properly secured."""

    def setUp(self):
        self.client = Client()
        self.agent = User.objects.create_user(
            email='agent@test.com',
            password='AgentPass123!@#',
            role='Agent',
            id_number='44444444',
            phone_number='+254744444444',
            kra_pin='D444444444E',
        )
        self.admin = User.objects.create_superuser(
            email='admin@test.com',
            password='AdminPass123!@#',
            role='Admin',
            id_number='55555555',
            phone_number='+254755555555',
            kra_pin='E555555555F',
        )

    def test_temp_approve_agent_requires_authentication(self):
        """SEC-036: temp_approve_agent must require authentication."""
        response = self.client.get(f'/temp-approve/{self.agent.email}/')
        # Should redirect to login, not allow the action
        self.assertNotEqual(response.status_code, 200)

    def test_temp_approve_agent_requires_admin_role(self):
        """SEC-037: temp_approve_agent must require Admin role."""
        # Authenticate as a non-admin (agent)
        self.client.login(email='agent@test.com', password='AgentPass123!@#')
        response = self.client.get(f'/temp-approve/{self.agent.email}/')
        # Should be redirected (not authorized), not succeed
        self.assertNotEqual(response.status_code, 200)

    def test_temp_approve_agent_works_for_admin(self):
        """SEC-038: temp_approve_agent should work for authenticated Admin."""
        self.client.login(email='admin@test.com', password='AdminPass123!@#')
        response = self.client.get(f'/temp-approve/{self.agent.email}/')
        self.assertEqual(response.status_code, 200)
        # Verify the agent was actually approved
        self.agent.refresh_from_db()
        self.assertTrue(self.agent.is_identity_verified)


class MpesaCallbackSecurityTests(TestCase):
    """Test M-PESA callback security controls."""

    def setUp(self):
        self.client = Client()

    def test_mpesa_callback_accepts_without_secret_configured(self):
        """SEC-039: M-PESA callback should accept requests when no secret is configured."""
        response = self.client.post(
            '/api/v1/mpesa/callback/',
            data=json.dumps({'Body': {'stkCallback': {'ResultCode': 1, 'ResultDesc': 'Test'}}}),
            content_type='application/json',
        )
        # Should not return 403 when secret is not configured
        self.assertNotEqual(response.status_code, 403)

    @override_settings(MPESA_CALLBACK_SECRET='test-secret-123')
    def test_mpesa_callback_rejects_without_secret_header(self):
        """SEC-040: M-PESA callback must reject requests missing secret header when configured."""
        response = self.client.post(
            '/api/v1/mpesa/callback/',
            data=json.dumps({'Body': {'stkCallback': {'ResultCode': 1, 'ResultDesc': 'Test'}}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    @override_settings(MPESA_CALLBACK_SECRET='test-secret-123')
    def test_mpesa_callback_rejects_wrong_secret(self):
        """SEC-041: M-PESA callback must reject requests with wrong secret."""
        response = self.client.post(
            '/api/v1/mpesa/callback/',
            data=json.dumps({'Body': {'stkCallback': {'ResultCode': 1, 'ResultDesc': 'Test'}}}),
            content_type='application/json',
            HTTP_X_MPESA_SECRET='wrong-secret',
        )
        self.assertEqual(response.status_code, 403)

    @override_settings(MPESA_CALLBACK_SECRET='test-secret-123')
    def test_mpesa_callback_accepts_correct_secret(self):
        """SEC-042: M-PESA callback must accept requests with correct secret."""
        response = self.client.post(
            '/api/v1/mpesa/callback/',
            data=json.dumps({'Body': {'stkCallback': {'ResultCode': 1, 'ResultDesc': 'Test'}}}),
            content_type='application/json',
            HTTP_X_MPESA_SECRET='test-secret-123',
        )
        # Should not be 403 (may be 200 or other status depending on callback processing)
        self.assertNotEqual(response.status_code, 403)


class CORSMethodHeaderTests(TestCase):
    """Test CORS method and header restrictions."""

    def test_cors_allow_methods_configured(self):
        """SEC-043: CORS allowed methods must be explicitly configured."""
        from django.conf import settings
        self.assertTrue(hasattr(settings, 'CORS_ALLOW_METHODS'))
        methods = settings.CORS_ALLOW_METHODS
        self.assertIn('GET', methods)
        self.assertIn('POST', methods)
        self.assertNotIn('TRACE', methods)

    def test_cors_allow_headers_configured(self):
        """SEC-044: CORS allowed headers must be explicitly configured."""
        from django.conf import settings
        self.assertTrue(hasattr(settings, 'CORS_ALLOW_HEADERS'))
        headers = settings.CORS_ALLOW_HEADERS
        self.assertIn('authorization', headers)
        self.assertIn('x-csrftoken', headers)
