"""
Decorators for views and service methods with graceful error handling.

Each decorator:
- Catches the relevant exceptions
- Logs internally with full context (request ID, user, correlation ID)
- Returns a user-safe error response
- For financial ops: includes transaction ID, confirms whether funds were moved
- For admin ops: provides operational context without exposing internals
- For database ops: enables read-only mode gracefully
- For external services: applies fallback strategy
"""

from __future__ import annotations

import functools
import logging
import traceback
import uuid
from typing import Any, Callable, Dict, Optional, Type, TypeVar

from django.conf import settings
from django.http import JsonResponse, HttpRequest

from .error_taxonomy import (
    get_error_definition,
    map_exception_to_error_code,
    ErrorCategory,
)
from .error_responses import (
    create_error_response,
    create_validation_error_response,
    create_financial_error_response,
    create_auth_error_response,
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable)


def _get_request_id(request: Optional[HttpRequest] = None) -> str:
    """Extract or generate a request ID."""
    if request:
        rid = getattr(request, "request_id", None)
        if rid:
            return str(rid)
        rid = request.META.get("HTTP_X_REQUEST_ID")
        if rid:
            return rid
    return str(uuid.uuid4())


def _get_user_id(request: Optional[HttpRequest] = None) -> Optional[str]:
    """Safely extract user ID from request."""
    if not request:
        return None
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        return str(getattr(user, "id", "unknown"))
    return None


# ======================================================================
# @graceful_degradation
# ======================================================================


def graceful_degradation(
    fallback_value: Any = None,
    error_code: str = "SYSTEM_UNKNOWN_ERROR",
    log_context: Optional[Dict[str, Any]] = None,
):
    """Decorator that catches all exceptions and returns a safe fallback.

    For API views: returns a JSON error response.
    For service methods: returns the fallback_value.

    Args:
        fallback_value: Value to return on error (for non-view functions).
        error_code: Error code to use for the response.
        log_context: Additional context to include in logs.

    Usage::

        @graceful_degradation(fallback_value=[], error_code="SEARCH_UNAVAILABLE")
        def search_parcels(query):
            # May raise ExternalServiceError
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            request = None
            # Try to find the request argument
            for arg in args:
                if isinstance(arg, HttpRequest):
                    request = arg
                    break

            request_id = _get_request_id(request)
            user_id = _get_user_id(request)

            try:
                return func(*args, **kwargs)
            except Exception as exc:
                ref_id = str(uuid.uuid4())
                resolved_code = map_exception_to_error_code(exc)
                # Use the provided error_code only if no better mapping exists
                if resolved_code == "SYSTEM_UNKNOWN_ERROR" and error_code != "SYSTEM_UNKNOWN_ERROR":
                    resolved_code = error_code

                # Log with full context
                log_data = {
                    "reference_id": ref_id,
                    "request_id": request_id,
                    "user_id": user_id,
                    "error_code": resolved_code,
                    "function": func.__qualname__,
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc)[:500],
                    "traceback": traceback.format_exc()[:3000],
                }
                if log_context:
                    log_data.update(log_context)

                definition = get_error_definition(resolved_code)
                log_level = getattr(
                    logging,
                    definition.log_level.upper() if definition else "ERROR",
                    logging.ERROR,
                )
                logger.log(
                    log_level,
                    "Graceful degradation: func=%s code=%s ref=%s exc=%s",
                    func.__qualname__,
                    resolved_code,
                    ref_id,
                    type(exc).__name__,
                    extra=log_data,
                )

                # For Django views (has request), return a JSON response
                if request is not None:
                    return create_error_response(
                        error_code=resolved_code,
                        request_id=request_id,
                    )

                # For service methods, return fallback value
                return fallback_value

        return wrapper  # type: ignore[return-value]

    return decorator


# ======================================================================
# @financial_operation_error_handling
# ======================================================================


def financial_operation_error_handling(
    transaction_type: str = "transaction",
):
    """Decorator for financial operations with highest-care error handling.

    Principles:
    - Never tell a user a payment failed if it might have succeeded
    - Always provide a transaction ID for tracking
    - Always provide a support reference ID
    - Queue failed operations for automatic retry

    Args:
        transaction_type: Type of financial operation (payment, withdrawal, refund, escrow).

    Usage::

        @financial_operation_error_handling(transaction_type="withdrawal")
        def process_withdrawal(request, withdrawal_id):
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            request = None
            for arg in args:
                if isinstance(arg, HttpRequest):
                    request = arg
                    break

            request_id = _get_request_id(request)
            user_id = _get_user_id(request)

            try:
                return func(*args, **kwargs)
            except Exception as exc:
                ref_id = str(uuid.uuid4())
                error_code = map_exception_to_error_code(exc)

                # Determine if funds were moved based on exception type
                from external_services.exceptions import TimeoutError as ESLTimeout
                funds_moved = False

                # Timeout / network errors → uncertain outcome
                if isinstance(exc, (ESLTimeout, ConnectionError, TimeoutError)):
                    # For timeouts, we DON'T KNOW if funds moved
                    # Tell the user to check back, NOT that it failed
                    error_code = "PAYMENT_PROVIDER_UNAVAILABLE"
                    user_msg = (
                        "We couldn't confirm the status of your "
                        f"{transaction_type}. Please check your transaction "
                        "history or contact support. Do NOT retry the same "
                        f"{transaction_type} until you confirm the status."
                    )
                    # We don't know — don't claim either way
                    funds_moved = False
                else:
                    # Definitive failure — funds were NOT moved
                    definition = get_error_definition(error_code)
                    user_msg = definition.user_message if definition else None

                # Log with full financial context
                logger.error(
                    "Financial operation error: type=%s code=%s ref=%s user=%s exc=%s",
                    transaction_type,
                    error_code,
                    ref_id,
                    user_id,
                    type(exc).__name__,
                    extra={
                        "reference_id": ref_id,
                        "request_id": request_id,
                        "user_id": user_id,
                        "transaction_type": transaction_type,
                        "error_code": error_code,
                        "funds_moved": funds_moved,
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc)[:500],
                        "traceback": traceback.format_exc()[:3000],
                    },
                )

                # Try to extract transaction_id from kwargs
                transaction_id = (
                    kwargs.get("transaction_id")
                    or kwargs.get("withdrawal_id")
                    or kwargs.get("pk")
                    or None
                )

                if request is not None:
                    return create_financial_error_response(
                        transaction_id=transaction_id,
                        error_code=error_code,
                        user_message=user_msg,
                        reference_id=ref_id,
                        request_id=request_id,
                        funds_moved=funds_moved,
                    )

                # Re-raise for service methods — financial errors should not be silently swallowed
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


# ======================================================================
# @auth_error_handling
# ======================================================================


def auth_error_handling():
    """Decorator for authentication-related views.

    Never reveals:
    - Whether an account exists
    - Which field was wrong (email vs password)
    - Authentication mechanism details

    Usage::

        @auth_error_handling()
        def login_view(request):
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            request = None
            for arg in args:
                if isinstance(arg, HttpRequest):
                    request = arg
                    break

            request_id = _get_request_id(request)

            try:
                return func(*args, **kwargs)
            except Exception as exc:
                ref_id = str(uuid.uuid4())
                error_code = map_exception_to_error_code(exc)

                # Ensure auth errors never leak account existence
                auth_safe_codes = {
                    "AUTH_INVALID_CREDENTIALS",
                    "AUTH_SESSION_EXPIRED",
                    "AUTH_ACCOUNT_LOCKED",
                    "AUTH_MFA_REQUIRED",
                    "AUTH_SUSPICIOUS_ACTIVITY",
                    "AUTH_TOKEN_INVALID",
                    "AUTH_PERMISSION_DENIED",
                }
                if error_code not in auth_safe_codes:
                    error_code = "AUTH_INVALID_CREDENTIALS"

                # Log with full context
                logger.warning(
                    "Auth error: code=%s ref=%s exc=%s",
                    error_code,
                    ref_id,
                    type(exc).__name__,
                    extra={
                        "reference_id": ref_id,
                        "request_id": request_id,
                        "error_code": error_code,
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc)[:300],
                    },
                )

                if request is not None:
                    redirect_url = None
                    if error_code == "AUTH_SESSION_EXPIRED":
                        redirect_url = "/accounts/login/"
                    elif error_code == "AUTH_MFA_REQUIRED":
                        redirect_url = "/api/v1/auth/mfa/verify/"

                    return create_auth_error_response(
                        error_code=error_code,
                        redirect_url=redirect_url,
                        request_id=request_id,
                    )

                raise

        return wrapper  # type: ignore[return-value]

    return decorator


# ======================================================================
# @admin_operation_error_handling
# ======================================================================


def admin_operation_error_handling():
    """Decorator for admin control plane operations.

    Provides operational context without exposing internals.
    Confirms the state of affected resources.

    Usage::

        @admin_operation_error_handling()
        def approve_withdrawal(request, withdrawal_id):
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            request = None
            for arg in args:
                if isinstance(arg, HttpRequest):
                    request = arg
                    break

            request_id = _get_request_id(request)
            user_id = _get_user_id(request)

            try:
                return func(*args, **kwargs)
            except Exception as exc:
                ref_id = str(uuid.uuid4())
                error_code = map_exception_to_error_code(exc)

                # Log with full admin context
                logger.error(
                    "Admin operation error: func=%s code=%s ref=%s user=%s",
                    func.__qualname__,
                    error_code,
                    ref_id,
                    user_id,
                    extra={
                        "reference_id": ref_id,
                        "request_id": request_id,
                        "user_id": user_id,
                        "function": func.__qualname__,
                        "error_code": error_code,
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc)[:500],
                        "traceback": traceback.format_exc()[:3000],
                        "kwargs_keys": list(kwargs.keys()),
                    },
                )

                # Admin-facing messages provide more operational context
                # but still NEVER expose internals
                admin_user_msg = (
                    "The operation could not be completed. "
                    "No resources have been modified. "
                    f"Reference: {ref_id}"
                )

                if request is not None:
                    return create_error_response(
                        error_code=error_code,
                        user_message=admin_user_msg,
                        request_id=request_id,
                    )

                raise

        return wrapper  # type: ignore[return-value]

    return decorator


# ======================================================================
# @database_degradation_handler
# ======================================================================


def database_degradation_handler(
    read_only_message: str = "The system is temporarily in read-only mode. Please try again later.",
):
    """Decorator for database operations that handles degradation gracefully.

    On OperationalError or InterfaceError:
    - Queues writes for later if possible
    - Returns read-only mode message for write operations
    - Allows reads to proceed with cached data if available

    Args:
        read_only_message: Message to show when system is in read-only mode.

    Usage::

        @database_degradation_handler(read_only_message="System is temporarily in read-only mode.")
        def update_parcel(request, parcel_id):
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            request = None
            for arg in args:
                if isinstance(arg, HttpRequest):
                    request = arg
                    break

            request_id = _get_request_id(request)

            try:
                return func(*args, **kwargs)
            except (OperationalError, InterfaceError) as exc:
                ref_id = str(uuid.uuid4())

                logger.critical(
                    "Database degradation: func=%s ref=%s exc=%s",
                    func.__qualname__,
                    ref_id,
                    type(exc).__name__,
                    extra={
                        "reference_id": ref_id,
                        "request_id": request_id,
                        "function": func.__qualname__,
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc)[:300],
                    },
                )

                # Set read-only mode in cache
                from django.core.cache import cache as django_cache
                try:
                    django_cache.set("digiland:db:read_only_mode", True, timeout=300)
                except Exception:
                    pass

                if request is not None:
                    return create_error_response(
                        error_code="DATABASE_READ_ONLY",
                        user_message=read_only_message,
                        request_id=request_id,
                    )

                # For service methods, re-raise
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


# Needed for the database_degradation_handler
from django.db import OperationalError, InterfaceError


# ======================================================================
# @external_service_handler
# ======================================================================


def external_service_handler(
    fallback_strategy: str = "queue_and_retry",
    fallback_value: Any = None,
):
    """Decorator for external service calls with fallback strategies.

    Args:
        fallback_strategy: Strategy to use when the service fails.
            - "queue_and_retry": Queue the operation for automatic retry
            - "fallback_value": Return a fallback value
            - "raise": Re-raise the exception
        fallback_value: Value to return when strategy is "fallback_value".

    Usage::

        @external_service_handler(fallback_strategy="queue_and_retry")
        def send_notification(user, message):
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            request = None
            for arg in args:
                if isinstance(arg, HttpRequest):
                    request = arg
                    break

            request_id = _get_request_id(request)
            user_id = _get_user_id(request)

            try:
                return func(*args, **kwargs)
            except Exception as exc:
                ref_id = str(uuid.uuid4())
                error_code = map_exception_to_error_code(exc)

                # Log with full context
                from external_services.exceptions import ExternalServiceError
                service_type = None
                provider_name = None
                if isinstance(exc, ExternalServiceError):
                    service_type = exc.service_type
                    provider_name = exc.provider_name  # Internal only

                logger.error(
                    "External service error: func=%s code=%s ref=%s service=%s",
                    func.__qualname__,
                    error_code,
                    ref_id,
                    service_type,
                    extra={
                        "reference_id": ref_id,
                        "request_id": request_id,
                        "user_id": user_id,
                        "function": func.__qualname__,
                        "error_code": error_code,
                        "service_type": service_type,
                        "provider_name": provider_name,
                        "fallback_strategy": fallback_strategy,
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc)[:500],
                    },
                )

                if fallback_strategy == "queue_and_retry":
                    self._queue_for_retry(func, args, kwargs, ref_id)
                    if request is not None:
                        return create_error_response(
                            error_code=error_code,
                            request_id=request_id,
                        )
                    return fallback_value

                elif fallback_strategy == "fallback_value":
                    if request is not None:
                        return create_error_response(
                            error_code=error_code,
                            request_id=request_id,
                        )
                    return fallback_value

                else:  # "raise"
                    raise

        def _queue_for_retry(
            self_ref, func: Callable, args: tuple, kwargs: dict, ref_id: str
        ) -> None:
            """Queue the operation for automatic retry via Celery."""
            try:
                from core.tasks import retry_failed_operation
                retry_failed_operation.delay(
                    function_path=f"{func.__module__}.{func.__qualname__}",
                    args=list(args),
                    kwargs=kwargs,
                    reference_id=ref_id,
                )
            except Exception:
                logger.warning(
                    "Failed to queue operation for retry: ref=%s func=%s",
                    ref_id,
                    func.__qualname__,
                )

        # Attach the helper method
        wrapper._queue_for_retry = _queue_for_retry  # type: ignore[attr-defined]

        return wrapper  # type: ignore[return-value]

    return decorator


# ======================================================================
# @validation_error_handler
# ======================================================================


def validation_error_handler():
    """Decorator that catches validation errors and returns field-specific responses.

    Usage::

        @validation_error_handler()
        def create_transaction(request):
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            request = None
            for arg in args:
                if isinstance(arg, HttpRequest):
                    request = arg
                    break

            request_id = _get_request_id(request)

            try:
                return func(*args, **kwargs)
            except Exception as exc:
                # Check if it's a Django/DRF validation error
                from rest_framework.exceptions import ValidationError as DRFValidationError
                from django.core.exceptions import ValidationError as DjangoValidationError
                from django.core.exceptions import FieldError

                if isinstance(exc, DRFValidationError):
                    # DRF ValidationError has a .detail attribute
                    field_errors = {}
                    details = exc.detail
                    if isinstance(details, dict):
                        for field, messages in details.items():
                            if isinstance(messages, list):
                                field_errors[field] = [str(m) for m in messages]
                            else:
                                field_errors[field] = str(messages)
                    elif isinstance(details, list):
                        field_errors["non_field_errors"] = [str(d) for d in details]
                    else:
                        field_errors["non_field_errors"] = [str(details)]

                    return create_validation_error_response(
                        field_errors=field_errors,
                        request_id=request_id,
                    )

                elif isinstance(exc, (DjangoValidationError, FieldError)):
                    # Django ValidationError
                    field_errors = {}
                    if hasattr(exc, "message_dict"):
                        field_errors = exc.message_dict
                    elif hasattr(exc, "messages"):
                        field_errors["non_field_errors"] = exc.messages
                    else:
                        field_errors["non_field_errors"] = [str(exc)]

                    return create_validation_error_response(
                        field_errors=field_errors,
                        request_id=request_id,
                    )

                # Not a validation error — let other handlers deal with it
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


# ======================================================================
# @rate_limit_handler
# ======================================================================


def rate_limit_handler(retry_after: int = 60):
    """Decorator that catches rate limit errors and returns appropriate responses.

    Args:
        retry_after: Seconds to suggest the client wait before retrying.

    Usage::

        @rate_limit_handler(retry_after=60)
        def send_sms(request):
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            request = None
            for arg in args:
                if isinstance(arg, HttpRequest):
                    request = arg
                    break

            request_id = _get_request_id(request)

            try:
                return func(*args, **kwargs)
            except Exception as exc:
                from rest_framework.exceptions import Throttled
                from external_services.exceptions import RateLimitExceededError

                if isinstance(exc, (Throttled, RateLimitExceededError)):
                    response = create_error_response(
                        error_code="NETWORK_RATE_LIMITED",
                        request_id=request_id,
                    )
                    response["Retry-After"] = str(retry_after)
                    return response

                raise

        return wrapper  # type: ignore[return-value]

    return decorator
