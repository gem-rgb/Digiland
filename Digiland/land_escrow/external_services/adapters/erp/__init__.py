"""
ERP provider adapters for the External Services Layer.

Implements the :class:`ERPProviderInterface` for two enterprise resource
planning backends:

* **SAPAdapter** — SAP S/4HANA Cloud via OData REST API with OAuth2 auth.
* **OracleERPAdapter** — Oracle ERP Cloud via REST API with OAuth2 auth.

Factory Function
----------------
:func:`create_erp_provider` returns an adapter instance by provider name,
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
# ERP Provider Interface
# ======================================================================


class ERPProviderInterface(ExternalProvider, ABC):
    """Abstract interface for ERP provider adapters.

    Defines the contract that every ERP integration must fulfil.  Concrete
    adapters (SAP, Oracle) implement each method by mapping it to the
    provider's specific API endpoints and data shapes.

    Methods:
        create_invoice: Create a new invoice in the ERP.
        get_invoice: Retrieve an invoice by ID.
        sync_payment: Synchronise a payment from Digiland to the ERP.
        get_chart_of_accounts: Retrieve the chart of accounts.
        create_journal_entry: Create a general-ledger journal entry.
        get_financial_report: Retrieve a financial report.
    """

    @abstractmethod
    def create_invoice(
        self,
        customer_id: str,
        line_items: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        """Create a new invoice in the ERP system.

        Args:
            customer_id: ERP-specific customer identifier.
            line_items: List of line-item dicts with at least
                ``description``, ``quantity``, ``unit_price``, and
                optionally ``tax_code`` and ``account_code``.
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
        """Retrieve an invoice by its ERP identifier.

        Args:
            invoice_id: ERP-specific invoice identifier.
            **kwargs: Provider-specific options.

        Returns:
            :class:`ProviderResponse` with invoice data.
        """

    @abstractmethod
    def sync_payment(
        self,
        payment_id: str,
        payment_data: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        """Synchronise a payment from Digiland to the ERP.

        Records the payment against the relevant invoice(s) in the ERP,
        ensuring that accounts receivable stays in sync.

        Args:
            payment_id: Internal Digiland payment identifier.
            payment_data: Payment attributes (amount, currency, method,
                invoice references, etc.).
            **kwargs: Provider-specific options.

        Returns:
            :class:`ProviderResponse` confirming the sync.
        """

    @abstractmethod
    def get_chart_of_accounts(
        self,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Retrieve the chart of accounts from the ERP.

        Args:
            **kwargs: Provider-specific filters (company_code, etc.).

        Returns:
            :class:`ProviderResponse` with a list of account records.
        """

    @abstractmethod
    def create_journal_entry(
        self,
        entry_lines: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        """Create a general-ledger journal entry in the ERP.

        Each line in ``entry_lines`` must contain at least ``account_code``,
        ``debit`` or ``credit``, and optionally ``cost_center``,
        ``description``, and ``reference``.

        Args:
            entry_lines: List of journal entry line dicts.
            **kwargs: Provider-specific fields (posting_date, document_type,
                header_text, etc.).

        Returns:
            :class:`ProviderResponse` with the journal entry ID.
        """

    @abstractmethod
    def get_financial_report(
        self,
        report_type: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Retrieve a financial report from the ERP.

        Args:
            report_type: Report identifier (e.g. ``"balance_sheet"``,
                ``"profit_loss"``, ``"trial_balance"``, ``"cash_flow"``).
            **kwargs: Provider-specific filters (period, company_code, etc.).

        Returns:
            :class:`ProviderResponse` with the report data.
        """


# ======================================================================
# SAP Adapter
# ======================================================================


class SAPAdapter(ERPProviderInterface):
    """SAP S/4HANA Cloud adapter using the OData REST API with OAuth2 auth.

    Communicates with SAP's OData v4 APIs for business partner, billing,
    and financial accounting operations.  The adapter manages OAuth2 token
    lifecycle automatically.

    Configuration (via Django settings):
        ``SAP_CLIENT_ID``       — OAuth2 client ID.
        ``SAP_CLIENT_SECRET``   — OAuth2 client secret.
        ``SAP_TOKEN_URL``       — OAuth2 token endpoint URL.
        ``SAP_BASE_URL``        — SAP OData API base URL.
        ``SAP_COMPANY_CODE``    — Default company code for postings.
    """

    PROVIDER_NAME = "sap"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            provider_name=self.PROVIDER_NAME,
            service_type="erp",
            **kwargs,
        )
        self._client_id: str = getattr(settings, "SAP_CLIENT_ID", "")
        self._client_secret: str = getattr(
            settings, "SAP_CLIENT_SECRET", ""
        )
        self._token_url: str = getattr(settings, "SAP_TOKEN_URL", "")
        self._base_url: str = getattr(
            settings, "SAP_BASE_URL", "https://my.sap-system.com"
        )
        self._company_code: str = getattr(
            settings, "SAP_COMPANY_CODE", "1000"
        )
        self._access_token: Optional[str] = None
        self._session: Optional[requests.Session] = None

    # -- helpers -----------------------------------------------------------

    def _authenticate(self) -> None:
        """Obtain an OAuth2 access token from SAP."""
        payload = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        try:
            resp = requests.post(
                self._token_url, data=payload, timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                self._access_token = data.get("access_token")
            elif resp.status_code in (400, 401):
                raise AuthenticationError(
                    provider_name=self.PROVIDER_NAME,
                    message=f"SAP OAuth2 failed: {resp.text}",
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
                message=f"SAP auth failed: {exc}",
            ) from exc

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> requests.Response:
        """Make an authenticated request to the SAP OData API."""
        if not self._access_token:
            self._authenticate()
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        url = f"{self._base_url}{path}"
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
                service_type="erp",
            )
        return resp

    # -- lifecycle ---------------------------------------------------------

    def connect(self) -> bool:
        try:
            self._session = requests.Session()
            self._authenticate()
            # Verify connectivity with a lightweight call
            resp = self._request(
                "GET",
                "/sap/opu/odata/sap/API_COSTCENTER_SRV/A_CostCenterArea?$top=1",
                timeout=10,
            )
            if resp.status_code in (200, 404):
                # 404 is acceptable — the service may not be active but auth works
                self.is_connected = True
                return True
            raise ProviderUnavailableError(
                provider_name=self.PROVIDER_NAME, service_type="erp"
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
                self._authenticate()
            resp = self._request(
                "GET",
                "/sap/opu/odata/sap/API_COSTCENTER_SRV/A_CostCenterArea?$top=1",
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
            errors.append("SAP_CLIENT_ID is not configured")
        if not self._client_secret:
            errors.append("SAP_CLIENT_SECRET is not configured")
        if not self._token_url:
            errors.append("SAP_TOKEN_URL is not configured")
        if not self._base_url or "my.sap-system.com" in self._base_url:
            warnings.append(
                "SAP_BASE_URL appears to be the default placeholder"
            )
        if not self._company_code:
            warnings.append("SAP_COMPANY_CODE is not set; using default 1000")
        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    # -- ERP operations ----------------------------------------------------

    def create_invoice(
        self,
        customer_id: str,
        line_items: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            # Build SAP billing document payload (simplified A_BillingDocumentType)
            to_billing_item = []
            for idx, item in enumerate(line_items, start=1):
                to_billing_item.append({
                    "BillingDocumentItem": str(idx).zfill(6),
                    "Material": item.get("material_code", "SERVICE"),
                    "Plant": item.get("plant", "1000"),
                    "Quantity": item.get("quantity", 1),
                    "BillingDocumentItemText": item.get("description", ""),
                    "NetAmount": float(item.get("unit_price", 0)) * item.get("quantity", 1),
                })
            payload = {
                "BillingDocumentType": kwargs.get("doc_type", "DR"),
                "CompanyCode": kwargs.get("company_code", self._company_code),
                "SoldToParty": customer_id,
                "BillingDocumentDate": kwargs.get(
                    "billing_date", time.strftime("%Y-%m-%d")
                ),
                "to_BillingDocumentItem": to_billing_item,
            }
            if kwargs.get("currency"):
                payload["TransactionCurrency"] = kwargs["currency"]
            resp = self._request(
                "POST",
                "/sap/opu/odata/sap/API_BILLING_SRV/A_BillingDocument",
                json=payload,
            )
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code in (200, 201):
                return ProviderResponse(
                    success=True,
                    data={
                        "id": data.get("BillingDocument"),
                        "data": data.get("d", data),
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=data.get("error", {}).get("message", str(data)),
                service_type="erp",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="erp",
            ) from exc

    def get_invoice(
        self,
        invoice_id: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            resp = self._request(
                "GET",
                f"/sap/opu/odata/sap/API_BILLING_SRV/A_BillingDocument('{invoice_id}')",
            )
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                data = resp.json()
                return ProviderResponse(
                    success=True,
                    data=data.get("d", data),
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                service_type="erp",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="erp",
            ) from exc

    def sync_payment(
        self,
        payment_id: str,
        payment_data: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            # Create a payment advice in SAP
            payload = {
                "CompanyCode": kwargs.get("company_code", self._company_code),
                "PaymentAdviceExternalReference": payment_id,
                "PaymentAdviceType": kwargs.get("advice_type", "ZESC"),
                "Payer": payment_data.get("customer_id", ""),
                "PaymentAdviceAmount": float(payment_data.get("amount", 0)),
                "Currency": payment_data.get("currency", "KES"),
                "PaymentAdviceDate": payment_data.get(
                    "payment_date", time.strftime("%Y-%m-%d")
                ),
            }
            resp = self._request(
                "POST",
                "/sap/opu/odata/sap/API_OPEN_ITEM_SRV/A_PaymentAdvice",
                json=payload,
            )
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code in (200, 201):
                return ProviderResponse(
                    success=True,
                    data={
                        "id": data.get("PaymentAdvice"),
                        "payment_id": payment_id,
                        "synced": True,
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=str(data),
                service_type="erp",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="erp",
            ) from exc

    def get_chart_of_accounts(
        self,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            company_code = kwargs.get("company_code", self._company_code)
            resp = self._request(
                "GET",
                f"/sap/opu/odata/sap/API_CHARTOFACCOUNTS_SRV/A_ChartOfAccounts",
                params={"$filter": f"ChartOfAccounts eq '{company_code}'", "$top": 200},
            )
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("d", {}).get("results", [])
                return ProviderResponse(
                    success=True,
                    data={"accounts": results, "count": len(results)},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                service_type="erp",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="erp",
            ) from exc

    def create_journal_entry(
        self,
        entry_lines: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            to_gl_item = []
            for idx, line in enumerate(entry_lines, start=1):
                gl_item = {
                    "LedgerGroup": line.get("ledger_group", "0L"),
                    "GLAccount": line["account_code"],
                    "DocumentItemText": line.get("description", ""),
                    "CostCenter": line.get("cost_center", ""),
                }
                if line.get("debit"):
                    gl_item["DebitCreditCode"] = "S"  # SAP: S = debit
                    gl_item["AmountInTransactionCurrency"] = str(line["debit"])
                elif line.get("credit"):
                    gl_item["DebitCreditCode"] = "H"  # SAP: H = credit
                    gl_item["AmountInTransactionCurrency"] = str(line["credit"])
                to_gl_item.append(gl_item)

            payload = {
                "CompanyCode": kwargs.get("company_code", self._company_code),
                "DocumentType": kwargs.get("document_type", "SA"),
                "PostingDate": kwargs.get(
                    "posting_date", time.strftime("%Y-%m-%d")
                ),
                "DocumentDate": kwargs.get(
                    "document_date", time.strftime("%Y-%m-%d")
                ),
                "HeaderText": kwargs.get("header_text", f"Digiland-{uuid.uuid4().hex[:8]}"),
                "to_GLItem": to_gl_item,
            }
            resp = self._request(
                "POST",
                "/sap/opu/odata/sap/API_JOURNAL_ENTRY_SRV/A_JournalEntry",
                json=payload,
            )
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code in (200, 201):
                return ProviderResponse(
                    success=True,
                    data={
                        "id": data.get("AccountingDocument"),
                        "data": data.get("d", data),
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=data.get("error", {}).get("message", str(data)),
                service_type="erp",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="erp",
            ) from exc

    def get_financial_report(
        self,
        report_type: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            # Map abstract report types to SAP CDS view endpoints
            report_endpoints = {
                "balance_sheet": "/sap/opu/odata/sap/API_FINPLANNINGDATA_SRV/A_BalanceSheet",
                "profit_loss": "/sap/opu/odata/sap/API_FINPLANNINGDATA_SRV/A_ProfitAndLoss",
                "trial_balance": "/sap/opu/odata/sap/API_FINPLANNINGDATA_SRV/A_TrialBalance",
                "cash_flow": "/sap/opu/odata/sap/API_FINPLANNINGDATA_SRV/A_CashFlow",
            }
            endpoint = report_endpoints.get(report_type)
            if not endpoint:
                raise ESLValidationError(
                    message=f"Unknown report type '{report_type}'. Supported: {list(report_endpoints.keys())}",
                    provider_name=self.PROVIDER_NAME,
                    service_type="erp",
                )
            params = {
                "$filter": f"CompanyCode eq '{kwargs.get('company_code', self._company_code)}'",
            }
            if kwargs.get("period"):
                params["$filter"] += f" and FiscalPeriod eq '{kwargs['period']}'"
            resp = self._request("GET", endpoint, params=params)
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("d", {}).get("results", [])
                return ProviderResponse(
                    success=True,
                    data={"report_type": report_type, "entries": results},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                service_type="erp",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError, ESLValidationError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="erp",
            ) from exc


# ======================================================================
# Oracle ERP Adapter
# ======================================================================


class OracleERPAdapter(ERPProviderInterface):
    """Oracle ERP Cloud adapter using the REST API with OAuth2 auth.

    Communicates with Oracle ERP Cloud's REST endpoints for invoicing,
    payments, and general ledger operations.  Supports OAuth2 token
    lifecycle management with automatic refresh.

    Configuration (via Django settings):
        ``ORACLE_ERP_CLIENT_ID``     — OAuth2 client ID.
        ``ORACLE_ERP_CLIENT_SECRET`` — OAuth2 client secret.
        ``ORACLE_ERP_TOKEN_URL``     — OAuth2 token endpoint.
        ``ORACLE_ERP_BASE_URL``      — Oracle ERP Cloud REST API base URL.
    """

    PROVIDER_NAME = "oracle_erp"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            provider_name=self.PROVIDER_NAME,
            service_type="erp",
            **kwargs,
        )
        self._client_id: str = getattr(
            settings, "ORACLE_ERP_CLIENT_ID", ""
        )
        self._client_secret: str = getattr(
            settings, "ORACLE_ERP_CLIENT_SECRET", ""
        )
        self._token_url: str = getattr(
            settings, "ORACLE_ERP_TOKEN_URL", ""
        )
        self._base_url: str = getattr(
            settings, "ORACLE_ERP_BASE_URL",
            "https://fa-emxx.oraclecloud.com",
        )
        self._access_token: Optional[str] = None
        self._session: Optional[requests.Session] = None

    # -- helpers -----------------------------------------------------------

    def _authenticate(self) -> None:
        """Obtain an OAuth2 access token from Oracle ERP Cloud."""
        payload = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": "erp",
        }
        try:
            resp = requests.post(
                self._token_url, data=payload, timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                self._access_token = data.get("access_token")
            elif resp.status_code in (400, 401):
                raise AuthenticationError(
                    provider_name=self.PROVIDER_NAME,
                    message=f"Oracle ERP OAuth2 failed: {resp.text}",
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
                message=f"Oracle ERP auth failed: {exc}",
            ) from exc

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> requests.Response:
        """Make an authenticated request to the Oracle ERP Cloud API."""
        if not self._access_token:
            self._authenticate()
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        url = f"{self._base_url}{path}"
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
                service_type="erp",
            )
        return resp

    # -- lifecycle ---------------------------------------------------------

    def connect(self) -> bool:
        try:
            self._session = requests.Session()
            self._authenticate()
            resp = self._request(
                "GET",
                "/fscmRestApi/resources/11.13.18.05/receivablesInvoices?limit=1",
                timeout=10,
            )
            if resp.status_code in (200, 404):
                self.is_connected = True
                return True
            raise ProviderUnavailableError(
                provider_name=self.PROVIDER_NAME, service_type="erp"
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
                self._authenticate()
            resp = self._request(
                "GET",
                "/fscmRestApi/resources/11.13.18.05/receivablesInvoices?limit=1",
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
            errors.append("ORACLE_ERP_CLIENT_ID is not configured")
        if not self._client_secret:
            errors.append("ORACLE_ERP_CLIENT_SECRET is not configured")
        if not self._token_url:
            errors.append("ORACLE_ERP_TOKEN_URL is not configured")
        if "fa-emxx.oraclecloud.com" in self._base_url:
            warnings.append(
                "ORACLE_ERP_BASE_URL appears to be the default placeholder"
            )
        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    # -- ERP operations ----------------------------------------------------

    def create_invoice(
        self,
        customer_id: str,
        line_items: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            lines = []
            for idx, item in enumerate(line_items, start=1):
                lines.append({
                    "LineNumber": idx,
                    "Description": item.get("description", ""),
                    "Quantity": item.get("quantity", 1),
                    "UnitSellingPrice": float(item.get("unit_price", 0)),
                    "TaxClassificationCode": item.get("tax_code", ""),
                })
            payload = {
                "InvoiceNumber": kwargs.get(
                    "invoice_number", f"DL-{uuid.uuid4().hex[:8]}"
                ),
                "BusinessUnit": kwargs.get("business_unit", "Digiland BU"),
                "CustomerNumber": customer_id,
                "InvoiceDate": kwargs.get(
                    "invoice_date", time.strftime("%Y-%m-%d")
                ),
                "InvoiceCurrencyCode": kwargs.get("currency", "KES"),
                "lines": lines,
            }
            resp = self._request(
                "POST",
                "/fscmRestApi/resources/11.13.18.05/receivablesInvoices",
                json=payload,
            )
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code in (200, 201):
                return ProviderResponse(
                    success=True,
                    data={
                        "id": data.get("InvoiceNumber"),
                        "invoice_id": data.get("InvoiceId"),
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=data.get("detail", str(data)),
                service_type="erp",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="erp",
            ) from exc

    def get_invoice(
        self,
        invoice_id: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            resp = self._request(
                "GET",
                f"/fscmRestApi/resources/11.13.18.05/receivablesInvoices/{invoice_id}",
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
                service_type="erp",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="erp",
            ) from exc

    def sync_payment(
        self,
        payment_id: str,
        payment_data: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {
                "ReceiptNumber": kwargs.get(
                    "receipt_number", f"RCPT-{uuid.uuid4().hex[:8]}"
                ),
                "BusinessUnit": kwargs.get("business_unit", "Digiland BU"),
                "ReceiptMethod": payment_data.get("method", "WIRE"),
                "ReceiptAmount": float(payment_data.get("amount", 0)),
                "CurrencyCode": payment_data.get("currency", "KES"),
                "ReceiptDate": payment_data.get(
                    "payment_date", time.strftime("%Y-%m-%d")
                ),
                "CustomerNumber": payment_data.get("customer_id", ""),
                "CrossReference": payment_id,
            }
            if payment_data.get("invoice_id"):
                payload["ApplicationLines"] = [
                    {
                        "InvoiceNumber": payment_data["invoice_id"],
                        "AmountApplied": float(payment_data.get("amount", 0)),
                    }
                ]
            resp = self._request(
                "POST",
                "/fscmRestApi/resources/11.13.18.05/receipts",
                json=payload,
            )
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code in (200, 201):
                return ProviderResponse(
                    success=True,
                    data={
                        "id": data.get("ReceiptNumber"),
                        "payment_id": payment_id,
                        "synced": True,
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=data.get("detail", str(data)),
                service_type="erp",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="erp",
            ) from exc

    def get_chart_of_accounts(
        self,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            resp = self._request(
                "GET",
                "/fscmRestApi/resources/11.13.18.05/glAccountCombinations",
                params={"limit": 200, "onlyData": "true"},
            )
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                return ProviderResponse(
                    success=True,
                    data={"accounts": items, "count": len(items)},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                service_type="erp",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="erp",
            ) from exc

    def create_journal_entry(
        self,
        entry_lines: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            je_lines = []
            for line in entry_lines:
                je_line = {
                    "AccountCombination": line["account_code"],
                    "EnteredDr": float(line.get("debit", 0)),
                    "EnteredCr": float(line.get("credit", 0)),
                    "LineNumber": len(je_lines) + 1,
                }
                if line.get("description"):
                    je_line["LineDescription"] = line["description"]
                if line.get("cost_center"):
                    je_line["CostCenter"] = line["cost_center"]
                je_lines.append(je_line)

            payload = {
                "JournalBatchName": kwargs.get(
                    "batch_name", f"DL-BATCH-{uuid.uuid4().hex[:8]}"
                ),
                "LedgerName": kwargs.get("ledger", "Primary Ledger"),
                "JournalName": kwargs.get(
                    "journal_name", f"DL-JE-{uuid.uuid4().hex[:8]}"
                ),
                "JournalEntryType": kwargs.get("entry_type", "Standard"),
                "AccountingDate": kwargs.get(
                    "accounting_date", time.strftime("%Y-%m-%d")
                ),
                "lines": je_lines,
            }
            resp = self._request(
                "POST",
                "/fscmRestApi/resources/11.13.18.05/generalLedgerJournals",
                json=payload,
            )
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code in (200, 201):
                return ProviderResponse(
                    success=True,
                    data={
                        "id": data.get("JournalBatchName"),
                        "journal_id": data.get("JournalEntryId"),
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                provider_message=data.get("detail", str(data)),
                service_type="erp",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="erp",
            ) from exc

    def get_financial_report(
        self,
        report_type: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        start = time.monotonic()
        try:
            report_endpoints = {
                "balance_sheet": "/fscmRestApi/resources/11.13.18.05/glBalanceSheetReports",
                "profit_loss": "/fscmRestApi/resources/11.13.18.05/glProfitAndLossReports",
                "trial_balance": "/fscmRestApi/resources/11.13.18.05/glTrialBalanceReports",
                "cash_flow": "/fscmRestApi/resources/11.13.18.05/glCashFlowReports",
            }
            endpoint = report_endpoints.get(report_type)
            if not endpoint:
                raise ESLValidationError(
                    message=f"Unknown report type '{report_type}'. Supported: {list(report_endpoints.keys())}",
                    provider_name=self.PROVIDER_NAME,
                    service_type="erp",
                )
            params = {"limit": 500, "onlyData": "true"}
            if kwargs.get("period"):
                params["q"] = f"PeriodName='{kwargs['period']}'"
            resp = self._request("GET", endpoint, params=params)
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                return ProviderResponse(
                    success=True,
                    data={"report_type": report_type, "entries": items},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                provider_status=resp.status_code,
                service_type="erp",
            )
        except (ProviderResponseError, ESLTimeoutError, RateLimitExceededError, ESLValidationError):
            raise
        except Exception as exc:
            raise ProviderResponseError(
                provider_name=self.PROVIDER_NAME,
                message=str(exc),
                service_type="erp",
            ) from exc


# ======================================================================
# Factory Function
# ======================================================================


_ERP_PROVIDERS: Dict[str, type] = {
    "sap": SAPAdapter,
    "oracle_erp": OracleERPAdapter,
}


def create_erp_provider(
    provider_name: str,
    **config: Any,
) -> ERPProviderInterface:
    """Factory function to create an ERP provider adapter by name.

    This is the primary entry point for obtaining an ERP adapter instance.
    It decouples caller code from specific adapter classes, enabling
    configuration-driven provider selection.

    Args:
        provider_name: Identifier for the desired ERP provider.
            Supported values: ``"sap"``, ``"oracle_erp"``.
        **config: Additional configuration passed to the adapter constructor.

    Returns:
        An initialised (but not yet connected) :class:`ERPProviderInterface`
        instance.

    Raises:
        ConfigurationError: If ``provider_name`` is not recognised.

    Example::

        erp = create_erp_provider("sap")
        erp.connect()
        invoice = erp.create_invoice("CUST001", [...])
    """
    adapter_class = _ERP_PROVIDERS.get(provider_name)
    if adapter_class is None:
        supported = ", ".join(sorted(_ERP_PROVIDERS.keys()))
        raise ConfigurationError(
            provider_name=provider_name,
            message=(
                f"Unknown ERP provider '{provider_name}'. "
                f"Supported providers: {supported}"
            ),
            service_type="erp",
        )
    return adapter_class(**config)


def list_erp_providers() -> List[str]:
    """Return a sorted list of registered ERP provider names.

    Returns:
        E.g. ``["oracle_erp", "sap"]``
    """
    return sorted(_ERP_PROVIDERS.keys())
