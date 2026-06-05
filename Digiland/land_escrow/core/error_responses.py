"""
Standardized DRF error responses with security-conscious error disclosure.

Production responses contain ONLY:
- error_code
- user_message
- reference_id (for support lookup)

Development responses additionally include:
- internal_message
- details
- stack_trace (truncated)

NEVER expose in any environment:
- Stack traces (production)
- SQL errors
- Database names / table names
- Internal service names (Stripe, M-Pesa, Redis, etc.)
- Infrastructure details
- Secret values / API keys
- Authentication mechanism details
"""

from __future__ import annotations

import logging
import os
import traceback
import uuid
from typing import Any, Dict, Optional

from django.conf import settings
from django.http import JsonResponse

from .error_taxonomy import ErrorDefinition, get_error_definition

logger = logging.getLogger(__name__)

# Sensitive patterns that must NEVER appear in user-facing responses
SENSITIVE_PATTERNS = [
    "stripe", "mpesa", "paystack", "kcb", "daraja",
    "redis", "celery", "postgresql", "postgis",
    "sentry", "opensearch", "elasticsearch",
    "database", "db.sqlite", "table", "column", "sql",
    "select ", "insert ", "update ", "delete ",
    "connection", "socket", "timeout", "dns",
    "api_key", "secret", "token", "password", "credential",
    "traceback", "exception", "stack",
    "/home/", "/etc/", "/var/", "/usr/",
    "http://", "https://",  # internal URLs
    "operation_id", "query",
]


def _is_production() -> bool:
    """Determine if we're in a production environment."""
    if getattr(settings, "DEBUG", False):
        return False
    env = os.environ.get("DJANGO_ENV", "").lower()
    return env in ("production", "staging")


def _sanitize_message(message: str) -> str:
    """Remove any potentially sensitive information from a message."""
    sanitized = message
    for pattern in SENSITIVE_PATTERNS:
        if pattern.lower() in sanitized.lower():
            # Replace the sensitive portion with a safe placeholder
            import re
            sanitized = re.sub(
                re.escape(pattern),
                "[REDACTED]",
                sanitized,
                flags=re.IGNORECASE,
            )
    return sanitized


def _generate_reference_id() -> str:
    """Generate a unique reference ID for error tracking."""
    return str(uuid.uuid4())


def _get_truncated_trace() -> str:
    """Get a truncated stack trace for development mode."""
    tb = traceback.format_exc()
    # Truncate to prevent overly large responses
    if len(tb) > 2000:
        tb = tb[:2000] + "\n... [truncated]"
    return tb


def create_error_response(
    error_code: str,
    user_message: Optional[str] = None,
    request_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    status_code: Optional[int] = None,
) -> JsonResponse:
    """Create a user-safe error response.

    Production: Only user_message, error_code, reference_id
    Development: Also includes internal_message, details, stack_trace

    Args:
        error_code: The error code from the taxonomy.
        user_message: Override the default user message. If None, looked up from taxonomy.
        request_id: Optional request/correlation ID.
        details: Additional context. ONLY included in non-production environments.
        status_code: Override the HTTP status code.

    Returns:
        JsonResponse with appropriate content based on environment.
    """
    definition = get_error_definition(error_code)
    reference_id = _generate_reference_id()

    if definition is None:
        # Unknown error code - use the system fallback
        definition = get_error_definition("SYSTEM_UNKNOWN_ERROR")
        if definition is None:
            # Absolute fallback
            definition = ErrorDefinition(
                error_code="SYSTEM_UNKNOWN_ERROR",
                category="system",
                severity="critical",
                user_message="Something went wrong. Our team has been notified.",
                internal_message="Unknown error code with no fallback",
                recovery_action="Contact support.",
                http_status_code=500,
                is_retryable=True,
                log_level="CRITICAL",
            )

    # Resolve user message
    resolved_message = user_message or definition.user_message
    # Sanitize user message even further (defense in depth)
    resolved_message = _sanitize_message(resolved_message)

    # Resolve status code
    resolved_status = status_code or definition.http_status_code

    # Build the response body
    response_body: Dict[str, Any] = {
        "error": {
            "code": error_code,
            "message": resolved_message,
            "reference_id": reference_id,
        }
    }

    # Add retryability hint for client
    if definition.is_retryable:
        response_body["error"]["retryable"] = True

    # Add recovery action if available
    if definition.recovery_action:
        response_body["error"]["recovery_action"] = definition.recovery_action

    # Development-only details
    if not _is_production():
        dev_details: Dict[str, Any] = {
            "internal_message": definition.internal_message,
        }
        if details:
            dev_details["details"] = details
        if request_id:
            dev_details["request_id"] = request_id
        dev_details["stack_trace"] = _get_truncated_trace()
        response_body["error"]["_debug"] = dev_details

    # Log internally with full context
    log_data = {
        "error_code": error_code,
        "reference_id": reference_id,
        "request_id": request_id,
        "internal_message": definition.internal_message,
        "severity": definition.severity.value if hasattr(definition.severity, 'value') else definition.severity,
        "category": definition.category.value if hasattr(definition.category, 'value') else definition.category,
    }
    if details:
        log_data["details"] = details

    log_level = getattr(logging, definition.log_level.upper(), logging.ERROR)
    logger.log(
        log_level,
        "Error response: code=%s reference_id=%s internal=%s",
        error_code,
        reference_id,
        definition.internal_message,
        extra=log_data,
    )

    response = JsonResponse(response_body, status=resolved_status)
    # Set reference ID in header for easy client-side extraction
    response["X-Reference-ID"] = reference_id
    return response


def create_validation_error_response(
    field_errors: Dict[str, Any],
    request_id: Optional[str] = None,
) -> JsonResponse:
    """Create a field-specific validation error response.

    Args:
        field_errors: Dict mapping field names to error messages or lists of messages.
            Example: {"email": ["Enter a valid email."], "phone": ["Invalid format."]}

    Returns:
        JsonResponse with per-field error details.
    """
    reference_id = _generate_reference_id()

    # Sanitize field error messages
    safe_errors: Dict[str, Any] = {}
    for field_name, messages in field_errors.items():
        if isinstance(messages, list):
            safe_errors[field_name] = [_sanitize_message(str(m)) for m in messages]
        else:
            safe_errors[field_name] = _sanitize_message(str(messages))

    response_body: Dict[str, Any] = {
        "error": {
            "code": "VALIDATION_INVALID_FORMAT",
            "message": "Please correct the errors below and try again.",
            "reference_id": reference_id,
            "fields": safe_errors,
        }
    }

    # Development-only: include internal details
    if not _is_production():
        response_body["error"]["_debug"] = {
            "internal_message": "Field-level validation failed",
            "request_id": request_id,
            "raw_field_errors": field_errors,
        }

    logger.info(
        "Validation error: reference_id=%s fields=%s",
        reference_id,
        list(field_errors.keys()),
        extra={
            "error_code": "VALIDATION_INVALID_FORMAT",
            "reference_id": reference_id,
            "request_id": request_id,
            "failed_fields": list(field_errors.keys()),
        },
    )

    response = JsonResponse(response_body, status=400)
    response["X-Reference-ID"] = reference_id
    return response


def create_financial_error_response(
    transaction_id: Optional[str],
    error_code: str,
    user_message: Optional[str] = None,
    reference_id: Optional[str] = None,
    request_id: Optional[str] = None,
    funds_moved: bool = False,
) -> JsonResponse:
    """Create a financial operation error response.

    CRITICAL: Never tell a user a payment failed if it might have succeeded.
    For uncertain outcomes, use PAYMENT_PROVIDER_UNAVAILABLE and state that
    the status is being verified.

    Args:
        transaction_id: The transaction reference for tracking.
        error_code: Error code from taxonomy.
        user_message: Override user message.
        reference_id: Support reference ID. Generated if not provided.
        request_id: Request/correlation ID.
        funds_moved: Whether funds were definitively moved.

    Returns:
        JsonResponse with financial error details.
    """
    if reference_id is None:
        reference_id = _generate_reference_id()

    definition = get_error_definition(error_code)
    if definition is None:
        definition = get_error_definition("SYSTEM_UNKNOWN_ERROR")

    resolved_message = user_message or definition.user_message
    resolved_message = _sanitize_message(resolved_message)

    response_body: Dict[str, Any] = {
        "error": {
            "code": error_code,
            "message": resolved_message,
            "reference_id": reference_id,
        }
    }

    # Always include transaction ID for financial operations
    if transaction_id:
        response_body["error"]["transaction_id"] = str(transaction_id)

    # Explicitly state whether funds were moved
    if funds_moved:
        response_body["error"]["funds_status"] = "moved"
    else:
        response_body["error"]["funds_status"] = "not_moved"

    # Add support message for financial errors
    response_body["error"]["support_message"] = (
        f"If you have questions, contact support with reference: {reference_id}"
    )

    if definition.is_retryable:
        response_body["error"]["retryable"] = True

    if definition.recovery_action:
        response_body["error"]["recovery_action"] = definition.recovery_action

    # Development-only details
    if not _is_production():
        dev_details: Dict[str, Any] = {
            "internal_message": definition.internal_message,
            "funds_moved": funds_moved,
        }
        if request_id:
            dev_details["request_id"] = request_id
        response_body["error"]["_debug"] = dev_details

    # Log with full context
    logger.error(
        "Financial error: code=%s transaction=%s reference_id=%s funds_moved=%s",
        error_code,
        transaction_id,
        reference_id,
        funds_moved,
        extra={
            "error_code": error_code,
            "transaction_id": str(transaction_id) if transaction_id else None,
            "reference_id": reference_id,
            "request_id": request_id,
            "funds_moved": funds_moved,
            "internal_message": definition.internal_message,
        },
    )

    response = JsonResponse(response_body, status=definition.http_status_code)
    response["X-Reference-ID"] = reference_id
    if transaction_id:
        response["X-Transaction-ID"] = str(transaction_id)
    return response


def create_auth_error_response(
    error_code: str,
    user_message: Optional[str] = None,
    redirect_url: Optional[str] = None,
    request_id: Optional[str] = None,
) -> JsonResponse:
    """Create an authentication error response.

    SECURITY: Auth error messages MUST NEVER reveal:
    - Whether an account exists
    - Which specific field was wrong (email vs password)
    - Authentication mechanism details
    - Security control specifics

    Args:
        error_code: Error code from taxonomy.
        user_message: Override user message.
        redirect_url: URL to redirect the client to (e.g. sign-in page).
        request_id: Request/correlation ID.

    Returns:
        JsonResponse with auth error details.
    """
    reference_id = _generate_reference_id()
    definition = get_error_definition(error_code)
    if definition is None:
        definition = get_error_definition("AUTH_TOKEN_INVALID")

    resolved_message = user_message or definition.user_message
    resolved_message = _sanitize_message(resolved_message)

    response_body: Dict[str, Any] = {
        "error": {
            "code": error_code,
            "message": resolved_message,
            "reference_id": reference_id,
        }
    }

    if redirect_url:
        response_body["error"]["redirect_url"] = redirect_url

    if definition.recovery_action:
        response_body["error"]["recovery_action"] = definition.recovery_action

    # Development-only details
    if not _is_production():
        dev_details: Dict[str, Any] = {
            "internal_message": definition.internal_message,
        }
        if request_id:
            dev_details["request_id"] = request_id
        response_body["error"]["_debug"] = dev_details

    # Log auth errors at WARNING level (don't spam ERROR for normal login failures)
    logger.warning(
        "Auth error: code=%s reference_id=%s",
        error_code,
        reference_id,
        extra={
            "error_code": error_code,
            "reference_id": reference_id,
            "request_id": request_id,
            "internal_message": definition.internal_message,
        },
    )

    response = JsonResponse(response_body, status=definition.http_status_code)
    response["X-Reference-ID"] = reference_id
    return response
