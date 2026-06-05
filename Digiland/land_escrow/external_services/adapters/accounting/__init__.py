"""
Accounting provider adapters for the External Services Layer.

Implements the :class:`AccountingProviderInterface` for two cloud
accounting backends:

* **QuickBooksAdapter** — QuickBooks Online via REST API with OAuth2 auth.
* **XeroAdapter** — Xero via REST API with OAuth2 auth.

Factory Function
----------------
:func:`create_accounting_provider` returns an adapter instance by provider
name, enabling configuration-driven provider selection without importing
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
# Accounting Provider Interface
# ======================================================================


class AccountingProviderInterface(ExternalProvider, ABC):
    """Abstract interface for accounting provider adapters.

    Defines the contract that every accounting integration must fulfil.
    Concrete adapters (QuickBooks, Xero) implement each method by mapping
    it to the provider's specific API endpoints and data shapes.

    Methods:
        create_invoice: Create a new invoice in the accounting system.
        get_invoice: Retrieve an invoice by ID.
        record_payment: Record a payment against an invoice.
        reconcile_transaction: Reconcile a bank transaction.
        get_balance_sheet: Retrieve the balance sheet report.
        get_profit_loss: Retrieve the profit and loss report.
        generate_receipt: Generate a payment receipt.
    """

    @abstractmethod
    def create_invoice(
        self,
        customer_id: str,
        line_items: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        """Create a new invoice in the accounting system.

        Args:
            customer_id: Provider-specific customer identifier.
            line_items: List of line-item dicts with at least
                ``description``, ``quantity``, ``unit_price``, and
                optionally ``account_code`` and ``tax_type``.
            **kwargs: Provider-specific fields (due_date, currency, etc.).

        Returns:
            :class:`ProviderResponse` with the created invoice ID and data.
        """

    @abstractmethod
    def get_invoice(
        self,
        invoice_id: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Retrieve an invoice by its provider identifier.

        Args:
            invoice_id: Provider-specific invoice identifier.
            **kwargs: Provider-specific options.

        Returns:
            :class:`ProviderResponse` with invoice data.
        """

    @abstractmethod
    def record_payment(
        self,
        invoice_id: str,
        amount: Decimal,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Record a payment against an invoice.

        Args:
            invoice_id: Provider-specific invoice identifier.
            amount: Payment amount.
            **kwargs: Provider-specific fields (payment_method, reference,
                date, bank_account, etc.).

        Returns:
            :class:`ProviderResponse` with the payment ID.
        """

    @abstractmethod
    def reconcile_transaction(
        self,
        transaction_id: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Reconcile a bank transaction with an invoice or ledger entry.

        Args:
            transaction_id: Provider-specific bank transaction identifier.
            **kwargs: Provider-specific fields (invoice_ids, account_code, etc.).

        Returns:
            :class:`ProviderResponse` confirming the reconciliation.
        """

    @abstractmethod
    def get_balance_sheet(
        self,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Retrieve the balance sheet report.

        Args:
            **kwargs: Provider-specific filters (as_of_date, summarise_by, etc.).

        Returns:
            :class:`ProviderResponse` with the balance sheet data.
        """

    @abstractmethod
    def get_profit_loss(
        self,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Retrieve the profit and loss (income statement) report.

        Args:
            **kwargs: Provider-specific filters (from_date, to_date, etc.).

        Returns:
            :class:`ProviderResponse` with the P&L data.
        """

    @abstractmethod
    def generate_receipt(
        self,
        payment_id: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Generate a payment receipt document.

        Args:
            payment_id: Provider-specific payment identifier.
            **kwargs: Provider-specific fields (format, template, etc.).

        Returns:
            :class:`ProviderResponse` with receipt data or URL.
        """


# ======================================================================
# QuickBooks Adapter
# ======================================================================


class QuickBooksAdapter(AccountingProviderInterface):
    """QuickBooks Online adapter using the REST API with OAuth2 auth.

    Communicates with QuickBooks Online's v3 REST API endpoints for
    invoicing, payments, and reporting.  The adapter manages OAuth2
    token lifecycle with automatic refresh using a stored refresh token.

    Configuration (via Django settings):
        ``QB_CLIENT_ID``          — OAuth2 client ID.
        ``QB_CLIENT_SECRET``      — OAuth2 client secret.
        ``QB_REFRESH_TOKEN``      — OAuth2 refresh token.
        ``QB_REALM_ID``           — QuickBooks company / realm ID.
        ``QB_BASE_URL``           — API base URL (default sandbox URL).
        ``QB_TOKEN_URL``          — OAuth2 token endpoint.
        ``QB_MINOR_VERSION``      — API minor version (default ``"65"``).
    """

    PROVIDER_NAME = "quickbooks"
    _DEFAULT_BASE_URL = (
        "https://sandbox-quickbooks.api.intuit.com/v3/company"
    )
    _DEFAULT_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            provider_name=self.PROVIDER_NAME,
            service_type="accounting",
            **kwargs,
        )
        self._client_id: str = getattr(settings, "QB_CLIENT_ID", "")
        self._client_secret: str = getattr(
            settings, "QB_CLIENT_SECRET", ""
        )
        self._refresh_token: str = getattr(
            settings, "QB_REFRESH_TOKEN", ""
        )
        self._realm_id: str = getattr(settings, "QB_REALM_ID", "")
        self._base_url: str = getattr(
            settings, "QB_BASE_URL", self._DEFAULT_BASE_URL
        )
        self._token_url: str = getattr(
            settings, "QB_TOKEN_URL", self._DEFAULT_TOKEN_URL
        )
        self._minor_version: str = getattr(
            settings, "QB_MINOR_VERSION", "65"
        )
        self._access_token: Optional[str] = None
        self._session: Optional[requests.Session] = None

    # -- helpers -----------------------------------------------------------

    def _refresh_access_token(self) -> None:
        """Refresh the OAuth2 access token using the refresh token."""
        import base64

        credentials = base64.b64encode(
            f"{self._client_id}:{self._client_secret}".encode()
        ).decode()
        headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
        }
        try:
            resp = requests.post(
                self._token_url,
                headers=headers,
                data=payload,
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                self._access_token = data.get("access_token")
                # Update refresh token if rotated
                new_refresh = data.get("refresh_token")
                if new_refresh:
                    self._refresh_token = new_refresh
            elif resp.status_code in (400, 401):
                raise AuthenticationError(
                    provider_name=self.PROVIDER_NAME,
                    message=f"QuickBooks OAuth2 refresh failed: {resp.text}",
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
                message=f"QuickBooks token refresh failed: {exc}",
            ) from exc

    def _api_url(self, resource: str) -> str:
        """Build the full API URL for a resource."""
        return f"{self._base_url}/{self._realm_id}/{resource}"

    def _request(
        self,
        method: str,
        resource: str,
        **kwargs: Any,
    ) -> requests.Response:
        """Make an authenticated request to the QuickBooks API."""
        if not self._access_token:
            self._refresh_access_token()
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        url = self._api_url(resource)
        params = kwargs.pop("params", {})
        params["minorversion"] = self._minor_version
        timeout = kwargs.pop("timeout", 30)
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
            self._refresh_access_token()
            headers["Authorization"] = f"Bearer {self._access_token}"
            resp = self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                timeout=timeout,
                **kwargs,
            )
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", 60))
            raise RateLimitExceededError(
                provider_name=self.PROVIDER_NAME,
                retry_after=retry_after,
                service_type="accounting",
            )
        return resp

    # -- lifecycle ---------------------------------------------------------

    def connect(self) -> bool:
        try:
            self._session = requests.Session()
            self._refresh_access_token()
            # Verify connectivity
            resp = self._request(
                "GET", "query",
                params={"query": "SELECT * FROM Customer MAXRESULTS 1"},
                timeout=10,
            )
            if resp.status_code == 200:
                self.is_connected = True
                return True
            raise ProviderUnavailableError(
                provider_name=self.PROVIDER_NAME,
                service_type="accounting",
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
        self._access_token = None
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            if not self._access_token:
                self._refresh_access_token()
            resp = self._request(
                "GET", "query",
                params={"query": "SELECT * FROM Customer MAXRESULTS 1"},
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
        if not self._client_id:
            errors.append("QB_CLIENT_ID is not configured")
        if not self._client_secret:
            errors.append("QB_CLIENT_SECRET is not configured")
        if not self._refresh_token:
            errors.append("QB_REFRESH_TOKEN is not configured")
        if not self._realm_id:
            errors.append("QB_REALM_ID is not configured")
        if "sandbox" in self._base_url:
            warnings.append(
                "QB_BASE_URL points to sandbox; verify for production"
            )
        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    # -- Accounting operations ---------------------------------------------

    def create_invoice(
        self,
        customer_id: str,
        line_items: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            qb_lines = []
            for item in line_items:
                line = {
                    "Amount": float(item.get("quantity", 1))
                    * float(item.get("unit_price", 0)),
                    "DetailType": "SalesItemLineDetail",
                    "SalesItemLineDetail": {
                        "ItemRef": {
                            "value": item.get("item_id", "1"),
                            "name": item.get("description", "Service"),
                        },
                        "Qty": item.get("quantity", 1),
                        "UnitPrice": float(item.get("unit_price", 0)),
                    },
                }
                if item.get("description"):
                    line["Description"] = item["description"]
                if item.get("tax_code"):
                    line["SalesItemLineDetail"]["TaxCodeRef"] = {
                        "value": item["tax_code"]
                    }
                qb_lines.append(line)

            payload = {
                "Line": qb_lines,
                "CustomerRef": {"value": customer_id},
            }
            if kwargs.get("due_date"):
                payload["DueDate"] = kwargs["due_date"]
            if kwargs.get("currency"):
                payload["CurrencyRef"] = {"value": kwargs["currency"]}
            if kwargs.get("invoice_number"):
                payload["DocNumber"] = kwargs["invoice_number"]

            resp = self._request("POST", "invoice", json=payload)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            invoice = data.get("Invoice", data)
            if resp.status_code == 200 and "Id" in invoice:
                return ProviderResponse(
                    success=True,
                    data={"id": invoice["Id"], "doc_number": invoice.get("DocNumber"), "total": invoice.get("TotalAmt")},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            fault = data.get("Fault", {})
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=fault.get("Error", [{}])[0].get("Message", str(data)),
                service_type="accounting",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="accounting",
            ) from exc

    def get_invoice(
        self,
        invoice_id: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            resp = self._request("GET", f"invoice/{invoice_id}")
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            invoice = data.get("Invoice", data)
            if resp.status_code == 200:
                return ProviderResponse(
                    success=True,
                    data=invoice,
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                service_type="accounting",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="accounting",
            ) from exc

    def record_payment(
        self,
        invoice_id: str,
        amount: Decimal,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {
                "TotalAmt": float(amount),
                "CustomerRef": {
                    "value": kwargs.get("customer_id", ""),
                },
                "Line": [
                    {
                        "Amount": float(amount),
                        "LinkedTxn": [
                            {
                                "TxnId": invoice_id,
                                "TxnType": "Invoice",
                            }
                        ],
                    }
                ],
                "PaymentMethodRef": {
                    "value": kwargs.get("payment_method", "cash"),
                },
            }
            if kwargs.get("reference"):
                payload["PaymentRefNum"] = kwargs["reference"]
            if kwargs.get("date"):
                payload["TxnDate"] = kwargs["date"]
            if kwargs.get("deposit_account"):
                payload["DepositToAccountRef"] = {
                    "value": kwargs["deposit_account"]
                }

            resp = self._request("POST", "payment", json=payload)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            payment = data.get("Payment", data)
            if resp.status_code == 200 and "Id" in payment:
                return ProviderResponse(
                    success=True,
                    data={"id": payment["Id"], "amount": payment.get("TotalAmt")},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            fault = data.get("Fault", {})
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=fault.get("Error", [{}])[0].get("Message", str(data)),
                service_type="accounting",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="accounting",
            ) from exc

    def reconcile_transaction(
        self,
        transaction_id: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            # QuickBooks reconciliation through updating the bank transaction
            # with matched transactions
            payload: Dict[str, Any] = {
                "Id": transaction_id,
                "SyncToken": kwargs.get("sync_token", "0"),
            }
            if kwargs.get("invoice_ids"):
                payload["LinkedTxn"] = [
                    {"TxnId": inv_id, "TxnType": "Invoice"}
                    for inv_id in kwargs["invoice_ids"]
                ]
            resp = self._request(
                "POST",
                "banktransaction",
                json=payload,
            )
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            txn = data.get("BankTransaction", data)
            if resp.status_code == 200:
                return ProviderResponse(
                    success=True,
                    data={
                        "id": transaction_id,
                        "reconciled": True,
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=str(data),
                service_type="accounting",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="accounting",
            ) from exc

    def get_balance_sheet(
        self,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            params = {
                "report": "BalanceSheet",
                "summarize_column_by": kwargs.get("summarize_by", "Month"),
            }
            if kwargs.get("as_of_date"):
                params["as_of_date"] = kwargs["as_of_date"]
            resp = self._request("GET", "reports/BalanceSheet", params=params)
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                data = resp.json()
                return ProviderResponse(
                    success=True,
                    data=data,
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                service_type="accounting",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="accounting",
            ) from exc

    def get_profit_loss(
        self,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            params = {
                "report": "ProfitAndLoss",
                "summarize_column_by": kwargs.get("summarize_by", "Month"),
            }
            if kwargs.get("from_date"):
                params["start_date"] = kwargs["from_date"]
            if kwargs.get("to_date"):
                params["end_date"] = kwargs["to_date"]
            resp = self._request(
                "GET", "reports/ProfitAndLoss", params=params
            )
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                data = resp.json()
                return ProviderResponse(
                    success=True,
                    data=data,
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                service_type="accounting",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="accounting",
            ) from exc

    def generate_receipt(
        self,
        payment_id: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            # QuickBooks doesn't have a native receipt endpoint;
            # we retrieve the payment and format it as a receipt.
            resp = self._request("GET", f"payment/{payment_id}")
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            payment = data.get("Payment", data)
            if resp.status_code == 200:
                receipt = {
                    "receipt_number": f"RCPT-{payment_id}",
                    "payment_id": payment.get("Id", payment_id),
                    "amount": payment.get("TotalAmt"),
                    "date": payment.get("TxnDate"),
                    "method": payment.get("PaymentMethodRef", {}).get(
                        "value", ""
                    ),
                    "customer": payment.get("CustomerRef", {}).get("name", ""),
                    "reference": payment.get("PaymentRefNum", ""),
                    "format": kwargs.get("format", "json"),
                }
                return ProviderResponse(
                    success=True,
                    data=receipt,
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                service_type="accounting",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="accounting",
            ) from exc


# ======================================================================
# Xero Adapter
# ======================================================================


class XeroAdapter(AccountingProviderInterface):
    """Xero adapter using the REST API with OAuth2 auth.

    Communicates with Xero's v2 REST API for accounting, invoicing,
    and bank reconciliation.  Supports OAuth2 token management with
    automatic refresh.

    Configuration (via Django settings):
        ``XERO_CLIENT_ID``       — OAuth2 client ID.
        ``XERO_CLIENT_SECRET``   — OAuth2 client secret.
        ``XERO_REFRESH_TOKEN``   — OAuth2 refresh token.
        ``XERO_TENANT_ID``       — Xero organisation / tenant ID.
        ``XERO_BASE_URL``        — API base URL.
        ``XERO_TOKEN_URL``       — OAuth2 token endpoint.
    """

    PROVIDER_NAME = "xero"
    _DEFAULT_BASE_URL = "https://api.xero.com/api.xro/2.0"
    _DEFAULT_TOKEN_URL = "https://identity.xero.com/connect/token"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            provider_name=self.PROVIDER_NAME,
            service_type="accounting",
            **kwargs,
        )
        self._client_id: str = getattr(settings, "XERO_CLIENT_ID", "")
        self._client_secret: str = getattr(
            settings, "XERO_CLIENT_SECRET", ""
        )
        self._refresh_token: str = getattr(
            settings, "XERO_REFRESH_TOKEN", ""
        )
        self._tenant_id: str = getattr(settings, "XERO_TENANT_ID", "")
        self._base_url: str = getattr(
            settings, "XERO_BASE_URL", self._DEFAULT_BASE_URL
        )
        self._token_url: str = getattr(
            settings, "XERO_TOKEN_URL", self._DEFAULT_TOKEN_URL
        )
        self._access_token: Optional[str] = None
        self._session: Optional[requests.Session] = None

    # -- helpers -----------------------------------------------------------

    def _refresh_access_token(self) -> None:
        """Refresh the OAuth2 access token using the refresh token."""
        import base64

        credentials = base64.b64encode(
            f"{self._client_id}:{self._client_secret}".encode()
        ).decode()
        headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
        }
        try:
            resp = requests.post(
                self._token_url,
                headers=headers,
                data=payload,
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                self._access_token = data.get("access_token")
                new_refresh = data.get("refresh_token")
                if new_refresh:
                    self._refresh_token = new_refresh
            elif resp.status_code in (400, 401):
                raise AuthenticationError(
                    provider_name=self.PROVIDER_NAME,
                    message=f"Xero OAuth2 refresh failed: {resp.text}",
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
                message=f"Xero token refresh failed: {exc}",
            ) from exc

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> requests.Response:
        """Make an authenticated request to the Xero API."""
        if not self._access_token:
            self._refresh_access_token()
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Xero-tenant-id": self._tenant_id,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/{path}"
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
            headers["Authorization"] = f"Bearer {self._access_token}"
            resp = self._session.request(
                method, url, headers=headers, timeout=timeout, **kwargs
            )
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", 60))
            raise RateLimitExceededError(
                provider_name=self.PROVIDER_NAME,
                retry_after=retry_after,
                service_type="accounting",
            )
        return resp

    # -- lifecycle ---------------------------------------------------------

    def connect(self) -> bool:
        try:
            self._session = requests.Session()
            self._refresh_access_token()
            # Verify connectivity by fetching organisation info
            resp = self._request("GET", "Organisations", timeout=10)
            if resp.status_code == 200:
                self.is_connected = True
                return True
            raise ProviderUnavailableError(
                provider_name=self.PROVIDER_NAME,
                service_type="accounting",
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
        self._access_token = None
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            if not self._access_token:
                self._refresh_access_token()
            resp = self._request("GET", "Organisations", timeout=5)
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
            errors.append("XERO_CLIENT_ID is not configured")
        if not self._client_secret:
            errors.append("XERO_CLIENT_SECRET is not configured")
        if not self._refresh_token:
            errors.append("XERO_REFRESH_TOKEN is not configured")
        if not self._tenant_id:
            errors.append("XERO_TENANT_ID is not configured")
        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    # -- Accounting operations ---------------------------------------------

    def create_invoice(
        self,
        customer_id: str,
        line_items: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            xero_lines = []
            for item in line_items:
                line: Dict[str, Any] = {
                    "Description": item.get("description", ""),
                    "Quantity": item.get("quantity", 1),
                    "UnitAmount": float(item.get("unit_price", 0)),
                    "AccountCode": item.get("account_code", "4000"),
                }
                if item.get("tax_type"):
                    line["TaxType"] = item["tax_type"]
                if item.get("item_code"):
                    line["ItemCode"] = item["item_code"]
                xero_lines.append(line)

            payload = {
                "Type": kwargs.get("type", "ACCREC"),
                "Contact": {"ContactID": customer_id},
                "LineItems": xero_lines,
                "Status": kwargs.get("status", "AUTHORISED"),
            }
            if kwargs.get("due_date"):
                payload["DueDate"] = kwargs["due_date"]
            if kwargs.get("date"):
                payload["Date"] = kwargs["date"]
            if kwargs.get("invoice_number"):
                payload["InvoiceNumber"] = kwargs["invoice_number"]
            if kwargs.get("currency"):
                payload["CurrencyCode"] = kwargs["currency"]
            if kwargs.get("reference"):
                payload["Reference"] = kwargs["reference"]

            resp = self._request(
                "PUT", "Invoices", json={"Invoices": [payload]}
            )
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            invoices = data.get("Invoices", [])
            if resp.status_code in (200, 201) and invoices:
                inv = invoices[0]
                return ProviderResponse(
                    success=True,
                    data={
                        "id": inv.get("InvoiceID"),
                        "invoice_number": inv.get("InvoiceNumber"),
                        "total": inv.get("Total"),
                        "status": inv.get("Status"),
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=str(data),
                service_type="accounting",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="accounting",
            ) from exc

    def get_invoice(
        self,
        invoice_id: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            resp = self._request("GET", f"Invoices/{invoice_id}")
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            invoices = data.get("Invoices", [])
            if resp.status_code == 200 and invoices:
                return ProviderResponse(
                    success=True,
                    data=invoices[0],
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                service_type="accounting",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="accounting",
            ) from exc

    def record_payment(
        self,
        invoice_id: str,
        amount: Decimal,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {
                "Invoice": {"InvoiceID": invoice_id},
                "Account": {
                    "Code": kwargs.get("bank_account_code", "090"),
                },
                "Amount": float(amount),
            }
            if kwargs.get("date"):
                payload["Date"] = kwargs["date"]
            if kwargs.get("reference"):
                payload["Reference"] = kwargs["reference"]

            resp = self._request(
                "PUT", "Payments", json={"Payments": [payload]}
            )
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            payments = data.get("Payments", [])
            if resp.status_code in (200, 201) and payments:
                pay = payments[0]
                return ProviderResponse(
                    success=True,
                    data={
                        "id": pay.get("PaymentID"),
                        "amount": pay.get("Amount"),
                        "status": pay.get("Status"),
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=str(data),
                service_type="accounting",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="accounting",
            ) from exc

    def reconcile_transaction(
        self,
        transaction_id: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            # Xero bank transaction reconciliation
            # Update the bank transaction with allocation details
            payload: Dict[str, Any] = {
                "BankTransactionID": transaction_id,
            }
            if kwargs.get("invoice_ids"):
                payload["LineItems"] = []
                for inv_id in kwargs["invoice_ids"]:
                    payload["LineItems"].append({
                        "Description": f"Reconciliation for invoice {inv_id}",
                        "UnitAmount": 0,  # Allocation handled by Xero
                        "AccountCode": kwargs.get("account_code", "4000"),
                        "LinkedTransaction": {
                            "LinkedTransactionID": inv_id,
                        },
                    })
            resp = self._request(
                "POST",
                "BankTransactions",
                json={"BankTransactions": [payload]},
            )
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code in (200, 201):
                return ProviderResponse(
                    success=True,
                    data={
                        "id": transaction_id,
                        "reconciled": True,
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            data = resp.json()
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=str(data),
                service_type="accounting",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="accounting",
            ) from exc

    def get_balance_sheet(
        self,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            params = {}
            if kwargs.get("as_of_date"):
                params["date"] = kwargs["as_of_date"]
            if kwargs.get("periods"):
                params["periods"] = kwargs["periods"]
            if kwargs.get("summarize_by"):
                params["timeframe"] = kwargs["summarize_by"]
            resp = self._request(
                "GET", "Reports/BalanceSheet", params=params
            )
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                data = resp.json()
                return ProviderResponse(
                    success=True,
                    data=data.get("Reports", [data]),
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                service_type="accounting",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="accounting",
            ) from exc

    def get_profit_loss(
        self,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            params = {}
            if kwargs.get("from_date"):
                params["fromDate"] = kwargs["from_date"]
            if kwargs.get("to_date"):
                params["toDate"] = kwargs["to_date"]
            if kwargs.get("periods"):
                params["periods"] = kwargs["periods"]
            if kwargs.get("summarize_by"):
                params["timeframe"] = kwargs["summarize_by"]
            resp = self._request(
                "GET", "Reports/ProfitAndLoss", params=params
            )
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                data = resp.json()
                return ProviderResponse(
                    success=True,
                    data=data.get("Reports", [data]),
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                service_type="accounting",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="accounting",
            ) from exc

    def generate_receipt(
        self,
        payment_id: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            # Xero doesn't have a dedicated receipt endpoint;
            # we retrieve the payment and format it as a receipt.
            resp = self._request("GET", f"Payments/{payment_id}")
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            payments = data.get("Payments", [])
            if resp.status_code == 200 and payments:
                pay = payments[0]
                receipt = {
                    "receipt_number": f"RCPT-{payment_id}",
                    "payment_id": pay.get("PaymentID", payment_id),
                    "amount": pay.get("Amount"),
                    "date": pay.get("Date"),
                    "reference": pay.get("Reference", ""),
                    "bank_account": pay.get("Account", {}).get("Code", ""),
                    "invoice": pay.get("Invoice", {}).get("InvoiceID", ""),
                    "format": kwargs.get("format", "json"),
                }
                return ProviderResponse(
                    success=True,
                    data=receipt,
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                service_type="accounting",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="accounting",
            ) from exc


# ======================================================================
# Factory Function
# ======================================================================


_ACCOUNTING_PROVIDERS: Dict[str, type] = {
    "quickbooks": QuickBooksAdapter,
    "xero": XeroAdapter,
}


def create_accounting_provider(
    provider_name: str,
    **config: Any,
) -> AccountingProviderInterface:
    """Factory function to create an accounting provider adapter by name.

    This is the primary entry point for obtaining an accounting adapter
    instance.  It decouples caller code from specific adapter classes,
    enabling configuration-driven provider selection.

    Args:
        provider_name: Identifier for the desired accounting provider.
            Supported values: ``"quickbooks"``, ``"xero"``.
        **config: Additional configuration passed to the adapter constructor.

    Returns:
        An initialised (but not yet connected)
        :class:`AccountingProviderInterface` instance.

    Raises:
        ConfigurationError: If ``provider_name`` is not recognised.

    Example::

        acc = create_accounting_provider("xero")
        acc.connect()
        invoice = acc.create_invoice("CUST-001", [...])
    """
    adapter_class = _ACCOUNTING_PROVIDERS.get(provider_name)
    if adapter_class is None:
        supported = ", ".join(sorted(_ACCOUNTING_PROVIDERS.keys()))
        raise ConfigurationError(
            provider_name=provider_name,
            message=(
                f"Unknown accounting provider '{provider_name}'. "
                f"Supported providers: {supported}"
            ),
            service_type="accounting",
        )
    return adapter_class(**config)


def list_accounting_providers() -> List[str]:
    """Return a sorted list of registered accounting provider names.

    Returns:
        E.g. ``["quickbooks", "xero"]``
    """
    return sorted(_ACCOUNTING_PROVIDERS.keys())
