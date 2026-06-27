"""DRF authentication classes that block unverified accounts."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


PUBLIC_AUTH_PATH_PREFIXES = (
    "/api/v1/auth/",
)


def _path_allows_unverified(request) -> bool:
    path = request.path.rstrip("/")
    return any(path.startswith(prefix.rstrip("/")) for prefix in PUBLIC_AUTH_PATH_PREFIXES)


class _EmailVerificationGuardMixin:
    """Reject authenticated requests when the email is not yet verified."""

    verification_error = "Your email address has not yet been verified. Please verify your email to continue."

    def _enforce_verified_email(self, request, user) -> None:
        if not user or not getattr(user, "is_authenticated", False):
            return
        if _path_allows_unverified(request):
            return
        if not getattr(user, "is_email_verified", False):
            raise AuthenticationFailed(self.verification_error, code="email_not_verified")


class EmailVerifiedJWTAuthentication(_EmailVerificationGuardMixin, JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if not result:
            return None
        user, token = result
        self._enforce_verified_email(request, user)
        return user, token


class EmailVerifiedSessionAuthentication(_EmailVerificationGuardMixin, SessionAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if not result:
            return None
        user, auth = result
        self._enforce_verified_email(request, user)
        return user, auth
