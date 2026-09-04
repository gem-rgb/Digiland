"""
Unified error taxonomy for the Digiland platform.

Every error code has:
- ERROR_CODE constant
- category: logical grouping (auth, payment, network, etc.)
- severity: critical | high | medium | low
- user_message: SAFE message shown to users (no technical details)
- internal_message: detailed message for logging (NOT for users)
- recovery_action: what the user should do next
- http_status_code: appropriate HTTP status
- is_retryable: whether the client may safely retry
- log_level: Python logging level

SECURITY: user_message MUST NEVER expose stack traces, SQL errors,
database names, table names, internal service names, infrastructure
details, provider names (Stripe, M-Pesa, etc.), secret values,
API endpoints, or authentication mechanisms.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class ErrorCategory(str, Enum):
    """Top-level error categories."""
    AUTH = "auth"
    PAYMENT = "payment"
    WITHDRAWAL = "withdrawal"
    NETWORK = "network"
    DATABASE = "database"
    VALIDATION = "validation"
    FILE_UPLOAD = "file_upload"
    SEARCH = "search"
    SYSTEM = "system"
    TRANSACTION = "transaction"
    ESCROW = "transaction"  # Backward compatibility alias
    NOTIFICATION = "notification"
    EXTERNAL_SERVICE = "external_service"
    VERIFICATION = "verification"
    COMPLIANCE = "compliance"
    PARCEL = "parcel"


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class ErrorDefinition:
    """Immutable definition of a single error code."""

    error_code: str
    category: ErrorCategory
    severity: ErrorSeverity
    user_message: str
    internal_message: str
    recovery_action: str
    http_status_code: int
    is_retryable: bool
    log_level: str = "ERROR"


# ======================================================================
# Error Registry
# ======================================================================

ERROR_REGISTRY: Dict[str, ErrorDefinition] = {}


def register_error(definition: ErrorDefinition) -> ErrorDefinition:
    """Register an error definition and return it for convenient assignment."""
    ERROR_REGISTRY[definition.error_code] = definition
    return definition


def get_error_definition(error_code: str) -> Optional[ErrorDefinition]:
    """Look up an error definition by its code."""
    return ERROR_REGISTRY.get(error_code)


def get_errors_by_category(category: ErrorCategory) -> Dict[str, ErrorDefinition]:
    """Return all error definitions for a given category."""
    return {
        code: defn
        for code, defn in ERROR_REGISTRY.items()
        if defn.category == category
    }


# ======================================================================
# AUTH Errors
# ======================================================================

AUTH_INVALID_CREDENTIALS = register_error(ErrorDefinition(
    error_code="AUTH_INVALID_CREDENTIALS",
    category=ErrorCategory.AUTH,
    severity=ErrorSeverity.MEDIUM,
    user_message="The information you entered is incorrect. Please try again.",
    internal_message="Authentication failed: invalid credentials provided",
    recovery_action="Try again or use the account recovery flow.",
    http_status_code=401,
    is_retryable=True,
    log_level="WARNING",
))

AUTH_SESSION_EXPIRED = register_error(ErrorDefinition(
    error_code="AUTH_SESSION_EXPIRED",
    category=ErrorCategory.AUTH,
    severity=ErrorSeverity.LOW,
    user_message="Your session has expired. Please sign in again.",
    internal_message="User session expired or JWT token no longer valid",
    recovery_action="Sign in again to continue.",
    http_status_code=401,
    is_retryable=True,
    log_level="INFO",
))

AUTH_ACCOUNT_LOCKED = register_error(ErrorDefinition(
    error_code="AUTH_ACCOUNT_LOCKED",
    category=ErrorCategory.AUTH,
    severity=ErrorSeverity.HIGH,
    user_message="Your account is temporarily locked. Please try again later or contact support for assistance.",
    internal_message="Account locked due to brute-force protection or admin action",
    recovery_action="Wait for the lockout period to expire or contact support.",
    http_status_code=423,
    is_retryable=False,
    log_level="WARNING",
))

AUTH_MFA_REQUIRED = register_error(ErrorDefinition(
    error_code="AUTH_MFA_REQUIRED",
    category=ErrorCategory.AUTH,
    severity=ErrorSeverity.MEDIUM,
    user_message="Multi-factor authentication is required. Please complete the verification step.",
    internal_message="MFA step-up required for this operation",
    recovery_action="Complete the MFA verification to proceed.",
    http_status_code=403,
    is_retryable=True,
    log_level="INFO",
))

AUTH_PERMISSION_DENIED = register_error(ErrorDefinition(
    error_code="AUTH_PERMISSION_DENIED",
    category=ErrorCategory.AUTH,
    severity=ErrorSeverity.MEDIUM,
    user_message="You do not have permission to perform this action.",
    internal_message="User lacks required role or permission for this operation",
    recovery_action="Contact your administrator if you believe this is an error.",
    http_status_code=403,
    is_retryable=False,
    log_level="WARNING",
))

AUTH_SUSPICIOUS_ACTIVITY = register_error(ErrorDefinition(
    error_code="AUTH_SUSPICIOUS_ACTIVITY",
    category=ErrorCategory.AUTH,
    severity=ErrorSeverity.HIGH,
    user_message="Unusual activity detected on your account. Please verify your identity to continue.",
    internal_message="Suspicious login/activity pattern detected - potential account compromise",
    recovery_action="Verify your identity or contact support for assistance.",
    http_status_code=403,
    is_retryable=False,
    log_level="CRITICAL",
))

AUTH_TOKEN_INVALID = register_error(ErrorDefinition(
    error_code="AUTH_TOKEN_INVALID",
    category=ErrorCategory.AUTH,
    severity=ErrorSeverity.MEDIUM,
    user_message="Your authentication is invalid. Please sign in again.",
    internal_message="JWT token is malformed, expired, or revoked",
    recovery_action="Sign in again to obtain a new session.",
    http_status_code=401,
    is_retryable=True,
    log_level="WARNING",
))


# ======================================================================
# PAYMENT Errors
# ======================================================================

PAYMENT_PROVIDER_UNAVAILABLE = register_error(ErrorDefinition(
    error_code="PAYMENT_PROVIDER_UNAVAILABLE",
    category=ErrorCategory.PAYMENT,
    severity=ErrorSeverity.HIGH,
    user_message="We're unable to process your payment right now. Please try again in a few minutes.",
    internal_message="Payment provider is unavailable or circuit breaker is open",
    recovery_action="Wait a few minutes and try again. Your money has not been debited.",
    http_status_code=503,
    is_retryable=True,
    log_level="ERROR",
))

PAYMENT_PROCESSING_FAILED = register_error(ErrorDefinition(
    error_code="PAYMENT_PROCESSING_FAILED",
    category=ErrorCategory.PAYMENT,
    severity=ErrorSeverity.HIGH,
    user_message="Your payment could not be processed. Please try a different payment method.",
    internal_message="Payment processing failed at the provider level",
    recovery_action="Try a different payment method or contact your bank.",
    http_status_code=402,
    is_retryable=True,
    log_level="ERROR",
))

PAYMENT_INSUFFICIENT_FUNDS = register_error(ErrorDefinition(
    error_code="PAYMENT_INSUFFICIENT_FUNDS",
    category=ErrorCategory.PAYMENT,
    severity=ErrorSeverity.MEDIUM,
    user_message="Your account does not have sufficient funds for this transaction.",
    internal_message="Payment rejected: insufficient funds in user's account",
    recovery_action="Top up your account or use a different payment method.",
    http_status_code=402,
    is_retryable=False,
    log_level="WARNING",
))

PAYMENT_LIMIT_EXCEEDED = register_error(ErrorDefinition(
    error_code="PAYMENT_LIMIT_EXCEEDED",
    category=ErrorCategory.PAYMENT,
    severity=ErrorSeverity.MEDIUM,
    user_message="This transaction exceeds the allowed limit. Please contact support for assistance.",
    internal_message="Transaction amount exceeds daily/per-transaction payment limit",
    recovery_action="Contact support to increase your transaction limits.",
    http_status_code=422,
    is_retryable=False,
    log_level="WARNING",
))

PAYMENT_DUPLICATE_REFERENCE = register_error(ErrorDefinition(
    error_code="PAYMENT_DUPLICATE_REFERENCE",
    category=ErrorCategory.PAYMENT,
    severity=ErrorSeverity.MEDIUM,
    user_message="A payment with this reference already exists. Please check your transaction history.",
    internal_message="Duplicate payment reference detected - idempotency guard triggered",
    recovery_action="Check your transaction history before retrying.",
    http_status_code=409,
    is_retryable=False,
    log_level="WARNING",
))


# ======================================================================
# WITHDRAWAL Errors
# ======================================================================

WITHDRAWAL_PENDING_RETRY = register_error(ErrorDefinition(
    error_code="WITHDRAWAL_PENDING_RETRY",
    category=ErrorCategory.WITHDRAWAL,
    severity=ErrorSeverity.HIGH,
    user_message="Your withdrawal is being processed. We'll notify you once it's complete.",
    internal_message="Withdrawal is pending retry due to a temporary provider issue",
    recovery_action="Wait for the notification. Do not attempt another withdrawal for the same amount.",
    http_status_code=503,
    is_retryable=True,
    log_level="WARNING",
))

WITHDRAWAL_FAILED = register_error(ErrorDefinition(
    error_code="WITHDRAWAL_FAILED",
    category=ErrorCategory.WITHDRAWAL,
    severity=ErrorSeverity.HIGH,
    user_message="Your withdrawal could not be completed. Your funds remain in your account.",
    internal_message="Withdrawal definitively failed at the provider level - funds not moved",
    recovery_action="Try again later or contact support.",
    http_status_code=402,
    is_retryable=True,
    log_level="ERROR",
))

WITHDRAWAL_LIMIT_EXCEEDED = register_error(ErrorDefinition(
    error_code="WITHDRAWAL_LIMIT_EXCEEDED",
    category=ErrorCategory.WITHDRAWAL,
    severity=ErrorSeverity.MEDIUM,
    user_message="This withdrawal exceeds the allowed limit. Please try a smaller amount.",
    internal_message="Withdrawal amount exceeds daily/per-transaction withdrawal limit",
    recovery_action="Reduce the withdrawal amount or contact support to increase limits.",
    http_status_code=422,
    is_retryable=False,
    log_level="WARNING",
))

WITHDRAWAL_NOT_ALLOWED = register_error(ErrorDefinition(
    error_code="WITHDRAWAL_NOT_ALLOWED",
    category=ErrorCategory.WITHDRAWAL,
    severity=ErrorSeverity.MEDIUM,
    user_message="Withdrawals are not available at this time. Please try again later.",
    internal_message="Withdrawal not allowed due to account state, compliance, or system restriction",
    recovery_action="Contact support if you believe this is an error.",
    http_status_code=403,
    is_retryable=False,
    log_level="WARNING",
))


# ======================================================================
# NETWORK Errors
# ======================================================================

NETWORK_TIMEOUT = register_error(ErrorDefinition(
    error_code="NETWORK_TIMEOUT",
    category=ErrorCategory.NETWORK,
    severity=ErrorSeverity.HIGH,
    user_message="The request took too long to process. Please try again.",
    internal_message="Network request timed out - no response received within deadline",
    recovery_action="Check your connection and try again.",
    http_status_code=504,
    is_retryable=True,
    log_level="ERROR",
))

NETWORK_OFFLINE = register_error(ErrorDefinition(
    error_code="NETWORK_OFFLINE",
    category=ErrorCategory.NETWORK,
    severity=ErrorSeverity.HIGH,
    user_message="You appear to be offline. Please check your internet connection.",
    internal_message="Client appears offline or DNS resolution failed",
    recovery_action="Check your internet connection and try again.",
    http_status_code=503,
    is_retryable=True,
    log_level="WARNING",
))

NETWORK_SERVER_ERROR = register_error(ErrorDefinition(
    error_code="NETWORK_SERVER_ERROR",
    category=ErrorCategory.NETWORK,
    severity=ErrorSeverity.HIGH,
    user_message="Something went wrong on our end. Please try again in a moment.",
    internal_message="Upstream server returned 5xx error",
    recovery_action="Wait a moment and try again.",
    http_status_code=502,
    is_retryable=True,
    log_level="ERROR",
))

NETWORK_RATE_LIMITED = register_error(ErrorDefinition(
    error_code="NETWORK_RATE_LIMITED",
    category=ErrorCategory.NETWORK,
    severity=ErrorSeverity.LOW,
    user_message="You're making requests too quickly. Please wait a moment and try again.",
    internal_message="Rate limit exceeded - too many requests in the time window",
    recovery_action="Wait before making another request.",
    http_status_code=429,
    is_retryable=True,
    log_level="WARNING",
))


# ======================================================================
# DATABASE Errors
# ======================================================================

DATABASE_READ_ONLY = register_error(ErrorDefinition(
    error_code="DATABASE_READ_ONLY",
    category=ErrorCategory.DATABASE,
    severity=ErrorSeverity.HIGH,
    user_message="The system is temporarily in read-only mode. You can browse but cannot make changes right now.",
    internal_message="Database is in read-only mode - write operations rejected",
    recovery_action="Please try again later. Your data is safe.",
    http_status_code=503,
    is_retryable=True,
    log_level="CRITICAL",
))

DATABASE_UNAVAILABLE = register_error(ErrorDefinition(
    error_code="DATABASE_UNAVAILABLE",
    category=ErrorCategory.DATABASE,
    severity=ErrorSeverity.CRITICAL,
    user_message="We're experiencing technical difficulties. Please try again in a few minutes.",
    internal_message="Database is completely unavailable - connection refused or timeout",
    recovery_action="Wait a few minutes and try again.",
    http_status_code=503,
    is_retryable=True,
    log_level="CRITICAL",
))

DATABASE_SLOW_RESPONSE = register_error(ErrorDefinition(
    error_code="DATABASE_SLOW_RESPONSE",
    category=ErrorCategory.DATABASE,
    severity=ErrorSeverity.MEDIUM,
    user_message="Things are taking a little longer than usual. Please be patient.",
    internal_message="Database response time exceeded slow-query threshold",
    recovery_action="Wait for the operation to complete or try again.",
    http_status_code=504,
    is_retryable=True,
    log_level="WARNING",
))

DATABASE_CONNECTION_FAILED = register_error(ErrorDefinition(
    error_code="DATABASE_CONNECTION_FAILED",
    category=ErrorCategory.DATABASE,
    severity=ErrorSeverity.CRITICAL,
    user_message="We're experiencing technical difficulties. Please try again shortly.",
    internal_message="Failed to establish database connection - connection pool exhausted or server down",
    recovery_action="Wait a moment and try again.",
    http_status_code=503,
    is_retryable=True,
    log_level="CRITICAL",
))


# ======================================================================
# VALIDATION Errors
# ======================================================================

VALIDATION_INVALID_EMAIL = register_error(ErrorDefinition(
    error_code="VALIDATION_INVALID_EMAIL",
    category=ErrorCategory.VALIDATION,
    severity=ErrorSeverity.LOW,
    user_message="Please enter a valid email address.",
    internal_message="Email validation failed - format or DNS check rejected",
    recovery_action="Check the email address and try again.",
    http_status_code=400,
    is_retryable=False,
    log_level="INFO",
))

VALIDATION_PASSWORD_TOO_SHORT = register_error(ErrorDefinition(
    error_code="VALIDATION_PASSWORD_TOO_SHORT",
    category=ErrorCategory.VALIDATION,
    severity=ErrorSeverity.LOW,
    user_message="The entry must be at least 10 characters long and include a mix of letters, numbers, and symbols.",
    internal_message="Password does not meet minimum complexity requirements",
    recovery_action="Choose a stronger entry with at least 10 characters.",
    http_status_code=400,
    is_retryable=False,
    log_level="INFO",
))

VALIDATION_FILE_TOO_LARGE = register_error(ErrorDefinition(
    error_code="VALIDATION_FILE_TOO_LARGE",
    category=ErrorCategory.VALIDATION,
    severity=ErrorSeverity.LOW,
    user_message="The file you're trying to upload is too large. Maximum size is 10 MB.",
    internal_message="File upload rejected - exceeds maximum allowed size",
    recovery_action="Compress the file or upload a smaller version.",
    http_status_code=413,
    is_retryable=False,
    log_level="INFO",
))

VALIDATION_INVALID_FORMAT = register_error(ErrorDefinition(
    error_code="VALIDATION_INVALID_FORMAT",
    category=ErrorCategory.VALIDATION,
    severity=ErrorSeverity.LOW,
    user_message="The information you entered is not in the correct format. Please check and try again.",
    internal_message="Input data format validation failed",
    recovery_action="Check the format requirements and try again.",
    http_status_code=400,
    is_retryable=False,
    log_level="INFO",
))

VALIDATION_REQUIRED_FIELD = register_error(ErrorDefinition(
    error_code="VALIDATION_REQUIRED_FIELD",
    category=ErrorCategory.VALIDATION,
    severity=ErrorSeverity.LOW,
    user_message="A required field is missing. Please fill in all required information.",
    internal_message="Required field missing from request",
    recovery_action="Fill in all required fields and try again.",
    http_status_code=400,
    is_retryable=False,
    log_level="INFO",
))


# ======================================================================
# FILE UPLOAD Errors
# ======================================================================

FILE_UPLOAD_TOO_LARGE = register_error(ErrorDefinition(
    error_code="FILE_UPLOAD_TOO_LARGE",
    category=ErrorCategory.FILE_UPLOAD,
    severity=ErrorSeverity.LOW,
    user_message="The file you're trying to upload is too large. Please reduce the file size and try again.",
    internal_message="File upload size exceeds configured limit",
    recovery_action="Reduce the file size or contact support for alternative upload methods.",
    http_status_code=413,
    is_retryable=False,
    log_level="INFO",
))

FILE_UPLOAD_UNSUPPORTED_TYPE = register_error(ErrorDefinition(
    error_code="FILE_UPLOAD_UNSUPPORTED_TYPE",
    category=ErrorCategory.FILE_UPLOAD,
    severity=ErrorSeverity.LOW,
    user_message="This file type is not supported. Please upload a file in an accepted format.",
    internal_message="File MIME type not in allowed list",
    recovery_action="Check the accepted file types and upload a supported format.",
    http_status_code=415,
    is_retryable=False,
    log_level="INFO",
))

FILE_UPLOAD_FAILED = register_error(ErrorDefinition(
    error_code="FILE_UPLOAD_FAILED",
    category=ErrorCategory.FILE_UPLOAD,
    severity=ErrorSeverity.MEDIUM,
    user_message="We couldn't upload your file right now. Please try again.",
    internal_message="File upload to storage provider failed",
    recovery_action="Try uploading again. If the problem persists, contact support.",
    http_status_code=500,
    is_retryable=True,
    log_level="ERROR",
))

FILE_UPLOAD_VIRUS_DETECTED = register_error(ErrorDefinition(
    error_code="FILE_UPLOAD_VIRUS_DETECTED",
    category=ErrorCategory.FILE_UPLOAD,
    severity=ErrorSeverity.HIGH,
    user_message="The file you uploaded appears to contain malicious content and has been rejected for your safety.",
    internal_message="Virus/malware detected in uploaded file - file quarantined",
    recovery_action="Scan your file for malware and upload a clean version.",
    http_status_code=422,
    is_retryable=False,
    log_level="CRITICAL",
))


# ======================================================================
# SEARCH Errors
# ======================================================================

SEARCH_UNAVAILABLE = register_error(ErrorDefinition(
    error_code="SEARCH_UNAVAILABLE",
    category=ErrorCategory.SEARCH,
    severity=ErrorSeverity.MEDIUM,
    user_message="Search is temporarily unavailable. Please try again in a moment.",
    internal_message="Search engine service is down or circuit breaker is open",
    recovery_action="Wait a moment and try your search again.",
    http_status_code=503,
    is_retryable=True,
    log_level="ERROR",
))

SEARCH_INDEX_ERROR = register_error(ErrorDefinition(
    error_code="SEARCH_INDEX_ERROR",
    category=ErrorCategory.SEARCH,
    severity=ErrorSeverity.MEDIUM,
    user_message="Search results may be incomplete. We're working on it.",
    internal_message="Search index error - results may be stale or incomplete",
    recovery_action="Try again later for updated results.",
    http_status_code=503,
    is_retryable=True,
    log_level="ERROR",
))


# ======================================================================
# SYSTEM Errors
# ======================================================================

SYSTEM_MAINTENANCE = register_error(ErrorDefinition(
    error_code="SYSTEM_MAINTENANCE",
    category=ErrorCategory.SYSTEM,
    severity=ErrorSeverity.MEDIUM,
    user_message="We're currently performing scheduled maintenance. We'll be back soon.",
    internal_message="System is in maintenance mode - all requests rejected",
    recovery_action="Please check back in a few minutes.",
    http_status_code=503,
    is_retryable=True,
    log_level="WARNING",
))

SYSTEM_UNKNOWN_ERROR = register_error(ErrorDefinition(
    error_code="SYSTEM_UNKNOWN_ERROR",
    category=ErrorCategory.SYSTEM,
    severity=ErrorSeverity.CRITICAL,
    user_message="Something went wrong. Our team has been notified. Please try again later.",
    internal_message="Unexpected/unhandled exception - no specific error mapping found",
    recovery_action="Try again later. If the problem persists, contact support with your reference ID.",
    http_status_code=500,
    is_retryable=True,
    log_level="CRITICAL",
))

SYSTEM_CONFIGURATION_ERROR = register_error(ErrorDefinition(
    error_code="SYSTEM_CONFIGURATION_ERROR",
    category=ErrorCategory.SYSTEM,
    severity=ErrorSeverity.CRITICAL,
    user_message="We're experiencing a technical issue. Please try again later.",
    internal_message="System configuration error - missing keys, invalid URLs, etc.",
    recovery_action="Contact support if this persists.",
    http_status_code=500,
    is_retryable=False,
    log_level="CRITICAL",
))


# ======================================================================
# TRANSACTION Errors
# ======================================================================

TRANSACTION_PROCESSING_ERROR = register_error(ErrorDefinition(
    error_code="TRANSACTION_PROCESSING_ERROR",
    category=ErrorCategory.TRANSACTION,
    severity=ErrorSeverity.HIGH,
    user_message="We couldn't complete the transaction processing. Please verify and try again.",
    internal_message="Transaction processing failed during direct settlement coordination",
    recovery_action="Try again later or contact support with your transaction reference.",
    http_status_code=500,
    is_retryable=True,
    log_level="ERROR",
))

# Backward-compatibility alias
ESCROW_ERROR = TRANSACTION_PROCESSING_ERROR
ERROR_REGISTRY["ESCROW_ERROR"] = TRANSACTION_PROCESSING_ERROR

REFUND_PENDING = register_error(ErrorDefinition(
    error_code="REFUND_PENDING",
    category=ErrorCategory.TRANSACTION,
    severity=ErrorSeverity.MEDIUM,
    user_message="Your refund or payment reversal is being processed. You'll receive a notification once it's complete.",
    internal_message="Payment reversal initiated but not yet confirmed by provider",
    recovery_action="Wait for the provider reversal notification. Do not initiate another reversal.",
    http_status_code=409,
    is_retryable=False,
    log_level="WARNING",
))

TRANSACTION_NOT_FOUND = register_error(ErrorDefinition(
    error_code="TRANSACTION_NOT_FOUND",
    category=ErrorCategory.TRANSACTION,
    severity=ErrorSeverity.LOW,
    user_message="The transaction you're looking for could not be found.",
    internal_message="Transaction lookup returned no results",
    recovery_action="Check the transaction reference and try again.",
    http_status_code=404,
    is_retryable=False,
    log_level="INFO",
))

TRANSACTION_ALREADY_PROCESSED = register_error(ErrorDefinition(
    error_code="TRANSACTION_ALREADY_PROCESSED",
    category=ErrorCategory.TRANSACTION,
    severity=ErrorSeverity.MEDIUM,
    user_message="This transaction has already been processed and cannot be modified.",
    internal_message="Attempted to modify a transaction in a terminal state",
    recovery_action="Check your transaction history for the current status.",
    http_status_code=409,
    is_retryable=False,
    log_level="WARNING",
))


# ======================================================================
# NOTIFICATION Errors
# ======================================================================

NOTIFICATION_DELIVERY_FAILED = register_error(ErrorDefinition(
    error_code="NOTIFICATION_DELIVERY_FAILED",
    category=ErrorCategory.NOTIFICATION,
    severity=ErrorSeverity.MEDIUM,
    user_message="We couldn't send a notification right now, but your action was completed successfully.",
    internal_message="Notification delivery failed - message queued for retry",
    recovery_action="No action needed. We'll retry sending the notification.",
    http_status_code=503,
    is_retryable=True,
    log_level="WARNING",
))

NOTIFICATION_PROVIDER_UNAVAILABLE = register_error(ErrorDefinition(
    error_code="NOTIFICATION_PROVIDER_UNAVAILABLE",
    category=ErrorCategory.NOTIFICATION,
    severity=ErrorSeverity.MEDIUM,
    user_message="Notifications are temporarily delayed. Your request was still processed.",
    internal_message="Notification service unavailable - all notifications queued",
    recovery_action="No action needed. Notifications will be sent when the service recovers.",
    http_status_code=503,
    is_retryable=True,
    log_level="WARNING",
))


# ======================================================================
# EXTERNAL SERVICE Errors
# ======================================================================

EXTERNAL_SERVICE_UNAVAILABLE = register_error(ErrorDefinition(
    error_code="EXTERNAL_SERVICE_UNAVAILABLE",
    category=ErrorCategory.EXTERNAL_SERVICE,
    severity=ErrorSeverity.HIGH,
    user_message="A required service is temporarily unavailable. Please try again shortly.",
    internal_message="External service is down or unreachable - circuit breaker may be open",
    recovery_action="Wait a few minutes and try again.",
    http_status_code=503,
    is_retryable=True,
    log_level="ERROR",
))

EXTERNAL_SERVICE_TIMEOUT = register_error(ErrorDefinition(
    error_code="EXTERNAL_SERVICE_TIMEOUT",
    category=ErrorCategory.EXTERNAL_SERVICE,
    severity=ErrorSeverity.HIGH,
    user_message="The service took too long to respond. Please try again.",
    internal_message="External service request timed out - response not received within deadline",
    recovery_action="Try again. If the problem persists, contact support.",
    http_status_code=504,
    is_retryable=True,
    log_level="ERROR",
))

EXTERNAL_SERVICE_RATE_LIMITED = register_error(ErrorDefinition(
    error_code="EXTERNAL_SERVICE_RATE_LIMITED",
    category=ErrorCategory.EXTERNAL_SERVICE,
    severity=ErrorSeverity.MEDIUM,
    user_message="We're processing too many requests. Please wait a moment and try again.",
    internal_message="External service rate limit hit - need to back off",
    recovery_action="Wait before trying again.",
    http_status_code=429,
    is_retryable=True,
    log_level="WARNING",
))


# ======================================================================
# VERIFICATION Errors
# ======================================================================

VERIFICATION_SERVICE_UNAVAILABLE = register_error(ErrorDefinition(
    error_code="VERIFICATION_SERVICE_UNAVAILABLE",
    category=ErrorCategory.VERIFICATION,
    severity=ErrorSeverity.HIGH,
    user_message="Verification services are temporarily unavailable. Your submission is saved and will be reviewed when the service recovers.",
    internal_message="Identity/land verification provider is down or unreachable",
    recovery_action="Your data has been saved. No action needed — verification will resume automatically.",
    http_status_code=503,
    is_retryable=True,
    log_level="ERROR",
))

VERIFICATION_FAILED = register_error(ErrorDefinition(
    error_code="VERIFICATION_FAILED",
    category=ErrorCategory.VERIFICATION,
    severity=ErrorSeverity.MEDIUM,
    user_message="We couldn't verify your information. Please review and resubmit.",
    internal_message="Verification check returned a negative result - data mismatch or rejection",
    recovery_action="Review your submitted information and try again.",
    http_status_code=422,
    is_retryable=True,
    log_level="WARNING",
))

VERIFICATION_PENDING = register_error(ErrorDefinition(
    error_code="VERIFICATION_PENDING",
    category=ErrorCategory.VERIFICATION,
    severity=ErrorSeverity.LOW,
    user_message="Your verification is being reviewed. You'll be notified once it's complete.",
    internal_message="Verification request is in the review queue - awaiting manual or automated check",
    recovery_action="Wait for the verification result. No action needed.",
    http_status_code=409,
    is_retryable=False,
    log_level="INFO",
))

VERIFICATION_EXPIRED = register_error(ErrorDefinition(
    error_code="VERIFICATION_EXPIRED",
    category=ErrorCategory.VERIFICATION,
    severity=ErrorSeverity.MEDIUM,
    user_message="Your verification session has expired. Please start the process again.",
    internal_message="Verification session or OTP expired - user must re-initiate",
    recovery_action="Start the verification process again.",
    http_status_code=410,
    is_retryable=True,
    log_level="WARNING",
))


# ======================================================================
# COMPLIANCE Errors
# ======================================================================

COMPLIANCE_CHECK_FAILED = register_error(ErrorDefinition(
    error_code="COMPLIANCE_CHECK_FAILED",
    category=ErrorCategory.COMPLIANCE,
    severity=ErrorSeverity.HIGH,
    user_message="Your request could not be completed due to a compliance restriction. Please contact support.",
    internal_message="Compliance/KYC/AML check failed - regulatory constraint prevents operation",
    recovery_action="Contact support for assistance with compliance requirements.",
    http_status_code=403,
    is_retryable=False,
    log_level="ERROR",
))

COMPLIANCE_REVIEW_REQUIRED = register_error(ErrorDefinition(
    error_code="COMPLIANCE_REVIEW_REQUIRED",
    category=ErrorCategory.COMPLIANCE,
    severity=ErrorSeverity.MEDIUM,
    user_message="Your request requires additional review. We'll notify you once it's been processed.",
    internal_message="Operation flagged for manual compliance review - cannot proceed automatically",
    recovery_action="Wait for the compliance review to be completed.",
    http_status_code=409,
    is_retryable=False,
    log_level="WARNING",
))

COMPLIANCE_SERVICE_UNAVAILABLE = register_error(ErrorDefinition(
    error_code="COMPLIANCE_SERVICE_UNAVAILABLE",
    category=ErrorCategory.COMPLIANCE,
    severity=ErrorSeverity.HIGH,
    user_message="Compliance checks are temporarily unavailable. Your request has been saved for processing.",
    internal_message="KRA/AML/compliance verification service is down - operations queued",
    recovery_action="Your request has been saved and will be processed when the service recovers.",
    http_status_code=503,
    is_retryable=True,
    log_level="ERROR",
))


# ======================================================================
# PARCEL / LAND Errors
# ======================================================================

PARCEL_NOT_FOUND = register_error(ErrorDefinition(
    error_code="PARCEL_NOT_FOUND",
    category=ErrorCategory.PARCEL,
    severity=ErrorSeverity.LOW,
    user_message="The land parcel you're looking for could not be found.",
    internal_message="LandParcel lookup returned no results",
    recovery_action="Check the parcel number and try again.",
    http_status_code=404,
    is_retryable=False,
    log_level="INFO",
))

PARCEL_ALREADY_LISTED = register_error(ErrorDefinition(
    error_code="PARCEL_ALREADY_LISTED",
    category=ErrorCategory.PARCEL,
    severity=ErrorSeverity.MEDIUM,
    user_message="This land parcel has already been listed. Each parcel can only be listed once.",
    internal_message="Attempted to create a duplicate listing for an already-listed parcel",
    recovery_action="Check your existing listings or contact support.",
    http_status_code=409,
    is_retryable=False,
    log_level="WARNING",
))

PARCEL_VERIFICATION_REQUIRED = register_error(ErrorDefinition(
    error_code="PARCEL_VERIFICATION_REQUIRED",
    category=ErrorCategory.PARCEL,
    severity=ErrorSeverity.MEDIUM,
    user_message="This parcel requires verification before it can be transacted.",
    internal_message="Parcel is in a state that requires verification before transactions",
    recovery_action="Submit the required documents for verification.",
    http_status_code=422,
    is_retryable=False,
    log_level="INFO",
))

PARCEL_DISPUTED = register_error(ErrorDefinition(
    error_code="PARCEL_DISPUTED",
    category=ErrorCategory.PARCEL,
    severity=ErrorSeverity.HIGH,
    user_message="This parcel is currently under dispute and cannot be transacted.",
    internal_message="Parcel verification_status is Disputed - transactions blocked",
    recovery_action="Wait for the dispute to be resolved or contact support.",
    http_status_code=403,
    is_retryable=False,
    log_level="WARNING",
))


# ======================================================================
# Additional SYSTEM Errors
# ======================================================================

SYSTEM_OVERLOADED = register_error(ErrorDefinition(
    error_code="SYSTEM_OVERLOADED",
    category=ErrorCategory.SYSTEM,
    severity=ErrorSeverity.HIGH,
    user_message="We're experiencing high demand. Please try again in a few minutes.",
    internal_message="System is overloaded - request queue saturated, CPU/memory pressure",
    recovery_action="Wait a few minutes and try again.",
    http_status_code=503,
    is_retryable=True,
    log_level="ERROR",
))


# ======================================================================
# Additional AUTH Errors
# ======================================================================

AUTH_EMAIL_NOT_VERIFIED = register_error(ErrorDefinition(
    error_code="AUTH_EMAIL_NOT_VERIFIED",
    category=ErrorCategory.AUTH,
    severity=ErrorSeverity.MEDIUM,
    user_message="Please verify your email address before continuing.",
    internal_message="User's email has not been verified - account activation incomplete",
    recovery_action="Check your email for the verification link, or request a new one.",
    http_status_code=403,
    is_retryable=True,
    log_level="INFO",
))

AUTH_OAUTH_ERROR = register_error(ErrorDefinition(
    error_code="AUTH_OAUTH_ERROR",
    category=ErrorCategory.AUTH,
    severity=ErrorSeverity.MEDIUM,
    user_message="We couldn't complete the sign-in with your provider. Please try again or use a different method.",
    internal_message="OAuth/SSO authentication flow failed - provider returned error",
    recovery_action="Try again or sign in with a different method.",
    http_status_code=401,
    is_retryable=True,
    log_level="WARNING",
))


# ======================================================================
# Additional PAYMENT Errors
# ======================================================================

PAYMENT_TIMEOUT = register_error(ErrorDefinition(
    error_code="PAYMENT_TIMEOUT",
    category=ErrorCategory.PAYMENT,
    severity=ErrorSeverity.HIGH,
    user_message="Your payment is taking longer than expected. Please check your transaction history before retrying.",
    internal_message="Payment request timed out - outcome uncertain, funds status unknown",
    recovery_action="Check your transaction history. Do NOT retry the same payment until you confirm the status.",
    http_status_code=504,
    is_retryable=True,
    log_level="ERROR",
))

PAYMENT_VERIFICATION_PENDING = register_error(ErrorDefinition(
    error_code="PAYMENT_VERIFICATION_PENDING",
    category=ErrorCategory.PAYMENT,
    severity=ErrorSeverity.MEDIUM,
    user_message="Your payment is being verified. You'll be notified once it's confirmed.",
    internal_message="Payment verification in progress - awaiting provider confirmation",
    recovery_action="Wait for the verification result. Do not retry the payment.",
    http_status_code=409,
    is_retryable=False,
    log_level="WARNING",
))


# ======================================================================
# Django Exception → Error Code Mapping
# ======================================================================

DJANGO_EXCEPTION_MAP: Dict[str, str] = {
    # Auth
    "AuthenticationFailed": "AUTH_INVALID_CREDENTIALS",
    "NotAuthenticated": "AUTH_TOKEN_INVALID",
    "PermissionDenied": "AUTH_PERMISSION_DENIED",

    # Validation
    "ValidationError": "VALIDATION_INVALID_FORMAT",
    "ParseError": "VALIDATION_INVALID_FORMAT",
    "FieldError": "VALIDATION_REQUIRED_FIELD",

    # Throttling
    "Throttled": "NETWORK_RATE_LIMITED",

    # Not Found
    "NotFound": "TRANSACTION_NOT_FOUND",

    # Method Not Allowed
    "MethodNotAllowed": "AUTH_PERMISSION_DENIED",

    # Database
    "OperationalError": "DATABASE_UNAVAILABLE",
    "InterfaceError": "DATABASE_CONNECTION_FAILED",
    "DataError": "VALIDATION_INVALID_FORMAT",
    "IntegrityError": "VALIDATION_INVALID_FORMAT",
    "InternalError": "DATABASE_UNAVAILABLE",

    # File Upload
    "SuspiciousFileOperation": "FILE_UPLOAD_FAILED",
    "MultiPartParserError": "FILE_UPLOAD_FAILED",

    # Request
    "RequestDataTooBig": "FILE_UPLOAD_TOO_LARGE",
    "TooManyFieldsSent": "VALIDATION_INVALID_FORMAT",
}
"""Map Django/DRF exception class names to error codes."""


def map_exception_to_error_code(exc: Exception) -> str:
    """Map any exception to an error code using the registry.

    Checks (in order):
    1. Exact class name match in ``DJANGO_EXCEPTION_MAP``
    2. MRO walk for base-class matches
    3. Falls back to ``SYSTEM_UNKNOWN_ERROR``
    """
    exc_name = type(exc).__name__
    if exc_name in DJANGO_EXCEPTION_MAP:
        return DJANGO_EXCEPTION_MAP[exc_name]

    # Walk the MRO for base class matches
    for base in type(exc).__mro__:
        base_name = base.__name__
        if base_name in DJANGO_EXCEPTION_MAP:
            return DJANGO_EXCEPTION_MAP[base_name]

    # Check if it's an ExternalServiceError subclass
    from external_services.exceptions import ExternalServiceError
    if isinstance(exc, ExternalServiceError):
        from external_services.exceptions import (
            ProviderUnavailableError,
            CircuitBreakerOpenError,
            RateLimitExceededError,
            TimeoutError as ESLTimeoutError,
        )
        if isinstance(exc, ProviderUnavailableError):
            return "EXTERNAL_SERVICE_UNAVAILABLE"
        if isinstance(exc, CircuitBreakerOpenError):
            return "EXTERNAL_SERVICE_UNAVAILABLE"
        if isinstance(exc, RateLimitExceededError):
            return "EXTERNAL_SERVICE_RATE_LIMITED"
        if isinstance(exc, ESLTimeoutError):
            return "EXTERNAL_SERVICE_TIMEOUT"
        return "EXTERNAL_SERVICE_UNAVAILABLE"

    return "SYSTEM_UNKNOWN_ERROR"
