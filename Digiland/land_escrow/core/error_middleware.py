"""
Django middleware for centralized error handling and graceful degradation.

Middleware classes:
- GracefulDegradationMiddleware: Catches all unhandled exceptions
- DatabaseDegradationMiddleware: Handles database connection/write failures
- ExternalServiceDegradationMiddleware: Maps ExternalServiceError to safe responses

SECURITY: Production errors MUST NEVER expose stack traces, SQL errors,
database names, internal service names, provider names, etc.
"""

from __future__ import annotations

import logging
import traceback
import uuid
from typing import Any, Callable, Dict, Optional

from django.conf import settings
from django.db import OperationalError, InterfaceError, DatabaseError
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.core.cache import cache

from .error_taxonomy import (
    map_exception_to_error_code,
    get_error_definition,
    ErrorCategory,
)
from .error_responses import create_error_response

logger = logging.getLogger(__name__)


# ======================================================================
# Sensitive data scrubbing for internal logs
# ======================================================================

_LOG_SCRUB_PATTERNS = [
    "password", "secret", "token", "api_key", "api-key",
    "authorization", "cookie", "session",
]


def _scrub_log_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive values from log context."""
    scrubbed = {}
    for key, value in context.items():
        key_lower = key.lower()
        if any(p in key_lower for p in _LOG_SCRUB_PATTERNS):
            scrubbed[key] = "[REDACTED]"
        elif isinstance(value, dict):
            scrubbed[key] = _scrub_log_context(value)
        elif isinstance(value, str) and len(value) > 500:
            # Truncate very long values
            scrubbed[key] = value[:500] + "... [truncated]"
        else:
            scrubbed[key] = value
    return scrubbed


def _get_request_context(request: HttpRequest) -> Dict[str, Any]:
    """Extract safe context from the request for logging."""
    user = getattr(request, "user", None)
    context: Dict[str, Any] = {
        "method": request.method,
        "path": request.path,
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
    }
    if user and getattr(user, "is_authenticated", False):
        context["user_id"] = str(getattr(user, "id", "unknown"))
        context["user_role"] = getattr(user, "role", "unknown")
    # Client IP
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        context["client_ip"] = xff.split(",")[0].strip()
    else:
        context["client_ip"] = request.META.get("REMOTE_ADDR", "unknown")
    return context


def _is_api_request(request: HttpRequest) -> bool:
    """Check if the request expects a JSON response."""
    path = request.path
    accept = request.META.get("HTTP_ACCEPT", "")
    if path.startswith("/api/"):
        return True
    if "application/json" in accept:
        return True
    return False


def _is_production() -> bool:
    """Check if running in production."""
    if getattr(settings, "DEBUG", False):
        return False
    import os
    return os.environ.get("DJANGO_ENV", "").lower() in ("production", "staging")


# ======================================================================
# GracefulDegradationMiddleware
# ======================================================================


class GracefulDegradationMiddleware:
    """Catch all unhandled exceptions and return safe error responses.

    In production:
    - Returns a safe, user-friendly JSON error with a reference ID
    - Logs the full error context internally (Sentry, structured logs)

    In development:
    - Returns detailed error info for debugging

    NEVER exposes to users:
    - Stack traces
    - SQL errors
    - Database names / table names
    - Internal service names (Stripe, M-Pesa, Redis, etc.)
    - Infrastructure details
    - Provider names
    - Secret values
    """

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        try:
            return self.get_response(request)
        except Exception as exc:
            return self._handle_exception(request, exc)

    def _handle_exception(self, request: HttpRequest, exc: Exception) -> HttpResponse:
        """Convert an unhandled exception to a safe error response."""
        error_code = map_exception_to_error_code(exc)
        reference_id = str(uuid.uuid4())
        request_context = _get_request_context(request)

        # Build internal log context with FULL details
        log_context = _scrub_log_context({
            "reference_id": reference_id,
            "error_code": error_code,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc)[:1000],
            "request": request_context,
            "traceback": traceback.format_exc()[:5000],
        })

        # Log internally with full context
        definition = get_error_definition(error_code)
        log_level = getattr(
            logging,
            definition.log_level.upper() if definition else "ERROR",
            logging.ERROR,
        )
        logger.log(
            log_level,
            "Unhandled exception: code=%s ref=%s exc=%s",
            error_code,
            reference_id,
            type(exc).__name__,
            extra=log_context,
        )

        # Try to send to Sentry if available
        self._capture_sentry(exc, reference_id, request_context)

        # Return safe response
        if _is_api_request(request):
            response = create_error_response(
                error_code=error_code,
                request_id=reference_id,
                details={
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc)[:200],
                },
            )
        else:
            # For non-API requests, return a simple JSON response
            if _is_production():
                response = JsonResponse(
                    {
                        "error": {
                            "code": error_code,
                            "message": (
                                definition.user_message
                                if definition
                                else "Something went wrong. Please try again later."
                            ),
                            "reference_id": reference_id,
                        }
                    },
                    status=definition.http_status_code if definition else 500,
                )
            else:
                response = JsonResponse(
                    {
                        "error": {
                            "code": error_code,
                            "message": (
                                definition.user_message
                                if definition
                                else "Something went wrong."
                            ),
                            "reference_id": reference_id,
                            "_debug": {
                                "exception_type": type(exc).__name__,
                                "exception_message": str(exc)[:500],
                                "traceback": traceback.format_exc()[:3000],
                            },
                        }
                    },
                    status=definition.http_status_code if definition else 500,
                )

        response["X-Reference-ID"] = reference_id
        return response

    def _capture_sentry(
        self,
        exc: Exception,
        reference_id: str,
        request_context: Dict[str, Any],
    ) -> None:
        """Attempt to capture the exception in Sentry if configured."""
        try:
            import sentry_sdk
            sentry_sdk.set_tag("reference_id", reference_id)
            sentry_sdk.set_context("request", _scrub_log_context(request_context))
            sentry_sdk.capture_exception(exc)
        except ImportError:
            pass  # Sentry not configured
        except Exception:
            pass  # Don't let Sentry failures break error handling


# ======================================================================
# DatabaseDegradationMiddleware
# ======================================================================


class DatabaseDegradationMiddleware:
    """Handle database failures gracefully.

    On database connection errors:
    1. Returns a cached response if available
    2. Sets a "read-only mode" flag on the request
    3. Returns a user-friendly "temporarily in read-only mode" message
       for write operations
    """

    # Cache key for read-only mode flag
    READ_ONLY_CACHE_KEY = "digiland:db:read_only_mode"
    READ_ONLY_TTL = 300  # 5 minutes

    # HTTP methods that require database writes
    WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Check if we're already in read-only mode
        if self._is_read_only_mode():
            request.db_read_only = True
            if request.method in self.WRITE_METHODS and _is_api_request(request):
                return self._read_only_response(request)

        try:
            response = self.get_response(request)
            # If we were in read-only mode and the request succeeded (read),
            # the DB might be back — clear the flag
            if getattr(request, "db_read_only", False):
                self._clear_read_only_mode()
            return response
        except (OperationalError, InterfaceError) as exc:
            return self._handle_db_error(request, exc)
        except DatabaseError as exc:
            # Other database errors might be transient
            if "connection" in str(exc).lower() or "timeout" in str(exc).lower():
                return self._handle_db_error(request, exc)
            raise  # Let GracefulDegradationMiddleware handle it

    def _handle_db_error(
        self, request: HttpRequest, exc: Exception
    ) -> HttpResponse:
        """Handle a database connection error."""
        reference_id = str(uuid.uuid4())

        # Set read-only mode flag in cache
        self._set_read_only_mode()

        # Log with full context
        logger.critical(
            "Database degradation: ref=%s exc=%s path=%s method=%s",
            reference_id,
            type(exc).__name__,
            request.path,
            request.method,
            extra={
                "reference_id": reference_id,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc)[:500],
                "request": _get_request_context(request),
            },
        )

        # Try to return a cached response for reads
        if request.method == "GET":
            cached = self._get_cached_response(request)
            if cached is not None:
                cached["X-DB-Degraded"] = "true"
                cached["X-Reference-ID"] = reference_id
                return cached

        # For writes or uncached reads
        request.db_read_only = True

        if request.method in self.WRITE_METHODS:
            return self._read_only_response(request, reference_id)

        # For reads without cache
        return create_error_response(
            error_code="DATABASE_UNAVAILABLE",
            request_id=reference_id,
        )

    def _read_only_response(
        self,
        request: HttpRequest,
        reference_id: Optional[str] = None,
    ) -> JsonResponse:
        """Return a read-only mode response for write operations."""
        if reference_id is None:
            reference_id = str(uuid.uuid4())

        response = create_error_response(
            error_code="DATABASE_READ_ONLY",
            request_id=reference_id,
        )
        response["X-DB-Read-Only"] = "true"
        return response

    def _is_read_only_mode(self) -> bool:
        """Check if the system is currently in read-only mode."""
        try:
            return bool(cache.get(self.READ_ONLY_CACHE_KEY, False))
        except Exception:
            return False

    def _set_read_only_mode(self) -> None:
        """Set the read-only mode flag in cache."""
        try:
            cache.set(self.READ_ONLY_CACHE_KEY, True, timeout=self.READ_ONLY_TTL)
        except Exception:
            pass

    def _clear_read_only_mode(self) -> None:
        """Clear the read-only mode flag from cache."""
        try:
            cache.delete(self.READ_ONLY_CACHE_KEY)
        except Exception:
            pass

    def _get_cached_response(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Try to retrieve a cached response for this request path."""
        cache_key = f"digiland:db:cache:{request.get_full_path()}"
        try:
            cached_data = cache.get(cache_key)
            if cached_data:
                return JsonResponse(cached_data, safe=False)
        except Exception:
            pass
        return None


# ======================================================================
# ExternalServiceDegradationMiddleware
# ======================================================================


class ExternalServiceDegradationMiddleware:
    """Handle external service failures gracefully.

    Catches ExternalServiceError and its subclasses, maps them to
    appropriate user-safe error codes, returns fallback responses
    where possible, and logs internally with full context.
    """

    # Map ESL service types to user-safe error codes
    SERVICE_TYPE_ERROR_MAP: Dict[str, str] = {
        "payment": "PAYMENT_PROVIDER_UNAVAILABLE",
        "email": "NOTIFICATION_PROVIDER_UNAVAILABLE",
        "sms": "NOTIFICATION_PROVIDER_UNAVAILABLE",
        "push": "NOTIFICATION_DELIVERY_FAILED",
        "storage": "FILE_UPLOAD_FAILED",
        "ai": "EXTERNAL_SERVICE_UNAVAILABLE",
        "search": "SEARCH_UNAVAILABLE",
        "analytics": "EXTERNAL_SERVICE_UNAVAILABLE",
        "identity": "EXTERNAL_SERVICE_UNAVAILABLE",
        "maps": "EXTERNAL_SERVICE_UNAVAILABLE",
        "fraud_detection": "EXTERNAL_SERVICE_UNAVAILABLE",
        "accounting": "EXTERNAL_SERVICE_UNAVAILABLE",
        "crm": "EXTERNAL_SERVICE_UNAVAILABLE",
        "erp": "EXTERNAL_SERVICE_UNAVAILABLE",
    }

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        try:
            return self.get_response(request)
        except Exception as exc:
            # Check if this is an ExternalServiceError
            from external_services.exceptions import (
                ExternalServiceError,
                ProviderUnavailableError,
                CircuitBreakerOpenError,
                RateLimitExceededError,
                TimeoutError as ESLTimeoutError,
            )

            if isinstance(exc, ExternalServiceError):
                return self._handle_external_error(request, exc)

            raise  # Not an external service error; let other middleware handle it

    def _handle_external_error(
        self, request: HttpRequest, exc: "ExternalServiceError"
    ) -> HttpResponse:
        """Map an ExternalServiceError to a safe user response."""
        reference_id = str(uuid.uuid4())
        error_code = self._map_to_error_code(exc)

        # Log with full ESL context (internal only - never exposed to users)
        log_context = _scrub_log_context({
            "reference_id": reference_id,
            "error_code": error_code,
            "esl_error": exc.to_dict(),
            "request": _get_request_context(request),
        })
        logger.error(
            "External service error: code=%s ref=%s service=%s provider=%s",
            error_code,
            reference_id,
            exc.service_type,
            exc.provider_name,
            extra=log_context,
        )

        # Determine user message based on service type
        user_message = self._get_user_message(exc)

        response = create_error_response(
            error_code=error_code,
            user_message=user_message,
            request_id=reference_id,
            details={
                "service_type": exc.service_type,
                # NOTE: provider_name is NOT included — it's internal
                "is_retryable": exc.is_retryable,
            },
        )
        response["X-Reference-ID"] = reference_id
        return response

    def _map_to_error_code(self, exc: "ExternalServiceError") -> str:
        """Map an ExternalServiceError to the best error code."""
        from external_services.exceptions import (
            ProviderUnavailableError,
            CircuitBreakerOpenError,
            RateLimitExceededError,
            TimeoutError as ESLTimeoutError,
        )

        # Specific ESL error types
        if isinstance(exc, RateLimitExceededError):
            return "EXTERNAL_SERVICE_RATE_LIMITED"
        if isinstance(exc, ESLTimeoutError):
            return "EXTERNAL_SERVICE_TIMEOUT"
        if isinstance(exc, (ProviderUnavailableError, CircuitBreakerOpenError)):
            # Map to service-type-specific code if available
            if exc.service_type and exc.service_type in self.SERVICE_TYPE_ERROR_MAP:
                return self.SERVICE_TYPE_ERROR_MAP[exc.service_type]
            return "EXTERNAL_SERVICE_UNAVAILABLE"

        # Generic ESL error — try service type mapping
        if exc.service_type and exc.service_type in self.SERVICE_TYPE_ERROR_MAP:
            return self.SERVICE_TYPE_ERROR_MAP[exc.service_type]

        return "EXTERNAL_SERVICE_UNAVAILABLE"

    def _get_user_message(self, exc: "ExternalServiceError") -> Optional[str]:
        """Get a service-type-specific user message.

        These messages are more helpful than the generic taxonomy
        messages while still not exposing any internal details.
        """
        messages = {
            "payment": "We're unable to process payments right now. Your money has not been debited. Please try again in a few minutes.",
            "email": "Email delivery is temporarily delayed, but your request was processed successfully.",
            "sms": "SMS notifications are temporarily delayed. We'll send them as soon as possible.",
            "push": "Push notifications are temporarily unavailable. Your action was still completed.",
            "storage": "File storage is temporarily unavailable. Please try uploading again later.",
            "ai": "AI-powered features are temporarily unavailable. Basic functionality still works.",
            "search": "Search is temporarily unavailable. Please try again in a moment.",
            "analytics": "Analytics are temporarily unavailable. Your data is still being tracked.",
            "identity": "Identity verification is temporarily unavailable. You can continue with limited access.",
            "maps": "Map features are temporarily unavailable. Basic location information is still shown.",
        }
        if exc.service_type:
            return messages.get(exc.service_type)
        return None
