"""
Specialized authentication error handler.

Differentiated authentication error handling that:
- Never reveals whether an account exists
- Never reveals authentication mechanism details
- Never reveals security control details
- Always provides a clear user-friendly message
- Always provides a recovery action
- Always provides a reference ID for support

CRITICAL SECURITY: All auth error messages must be identical regardless of
whether the account exists. This prevents:
- Account enumeration attacks
- User enumeration via timing attacks
- Information leakage about security controls
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from django.http import HttpRequest

from .error_taxonomy import get_error_definition
from .error_responses import create_auth_error_response

logger = logging.getLogger(__name__)


class AuthErrorHandler:
    """Differentiated authentication error handling.

    Usage::

        handler = AuthErrorHandler()

        try:
            authenticate(username=email, password=password)
        except InvalidCredentialsError:
            response = handler.handle_invalid_credentials(request)
    """

    # The universal "wrong credentials" message — same whether account
    # exists or not, whether email or password was wrong
    INVALID_CREDENTIALS_MESSAGE = (
        "The email or password you entered is incorrect. "
        "Please try again or reset your password."
    )

    def handle_invalid_credentials(
        self, request: Optional[HttpRequest] = None
    ) -> Dict[str, Any]:
        """Handle invalid credentials with a generic message.

        The message is intentionally the same regardless of whether:
        - The account exists
        - The email is wrong
        - The password is wrong
        - The account is inactive

        This prevents account enumeration attacks.
        """
        reference_id = str(uuid.uuid4())

        logger.warning(
            "Invalid credentials attempt: ref=%s ip=%s",
            reference_id,
            self._get_client_ip(request),
            extra={
                "reference_id": reference_id,
                "error_code": "AUTH_INVALID_CREDENTIALS",
                "client_ip": self._get_client_ip(request),
                "path": request.path if request else None,
            },
        )

        return {
            "success": False,
            "error_code": "AUTH_INVALID_CREDENTIALS",
            "user_message": self.INVALID_CREDENTIALS_MESSAGE,
            "reference_id": reference_id,
            "redirect_url": None,
            "recovery_action": "Try again or reset your password.",
        }

    def handle_session_expired(
        self, request: Optional[HttpRequest] = None
    ) -> Dict[str, Any]:
        """Handle an expired session with a clear redirect.

        The user should be redirected to the sign-in page with
        a message explaining why.
        """
        reference_id = str(uuid.uuid4())

        logger.info(
            "Session expired: ref=%s",
            reference_id,
            extra={
                "reference_id": reference_id,
                "error_code": "AUTH_SESSION_EXPIRED",
                "user_id": self._get_user_id(request),
            },
        )

        return {
            "success": False,
            "error_code": "AUTH_SESSION_EXPIRED",
            "user_message": "Your session has expired. Please sign in again.",
            "reference_id": reference_id,
            "redirect_url": "/accounts/login/",
            "recovery_action": "Sign in again to continue.",
        }

    def handle_account_locked(
        self,
        request: Optional[HttpRequest] = None,
        user: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Handle a locked account.

        Suggests trying later or contacting support, but does NOT reveal:
        - How long the lockout lasts
        - Why the account was locked
        - Whether this is automated or manual
        """
        reference_id = str(uuid.uuid4())

        logger.warning(
            "Account locked: ref=%s user=%s",
            reference_id,
            self._get_user_id(request) or (str(user.id) if user else "unknown"),
            extra={
                "reference_id": reference_id,
                "error_code": "AUTH_ACCOUNT_LOCKED",
                "user_id": str(user.id) if user else None,
            },
        )

        return {
            "success": False,
            "error_code": "AUTH_ACCOUNT_LOCKED",
            "user_message": (
                "Your account is temporarily locked. "
                "Please try again later or contact support for assistance."
            ),
            "reference_id": reference_id,
            "redirect_url": "/accounts/login/",
            "recovery_action": (
                "Wait for the lockout to end, or contact support "
                f"with reference: {reference_id}"
            ),
        }

    def handle_mfa_required(
        self,
        request: Optional[HttpRequest] = None,
        user: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Handle MFA requirement with a redirect to verification.

        Does NOT reveal:
        - What type of MFA is configured (TOTP, SMS, hardware key)
        - Whether MFA was recently set up
        - Security policy details
        """
        reference_id = str(uuid.uuid4())

        logger.info(
            "MFA required: ref=%s user=%s",
            reference_id,
            self._get_user_id(request) or (str(user.id) if user else "unknown"),
            extra={
                "reference_id": reference_id,
                "error_code": "AUTH_MFA_REQUIRED",
                "user_id": str(user.id) if user else None,
            },
        )

        return {
            "success": False,
            "error_code": "AUTH_MFA_REQUIRED",
            "user_message": (
                "Multi-factor authentication is required. "
                "Please complete the verification step to continue."
            ),
            "reference_id": reference_id,
            "redirect_url": "/api/v1/auth/mfa/verify/",
            "recovery_action": "Complete the MFA verification to proceed.",
        }

    def handle_suspicious_activity(
        self,
        request: Optional[HttpRequest] = None,
        user: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Handle suspicious activity detection.

        Suggests verifying identity, but does NOT reveal:
        - What triggered the suspicion
        - What security controls detected it
        - Whether the account is now restricted
        """
        reference_id = str(uuid.uuid4())

        logger.critical(
            "Suspicious activity detected: ref=%s user=%s ip=%s",
            reference_id,
            self._get_user_id(request) or (str(user.id) if user else "unknown"),
            self._get_client_ip(request),
            extra={
                "reference_id": reference_id,
                "error_code": "AUTH_SUSPICIOUS_ACTIVITY",
                "user_id": str(user.id) if user else None,
                "client_ip": self._get_client_ip(request),
                "user_agent": (
                    request.META.get("HTTP_USER_AGENT", "")[:200]
                    if request else None
                ),
            },
        )

        return {
            "success": False,
            "error_code": "AUTH_SUSPICIOUS_ACTIVITY",
            "user_message": (
                "Unusual activity detected on your account. "
                "Please verify your identity to continue."
            ),
            "reference_id": reference_id,
            "redirect_url": "/accounts/login/",
            "recovery_action": (
                "Verify your identity or contact support for assistance "
                f"with reference: {reference_id}"
            ),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_client_ip(request: Optional[HttpRequest]) -> Optional[str]:
        """Extract client IP from request."""
        if not request:
            return None
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

    @staticmethod
    def _get_user_id(request: Optional[HttpRequest]) -> Optional[str]:
        """Safely extract user ID from request."""
        if not request:
            return None
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            return str(getattr(user, "id", "unknown"))
        return None
