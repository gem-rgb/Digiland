"""
Identity / OAuth provider adapters for the External Services Layer.

Implements the :class:`~external_services.base.IdentityProvider` interface
for three OAuth 2.0 identity providers:

* **GoogleOAuthAdapter**   — Google OAuth 2.0.
* **GitHubOAuthAdapter**   — GitHub OAuth.
* **MicrosoftOAuthAdapter** — Microsoft Identity Platform (Entra ID).
"""

from __future__ import annotations

import logging
import time
import urllib.parse
from typing import Any, Dict, Optional, Sequence

import requests
from django.conf import settings

from external_services.base import (
    HealthCheckResult,
    IdentityProvider,
    ProviderResponse,
    ValidationResult,
)
from external_services.exceptions import (
    AuthenticationError,
    ProviderResponseError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)


# ======================================================================
# Google OAuth Adapter
# ======================================================================


class GoogleOAuthAdapter(IdentityProvider):
    """Google OAuth 2.0 adapter.

    Supports the full authorization-code flow with PKCE-ready state,
    token exchange, user-info retrieval, refresh, and revocation.

    Configuration (via Django settings):
        ``GOOGLE_OAUTH_CLIENT_ID``     — OAuth client ID.
        ``GOOGLE_OAUTH_CLIENT_SECRET`` — OAuth client secret.
    """

    PROVIDER_NAME = "google"
    _AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    _TOKEN_URL = "https://oauth2.googleapis.com/token"
    _USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
    _REVOKE_URL = "https://oauth2.googleapis.com/revoke"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(provider_name=self.PROVIDER_NAME, service_type="identity", **kwargs)
        self._client_id: str = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")
        self._client_secret: str = getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "")
        self._session: Optional[requests.Session] = None

    # -- lifecycle --------------------------------------------------------

    def connect(self) -> bool:
        self._session = requests.Session()
        self.is_connected = True
        return True

    def disconnect(self) -> bool:
        if self._session:
            self._session.close()
            self._session = None
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            resp = requests.get(self._AUTH_URL, timeout=5, allow_redirects=False)
            elapsed = (time.monotonic() - start) * 1000
            return HealthCheckResult(status="healthy" if resp.status_code in (200, 302) else "degraded", provider=self.PROVIDER_NAME, response_time_ms=elapsed)
        except Exception:
            return HealthCheckResult(status="unhealthy", provider=self.PROVIDER_NAME)

    def validate_configuration(self) -> ValidationResult:
        errors = []
        if not self._client_id:
            errors.append("GOOGLE_OAUTH_CLIENT_ID is not configured")
        if not self._client_secret:
            errors.append("GOOGLE_OAUTH_CLIENT_SECRET is not configured")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    # -- OAuth operations -------------------------------------------------

    def get_authorize_url(self, scopes: Sequence[str], redirect_uri: str, state: str) -> ProviderResponse:
        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        url = f"{self._AUTH_URL}?{urllib.parse.urlencode(params)}"
        return ProviderResponse(success=True, data={"authorize_url": url}, provider=self.PROVIDER_NAME)

    def exchange_code(self, code: str, redirect_uri: str) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {
                "code": code,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }
            resp = requests.post(self._TOKEN_URL, data=payload, timeout=15)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code == 200:
                return ProviderResponse(success=True, data={"access_token": data.get("access_token"), "refresh_token": data.get("refresh_token"), "expires_in": data.get("expires_in"), "token_type": data.get("token_type")}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
            raise AuthenticationError(provider_name=self.PROVIDER_NAME, message=data.get("error_description", "Code exchange failed"))
        except AuthenticationError:
            raise
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def get_user_info(self, access_token: str) -> ProviderResponse:
        start = time.monotonic()
        try:
            resp = requests.get(self._USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                return ProviderResponse(success=True, data=resp.json(), provider=self.PROVIDER_NAME, latency_ms=elapsed)
            raise AuthenticationError(provider_name=self.PROVIDER_NAME, message="Failed to fetch user info")
        except AuthenticationError:
            raise
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def refresh_token(self, refresh_token: str) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {"refresh_token": refresh_token, "client_id": self._client_id, "client_secret": self._client_secret, "grant_type": "refresh_token"}
            resp = requests.post(self._TOKEN_URL, data=payload, timeout=15)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code == 200:
                return ProviderResponse(success=True, data={"access_token": data.get("access_token"), "expires_in": data.get("expires_in")}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
            raise AuthenticationError(provider_name=self.PROVIDER_NAME, message="Token refresh failed")
        except AuthenticationError:
            raise
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def revoke_token(self, token: str) -> ProviderResponse:
        start = time.monotonic()
        try:
            resp = requests.post(self._REVOKE_URL, params={"token": token}, timeout=10)
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=resp.status_code == 200, data={"revoked": resp.status_code == 200}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc


# ======================================================================
# GitHub OAuth Adapter
# ======================================================================


class GitHubOAuthAdapter(IdentityProvider):
    """GitHub OAuth adapter.

    Configuration (via Django settings):
        ``GITHUB_OAUTH_CLIENT_ID``     — OAuth client ID.
        ``GITHUB_OAUTH_CLIENT_SECRET`` — OAuth client secret.
    """

    PROVIDER_NAME = "github"
    _AUTH_URL = "https://github.com/login/oauth/authorize"
    _TOKEN_URL = "https://github.com/login/oauth/access_token"
    _USERINFO_URL = "https://api.github.com/user"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(provider_name=self.PROVIDER_NAME, service_type="identity", **kwargs)
        self._client_id: str = getattr(settings, "GITHUB_OAUTH_CLIENT_ID", "")
        self._client_secret: str = getattr(settings, "GITHUB_OAUTH_CLIENT_SECRET", "")
        self._session: Optional[requests.Session] = None

    def connect(self) -> bool:
        self._session = requests.Session()
        self.is_connected = True
        return True

    def disconnect(self) -> bool:
        if self._session:
            self._session.close()
            self._session = None
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            resp = requests.get("https://api.github.com/rate_limit", timeout=5)
            elapsed = (time.monotonic() - start) * 1000
            return HealthCheckResult(status="healthy" if resp.status_code == 200 else "degraded", provider=self.PROVIDER_NAME, response_time_ms=elapsed)
        except Exception:
            return HealthCheckResult(status="unhealthy", provider=self.PROVIDER_NAME)

    def validate_configuration(self) -> ValidationResult:
        errors = []
        if not self._client_id:
            errors.append("GITHUB_OAUTH_CLIENT_ID is not configured")
        if not self._client_secret:
            errors.append("GITHUB_OAUTH_CLIENT_SECRET is not configured")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def get_authorize_url(self, scopes: Sequence[str], redirect_uri: str, state: str) -> ProviderResponse:
        params = {"client_id": self._client_id, "redirect_uri": redirect_uri, "scope": " ".join(scopes), "state": state}
        url = f"{self._AUTH_URL}?{urllib.parse.urlencode(params)}"
        return ProviderResponse(success=True, data={"authorize_url": url}, provider=self.PROVIDER_NAME)

    def exchange_code(self, code: str, redirect_uri: str) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {"code": code, "client_id": self._client_id, "client_secret": self._client_secret, "redirect_uri": redirect_uri}
            resp = requests.post(self._TOKEN_URL, data=payload, headers={"Accept": "application/json"}, timeout=15)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code == 200 and data.get("access_token"):
                return ProviderResponse(success=True, data={"access_token": data.get("access_token"), "token_type": data.get("token_type", "bearer")}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
            raise AuthenticationError(provider_name=self.PROVIDER_NAME, message=data.get("error_description", "Code exchange failed"))
        except AuthenticationError:
            raise
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def get_user_info(self, access_token: str) -> ProviderResponse:
        start = time.monotonic()
        try:
            resp = requests.get(self._USERINFO_URL, headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"}, timeout=10)
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                data = resp.json()
                return ProviderResponse(success=True, data={"id": data.get("id"), "login": data.get("login"), "name": data.get("name"), "email": data.get("email"), "avatar_url": data.get("avatar_url")}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
            raise AuthenticationError(provider_name=self.PROVIDER_NAME, message="Failed to fetch GitHub user info")
        except AuthenticationError:
            raise
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def refresh_token(self, refresh_token: str) -> ProviderResponse:
        """GitHub OAuth tokens do not support refresh.

        GitHub access tokens do not expire, so refresh is a no-op
        returning the original token.
        """
        return ProviderResponse(success=True, data={"access_token": refresh_token, "note": "GitHub tokens do not expire; refresh is a no-op"}, provider=self.PROVIDER_NAME)

    def revoke_token(self, token: str) -> ProviderResponse:
        """Revoke a GitHub OAuth token by deleting the authorization."""
        start = time.monotonic()
        try:
            resp = requests.delete(f"https://api.github.com/applications/{self._client_id}/token", json={"access_token": token}, auth=(self._client_id, self._client_secret), timeout=10)
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=resp.status_code == 204, data={"revoked": resp.status_code == 204}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc


# ======================================================================
# Microsoft OAuth Adapter
# ======================================================================


class MicrosoftOAuthAdapter(IdentityProvider):
    """Microsoft Identity Platform (Entra ID) OAuth 2.0 adapter.

    Configuration (via Django settings):
        ``MICROSOFT_OAUTH_CLIENT_ID``     — Application (client) ID.
        ``MICROSOFT_OAUTH_CLIENT_SECRET`` — Client secret.
        ``MICROSOFT_OAUTH_TENANT_ID``     — Tenant ID (default ``"common"``).
    """

    PROVIDER_NAME = "microsoft"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(provider_name=self.PROVIDER_NAME, service_type="identity", **kwargs)
        self._client_id: str = getattr(settings, "MICROSOFT_OAUTH_CLIENT_ID", "")
        self._client_secret: str = getattr(settings, "MICROSOFT_OAUTH_CLIENT_SECRET", "")
        self._tenant_id: str = getattr(settings, "MICROSOFT_OAUTH_TENANT_ID", "common")
        self._auth_url = f"https://login.microsoftonline.com/{self._tenant_id}/oauth2/v2.0/authorize"
        self._token_url = f"https://login.microsoftonline.com/{self._tenant_id}/oauth2/v2.0/token"
        self._userinfo_url = "https://graph.microsoft.com/v1.0/me"
        self._session: Optional[requests.Session] = None

    def connect(self) -> bool:
        self._session = requests.Session()
        self.is_connected = True
        return True

    def disconnect(self) -> bool:
        if self._session:
            self._session.close()
            self._session = None
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            resp = requests.get(f"https://login.microsoftonline.com/{self._tenant_id}/v2.0/.well-known/openid-configuration", timeout=5)
            elapsed = (time.monotonic() - start) * 1000
            return HealthCheckResult(status="healthy" if resp.status_code == 200 else "degraded", provider=self.PROVIDER_NAME, response_time_ms=elapsed)
        except Exception:
            return HealthCheckResult(status="unhealthy", provider=self.PROVIDER_NAME)

    def validate_configuration(self) -> ValidationResult:
        errors = []
        if not self._client_id:
            errors.append("MICROSOFT_OAUTH_CLIENT_ID is not configured")
        if not self._client_secret:
            errors.append("MICROSOFT_OAUTH_CLIENT_SECRET is not configured")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def get_authorize_url(self, scopes: Sequence[str], redirect_uri: str, state: str) -> ProviderResponse:
        params = {"client_id": self._client_id, "redirect_uri": redirect_uri, "response_type": "code", "scope": " ".join(scopes), "state": state, "response_mode": "query"}
        url = f"{self._auth_url}?{urllib.parse.urlencode(params)}"
        return ProviderResponse(success=True, data={"authorize_url": url}, provider=self.PROVIDER_NAME)

    def exchange_code(self, code: str, redirect_uri: str) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {"code": code, "client_id": self._client_id, "client_secret": self._client_secret, "redirect_uri": redirect_uri, "grant_type": "authorization_code", "scope": "https://graph.microsoft.com/.default"}
            resp = requests.post(self._token_url, data=payload, timeout=15)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code == 200 and data.get("access_token"):
                return ProviderResponse(success=True, data={"access_token": data.get("access_token"), "refresh_token": data.get("refresh_token"), "expires_in": data.get("expires_in"), "id_token": data.get("id_token")}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
            raise AuthenticationError(provider_name=self.PROVIDER_NAME, message=data.get("error_description", "Code exchange failed"))
        except AuthenticationError:
            raise
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def get_user_info(self, access_token: str) -> ProviderResponse:
        start = time.monotonic()
        try:
            resp = requests.get(self._userinfo_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                data = resp.json()
                return ProviderResponse(success=True, data={"id": data.get("id"), "display_name": data.get("displayName"), "email": data.get("mail") or data.get("userPrincipalName"), "job_title": data.get("jobTitle")}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
            raise AuthenticationError(provider_name=self.PROVIDER_NAME, message="Failed to fetch Microsoft user info")
        except AuthenticationError:
            raise
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def refresh_token(self, refresh_token: str) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {"refresh_token": refresh_token, "client_id": self._client_id, "client_secret": self._client_secret, "grant_type": "refresh_token", "scope": "https://graph.microsoft.com/.default"}
            resp = requests.post(self._token_url, data=payload, timeout=15)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code == 200 and data.get("access_token"):
                return ProviderResponse(success=True, data={"access_token": data.get("access_token"), "expires_in": data.get("expires_in")}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
            raise AuthenticationError(provider_name=self.PROVIDER_NAME, message="Token refresh failed")
        except AuthenticationError:
            raise
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def revoke_token(self, token: str) -> ProviderResponse:
        """Microsoft does not support token revocation via a public endpoint.

        The recommended approach is to invalidate the user's sessions
        through the Microsoft Graph API with admin privileges.
        """
        logger.warning("Microsoft OAuth token revocation is not supported via public endpoint. Use admin Graph API.")
        return ProviderResponse(success=False, error="Token revocation not supported via public Microsoft endpoint", provider=self.PROVIDER_NAME)
