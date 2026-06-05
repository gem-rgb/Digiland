"""
CRM provider adapters for the External Services Layer.

Implements the :class:`CRMProviderInterface` for three CRM backends:

* **SalesforceAdapter** — Salesforce CRM via REST API with OAuth2 Bearer auth.
* **HubSpotAdapter** — HubSpot CRM via REST API with API-key and OAuth2 auth.
* **ZohoCRMAdapter** — Zoho CRM via REST API with OAuth2 token management.

Factory Function
----------------
:func:`create_crm_provider` returns an adapter instance by provider name,
enabling configuration-driven provider selection without importing
individual adapter classes.
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

import requests
from django.conf import settings

from external_services.base import (
    ExternalProvider,
    HealthCheckResult,
    ProviderResponse,
    ValidationResult,
)
from external_services.exceptions import (
    AuthenticationError,
    ConfigurationError,
    ProviderResponseError,
    ProviderUnavailableError,
    RateLimitExceededError,
    TimeoutError as ESLTimeoutError,
    ValidationError as ESLValidationError,
)

logger = logging.getLogger(__name__)


# ======================================================================
# CRM Provider Interface
# ======================================================================


class CRMProviderInterface(ExternalProvider, ABC):
    """Abstract interface for CRM provider adapters.

    Defines the contract that every CRM integration must fulfil.  Concrete
    adapters (Salesforce, HubSpot, Zoho) implement each method by mapping
    it to the provider's specific API endpoints and data shapes.

    Methods:
        create_contact: Create a new contact record in the CRM.
        update_contact: Update an existing contact record.
        get_contact: Retrieve a contact by ID or email.
        create_deal: Create a new deal/opportunity.
        update_deal: Update an existing deal/opportunity.
        search_contacts: Search contacts by criteria.
        sync_parcel_listing: Synchronise a parcel listing to the CRM.
        sync_transaction: Synchronise a transaction to the CRM.
    """

    @abstractmethod
    def create_contact(
        self,
        first_name: str,
        last_name: str,
        email: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Create a new contact in the CRM.

        Args:
            first_name: Contact's first name.
            last_name: Contact's last name.
            email: Contact's email address.
            **kwargs: Provider-specific fields (phone, company, title, etc.).

        Returns:
            :class:`ProviderResponse` with the created contact ID and data.
        """

    @abstractmethod
    def update_contact(
        self,
        contact_id: str,
        fields: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        """Update an existing contact in the CRM.

        Args:
            contact_id: The CRM-specific contact identifier.
            fields: Dict of field names to new values.
            **kwargs: Provider-specific options.

        Returns:
            :class:`ProviderResponse` confirming the update.
        """

    @abstractmethod
    def get_contact(
        self,
        contact_id: Optional[str] = None,
        email: Optional[str] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Retrieve a contact by ID or email.

        At least one of ``contact_id`` or ``email`` must be provided.

        Args:
            contact_id: CRM-specific contact identifier.
            email: Contact email address (used if ``contact_id`` is None).
            **kwargs: Provider-specific options.

        Returns:
            :class:`ProviderResponse` with contact data.
        """

    @abstractmethod
    def create_deal(
        self,
        deal_name: str,
        amount: Decimal,
        stage: str,
        contact_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Create a new deal / opportunity in the CRM.

        Args:
            deal_name: Human-readable deal name.
            amount: Deal amount.
            stage: Pipeline stage (e.g. ``"prospecting"``, ``"closed_won"``).
            contact_id: Optional contact to associate.
            **kwargs: Provider-specific fields (close_date, probability, etc.).

        Returns:
            :class:`ProviderResponse` with the created deal ID and data.
        """

    @abstractmethod
    def update_deal(
        self,
        deal_id: str,
        fields: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        """Update an existing deal / opportunity.

        Args:
            deal_id: CRM-specific deal identifier.
            fields: Dict of field names to new values.
            **kwargs: Provider-specific options.

        Returns:
            :class:`ProviderResponse` confirming the update.
        """

    @abstractmethod
    def search_contacts(
        self,
        query: str,
        limit: int = 25,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Search for contacts matching a query string.

        Args:
            query: Search term (name, email, company, etc.).
            limit: Maximum number of results to return.
            **kwargs: Provider-specific filters.

        Returns:
            :class:`ProviderResponse` with a list of matching contacts.
        """

    @abstractmethod
    def sync_parcel_listing(
        self,
        parcel_id: str,
        parcel_data: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        """Synchronise a parcel listing from Digiland to the CRM.

        Creates or updates the parcel as a custom object (or equivalent)
        in the CRM system so that sales teams can track listings.

        Args:
            parcel_id: Internal Digiland parcel identifier.
            parcel_data: Parcel attributes (location, price, size, etc.).
            **kwargs: Provider-specific options.

        Returns:
            :class:`ProviderResponse` with the CRM object ID.
        """

    @abstractmethod
    def sync_transaction(
        self,
        transaction_id: str,
        transaction_data: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        """Synchronise a transaction from Digiland to the CRM.

        Creates or updates the transaction record so that deal stages,
        amounts, and statuses stay in sync between Digiland and the CRM.

        Args:
            transaction_id: Internal Digiland transaction identifier.
            transaction_data: Transaction attributes.
            **kwargs: Provider-specific options.

        Returns:
            :class:`ProviderResponse` with the CRM object ID.
        """


# ======================================================================
# Salesforce Adapter
# ======================================================================


class SalesforceAdapter(CRMProviderInterface):
    """Salesforce CRM adapter using the REST API with OAuth2 Bearer auth.

    Authentication is performed via the OAuth2 client-credentials or
    username-password flow.  The adapter caches the access token and
    automatically refreshes it when it expires.

    Configuration (via Django settings):
        ``SALESFORCE_CLIENT_ID``       — OAuth2 client ID.
        ``SALESFORCE_CLIENT_SECRET``   — OAuth2 client secret.
        ``SALESFORCE_USERNAME``        — Salesforce username (password flow).
        ``SALESFORCE_PASSWORD``        — Salesforce password (password flow).
        ``SALESFORCE_SECURITY_TOKEN``  — Salesforce security token.
        ``SALESFORCE_BASE_URL``        — Instance URL (set after auth).
        ``SALESFORCE_API_VERSION``     — API version (default ``v58.0``).
    """

    PROVIDER_NAME = "salesforce"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            provider_name=self.PROVIDER_NAME,
            service_type="crm",
            **kwargs,
        )
        self._client_id: str = getattr(settings, "SALESFORCE_CLIENT_ID", "")
        self._client_secret: str = getattr(
            settings, "SALESFORCE_CLIENT_SECRET", ""
        )
        self._username: str = getattr(settings, "SALESFORCE_USERNAME", "")
        self._password: str = getattr(settings, "SALESFORCE_PASSWORD", "")
        self._security_token: str = getattr(
            settings, "SALESFORCE_SECURITY_TOKEN", ""
        )
        self._base_url: str = getattr(
            settings, "SALESFORCE_BASE_URL", "https://login.salesforce.com"
        )
        self._api_version: str = getattr(
            settings, "SALESFORCE_API_VERSION", "v58.0"
        )
        self._access_token: Optional[str] = None
        self._instance_url: Optional[str] = None
        self._session: Optional[requests.Session] = None

    # -- helpers -----------------------------------------------------------

    def _authenticate(self) -> None:
        """Obtain an OAuth2 access token from Salesforce."""
        token_url = f"{self._base_url}/services/oauth2/token"
        payload = {
            "grant_type": "password",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "username": self._username,
            "password": f"{self._password}{self._security_token}",
        }
        try:
            resp = requests.post(token_url, data=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                self._access_token = data["access_token"]
                self._instance_url = data["instance_url"]
            elif resp.status_code in (400, 401):
                raise AuthenticationError(
                    provider_name=self.PROVIDER_NAME,
                    message=f"Salesforce OAuth2 failed: {resp.text}",
                )
            else:
                raise ProviderResponseError(
                    provider_name=self.PROVIDER_NAME,
                    provider_status=resp.status_code,
                    provider_message=resp.text,
                )
        except (AuthenticationError, ProviderResponseError):
            raise
        except requests.Timeout:
            raise ESLTimeoutError(
                provider_name=self.PROVIDER_NAME, timeout_seconds=15
            )
        except Exception as exc:
            raise ProviderUnavailableError(
                provider_name=self.PROVIDER_NAME,
                message=f"Salesforce auth failed: {exc}",
            ) from exc

    def _api_url(self, path: str) -> str:
        """Build a full REST API URL for the given path."""
        instance = self._instance_url or self._base_url
        return f"{instance}/services/data/{self._api_version}{path}"

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> requests.Response:
        """Make an authenticated request to the Salesforce REST API."""
        if not self._access_token:
            self._authenticate()
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        url = self._api_url(path)
        timeout = kwargs.pop("timeout", 30)
        try:
            resp = self._session.request(
                method, url, headers=headers, timeout=timeout, **kwargs
            )
        except requests.Timeout:
            raise ESLTimeoutError(
                provider_name=self.PROVIDER_NAME, timeout_seconds=timeout
            )
        if resp.status_code == 401:
            # Token may have expired — re-authenticate once
            self._authenticate()
            headers["Authorization"] = f"Bearer {self._access_token}"
            resp = self._session.request(
                method, url, headers=headers, timeout=timeout, **kwargs
            )
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", 60))
            raise RateLimitExceededError(
                provider_name=self.PROVIDER_NAME,
                retry_after=retry_after,
                service_type="crm",
            )
        return resp

    # -- lifecycle ---------------------------------------------------------

    def connect(self) -> bool:
        try:
            self._session = requests.Session()
            self._authenticate()
            self.is_connected = True
            return True
        except (AuthenticationError, ProviderUnavailableError):
            raise
        except Exception as exc:
            raise ProviderUnavailableError(
                provider_name=self.PROVIDER_NAME
            ) from exc

    def disconnect(self) -> bool:
        if self._session:
            self._session.close()
            self._session = None
        self._access_token = None
        self._instance_url = None
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            if not self._access_token:
                self._authenticate()
            resp = self._request("GET", "/limits", timeout=5)
            elapsed = (time.monotonic() - start) * 1000
            status = "healthy" if resp.status_code == 200 else "degraded"
            return HealthCheckResult(
                status=status,
                provider=self.PROVIDER_NAME,
                response_time_ms=elapsed,
            )
        except Exception:
            return HealthCheckResult(
                status="unhealthy", provider=self.PROVIDER_NAME
            )

    def validate_configuration(self) -> ValidationResult:
        errors, warnings = [], []
        if not self._client_id:
            errors.append("SALESFORCE_CLIENT_ID is not configured")
        if not self._client_secret:
            errors.append("SALESFORCE_CLIENT_SECRET is not configured")
        if not self._username:
            errors.append("SALESFORCE_USERNAME is not configured")
        if not self._password:
            errors.append("SALESFORCE_PASSWORD is not configured")
        if not self._security_token:
            warnings.append(
                "SALESFORCE_SECURITY_TOKEN is not set; may be required"
            )
        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    # -- CRM operations ----------------------------------------------------

    def create_contact(
        self,
        first_name: str,
        last_name: str,
        email: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {
                "FirstName": first_name,
                "LastName": last_name,
                "Email": email,
                "Phone": kwargs.get("phone", ""),
                "Company": kwargs.get("company", ""),
                "Title": kwargs.get("title", ""),
            }
            # Remove empty optional fields
            payload = {k: v for k, v in payload.items() if v}
            resp = self._request(
                "POST", "/sobjects/Contact", json=payload
            )
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code in (200, 201):
                return ProviderResponse(
                    success=True,
                    data={"id": data.get("id"), "success": data.get("success")},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=data.get("message", str(data)),
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def update_contact(
        self,
        contact_id: str,
        fields: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            resp = self._request(
                "PATCH",
                f"/sobjects/Contact/{contact_id}",
                json=fields,
            )
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code in (200, 204):
                return ProviderResponse(
                    success=True,
                    data={"id": contact_id, "updated": True},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            data = resp.json() if resp.content else {}
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=data.get("message", "Update failed"),
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def get_contact(
        self,
        contact_id: Optional[str] = None,
        email: Optional[str] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            if contact_id:
                resp = self._request(
                    "GET", f"/sobjects/Contact/{contact_id}"
                )
            elif email:
                query = (
                    f"SELECT Id,FirstName,LastName,Email,Phone,Company "
                    f"FROM Contact WHERE Email='{email}' LIMIT 1"
                )
                resp = self._request(
                    "GET",
                    "/query",
                    params={"q": query},
                )
            else:
                raise ESLValidationError(
                    message="Either contact_id or email is required",
                    provider_name=self.PROVIDER_NAME,
                    service_type="crm",
                )
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code == 200:
                records = data.get("records", [data])
                contact = records[0] if records else None
                return ProviderResponse(
                    success=contact is not None,
                    data=contact,
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                service_type="crm",
            )
        except (
            ProviderResponseError,
            ESLTimeoutError,
            RateLimitExceededError,
            ESLValidationError,
        ):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def create_deal(
        self,
        deal_name: str,
        amount: Decimal,
        stage: str,
        contact_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload: Dict[str, Any] = {
                "Name": deal_name,
                "Amount": float(amount),
                "StageName": stage,
                "CloseDate": kwargs.get(
                    "close_date", time.strftime("%Y-%m-%d")
                ),
                "Type": kwargs.get("type", "New Land Sale"),
            }
            if contact_id:
                payload["ContactId"] = contact_id
            resp = self._request(
                "POST", "/sobjects/Opportunity", json=payload
            )
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code in (200, 201):
                return ProviderResponse(
                    success=True,
                    data={"id": data.get("id"), "success": data.get("success")},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=data.get("message", str(data)),
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def update_deal(
        self,
        deal_id: str,
        fields: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            resp = self._request(
                "PATCH",
                f"/sobjects/Opportunity/{deal_id}",
                json=fields,
            )
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code in (200, 204):
                return ProviderResponse(
                    success=True,
                    data={"id": deal_id, "updated": True},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            data = resp.json() if resp.content else {}
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=data.get("message", "Update failed"),
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def search_contacts(
        self,
        query: str,
        limit: int = 25,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            soql = (
                f"SELECT Id,FirstName,LastName,Email,Phone "
                f"FROM Contact "
                f"WHERE Name LIKE '%{query}%' "
                f"OR Email LIKE '%{query}%' "
                f"LIMIT {limit}"
            )
            resp = self._request(
                "GET", "/query", params={"q": soql}
            )
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code == 200:
                return ProviderResponse(
                    success=True,
                    data={
                        "records": data.get("records", []),
                        "total_size": data.get("totalSize", 0),
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def sync_parcel_listing(
        self,
        parcel_id: str,
        parcel_data: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            # Upsert by external ID field (Parcel_ID__c)
            payload = {
                "Parcel_ID__c": parcel_id,
                "Name": parcel_data.get("name", f"Parcel {parcel_id}"),
                "Location__c": parcel_data.get("location", ""),
                "Price__c": parcel_data.get("price", 0),
                "Size_Acres__c": parcel_data.get("size_acres", 0),
                "Status__c": parcel_data.get("status", "Available"),
            }
            resp = self._request(
                "PATCH",
                "/sobjects/Parcel__c/Parcel_ID__c/" + parcel_id,
                json=payload,
            )
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code in (200, 204):
                return ProviderResponse(
                    success=True,
                    data={
                        "id": resp.json().get("id") if resp.content else parcel_id,
                        "parcel_id": parcel_id,
                        "synced": True,
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            data = resp.json() if resp.content else {}
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=data.get("message", "Sync failed"),
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def sync_transaction(
        self,
        transaction_id: str,
        transaction_data: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {
                "Transaction_ID__c": transaction_id,
                "Name": f"TXN-{transaction_id}",
                "Amount__c": transaction_data.get("amount", 0),
                "Status__c": transaction_data.get("status", "Pending"),
                "Buyer_Email__c": transaction_data.get("buyer_email", ""),
                "Seller_Email__c": transaction_data.get("seller_email", ""),
                "Parcel_ID__c": transaction_data.get("parcel_id", ""),
            }
            resp = self._request(
                "PATCH",
                "/sobjects/Transaction__c/Transaction_ID__c/" + transaction_id,
                json=payload,
            )
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code in (200, 204):
                return ProviderResponse(
                    success=True,
                    data={
                        "id": resp.json().get("id") if resp.content else transaction_id,
                        "transaction_id": transaction_id,
                        "synced": True,
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            data = resp.json() if resp.content else {}
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=data.get("message", "Sync failed"),
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc


# ======================================================================
# HubSpot Adapter
# ======================================================================


class HubSpotAdapter(CRMProviderInterface):
    """HubSpot CRM adapter using the REST API with API-key and OAuth2 auth.

    Supports both API-key (for simple setups) and OAuth2 (for production)
    authentication.  The adapter uses HubSpot's v3 CRM endpoints.

    Configuration (via Django settings):
        ``HUBSPOT_API_KEY``     — HubSpot API key (development).
        ``HUBSPOT_ACCESS_TOKEN`` — OAuth2 access token (production).
        ``HUBSPOT_BASE_URL``    — Defaults to ``https://api.hubapi.com``.
    """

    PROVIDER_NAME = "hubspot"
    _BASE_URL = "https://api.hubapi.com"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            provider_name=self.PROVIDER_NAME,
            service_type="crm",
            **kwargs,
        )
        self._api_key: str = getattr(settings, "HUBSPOT_API_KEY", "")
        self._access_token: str = getattr(
            settings, "HUBSPOT_ACCESS_TOKEN", ""
        )
        self._base_url: str = getattr(
            settings, "HUBSPOT_BASE_URL", self._BASE_URL
        )
        self._session: Optional[requests.Session] = None

    # -- helpers -----------------------------------------------------------

    def _get_auth_headers(self) -> Dict[str, str]:
        """Return auth headers preferring OAuth2 over API key."""
        if self._access_token:
            return {"Authorization": f"Bearer {self._access_token}"}
        if self._api_key:
            return {}
        return {}

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> requests.Response:
        """Make an authenticated request to the HubSpot API."""
        headers = {
            "Content-Type": "application/json",
            **self._get_auth_headers(),
        }
        url = f"{self._base_url}{path}"
        timeout = kwargs.pop("timeout", 30)
        # Append API key as query param if no OAuth token
        params = kwargs.pop("params", {})
        if self._api_key and not self._access_token:
            params["hapikey"] = self._api_key
        try:
            resp = self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                timeout=timeout,
                **kwargs,
            )
        except requests.Timeout:
            raise ESLTimeoutError(
                provider_name=self.PROVIDER_NAME, timeout_seconds=timeout
            )
        if resp.status_code == 401:
            raise AuthenticationError(
                provider_name=self.PROVIDER_NAME,
                service_type="crm",
            )
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", 10))
            raise RateLimitExceededError(
                provider_name=self.PROVIDER_NAME,
                retry_after=retry_after,
                service_type="crm",
            )
        return resp

    # -- lifecycle ---------------------------------------------------------

    def connect(self) -> bool:
        try:
            self._session = requests.Session()
            resp = self._request("GET", "/crm/v3/objects/contacts", timeout=10)
            if resp.status_code == 200:
                self.is_connected = True
                return True
            if resp.status_code == 401:
                raise AuthenticationError(
                    provider_name=self.PROVIDER_NAME, service_type="crm"
                )
            raise ProviderUnavailableError(
                provider_name=self.PROVIDER_NAME, service_type="crm"
            )
        except (AuthenticationError, ProviderUnavailableError):
            raise
        except Exception as exc:
            raise ProviderUnavailableError(
                provider_name=self.PROVIDER_NAME
            ) from exc

    def disconnect(self) -> bool:
        if self._session:
            self._session.close()
            self._session = None
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            resp = self._request(
                "GET",
                "/crm/v3/objects/contacts",
                params={"limit": 1},
                timeout=5,
            )
            elapsed = (time.monotonic() - start) * 1000
            status = "healthy" if resp.status_code == 200 else "degraded"
            return HealthCheckResult(
                status=status,
                provider=self.PROVIDER_NAME,
                response_time_ms=elapsed,
            )
        except Exception:
            return HealthCheckResult(
                status="unhealthy", provider=self.PROVIDER_NAME
            )

    def validate_configuration(self) -> ValidationResult:
        errors, warnings = [], []
        if not self._api_key and not self._access_token:
            errors.append(
                "Either HUBSPOT_API_KEY or HUBSPOT_ACCESS_TOKEN must be configured"
            )
        if self._api_key and self._access_token:
            warnings.append(
                "Both HUBSPOT_API_KEY and HUBSPOT_ACCESS_TOKEN set; "
                "OAuth2 token will be preferred"
            )
        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    # -- CRM operations ----------------------------------------------------

    def create_contact(
        self,
        first_name: str,
        last_name: str,
        email: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            properties = {
                "firstname": first_name,
                "lastname": last_name,
                "email": email,
            }
            if kwargs.get("phone"):
                properties["phone"] = kwargs["phone"]
            if kwargs.get("company"):
                properties["company"] = kwargs["company"]
            if kwargs.get("title"):
                properties["jobtitle"] = kwargs["title"]
            payload = {"properties": properties}
            resp = self._request(
                "POST", "/crm/v3/objects/contacts", json=payload
            )
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code in (200, 201):
                return ProviderResponse(
                    success=True,
                    data={"id": data.get("id"), "properties": data.get("properties")},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=data.get("message", str(data)),
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError, AuthenticationError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def update_contact(
        self,
        contact_id: str,
        fields: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {"properties": fields}
            resp = self._request(
                "PATCH",
                f"/crm/v3/objects/contacts/{contact_id}",
                json=payload,
            )
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code in (200, 204):
                return ProviderResponse(
                    success=True,
                    data={"id": contact_id, "updated": True},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            data = resp.json() if resp.content else {}
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=data.get("message", "Update failed"),
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError, AuthenticationError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def get_contact(
        self,
        contact_id: Optional[str] = None,
        email: Optional[str] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            if contact_id:
                resp = self._request(
                    "GET",
                    f"/crm/v3/objects/contacts/{contact_id}",
                )
            elif email:
                resp = self._request(
                    "POST",
                    "/crm/v3/objects/contacts/batch/read",
                    json={
                        "properties": ["firstname", "lastname", "email", "phone"],
                        "idProperty": "email",
                        "inputs": [{"id": email}],
                    },
                )
            else:
                raise ESLValidationError(
                    message="Either contact_id or email is required",
                    provider_name=self.PROVIDER_NAME,
                    service_type="crm",
                )
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code == 200:
                results = data.get("results", [data])
                contact = results[0] if results else None
                return ProviderResponse(
                    success=contact is not None,
                    data=contact,
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                service_type="crm",
            )
        except (
            ProviderResponseError,
            ESLTimeoutError,
            RateLimitExceededError,
            ESLValidationError,
            AuthenticationError,
        ):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def create_deal(
        self,
        deal_name: str,
        amount: Decimal,
        stage: str,
        contact_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            properties = {
                "dealname": deal_name,
                "amount": str(amount),
                "dealstage": stage,
                "pipeline": kwargs.get("pipeline", "default"),
                "closedate": kwargs.get("close_date", ""),
            }
            payload: Dict[str, Any] = {"properties": properties}
            if contact_id:
                payload["associations"] = [
                    {
                        "to": {"id": contact_id},
                        "types": [
                            {
                                "associationCategory": "HUBSPOT_DEFINED",
                                "associationTypeId": 3,
                            }
                        ],
                    }
                ]
            resp = self._request(
                "POST", "/crm/v3/objects/deals", json=payload
            )
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code in (200, 201):
                return ProviderResponse(
                    success=True,
                    data={"id": data.get("id"), "properties": data.get("properties")},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=data.get("message", str(data)),
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError, AuthenticationError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def update_deal(
        self,
        deal_id: str,
        fields: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {"properties": fields}
            resp = self._request(
                "PATCH",
                f"/crm/v3/objects/deals/{deal_id}",
                json=payload,
            )
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code in (200, 204):
                return ProviderResponse(
                    success=True,
                    data={"id": deal_id, "updated": True},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            data = resp.json() if resp.content else {}
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=data.get("message", "Update failed"),
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError, AuthenticationError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def search_contacts(
        self,
        query: str,
        limit: int = 25,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {
                "query": query,
                "limit": limit,
                "properties": ["firstname", "lastname", "email", "phone"],
            }
            if kwargs.get("filters"):
                payload["filterGroups"] = kwargs["filters"]
            resp = self._request(
                "POST",
                "/crm/v3/objects/contacts/search",
                json=payload,
            )
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code == 200:
                return ProviderResponse(
                    success=True,
                    data={
                        "records": data.get("results", []),
                        "total": data.get("total", 0),
                        "paging": data.get("paging"),
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError, AuthenticationError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def sync_parcel_listing(
        self,
        parcel_id: str,
        parcel_data: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            # Use custom object type "parcels" (must be created in HubSpot)
            properties = {
                "parcel_id": parcel_id,
                "name": parcel_data.get("name", f"Parcel {parcel_id}"),
                "location": parcel_data.get("location", ""),
                "price": str(parcel_data.get("price", 0)),
                "size_acres": str(parcel_data.get("size_acres", 0)),
                "status": parcel_data.get("status", "Available"),
            }
            payload = {"properties": properties}
            resp = self._request(
                "POST",
                "/crm/v3/objects/parcels",
                json=payload,
            )
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code in (200, 201):
                return ProviderResponse(
                    success=True,
                    data={
                        "id": data.get("id"),
                        "parcel_id": parcel_id,
                        "synced": True,
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=data.get("message", "Sync failed"),
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError, AuthenticationError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def sync_transaction(
        self,
        transaction_id: str,
        transaction_data: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            properties = {
                "transaction_id": transaction_id,
                "name": f"TXN-{transaction_id}",
                "amount": str(transaction_data.get("amount", 0)),
                "status": transaction_data.get("status", "Pending"),
                "buyer_email": transaction_data.get("buyer_email", ""),
                "seller_email": transaction_data.get("seller_email", ""),
                "parcel_id": transaction_data.get("parcel_id", ""),
            }
            payload = {"properties": properties}
            resp = self._request(
                "POST",
                "/crm/v3/objects/transactions",
                json=payload,
            )
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code in (200, 201):
                return ProviderResponse(
                    success=True,
                    data={
                        "id": data.get("id"),
                        "transaction_id": transaction_id,
                        "synced": True,
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=data.get("message", "Sync failed"),
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError, AuthenticationError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc


# ======================================================================
# Zoho CRM Adapter
# ======================================================================


class ZohoCRMAdapter(CRMProviderInterface):
    """Zoho CRM adapter using the REST API with OAuth2 auth.

    Supports Zoho CRM v8 API with OAuth2 token management.
    The adapter caches the access token and automatically refreshes it.

    Configuration (via Django settings):
        ``ZOHO_CLIENT_ID``       — OAuth2 client ID.
        ``ZOHO_CLIENT_SECRET``   — OAuth2 client secret.
        ``ZOHO_REFRESH_TOKEN``   — OAuth2 refresh token.
        ``ZOHO_BASE_URL``        — Zoho API domain (default ``https://www.zohoapis.com``).
        ``ZOHO_API_DOMAIN``      — Accounts domain (default ``https://accounts.zoho.com``).
    """

    PROVIDER_NAME = "zoho_crm"
    _DEFAULT_BASE_URL = "https://www.zohoapis.com"
    _DEFAULT_ACCOUNTS_URL = "https://accounts.zoho.com"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            provider_name=self.PROVIDER_NAME,
            service_type="crm",
            **kwargs,
        )
        self._client_id: str = getattr(settings, "ZOHO_CLIENT_ID", "")
        self._client_secret: str = getattr(
            settings, "ZOHO_CLIENT_SECRET", ""
        )
        self._refresh_token: str = getattr(
            settings, "ZOHO_REFRESH_TOKEN", ""
        )
        self._base_url: str = getattr(
            settings, "ZOHO_BASE_URL", self._DEFAULT_BASE_URL
        )
        self._accounts_url: str = getattr(
            settings, "ZOHO_API_DOMAIN", self._DEFAULT_ACCOUNTS_URL
        )
        self._access_token: Optional[str] = None
        self._session: Optional[requests.Session] = None

    # -- helpers -----------------------------------------------------------

    def _refresh_access_token(self) -> None:
        """Obtain a new access token using the refresh token."""
        url = f"{self._accounts_url}/oauth/v2/token"
        payload = {
            "grant_type": "refresh_token",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": self._refresh_token,
        }
        try:
            resp = requests.post(url, data=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                self._access_token = data.get("access_token")
                if not self._access_token:
                    raise AuthenticationError(
                        provider_name=self.PROVIDER_NAME,
                        message="Zoho OAuth2 returned no access token",
                    )
            elif resp.status_code in (400, 401):
                raise AuthenticationError(
                    provider_name=self.PROVIDER_NAME,
                    message=f"Zoho OAuth2 refresh failed: {resp.text}",
                )
            else:
                raise ProviderResponseError(
                    provider_name=self.PROVIDER_NAME,
                    provider_status=resp.status_code,
                    provider_message=resp.text,
                )
        except (AuthenticationError, ProviderResponseError):
            raise
        except requests.Timeout:
            raise ESLTimeoutError(
                provider_name=self.PROVIDER_NAME, timeout_seconds=15
            )
        except Exception as exc:
            raise ProviderUnavailableError(
                provider_name=self.PROVIDER_NAME,
                message=f"Zoho token refresh failed: {exc}",
            ) from exc

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> requests.Response:
        """Make an authenticated request to the Zoho CRM API."""
        if not self._access_token:
            self._refresh_access_token()
        headers = {
            "Authorization": f"Zoho-oauthtoken {self._access_token}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/crm/v8{path}"
        timeout = kwargs.pop("timeout", 30)
        try:
            resp = self._session.request(
                method, url, headers=headers, timeout=timeout, **kwargs
            )
        except requests.Timeout:
            raise ESLTimeoutError(
                provider_name=self.PROVIDER_NAME, timeout_seconds=timeout
            )
        if resp.status_code == 401:
            self._refresh_access_token()
            headers["Authorization"] = f"Zoho-oauthtoken {self._access_token}"
            resp = self._session.request(
                method, url, headers=headers, timeout=timeout, **kwargs
            )
        if resp.status_code == 429:
            raise RateLimitExceededError(
                provider_name=self.PROVIDER_NAME,
                service_type="crm",
            )
        return resp

    # -- lifecycle ---------------------------------------------------------

    def connect(self) -> bool:
        try:
            self._session = requests.Session()
            self._refresh_access_token()
            self.is_connected = True
            return True
        except (AuthenticationError, ProviderUnavailableError):
            raise
        except Exception as exc:
            raise ProviderUnavailableError(
                provider_name=self.PROVIDER_NAME
            ) from exc

    def disconnect(self) -> bool:
        if self._session:
            self._session.close()
            self._session = None
        self._access_token = None
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            if not self._access_token:
                self._refresh_access_token()
            resp = self._request(
                "GET", "/settings/org", timeout=5
            )
            elapsed = (time.monotonic() - start) * 1000
            status = "healthy" if resp.status_code == 200 else "degraded"
            return HealthCheckResult(
                status=status,
                provider=self.PROVIDER_NAME,
                response_time_ms=elapsed,
            )
        except Exception:
            return HealthCheckResult(
                status="unhealthy", provider=self.PROVIDER_NAME
            )

    def validate_configuration(self) -> ValidationResult:
        errors, warnings = [], []
        if not self._client_id:
            errors.append("ZOHO_CLIENT_ID is not configured")
        if not self._client_secret:
            errors.append("ZOHO_CLIENT_SECRET is not configured")
        if not self._refresh_token:
            errors.append("ZOHO_REFRESH_TOKEN is not configured")
        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    # -- CRM operations ----------------------------------------------------

    def create_contact(
        self,
        first_name: str,
        last_name: str,
        email: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            data = {
                "First_Name": first_name,
                "Last_Name": last_name,
                "Email": email,
            }
            if kwargs.get("phone"):
                data["Phone"] = kwargs["phone"]
            if kwargs.get("title"):
                data["Title"] = kwargs["title"]
            payload = {"data": [data]}
            resp = self._request(
                "POST", "/Contacts", json=payload
            )
            elapsed = (time.monotonic() - start) * 1000
            resp_data = resp.json()
            if resp.status_code in (200, 201):
                details = resp_data.get("data", [{}])[0]
                return ProviderResponse(
                    success=details.get("code") == "SUCCESS",
                    data={
                        "id": details.get("details", {}).get("id"),
                        "code": details.get("code"),
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=str(resp_data),
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError, AuthenticationError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def update_contact(
        self,
        contact_id: str,
        fields: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {"data": [fields]}
            resp = self._request(
                "PUT", f"/Contacts/{contact_id}", json=payload
            )
            elapsed = (time.monotonic() - start) * 1000
            resp_data = resp.json()
            details = resp_data.get("data", [{}])[0]
            if resp.status_code in (200, 201) and details.get("code") == "SUCCESS":
                return ProviderResponse(
                    success=True,
                    data={"id": contact_id, "updated": True},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=details.get("message", "Update failed"),
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError, AuthenticationError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def get_contact(
        self,
        contact_id: Optional[str] = None,
        email: Optional[str] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            if contact_id:
                resp = self._request(
                    "GET", f"/Contacts/{contact_id}"
                )
            elif email:
                resp = self._request(
                    "GET",
                    "/Contacts/search",
                    params={"email": email},
                )
            else:
                raise ESLValidationError(
                    message="Either contact_id or email is required",
                    provider_name=self.PROVIDER_NAME,
                    service_type="crm",
                )
            elapsed = (time.monotonic() - start) * 1000
            resp_data = resp.json()
            if resp.status_code == 200:
                records = resp_data.get("data", [])
                contact = records[0] if records else None
                return ProviderResponse(
                    success=contact is not None,
                    data=contact,
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                service_type="crm",
            )
        except (
            ProviderResponseError,
            ESLTimeoutError,
            RateLimitExceededError,
            ESLValidationError,
            AuthenticationError,
        ):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def create_deal(
        self,
        deal_name: str,
        amount: Decimal,
        stage: str,
        contact_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            data: Dict[str, Any] = {
                "Deal_Name": deal_name,
                "Amount": float(amount),
                "Stage": stage,
            }
            if kwargs.get("close_date"):
                data["Closing_Date"] = kwargs["close_date"]
            if kwargs.get("type"):
                data["Type"] = kwargs["type"]
            payload: Dict[str, Any] = {"data": [data]}
            if contact_id:
                payload["data"][0]["Contact_Name"] = contact_id
            resp = self._request(
                "POST", "/Deals", json=payload
            )
            elapsed = (time.monotonic() - start) * 1000
            resp_data = resp.json()
            if resp.status_code in (200, 201):
                details = resp_data.get("data", [{}])[0]
                return ProviderResponse(
                    success=details.get("code") == "SUCCESS",
                    data={
                        "id": details.get("details", {}).get("id"),
                        "code": details.get("code"),
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=str(resp_data),
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError, AuthenticationError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def update_deal(
        self,
        deal_id: str,
        fields: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {"data": [fields]}
            resp = self._request(
                "PUT", f"/Deals/{deal_id}", json=payload
            )
            elapsed = (time.monotonic() - start) * 1000
            resp_data = resp.json()
            details = resp_data.get("data", [{}])[0]
            if resp.status_code in (200, 201) and details.get("code") == "SUCCESS":
                return ProviderResponse(
                    success=True,
                    data={"id": deal_id, "updated": True},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=details.get("message", "Update failed"),
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError, AuthenticationError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def search_contacts(
        self,
        query: str,
        limit: int = 25,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            resp = self._request(
                "GET",
                "/Contacts/search",
                params={"word": query, "per_page": limit},
            )
            elapsed = (time.monotonic() - start) * 1000
            resp_data = resp.json()
            if resp.status_code == 200:
                return ProviderResponse(
                    success=True,
                    data={
                        "records": resp_data.get("data", []),
                        "info": resp_data.get("info", {}),
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError, AuthenticationError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def sync_parcel_listing(
        self,
        parcel_id: str,
        parcel_data: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            data = {
                "Name": parcel_data.get("name", f"Parcel {parcel_id}"),
                "Parcel_ID": parcel_id,
                "Location": parcel_data.get("location", ""),
                "Price": str(parcel_data.get("price", 0)),
                "Size_Acres": str(parcel_data.get("size_acres", 0)),
                "Status": parcel_data.get("status", "Available"),
            }
            payload = {"data": [data]}
            resp = self._request(
                "POST", "/Parcels/upsert", json=payload
            )
            elapsed = (time.monotonic() - start) * 1000
            resp_data = resp.json()
            if resp.status_code in (200, 201):
                details = resp_data.get("data", [{}])[0]
                return ProviderResponse(
                    success=details.get("code") in ("SUCCESS", "DUPLICATE_DATA"),
                    data={
                        "id": details.get("details", {}).get("id", parcel_id),
                        "parcel_id": parcel_id,
                        "synced": True,
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=str(resp_data),
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError, AuthenticationError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc

    def sync_transaction(
        self,
        transaction_id: str,
        transaction_data: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            data = {
                "Name": f"TXN-{transaction_id}",
                "Transaction_ID": transaction_id,
                "Amount": str(transaction_data.get("amount", 0)),
                "Status": transaction_data.get("status", "Pending"),
                "Buyer_Email": transaction_data.get("buyer_email", ""),
                "Seller_Email": transaction_data.get("seller_email", ""),
                "Parcel_ID": transaction_data.get("parcel_id", ""),
            }
            payload = {"data": [data]}
            resp = self._request(
                "POST", "/Transactions/upsert", json=payload
            )
            elapsed = (time.monotonic() - start) * 1000
            resp_data = resp.json()
            if resp.status_code in (200, 201):
                details = resp_data.get("data", [{}])[0]
                return ProviderResponse(
                    success=details.get("code") in ("SUCCESS", "DUPLICATE_DATA"),
                    data={
                        "id": details.get("details", {}).get("id", transaction_id),
                        "transaction_id": transaction_id,
                        "synced": True,
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=str(resp_data),
                service_type="crm",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError, AuthenticationError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="crm",
            ) from exc


# ======================================================================
# Factory Function
# ======================================================================


# Registry mapping provider names to adapter classes
_CRM_PROVIDERS: Dict[str, type] = {
    "salesforce": SalesforceAdapter,
    "hubspot": HubSpotAdapter,
    "zoho_crm": ZohoCRMAdapter,
}


def create_crm_provider(
    provider_name: str,
    **config: Any,
) -> CRMProviderInterface:
    """Factory function to create a CRM provider adapter by name.

    This is the primary entry point for obtaining a CRM adapter instance.
    It decouples caller code from specific adapter classes, enabling
    configuration-driven provider selection.

    Args:
        provider_name: Identifier for the desired CRM provider.
            Supported values: ``"salesforce"``, ``"hubspot"``, ``"zoho_crm"``.
        **config: Additional configuration passed to the adapter constructor.

    Returns:
        An initialised (but not yet connected) :class:`CRMProviderInterface`
        instance.

    Raises:
        ConfigurationError: If ``provider_name`` is not recognised.

    Example::

        crm = create_crm_provider("salesforce")
        crm.connect()
        contact = crm.create_contact("Jane", "Doe", "jane@example.com")
    """
    adapter_class = _CRM_PROVIDERS.get(provider_name)
    if adapter_class is None:
        supported = ", ".join(sorted(_CRM_PROVIDERS.keys()))
        raise ConfigurationError(
            provider_name=provider_name,
            message=(
                f"Unknown CRM provider '{provider_name}'. "
                f"Supported providers: {supported}"
            ),
            service_type="crm",
        )
    return adapter_class(**config)


def list_crm_providers() -> List[str]:
    """Return a sorted list of registered CRM provider names.

    Returns:
        E.g. ``["hubspot", "salesforce", "zoho_crm"]``
    """
    return sorted(_CRM_PROVIDERS.keys())
