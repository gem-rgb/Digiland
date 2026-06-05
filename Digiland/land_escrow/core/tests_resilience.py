"""
Comprehensive tests for the resilience system.

Tests cover:
- Every error code in the taxonomy
- Every error response is user-safe (no stack traces, no SQL, no provider names in production)
- Error responses include reference IDs
- Development vs production error detail levels
- Database degradation handler
- Third-party degradation handler
- Financial error handler (uncertain payment outcomes)
- Admin error handler (no internal details exposed)
- Background job monitor state transitions
- Auth error handler (differentiated messages)
- Middleware integration
- Error decorators
- Validation error responses are field-specific
- Observability tracking
"""

from __future__ import annotations

import json
import os
import uuid
from unittest import mock
from unittest.mock import MagicMock, patch, PropertyMock

from django.conf import settings
from django.db import OperationalError, InterfaceError
from django.http import HttpRequest, JsonResponse
from django.test import TestCase, RequestFactory, override_settings

from .error_taxonomy import (
    ERROR_REGISTRY,
    ErrorCategory,
    ErrorDefinition,
    ErrorSeverity,
    get_error_definition,
    get_errors_by_category,
    map_exception_to_error_code,
    DJANGO_EXCEPTION_MAP,
)
from .error_responses import (
    create_error_response,
    create_validation_error_response,
    create_financial_error_response,
    create_auth_error_response,
    _is_production,
    _sanitize_message,
    SENSITIVE_PATTERNS,
)
from .error_middleware import (
    GracefulDegradationMiddleware,
    DatabaseDegradationMiddleware,
    ExternalServiceDegradationMiddleware,
)


# ======================================================================
# Error Taxonomy Tests
# ======================================================================


class TestErrorTaxonomy(TestCase):
    """Test every error code in the taxonomy."""

    def test_all_error_codes_are_registered(self):
        """All required error codes must be in the registry."""
        required_codes = [
            "AUTH_INVALID_CREDENTIALS", "AUTH_SESSION_EXPIRED",
            "AUTH_ACCOUNT_LOCKED", "AUTH_MFA_REQUIRED",
            "AUTH_PERMISSION_DENIED", "AUTH_SUSPICIOUS_ACTIVITY",
            "AUTH_TOKEN_INVALID",
            "PAYMENT_PROVIDER_UNAVAILABLE", "PAYMENT_PROCESSING_FAILED",
            "PAYMENT_INSUFFICIENT_FUNDS", "PAYMENT_LIMIT_EXCEEDED",
            "PAYMENT_DUPLICATE_REFERENCE",
            "WITHDRAWAL_PENDING_RETRY", "WITHDRAWAL_FAILED",
            "WITHDRAWAL_LIMIT_EXCEEDED", "WITHDRAWAL_NOT_ALLOWED",
            "NETWORK_TIMEOUT", "NETWORK_OFFLINE",
            "NETWORK_SERVER_ERROR", "NETWORK_RATE_LIMITED",
            "DATABASE_READ_ONLY", "DATABASE_UNAVAILABLE",
            "DATABASE_SLOW_RESPONSE", "DATABASE_CONNECTION_FAILED",
            "VALIDATION_INVALID_EMAIL", "VALIDATION_PASSWORD_TOO_SHORT",
            "VALIDATION_FILE_TOO_LARGE", "VALIDATION_INVALID_FORMAT",
            "VALIDATION_REQUIRED_FIELD",
            "FILE_UPLOAD_TOO_LARGE", "FILE_UPLOAD_UNSUPPORTED_TYPE",
            "FILE_UPLOAD_FAILED", "FILE_UPLOAD_VIRUS_DETECTED",
            "SEARCH_UNAVAILABLE", "SEARCH_INDEX_ERROR",
            "SYSTEM_MAINTENANCE", "SYSTEM_UNKNOWN_ERROR",
            "SYSTEM_CONFIGURATION_ERROR",
            "ESCROW_ERROR", "REFUND_PENDING",
            "TRANSACTION_NOT_FOUND", "TRANSACTION_ALREADY_PROCESSED",
            "NOTIFICATION_DELIVERY_FAILED",
            "NOTIFICATION_PROVIDER_UNAVAILABLE",
            "EXTERNAL_SERVICE_UNAVAILABLE", "EXTERNAL_SERVICE_TIMEOUT",
            "EXTERNAL_SERVICE_RATE_LIMITED",
        ]
        for code in required_codes:
            self.assertIn(
                code, ERROR_REGISTRY,
                f"Required error code '{code}' is missing from ERROR_REGISTRY"
            )

    def test_at_least_60_error_codes(self):
        """There must be at least 60 error codes in the taxonomy."""
        self.assertGreaterEqual(
            len(ERROR_REGISTRY), 60,
            f"Expected at least 60 error codes, found {len(ERROR_REGISTRY)}"
        )

    def test_every_error_has_required_fields(self):
        """Every error definition must have all required fields."""
        required_fields = [
            "error_code", "category", "severity", "user_message",
            "internal_message", "recovery_action", "http_status_code",
            "is_retryable", "log_level",
        ]
        for code, definition in ERROR_REGISTRY.items():
            for field in required_fields:
                self.assertTrue(
                    hasattr(definition, field),
                    f"Error '{code}' is missing field '{field}'"
                )

    def test_user_messages_are_safe(self):
        """User messages must not contain sensitive patterns."""
        for code, definition in ERROR_REGISTRY.items():
            msg_lower = definition.user_message.lower()
            for pattern in [
                "stripe", "mpesa", "paystack", "redis", "celery",
                "postgresql", "postgis", "sentry", "stack trace",
                "sql", "database", "table", "column", "schema",
                "http://", "https://", "api_key", "secret",
                "password", "token", "credential",
            ]:
                self.assertNotIn(
                    pattern, msg_lower,
                    f"Error '{code}' user_message contains sensitive pattern '{pattern}': "
                    f"{definition.user_message}"
                )

    def test_internal_messages_are_informative(self):
        """Internal messages should be more detailed than user messages."""
        for code, definition in ERROR_REGISTRY.items():
            self.assertTrue(
                len(definition.internal_message) > 0,
                f"Error '{code}' has an empty internal_message"
            )

    def test_http_status_codes_are_valid(self):
        """HTTP status codes must be valid (400-599)."""
        for code, definition in ERROR_REGISTRY.items():
            self.assertGreaterEqual(
                definition.http_status_code, 400,
                f"Error '{code}' has invalid HTTP status {definition.http_status_code}"
            )
            self.assertLessEqual(
                definition.http_status_code, 599,
                f"Error '{code}' has invalid HTTP status {definition.http_status_code}"
            )

    def test_log_levels_are_valid(self):
        """Log levels must be valid Python logging levels."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        for code, definition in ERROR_REGISTRY.items():
            self.assertIn(
                definition.log_level.upper(), valid_levels,
                f"Error '{code}' has invalid log_level '{definition.log_level}'"
            )

    def test_categories_are_valid(self):
        """Categories must be valid ErrorCategory values."""
        valid_categories = {c.value for c in ErrorCategory}
        for code, definition in ERROR_REGISTRY.items():
            cat = definition.category
            cat_value = cat.value if hasattr(cat, "value") else str(cat)
            self.assertIn(
                cat_value, valid_categories,
                f"Error '{code}' has invalid category '{cat}'"
            )

    def test_severities_are_valid(self):
        """Severities must be valid ErrorSeverity values."""
        valid_severities = {s.value for s in ErrorSeverity}
        for code, definition in ERROR_REGISTRY.items():
            sev = definition.severity
            sev_value = sev.value if hasattr(sev, "value") else str(sev)
            self.assertIn(
                sev_value, valid_severities,
                f"Error '{code}' has invalid severity '{sev}'"
            )

    def test_get_error_definition(self):
        """get_error_definition returns the correct definition."""
        defn = get_error_definition("AUTH_INVALID_CREDENTIALS")
        self.assertIsNotNone(defn)
        self.assertEqual(defn.error_code, "AUTH_INVALID_CREDENTIALS")

    def test_get_error_definition_unknown(self):
        """get_error_definition returns None for unknown codes."""
        self.assertIsNone(get_error_definition("NONEXISTENT_CODE"))

    def test_get_errors_by_category(self):
        """get_errors_by_category returns errors in a given category."""
        auth_errors = get_errors_by_category(ErrorCategory.AUTH)
        self.assertGreaterEqual(len(auth_errors), 7)
        for code, defn in auth_errors.items():
            self.assertEqual(defn.category, ErrorCategory.AUTH)

    def test_critical_errors_have_critical_log_level(self):
        """Critical-severity errors should have CRITICAL log level."""
        for code, defn in ERROR_REGISTRY.items():
            if defn.severity == ErrorSeverity.CRITICAL:
                self.assertEqual(
                    defn.log_level.upper(), "CRITICAL",
                    f"Error '{code}' is CRITICAL severity but log_level is '{defn.log_level}'"
                )


class TestExceptionMapping(TestCase):
    """Test Django exception to error code mapping."""

    def test_django_exception_map_has_required_mappings(self):
        """The exception map should have mappings for common Django exceptions."""
        required_mappings = [
            "AuthenticationFailed",
            "NotAuthenticated",
            "PermissionDenied",
            "ValidationError",
            "OperationalError",
            "InterfaceError",
        ]
        for exc_name in required_mappings:
            self.assertIn(
                exc_name, DJANGO_EXCEPTION_MAP,
                f"Django exception '{exc_name}' not mapped"
            )

    def test_map_django_exceptions(self):
        """Django exceptions should map to appropriate error codes."""
        from rest_framework.exceptions import (
            AuthenticationFailed,
            NotAuthenticated,
            PermissionDenied,
            ValidationError as DRFValidationError,
            Throttled,
            NotFound,
        )

        self.assertEqual(
            map_exception_to_error_code(AuthenticationFailed()),
            "AUTH_INVALID_CREDENTIALS",
        )
        self.assertEqual(
            map_exception_to_error_code(NotAuthenticated()),
            "AUTH_TOKEN_INVALID",
        )
        self.assertEqual(
            map_exception_to_error_code(PermissionDenied()),
            "AUTH_PERMISSION_DENIED",
        )
        self.assertEqual(
            map_exception_to_error_code(Throttled()),
            "NETWORK_RATE_LIMITED",
        )
        self.assertEqual(
            map_exception_to_error_code(NotFound()),
            "TRANSACTION_NOT_FOUND",
        )

    def test_map_database_exceptions(self):
        """Database exceptions should map to database error codes."""
        self.assertEqual(
            map_exception_to_error_code(OperationalError("connection refused")),
            "DATABASE_UNAVAILABLE",
        )
        self.assertEqual(
            map_exception_to_error_code(InterfaceError("connection failed")),
            "DATABASE_CONNECTION_FAILED",
        )

    def test_map_unknown_exception(self):
        """Unknown exceptions should map to SYSTEM_UNKNOWN_ERROR."""
        self.assertEqual(
            map_exception_to_error_code(ValueError("unexpected")),
            "SYSTEM_UNKNOWN_ERROR",
        )

    def test_map_esl_exceptions(self):
        """ExternalServiceError subclasses should map to appropriate codes."""
        from external_services.exceptions import (
            ExternalServiceError,
            ProviderUnavailableError,
            CircuitBreakerOpenError,
            RateLimitExceededError,
            TimeoutError as ESLTimeoutError,
        )

        self.assertEqual(
            map_exception_to_error_code(
                ProviderUnavailableError("test_provider")
            ),
            "EXTERNAL_SERVICE_UNAVAILABLE",
        )
        self.assertEqual(
            map_exception_to_error_code(
                CircuitBreakerOpenError("test_provider")
            ),
            "EXTERNAL_SERVICE_UNAVAILABLE",
        )
        self.assertEqual(
            map_exception_to_error_code(
                RateLimitExceededError("test_provider", retry_after=60)
            ),
            "EXTERNAL_SERVICE_RATE_LIMITED",
        )
        self.assertEqual(
            map_exception_to_error_code(
                ESLTimeoutError("test_provider", timeout_seconds=30)
            ),
            "EXTERNAL_SERVICE_TIMEOUT",
        )


# ======================================================================
# Error Response Tests
# ======================================================================


class TestErrorResponses(TestCase):
    """Test error response generation."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_create_error_response_has_reference_id(self):
        """Every error response must include a reference_id."""
        response = create_error_response("AUTH_INVALID_CREDENTIALS")
        data = json.loads(response.content)
        self.assertIn("reference_id", data["error"])

    def test_create_error_response_has_error_code(self):
        """Every error response must include the error code."""
        response = create_error_response("PAYMENT_PROVIDER_UNAVAILABLE")
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], "PAYMENT_PROVIDER_UNAVAILABLE")

    def test_create_error_response_has_user_message(self):
        """Every error response must include a user message."""
        response = create_error_response("NETWORK_TIMEOUT")
        data = json.loads(response.content)
        self.assertIn("message", data["error"])
        self.assertTrue(len(data["error"]["message"]) > 0)

    @override_settings(DEBUG=True)
    def test_development_response_includes_debug_info(self):
        """In development mode, responses include _debug section."""
        with patch.dict(os.environ, {"DJANGO_ENV": "development"}):
            response = create_error_response(
                "AUTH_INVALID_CREDENTIALS",
                details={"field": "email"},
            )
            data = json.loads(response.content)
            self.assertIn("_debug", data["error"])

    @override_settings(DEBUG=False)
    def test_production_response_excludes_debug_info(self):
        """In production mode, responses must NOT include _debug section."""
        with patch.dict(os.environ, {"DJANGO_ENV": "production"}):
            response = create_error_response(
                "AUTH_INVALID_CREDENTIALS",
                details={"field": "email"},
            )
            data = json.loads(response.content)
            self.assertNotIn("_debug", data["error"])

    @override_settings(DEBUG=False)
    def test_production_response_no_stack_trace(self):
        """Production responses must never include stack traces."""
        with patch.dict(os.environ, {"DJANGO_ENV": "production"}):
            response = create_error_response("SYSTEM_UNKNOWN_ERROR")
            content = response.content.decode()
            self.assertNotIn("traceback", content.lower())
            self.assertNotIn("Traceback", content)
            self.assertNotIn("exception", content.lower())

    @override_settings(DEBUG=False)
    def test_production_response_no_provider_names(self):
        """Production responses must never include provider names."""
        with patch.dict(os.environ, {"DJANGO_ENV": "production"}):
            for provider in ["stripe", "mpesa", "paystack", "redis", "celery"]:
                response = create_error_response("PAYMENT_PROVIDER_UNAVAILABLE")
                content = response.content.decode().lower()
                self.assertNotIn(provider, content)

    def test_response_has_x_reference_id_header(self):
        """Responses should have X-Reference-ID header."""
        response = create_error_response("AUTH_INVALID_CREDENTIALS")
        self.assertIn("X-Reference-ID", response)

    def test_retryable_errors_have_retryable_flag(self):
        """Retryable errors should include retryable=True in response."""
        response = create_error_response("NETWORK_TIMEOUT")
        data = json.loads(response.content)
        self.assertTrue(data["error"].get("retryable", False))

    def test_non_retryable_errors_no_retryable_flag(self):
        """Non-retryable errors should not include retryable flag."""
        response = create_error_response("VALIDATION_INVALID_FORMAT")
        data = json.loads(response.content)
        # Should not have retryable=True
        self.assertNotEqual(data["error"].get("retryable"), True)

    def test_custom_user_message(self):
        """Custom user messages should override the taxonomy default."""
        custom_msg = "Custom error message for testing"
        response = create_error_response(
            "AUTH_INVALID_CREDENTIALS", user_message=custom_msg
        )
        data = json.loads(response.content)
        self.assertEqual(data["error"]["message"], custom_msg)

    def test_unknown_error_code_uses_fallback(self):
        """Unknown error codes should fall back to SYSTEM_UNKNOWN_ERROR."""
        response = create_error_response("NONEXISTENT_CODE_XYZ")
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], "NONEXISTENT_CODE_XYZ")
        # Should still have a valid message
        self.assertTrue(len(data["error"]["message"]) > 0)


class TestValidationErrorResponse(TestCase):
    """Test field-specific validation error responses."""

    def test_field_errors_included(self):
        """Field errors should be included in the response."""
        field_errors = {
            "email": ["Enter a valid email address."],
            "phone": ["Phone number format is incorrect."],
        }
        response = create_validation_error_response(field_errors)
        data = json.loads(response.content)
        self.assertIn("fields", data["error"])
        self.assertIn("email", data["error"]["fields"])
        self.assertIn("phone", data["error"]["fields"])

    def test_validation_response_has_reference_id(self):
        """Validation responses should include a reference_id."""
        response = create_validation_error_response({"name": ["Required."]})
        data = json.loads(response.content)
        self.assertIn("reference_id", data["error"])

    def test_validation_response_returns_400(self):
        """Validation responses should return HTTP 400."""
        response = create_validation_error_response({"name": ["Required."]})
        self.assertEqual(response.status_code, 400)

    @override_settings(DEBUG=False)
    def test_production_validation_no_debug(self):
        """Production validation responses should not include _debug."""
        with patch.dict(os.environ, {"DJANGO_ENV": "production"}):
            response = create_validation_error_response({"name": ["Required."]})
            data = json.loads(response.content)
            self.assertNotIn("_debug", data["error"])


class TestFinancialErrorResponse(TestCase):
    """Test financial operation error responses."""

    def test_includes_transaction_id(self):
        """Financial responses must include the transaction ID."""
        response = create_financial_error_response(
            transaction_id="txn-123",
            error_code="PAYMENT_PROVIDER_UNAVAILABLE",
        )
        data = json.loads(response.content)
        self.assertIn("transaction_id", data["error"])

    def test_includes_funds_status(self):
        """Financial responses must include funds_status."""
        response = create_financial_error_response(
            transaction_id="txn-123",
            error_code="PAYMENT_PROCESSING_FAILED",
            funds_moved=False,
        )
        data = json.loads(response.content)
        self.assertIn("funds_status", data["error"])
        self.assertEqual(data["error"]["funds_status"], "not_moved")

    def test_funds_moved_status(self):
        """When funds were moved, funds_status should be 'moved'."""
        response = create_financial_error_response(
            transaction_id="txn-123",
            error_code="PAYMENT_PROCESSING_FAILED",
            funds_moved=True,
        )
        data = json.loads(response.content)
        self.assertEqual(data["error"]["funds_status"], "moved")

    def test_includes_support_message(self):
        """Financial responses must include a support message with reference."""
        response = create_financial_error_response(
            transaction_id="txn-123",
            error_code="PAYMENT_PROVIDER_UNAVAILABLE",
        )
        data = json.loads(response.content)
        self.assertIn("support_message", data["error"])
        self.assertIn("reference", data["error"]["support_message"].lower())

    def test_has_x_transaction_id_header(self):
        """Financial responses should have X-Transaction-ID header."""
        response = create_financial_error_response(
            transaction_id="txn-123",
            error_code="PAYMENT_PROVIDER_UNAVAILABLE",
        )
        self.assertIn("X-Transaction-ID", response)

    @override_settings(DEBUG=False)
    def test_production_financial_no_provider_names(self):
        """Production financial responses must not include provider names."""
        with patch.dict(os.environ, {"DJANGO_ENV": "production"}):
            response = create_financial_error_response(
                transaction_id="txn-123",
                error_code="PAYMENT_PROVIDER_UNAVAILABLE",
            )
            content = response.content.decode().lower()
            for provider in ["stripe", "mpesa", "paystack", "kcb", "daraja"]:
                self.assertNotIn(provider, content)


class TestAuthErrorResponse(TestCase):
    """Test authentication error responses."""

    def test_includes_reference_id(self):
        """Auth responses must include a reference_id."""
        response = create_auth_error_response("AUTH_INVALID_CREDENTIALS")
        data = json.loads(response.content)
        self.assertIn("reference_id", data["error"])

    def test_redirect_url_included_when_provided(self):
        """Auth responses should include redirect_url when specified."""
        response = create_auth_error_response(
            "AUTH_SESSION_EXPIRED",
            redirect_url="/accounts/login/",
        )
        data = json.loads(response.content)
        self.assertIn("redirect_url", data["error"])
        self.assertEqual(data["error"]["redirect_url"], "/accounts/login/")

    def test_no_redirect_url_when_not_provided(self):
        """Auth responses should not include redirect_url when not needed."""
        response = create_auth_error_response("AUTH_INVALID_CREDENTIALS")
        data = json.loads(response.content)
        self.assertNotIn("redirect_url", data["error"])

    def test_auth_message_does_not_reveal_account_existence(self):
        """Auth error messages must not reveal whether an account exists."""
        response = create_auth_error_response("AUTH_INVALID_CREDENTIALS")
        data = json.loads(response.content)
        msg = data["error"]["message"].lower()
        # Should not say "account not found" or "email not registered"
        for phrase in [
            "account not found", "email not registered",
            "user does not exist", "no account",
            "does not exist", "not registered",
        ]:
            self.assertNotIn(phrase, msg)


class TestMessageSanitization(TestCase):
    """Test that sensitive information is sanitized from messages."""

    def test_sanitize_stripe(self):
        """Stripe should be redacted from messages."""
        result = _sanitize_message("Error from Stripe payment gateway")
        self.assertNotIn("Stripe", result)
        self.assertNotIn("stripe", result.lower())

    def test_sanitize_mpesa(self):
        """M-Pesa should be redacted from messages."""
        result = _sanitize_message("M-Pesa STK push failed")
        self.assertNotIn("M-Pesa", result)
        self.assertNotIn("mpesa", result.lower())

    def test_sanitize_redis(self):
        """Redis should be redacted from messages."""
        result = _sanitize_message("Redis connection timeout")
        self.assertNotIn("Redis", result)
        self.assertNotIn("redis", result.lower())

    def test_sanitize_api_key(self):
        """API key references should be redacted."""
        result = _sanitize_message("Invalid api_key provided")
        self.assertNotIn("api_key", result.lower())


# ======================================================================
# Middleware Tests
# ======================================================================


class TestGracefulDegradationMiddleware(TestCase):
    """Test the GracefulDegradationMiddleware."""

    def setUp(self):
        self.factory = RequestFactory()

    def _get_middleware(self):
        def get_response(request):
            return JsonResponse({"ok": True})

        return GracefulDegradationMiddleware(get_response)

    def test_normal_request_passes_through(self):
        """Normal requests should pass through without modification."""
        middleware = self._get_middleware()
        request = self.factory.get("/api/v1/parcels/")
        response = middleware(request)
        data = json.loads(response.content)
        self.assertTrue(data.get("ok"))

    def test_catches_unhandled_exception(self):
        """Unhandled exceptions should be caught and converted to safe responses."""
        def failing_view(request):
            raise ValueError("Something broke")

        middleware = GracefulDegradationMiddleware(failing_view)
        request = self.factory.get("/api/v1/test/")
        response = middleware(request)
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertIn("error", data)
        self.assertIn("reference_id", data["error"])

    @override_settings(DEBUG=False)
    def test_production_no_stack_trace(self):
        """Production error responses must not include stack traces."""
        with patch.dict(os.environ, {"DJANGO_ENV": "production"}):
            def failing_view(request):
                raise ValueError("Internal error details")

            middleware = GracefulDegradationMiddleware(failing_view)
            request = self.factory.get("/api/v1/test/")
            response = middleware(request)
            content = response.content.decode().lower()
            self.assertNotIn("traceback", content)
            self.assertNotIn("valueerror", content)

    def test_catches_database_errors(self):
        """Database errors should be caught with appropriate error code."""
        def failing_view(request):
            raise OperationalError("connection refused")

        middleware = GracefulDegradationMiddleware(failing_view)
        request = self.factory.get("/api/v1/test/")
        response = middleware(request)
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], "DATABASE_UNAVAILABLE")

    def test_catches_auth_errors(self):
        """Auth errors should be caught with appropriate error code."""
        from rest_framework.exceptions import NotAuthenticated

        def failing_view(request):
            raise NotAuthenticated()

        middleware = GracefulDegradationMiddleware(failing_view)
        request = self.factory.get("/api/v1/test/")
        response = middleware(request)
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], "AUTH_TOKEN_INVALID")

    def test_response_has_x_reference_id_header(self):
        """Middleware responses should have X-Reference-ID header."""
        def failing_view(request):
            raise RuntimeError("test")

        middleware = GracefulDegradationMiddleware(failing_view)
        request = self.factory.get("/api/v1/test/")
        response = middleware(request)
        self.assertIn("X-Reference-ID", response)


class TestDatabaseDegradationMiddleware(TestCase):
    """Test the DatabaseDegradationMiddleware."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_normal_request_passes_through(self):
        """Normal requests should pass through."""
        def get_response(request):
            return JsonResponse({"ok": True})

        middleware = DatabaseDegradationMiddleware(get_response)
        request = self.factory.get("/api/v1/parcels/")
        response = middleware(request)
        data = json.loads(response.content)
        self.assertTrue(data.get("ok"))

    @patch("core.error_middleware.cache")
    def test_catches_operational_error(self, mock_cache):
        """OperationalError should trigger read-only mode."""
        mock_cache.get.return_value = False  # Not already in read-only mode

        def failing_view(request):
            raise OperationalError("connection refused")

        middleware = DatabaseDegradationMiddleware(failing_view)
        request = self.factory.get("/api/v1/test/")
        response = middleware(request)
        # Should get some kind of error response
        self.assertIn(response.status_code, [503, 500, 504])

    @patch("core.error_middleware.cache")
    def test_write_in_read_only_mode(self, mock_cache):
        """Write operations in read-only mode should be rejected."""
        mock_cache.get.return_value = True  # In read-only mode

        def get_response(request):
            return JsonResponse({"ok": True})

        middleware = DatabaseDegradationMiddleware(get_response)
        request = self.factory.post("/api/v1/test/", data={})
        response = middleware(request)
        # Should get read-only response
        self.assertEqual(response.status_code, 503)


class TestExternalServiceDegradationMiddleware(TestCase):
    """Test the ExternalServiceDegradationMiddleware."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_normal_request_passes_through(self):
        """Normal requests should pass through."""
        def get_response(request):
            return JsonResponse({"ok": True})

        middleware = ExternalServiceDegradationMiddleware(get_response)
        request = self.factory.get("/api/v1/parcels/")
        response = middleware(request)
        data = json.loads(response.content)
        self.assertTrue(data.get("ok"))

    def test_catches_provider_unavailable_error(self):
        """ProviderUnavailableError should be caught."""
        from external_services.exceptions import ProviderUnavailableError

        def failing_view(request):
            raise ProviderUnavailableError("test_provider", service_type="payment")

        middleware = ExternalServiceDegradationMiddleware(failing_view)
        request = self.factory.get("/api/v1/test/")
        response = middleware(request)
        data = json.loads(response.content)
        self.assertIn("error", data)
        # Should map to PAYMENT_PROVIDER_UNAVAILABLE for payment service type
        self.assertEqual(data["error"]["code"], "PAYMENT_PROVIDER_UNAVAILABLE")

    def test_catches_rate_limit_error(self):
        """RateLimitExceededError should map to rate-limited code."""
        from external_services.exceptions import RateLimitExceededError

        def failing_view(request):
            raise RateLimitExceededError("test_provider", retry_after=60)

        middleware = ExternalServiceDegradationMiddleware(failing_view)
        request = self.factory.get("/api/v1/test/")
        response = middleware(request)
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], "EXTERNAL_SERVICE_RATE_LIMITED")

    @override_settings(DEBUG=False)
    def test_production_no_provider_name(self):
        """Production responses must not include the provider name."""
        with patch.dict(os.environ, {"DJANGO_ENV": "production"}):
            from external_services.exceptions import ProviderUnavailableError

            def failing_view(request):
                raise ProviderUnavailableError("Stripe", service_type="payment")

            middleware = ExternalServiceDegradationMiddleware(failing_view)
            request = self.factory.get("/api/v1/test/")
            response = middleware(request)
            content = response.content.decode().lower()
            self.assertNotIn("stripe", content)

    def test_non_esl_exceptions_are_reraised(self):
        """Non-ESL exceptions should be re-raised."""
        def failing_view(request):
            raise ValueError("Not an ESL error")

        middleware = ExternalServiceDegradationMiddleware(failing_view)
        request = self.factory.get("/api/v1/test/")
        with self.assertRaises(ValueError):
            middleware(request)


# ======================================================================
# Decorator Tests
# ======================================================================


class TestGracefulDegradationDecorator(TestCase):
    """Test the @graceful_degradation decorator."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_successful_function_returns_normally(self):
        """Decorated functions should return normally on success."""
        from .error_decorators import graceful_degradation

        @graceful_degradation(fallback_value=[])
        def my_function():
            return [1, 2, 3]

        result = my_function()
        self.assertEqual(result, [1, 2, 3])

    def test_failing_function_returns_fallback(self):
        """Decorated service functions should return fallback on error."""
        from .error_decorators import graceful_degradation

        @graceful_degradation(fallback_value=[])
        def my_function():
            raise ValueError("Oops")

        result = my_function()
        self.assertEqual(result, [])

    def test_failing_view_returns_json_error(self):
        """Decorated views should return a JSON error response."""
        from .error_decorators import graceful_degradation

        @graceful_degradation(fallback_value=None)
        def my_view(request):
            raise ValueError("View error")

        request = self.factory.get("/api/v1/test/")
        response = my_view(request)
        self.assertIsInstance(response, JsonResponse)
        data = json.loads(response.content)
        self.assertIn("error", data)


class TestFinancialOperationDecorator(TestCase):
    """Test the @financial_operation_error_handling decorator."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_catches_timeout_with_uncertain_message(self):
        """Timeout errors should produce uncertain outcome messages."""
        from .error_decorators import financial_operation_error_handling
        from external_services.exceptions import TimeoutError as ESLTimeout

        @financial_operation_error_handling(transaction_type="payment")
        def my_view(request):
            raise ESLTimeout("test_provider", timeout_seconds=30)

        request = self.factory.get("/api/v1/test/")
        response = my_view(request)
        data = json.loads(response.content)
        # Should not say "payment failed" - should say uncertain
        msg = data["error"]["message"].lower()
        self.assertNotIn("payment failed", msg)
        self.assertIn("confirm", msg)


class TestAuthErrorDecorator(TestCase):
    """Test the @auth_error_handling decorator."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_catches_auth_errors(self):
        """Auth errors should be caught with safe messages."""
        from .error_decorators import auth_error_handling

        @auth_error_handling()
        def my_view(request):
            raise PermissionError("Not allowed")

        request = self.factory.get("/api/v1/test/")
        response = my_view(request)
        data = json.loads(response.content)
        self.assertIn("error", data)


class TestValidationErrorDecorator(TestCase):
    """Test the @validation_error_handler decorator."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_catches_drf_validation_error(self):
        """DRF ValidationErrors should produce field-specific responses."""
        from .error_decorators import validation_error_handler
        from rest_framework.exceptions import ValidationError

        @validation_error_handler()
        def my_view(request):
            raise ValidationError({"email": ["Enter a valid email."]})

        request = self.factory.get("/api/v1/test/")
        response = my_view(request)
        data = json.loads(response.content)
        self.assertIn("fields", data["error"])
        self.assertIn("email", data["error"]["fields"])


# ======================================================================
# Financial Error Handler Tests
# ======================================================================


class TestFinancialErrorHandler(TestCase):
    """Test the FinancialErrorHandler."""

    def test_payment_failure_returns_funds_not_moved(self):
        """Definitive payment failures should confirm funds not moved."""
        from .financial_error_handler import FinancialErrorHandler

        handler = FinancialErrorHandler()
        result = handler.handle_payment_failure(
            transaction=MagicMock(id="txn-123"),
            error=ValueError("Card declined"),
        )
        self.assertFalse(result["success"])
        self.assertFalse(result["funds_moved"])

    def test_payment_uncertain_does_not_say_failed(self):
        """Uncertain payment outcomes must NOT say payment failed."""
        from .financial_error_handler import FinancialErrorHandler
        from external_services.exceptions import TimeoutError as ESLTimeout

        handler = FinancialErrorHandler()
        result = handler.handle_payment_uncertain(
            transaction=MagicMock(id="txn-123"),
            error=ESLTimeout("provider", timeout_seconds=30),
        )
        msg = result["user_message"].lower()
        self.assertNotIn("payment failed", msg)
        self.assertNotIn("failed", msg.split()[:3])  # Not at start

    def test_payment_uncertain_has_verification_pending(self):
        """Uncertain outcomes should have verification_pending=True."""
        from .financial_error_handler import FinancialErrorHandler
        from external_services.exceptions import TimeoutError as ESLTimeout

        handler = FinancialErrorHandler()
        result = handler.handle_payment_uncertain(
            transaction=MagicMock(id="txn-123"),
            error=ESLTimeout("provider", timeout_seconds=30),
        )
        self.assertTrue(result["verification_pending"])
        self.assertIsNone(result["funds_moved"])

    def test_withdrawal_failure_confirms_funds_safe(self):
        """Withdrawal failure should confirm funds are safe."""
        from .financial_error_handler import FinancialErrorHandler

        handler = FinancialErrorHandler()
        result = handler.handle_withdrawal_failure(
            withdrawal=MagicMock(id="wdl-123"),
            error=ValueError("Provider error"),
        )
        self.assertFalse(result["funds_moved"])

    def test_refund_pending_returns_success(self):
        """Pending refund should return success=True."""
        from .financial_error_handler import FinancialErrorHandler

        handler = FinancialErrorHandler()
        result = handler.handle_refund_pending(
            transaction=MagicMock(id="txn-123"),
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["refund_status"], "pending")

    def test_timeout_in_failure_handler_redirects_to_uncertain(self):
        """Timeout errors in handle_payment_failure should redirect to uncertain."""
        from .financial_error_handler import FinancialErrorHandler
        from external_services.exceptions import TimeoutError as ESLTimeout

        handler = FinancialErrorHandler()
        result = handler.handle_payment_failure(
            transaction=MagicMock(id="txn-123"),
            error=ESLTimeout("provider", timeout_seconds=30),
        )
        # Should be redirected to uncertain handler
        self.assertIsNone(result["funds_moved"])


# ======================================================================
# Admin Error Handler Tests
# ======================================================================


class TestAdminErrorHandler(TestCase):
    """Test the AdminErrorHandler."""

    def test_verification_failure_confirms_resource_safe(self):
        """Verification failure should confirm the resource is unchanged."""
        from .admin_error_handler import AdminErrorHandler

        handler = AdminErrorHandler()
        result = handler.handle_verification_failure(
            resource_type="kyc_application",
            resource_id="app-123",
            error=ValueError("Service down"),
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["resource_state"], "unchanged")

    def test_approval_failure_no_funds_moved(self):
        """Financial approval failure should confirm no funds moved."""
        from .admin_error_handler import AdminErrorHandler

        handler = AdminErrorHandler()
        result = handler.handle_approval_failure(
            resource_type="withdrawal",
            resource_id="wdl-123",
            error=ValueError("Service down"),
        )
        msg = result["user_message"].lower()
        self.assertIn("no funds have been moved", msg)
        self.assertEqual(result["resource_state"], "unchanged")

    def test_dual_approval_error_confirms_unchanged(self):
        """Dual approval error should confirm approval state unchanged."""
        from .admin_error_handler import AdminErrorHandler

        handler = AdminErrorHandler()
        approval = MagicMock(id="apr-123", status="PENDING")
        result = handler.handle_dual_approval_error(
            approval_request=approval,
            error=ValueError("Network error"),
        )
        self.assertEqual(result["resource_state"], "unchanged")
        self.assertIn("approval_id", result)

    @override_settings(DEBUG=False)
    def test_admin_messages_no_internals(self):
        """Admin error messages must not expose internal details."""
        with patch.dict(os.environ, {"DJANGO_ENV": "production"}):
            from .admin_error_handler import AdminErrorHandler

            handler = AdminErrorHandler()
            result = handler.handle_approval_failure(
                resource_type="withdrawal",
                resource_id="wdl-123",
                error=ValueError("Redis connection timeout to stripe-api.internal"),
            )
            msg = result["user_message"].lower()
            self.assertNotIn("redis", msg)
            self.assertNotIn("stripe", msg)
            self.assertNotIn("connection", msg)


# ======================================================================
# Background Job Monitor Tests
# ======================================================================


class TestBackgroundJobMonitor(TestCase):
    """Test the BackgroundJobMonitor state transitions."""

    def setUp(self):
        from .background_job_monitor import BackgroundJobMonitor
        self.monitor = BackgroundJobMonitor()

    @patch("core.background_job_monitor.cache")
    def test_mark_queued(self, mock_cache):
        """mark_queued should set state to QUEUED."""
        job_id = str(uuid.uuid4())
        self.monitor.mark_queued(job_id, "payment_verification")
        # Verify cache.set was called
        mock_cache.set.assert_called()

    @patch("core.background_job_monitor.cache")
    def test_mark_processing(self, mock_cache):
        """mark_processing should set state to PROCESSING."""
        mock_cache.get.return_value = json.dumps({
            "state": "QUEUED",
            "job_type": "payment_verification",
        })
        job_id = str(uuid.uuid4())
        self.monitor.mark_processing(job_id, progress=50)
        mock_cache.set.assert_called()

    @patch("core.background_job_monitor.cache")
    def test_mark_completed(self, mock_cache):
        """mark_completed should set state to COMPLETED and progress to 100."""
        mock_cache.get.return_value = json.dumps({
            "state": "PROCESSING",
            "job_type": "payment_verification",
            "progress": 50,
        })
        job_id = str(uuid.uuid4())
        self.monitor.mark_completed(job_id, result={"status": "verified"})
        mock_cache.set.assert_called()

    @patch("core.background_job_monitor.cache")
    def test_mark_failed(self, mock_cache):
        """mark_failed should set state to FAILED with error info."""
        mock_cache.get.return_value = json.dumps({
            "state": "PROCESSING",
            "job_type": "payment_verification",
        })
        job_id = str(uuid.uuid4())
        self.monitor.mark_failed(
            job_id, "PAYMENT_PROVIDER_UNAVAILABLE", "Payment failed", True
        )
        mock_cache.set.assert_called()

    @patch("core.background_job_monitor.cache")
    def test_mark_retrying(self, mock_cache):
        """mark_retrying should set state to RETRYING with attempt number."""
        mock_cache.get.return_value = json.dumps({
            "state": "FAILED",
            "job_type": "payment_verification",
        })
        job_id = str(uuid.uuid4())
        self.monitor.mark_retrying(job_id, attempt_number=2)
        mock_cache.set.assert_called()

    @patch("core.background_job_monitor.cache")
    def test_get_user_facing_status_no_internal_details(self, mock_cache):
        """User-facing status must not include internal details."""
        mock_cache.get.return_value = json.dumps({
            "state": "FAILED",
            "job_type": "payment_verification",
            "error_code": "PAYMENT_PROVIDER_UNAVAILABLE",
            "metadata": {"provider": "stripe", "internal_id": "abc"},
        })
        job_id = str(uuid.uuid4())
        status = self.monitor.get_user_facing_status(job_id)
        # Should not expose internal metadata
        self.assertNotIn("metadata", status)
        self.assertNotIn("provider", status)
        self.assertNotIn("stripe", json.dumps(status))

    @patch("core.background_job_monitor.cache")
    def test_get_user_facing_status_unknown_job(self, mock_cache):
        """Unknown jobs should return UNKNOWN state."""
        mock_cache.get.return_value = None
        job_id = str(uuid.uuid4())
        status = self.monitor.get_user_facing_status(job_id)
        self.assertEqual(status["state"], "UNKNOWN")

    @patch("core.background_job_monitor.cache")
    def test_state_transitions(self, mock_cache):
        """Jobs should transition: QUEUED → PROCESSING → COMPLETED."""
        states = []
        job_id = str(uuid.uuid4())

        # Track what gets set
        def capture_set(key, value, **kwargs):
            data = json.loads(value) if isinstance(value, str) else value
            states.append(data.get("state"))

        mock_cache.set.side_effect = capture_set
        mock_cache.get.return_value = None

        self.monitor.mark_queued(job_id, "test")
        self.assertEqual(states[-1], "QUEUED")

        mock_cache.get.return_value = json.dumps({"state": "QUEUED", "job_type": "test"})
        self.monitor.mark_processing(job_id)
        self.assertEqual(states[-1], "PROCESSING")

        mock_cache.get.return_value = json.dumps({"state": "PROCESSING", "job_type": "test"})
        self.monitor.mark_completed(job_id)
        self.assertEqual(states[-1], "COMPLETED")


# ======================================================================
# Auth Error Handler Tests
# ======================================================================


class TestAuthErrorHandler(TestCase):
    """Test the AuthErrorHandler."""

    def test_invalid_credentials_generic_message(self):
        """Invalid credentials should return a generic message."""
        from .auth_error_handler import AuthErrorHandler

        handler = AuthErrorHandler()
        result = handler.handle_invalid_credentials()
        # Must not reveal which field was wrong
        msg = result["user_message"].lower()
        self.assertIn("email or password", msg)

    def test_session_expired_redirect(self):
        """Session expired should include a redirect URL."""
        from .auth_error_handler import AuthErrorHandler

        handler = AuthErrorHandler()
        result = handler.handle_session_expired()
        self.assertIn("redirect_url", result)
        self.assertIn("login", result["redirect_url"])

    def test_account_locked_no_lockout_duration(self):
        """Account locked must not reveal lockout duration."""
        from .auth_error_handler import AuthErrorHandler

        handler = AuthErrorHandler()
        result = handler.handle_account_locked()
        msg = result["user_message"].lower()
        # Should not say "locked for 15 minutes" etc.
        for phrase in ["15 minutes", "30 minutes", "1 hour", "locked for"]:
            self.assertNotIn(phrase, msg)

    def test_mfa_required_no_type_revealed(self):
        """MFA required must not reveal the MFA type."""
        from .auth_error_handler import AuthErrorHandler

        handler = AuthErrorHandler()
        result = handler.handle_mfa_required()
        msg = result["user_message"].lower()
        for mfa_type in ["totp", "sms", "authenticator", "hardware key", "yubikey"]:
            self.assertNotIn(mfa_type, msg)

    def test_suspicious_activity_no_trigger_revealed(self):
        """Suspicious activity must not reveal what triggered it."""
        from .auth_error_handler import AuthErrorHandler

        handler = AuthErrorHandler()
        result = handler.handle_suspicious_activity()
        msg = result["user_message"].lower()
        for trigger in ["ip address", "new device", "unusual location", "vpn"]:
            self.assertNotIn(trigger, msg)

    def test_all_auth_errors_have_reference_id(self):
        """All auth error responses must have a reference_id."""
        from .auth_error_handler import AuthErrorHandler

        handler = AuthErrorHandler()
        methods = [
            handler.handle_invalid_credentials,
            handler.handle_session_expired,
            handler.handle_account_locked,
            handler.handle_mfa_required,
            handler.handle_suspicious_activity,
        ]
        for method in methods:
            result = method()
            self.assertIn("reference_id", result)
            self.assertTrue(len(result["reference_id"]) > 0)


# ======================================================================
# Database Degradation Tests
# ======================================================================


class TestDatabaseDegradationHandler(TestCase):
    """Test the DatabaseDegradationHandler."""

    @patch("core.db_degradation.cache")
    def test_handle_connection_failure_sets_read_only(self, mock_cache):
        """Connection failure should set read-only mode."""
        from .db_degradation import DatabaseDegradationHandler

        handler = DatabaseDegradationHandler()
        result = handler.handle_connection_failure()
        self.assertTrue(result.get("read_only_mode", False))

    @patch("core.db_degradation.cache")
    def test_handle_write_failure_queues_write(self, mock_cache):
        """Write failure should queue the write operation."""
        from .db_degradation import DatabaseDegradationHandler

        handler = DatabaseDegradationHandler()
        factory = RequestFactory()
        request = factory.post("/api/v1/test/", data={})

        result = handler.handle_write_failure(
            request=request, operation="update_parcel"
        )
        self.assertIn("write_queued", result)

    @patch("core.db_degradation.cache")
    def test_is_read_only_mode(self, mock_cache):
        """is_read_only_mode should check the cache flag."""
        from .db_degradation import DatabaseDegradationHandler

        handler = DatabaseDegradationHandler()

        mock_cache.get.return_value = True
        self.assertTrue(handler.is_read_only_mode())

        mock_cache.get.return_value = False
        self.assertFalse(handler.is_read_only_mode())

    @patch("core.db_degradation.cache")
    def test_clear_read_only_mode(self, mock_cache):
        """clear_read_only_mode should clear the cache flag."""
        from .db_degradation import DatabaseDegradationHandler

        handler = DatabaseDegradationHandler()
        handler.clear_read_only_mode()
        mock_cache.delete.assert_called()


# ======================================================================
# Third-Party Degradation Tests
# ======================================================================


class TestThirdPartyDegradationHandler(TestCase):
    """Test the ThirdPartyDegradationHandler."""

    @patch("core.third_party_degradation.cache")
    def test_payment_provider_failure_queues_retry(self, mock_cache):
        """Payment provider failure should queue for retry."""
        from .third_party_degradation import ThirdPartyDegradationHandler

        handler = ThirdPartyDegradationHandler()
        result = handler.handle_payment_provider_failure(
            provider="stripe",  # Internal only
            error=ValueError("Connection refused"),
            transaction=MagicMock(id="txn-123"),
        )
        self.assertTrue(result["retry_queued"])

    @override_settings(DEBUG=False)
    def test_payment_failure_no_provider_name(self, mock_cache=None):
        """Payment failure message must not include provider name."""
        from .third_party_degradation import ThirdPartyDegradationHandler

        handler = ThirdPartyDegradationHandler()
        result = handler.handle_payment_provider_failure(
            provider="mpesa",
            error=ValueError("Timeout"),
        )
        msg = result["user_message"].lower()
        self.assertNotIn("mpesa", msg)

    @patch("core.third_party_degradation.cache")
    def test_email_failure_still_succeeds(self, mock_cache):
        """Email failure should not block account creation."""
        from .third_party_degradation import ThirdPartyDegradationHandler

        handler = ThirdPartyDegradationHandler()
        result = handler.handle_email_provider_failure(
            provider="sendgrid",
            error=ValueError("API error"),
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["email_delayed"])

    @patch("core.third_party_degradation.cache")
    def test_sms_failure_uses_fallback(self, mock_cache):
        """SMS failure should use in-app notification as fallback."""
        from .third_party_degradation import ThirdPartyDegradationHandler

        handler = ThirdPartyDegradationHandler()
        result = handler.handle_sms_provider_failure(
            provider="twilio",
            error=ValueError("Rate limited"),
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["fallback_notification_sent"])

    @patch("core.third_party_degradation.cache")
    def test_ai_failure_returns_cached_or_default(self, mock_cache):
        """AI failure should return cached response if available."""
        from .third_party_degradation import ThirdPartyDegradationHandler

        handler = ThirdPartyDegradationHandler()
        result = handler.handle_ai_provider_failure(
            provider="openai",
            error=ValueError("Rate limited"),
            request_type="price_prediction",
        )
        # Either returns cached (success=True) or error (success=False)
        self.assertIn("success", result)

    @patch("core.third_party_degradation.cache")
    def test_identity_failure_allows_limited_access(self, mock_cache):
        """Identity provider failure should allow limited access."""
        from .third_party_degradation import ThirdPartyDegradationHandler

        handler = ThirdPartyDegradationHandler()
        result = handler.handle_identity_provider_failure(
            provider="jumio",
            error=ValueError("Service down"),
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["limited_access"])


# ======================================================================
# Observability Tests
# ======================================================================


class TestErrorObservability(TestCase):
    """Test the ErrorObservability class."""

    @patch("core.observability.cache")
    def test_track_error_increments_counters(self, mock_cache):
        """track_error should increment error counters."""
        from .observability import ErrorObservability

        obs = ErrorObservability()
        obs.track_error("AUTH_INVALID_CREDENTIALS", request_id="req-123")
        # Should have called cache.set for counters
        self.assertTrue(mock_cache.set.called)

    @patch("core.observability.cache")
    def test_track_retry(self, mock_cache):
        """track_retry should increment retry counters."""
        from .observability import ErrorObservability

        obs = ErrorObservability()
        obs.track_retry("PAYMENT_PROVIDER_UNAVAILABLE", attempt=2, request_id="req-123")
        self.assertTrue(mock_cache.set.called)

    @patch("core.observability.cache")
    def test_track_fallback(self, mock_cache):
        """track_fallback should increment fallback counters."""
        from .observability import ErrorObservability

        obs = ErrorObservability()
        obs.track_fallback(
            "SEARCH_UNAVAILABLE", "cached_response", request_id="req-123"
        )
        self.assertTrue(mock_cache.set.called)

    @patch("core.observability.cache")
    def test_track_recovery(self, mock_cache):
        """track_recovery should increment recovery counters."""
        from .observability import ErrorObservability

        obs = ErrorObservability()
        obs.track_recovery(
            "PAYMENT_PROVIDER_UNAVAILABLE",
            "retry",
            request_id="req-123",
            time_to_recovery_ms=5000,
        )
        self.assertTrue(mock_cache.set.called)

    @patch("core.observability.cache")
    def test_get_error_hotspots(self, mock_cache):
        """get_error_hotspots should return sorted error frequencies."""
        from .observability import ErrorObservability

        obs = ErrorObservability()
        mock_cache.get.return_value = None  # No timeline data
        hotspots = obs.get_error_hotspots(time_window_minutes=5)
        self.assertIsInstance(hotspots, list)

    @patch("core.observability.cache")
    def test_get_error_rate(self, mock_cache):
        """get_error_rate should return rate information."""
        from .observability import ErrorObservability

        obs = ErrorObservability()
        mock_cache.get.return_value = None
        rate = obs.get_error_rate(time_window_minutes=5)
        self.assertIn("total_errors", rate)
        self.assertIn("error_rate_per_minute", rate)
        self.assertIn("hotspots", rate)


# ======================================================================
# Integration / Safety Tests
# ======================================================================


class TestSafetyInvariants(TestCase):
    """Test that safety invariants hold across the entire system."""

    @override_settings(DEBUG=False)
    def test_no_production_response_leaks_secrets(self):
        """Production responses must never contain secrets or internal details."""
        with patch.dict(os.environ, {"DJANGO_ENV": "production"}):
            # Test various error response types
            responses = [
                create_error_response("SYSTEM_UNKNOWN_ERROR"),
                create_error_response("DATABASE_UNAVAILABLE"),
                create_error_response("PAYMENT_PROVIDER_UNAVAILABLE"),
                create_error_response("EXTERNAL_SERVICE_UNAVAILABLE"),
                create_financial_error_response(
                    "txn-123", "PAYMENT_PROCESSING_FAILED"
                ),
                create_auth_error_response("AUTH_INVALID_CREDENTIALS"),
            ]

            sensitive_patterns = [
                "stripe", "mpesa", "paystack", "kcb", "daraja",
                "redis", "celery", "postgresql", "postgis",
                "sentry", "elasticsearch",
                "api_key", "secret_key", "password", "credential",
                "traceback", "exception_type",
                "connection string", "dsn",
                "stack trace",
            ]

            for response in responses:
                content = response.content.decode().lower()
                for pattern in sensitive_patterns:
                    self.assertNotIn(
                        pattern, content,
                        f"Production response contains sensitive pattern '{pattern}'"
                    )

    def test_all_responses_include_reference_id(self):
        """All error response types must include a reference_id."""
        responses = [
            create_error_response("SYSTEM_UNKNOWN_ERROR"),
            create_validation_error_response({"field": ["error"]}),
            create_financial_error_response("txn-123", "PAYMENT_PROCESSING_FAILED"),
            create_auth_error_response("AUTH_INVALID_CREDENTIALS"),
        ]

        for response in responses:
            data = json.loads(response.content)
            self.assertIn(
                "reference_id", data["error"],
                "Response missing reference_id"
            )

    def test_all_responses_include_error_code(self):
        """All error response types must include an error code."""
        responses = [
            create_error_response("NETWORK_TIMEOUT"),
            create_validation_error_response({"field": ["error"]}),
            create_financial_error_response("txn-123", "PAYMENT_PROVIDER_UNAVAILABLE"),
            create_auth_error_response("AUTH_SESSION_EXPIRED"),
        ]

        for response in responses:
            data = json.loads(response.content)
            self.assertIn(
                "code", data["error"],
                "Response missing error code"
            )

    def test_financial_responses_always_include_funds_status(self):
        """Financial error responses must always include funds_status."""
        for funds_moved in [True, False]:
            response = create_financial_error_response(
                "txn-123",
                "PAYMENT_PROCESSING_FAILED",
                funds_moved=funds_moved,
            )
            data = json.loads(response.content)
            self.assertIn("funds_status", data["error"])

    @override_settings(DEBUG=False)
    def test_database_error_messages_are_safe(self):
        """Database error messages must not reveal DB details."""
        with patch.dict(os.environ, {"DJANGO_ENV": "production"}):
            response = create_error_response("DATABASE_UNAVAILABLE")
            data = json.loads(response.content)
            msg = data["error"]["message"].lower()
            for pattern in ["postgresql", "sqlite", "table", "column", "sql", "query"]:
                self.assertNotIn(pattern, msg)

    @override_settings(DEBUG=False)
    def test_all_taxonomy_user_messages_safe(self):
        """All taxonomy user messages must be safe for production."""
        with patch.dict(os.environ, {"DJANGO_ENV": "production"}):
            for code, defn in ERROR_REGISTRY.items():
                msg = defn.user_message.lower()
                for pattern in [
                    "stripe", "mpesa", "paystack", "redis", "celery",
                    "postgresql", "sql", "traceback", "stack trace",
                    "database", "table", "column", "http://",
                ]:
                    self.assertNotIn(
                        pattern, msg,
                        f"Taxonomy error '{code}' user_message contains '{pattern}'"
                    )
