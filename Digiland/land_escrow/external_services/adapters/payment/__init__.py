"""
Payment provider adapters for the External Services Layer.

Implements the :class:`~external_services.base.PaymentProvider` interface
for five payment backends:

* **PaystackAdapter** — Paystack (Nigeria / Africa-focused) via REST API.
* **StripeAdapter** — Stripe via the official Python SDK.
* **MPesaAdapter** — Safaricom M-Pesa (Daraja API), wrapping the existing
  ``core.services.payment.DarajaAPI`` class.
* **KCBAdapter** — KCB Bank Open Banking API with OAuth2 token management.
* **EscrowWalletAdapter** — Internal ledger operations (hold / release /
  refund) with no external API dependency.
"""

from __future__ import annotations

import logging
import time
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional

import requests
from django.conf import settings

from external_services.base import (
    HealthCheckResult,
    PaymentProvider,
    ProviderResponse,
    ValidationResult,
)
from external_services.exceptions import (
    AuthenticationError,
    ProviderResponseError,
    ProviderUnavailableError,
    RateLimitExceededError,
    TimeoutError as ESLTimeoutError,
)

logger = logging.getLogger(__name__)


# ======================================================================
# Paystack Adapter
# ======================================================================


class PaystackAdapter(PaymentProvider):
    """Paystack payment gateway adapter.

    Uses the Paystack REST API with Bearer-token authentication.
    Amounts are converted to **kobo** (smallest currency unit) before
    being sent to the API.

    Configuration (via Django settings):
        ``PAYSTACK_SECRET_KEY`` — API secret key.
        ``PAYSTACK_BASE_URL``   — Defaults to ``https://api.paystack.co``.
    """

    PROVIDER_NAME = "paystack"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(provider_name=self.PROVIDER_NAME, service_type="payment", **kwargs)
        self._api_key: str = getattr(settings, "PAYSTACK_SECRET_KEY", "")
        self._base_url: str = getattr(settings, "PAYSTACK_BASE_URL", "https://api.paystack.co")
        self._session: Optional[requests.Session] = None

    # -- lifecycle --------------------------------------------------------

    def connect(self) -> bool:
        try:
            self._session = requests.Session()
            self._session.headers.update({
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            })
            resp = self._session.get(f"{self._base_url}/transaction", timeout=10)
            if resp.status_code in (200, 401):
                if resp.status_code == 401:
                    raise AuthenticationError(provider_name=self.PROVIDER_NAME)
                self.is_connected = True
                return True
            raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME)
        except (AuthenticationError, ProviderUnavailableError):
            raise
        except Exception as exc:
            raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME) from exc

    def disconnect(self) -> bool:
        if self._session:
            self._session.close()
            self._session = None
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            resp = requests.get(f"{self._base_url}/transaction", headers={"Authorization": f"Bearer {self._api_key}"}, timeout=5)
            elapsed = (time.monotonic() - start) * 1000
            status = "healthy" if resp.status_code == 200 else "degraded"
            return HealthCheckResult(status=status, provider=self.PROVIDER_NAME, response_time_ms=elapsed)
        except Exception:
            return HealthCheckResult(status="unhealthy", provider=self.PROVIDER_NAME)

    def validate_configuration(self) -> ValidationResult:
        errors, warnings = [], []
        if not self._api_key:
            errors.append("PAYSTACK_SECRET_KEY is not configured")
        if not self._base_url.startswith("https"):
            warnings.append("PAYSTACK_BASE_URL should use HTTPS")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    # -- payment operations -----------------------------------------------

    def initialize_payment(self, amount: Decimal, currency: str, reference: str, **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {
                "email": kwargs.get("email", ""),
                "amount": int(amount * 100),  # convert to kobo
                "reference": reference,
                "currency": currency,
                "callback_url": kwargs.get("callback_url", getattr(settings, "PAYSTACK_CALLBACK_URL", "")),
                "metadata": kwargs.get("metadata", {}),
            }
            resp = self._session.post(f"{self._base_url}/transaction/initialize", json=payload, timeout=30)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code == 200 and data.get("status"):
                return ProviderResponse(success=True, data=data.get("data"), provider=self.PROVIDER_NAME, latency_ms=elapsed)
            if resp.status_code == 401:
                raise AuthenticationError(provider_name=self.PROVIDER_NAME)
            if resp.status_code == 429:
                raise RateLimitExceededError(provider_name=self.PROVIDER_NAME)
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, provider_status=resp.status_code, provider_message=data.get("message"))
        except (AuthenticationError, RateLimitExceededError, ProviderResponseError):
            raise
        except requests.Timeout:
            raise ESLTimeoutError(provider_name=self.PROVIDER_NAME, timeout_seconds=30)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def verify_payment(self, reference: str) -> ProviderResponse:
        start = time.monotonic()
        try:
            resp = self._session.get(f"{self._base_url}/transaction/verify/{reference}", timeout=15)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code == 200 and data.get("data", {}).get("status") == "success":
                return ProviderResponse(success=True, data=data.get("data"), provider=self.PROVIDER_NAME, latency_ms=elapsed)
            return ProviderResponse(success=False, data=data.get("data"), error="Payment not verified", provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except requests.Timeout:
            raise ESLTimeoutError(provider_name=self.PROVIDER_NAME, timeout_seconds=15)

    def transfer(self, recipient: str, amount: Decimal, **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {"source": "balance", "amount": int(amount * 100), "recipient": recipient, "reason": kwargs.get("reason", "Escrow release")}
            resp = self._session.post(f"{self._base_url}/transfer", json=payload, timeout=30)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code == 200 and data.get("status"):
                return ProviderResponse(success=True, data=data.get("data"), provider=self.PROVIDER_NAME, latency_ms=elapsed)
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, provider_status=resp.status_code, provider_message=data.get("message"))
        except requests.Timeout:
            raise ESLTimeoutError(provider_name=self.PROVIDER_NAME, timeout_seconds=30)

    def refund(self, reference: str, amount: Decimal, **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            payload = {"transaction": reference, "amount": int(amount * 100)}
            resp = self._session.post(f"{self._base_url}/refund", json=payload, timeout=30)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code == 200 and data.get("status"):
                return ProviderResponse(success=True, data=data.get("data"), provider=self.PROVIDER_NAME, latency_ms=elapsed)
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, provider_status=resp.status_code, provider_message=data.get("message"))
        except requests.Timeout:
            raise ESLTimeoutError(provider_name=self.PROVIDER_NAME, timeout_seconds=30)

    def get_balance(self) -> ProviderResponse:
        start = time.monotonic()
        try:
            resp = self._session.get(f"{self._base_url}/balance", timeout=10)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code == 200:
                return ProviderResponse(success=True, data=data.get("data"), provider=self.PROVIDER_NAME, latency_ms=elapsed)
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, provider_status=resp.status_code)
        except requests.Timeout:
            raise ESLTimeoutError(provider_name=self.PROVIDER_NAME, timeout_seconds=10)


# ======================================================================
# Stripe Adapter
# ======================================================================


class StripeAdapter(PaymentProvider):
    """Stripe payment adapter using the official ``stripe`` Python SDK.

    Configuration (via Django settings):
<<<<<<< HEAD
        ``STRIPE_API_KEY`` — Stripe secret key.
=======
        ``STRIPE_API_KEY`` or ``STRIPE_SECRET_KEY`` — Stripe secret key.
>>>>>>> ef5ef7fac4c0377f4742dd64e6f81c4164c05836
    """

    PROVIDER_NAME = "stripe"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(provider_name=self.PROVIDER_NAME, service_type="payment", **kwargs)
<<<<<<< HEAD
        self._api_key: str = getattr(settings, "STRIPE_API_KEY", "")
=======
        self._api_key: str = getattr(settings, "STRIPE_API_KEY", "") or getattr(settings, "STRIPE_SECRET_KEY", "")
>>>>>>> ef5ef7fac4c0377f4742dd64e6f81c4164c05836
        self._stripe_mod = None

    def _get_stripe(self):
        """Lazy-import stripe to avoid hard dependency at module level."""
        if self._stripe_mod is None:
            try:
                import stripe
                stripe.api_key = self._api_key
                self._stripe_mod = stripe
            except ImportError as exc:
                raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME, message="stripe package not installed") from exc
        return self._stripe_mod

    # -- lifecycle --------------------------------------------------------

    def connect(self) -> bool:
        try:
            stripe = self._get_stripe()
            stripe.Balance.retrieve()
            self.is_connected = True
            return True
        except Exception as exc:
            raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME) from exc

    def disconnect(self) -> bool:
        self._stripe_mod = None
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            stripe = self._get_stripe()
            stripe.Balance.retrieve()
            return HealthCheckResult(status="healthy", provider=self.PROVIDER_NAME, response_time_ms=(time.monotonic() - start) * 1000)
        except Exception:
            return HealthCheckResult(status="unhealthy", provider=self.PROVIDER_NAME)

    def validate_configuration(self) -> ValidationResult:
        errors = []
        if not self._api_key:
<<<<<<< HEAD
            errors.append("STRIPE_API_KEY is not configured")
=======
            errors.append("STRIPE_API_KEY/STRIPE_SECRET_KEY is not configured")
>>>>>>> ef5ef7fac4c0377f4742dd64e6f81c4164c05836
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    # -- payment operations -----------------------------------------------

    def initialize_payment(self, amount: Decimal, currency: str, reference: str, **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            stripe = self._get_stripe()
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),
                currency=currency.lower(),
                metadata={"reference": reference, **kwargs.get("metadata", {})},
                idempotency_key=kwargs.get("idempotency_key", reference),
            )
            return ProviderResponse(success=True, data={"id": intent.id, "client_secret": intent.client_secret, "status": intent.status}, provider=self.PROVIDER_NAME, latency_ms=(time.monotonic() - start) * 1000)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def verify_payment(self, reference: str) -> ProviderResponse:
        start = time.monotonic()
        try:
            stripe = self._get_stripe()
            intent = stripe.PaymentIntent.retrieve(reference)
            return ProviderResponse(success=True, data={"id": intent.id, "status": intent.status, "amount": intent.amount}, provider=self.PROVIDER_NAME, latency_ms=(time.monotonic() - start) * 1000)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def transfer(self, recipient: str, amount: Decimal, **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            stripe = self._get_stripe()
            xfer = stripe.Transfer.create(amount=int(amount * 100), currency=kwargs.get("currency", "usd"), destination=recipient, metadata=kwargs.get("metadata", {}))
            return ProviderResponse(success=True, data={"id": xfer.id, "amount": xfer.amount}, provider=self.PROVIDER_NAME, latency_ms=(time.monotonic() - start) * 1000)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def refund(self, reference: str, amount: Decimal, **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            stripe = self._get_stripe()
            rf = stripe.Refund.create(payment_intent=reference, amount=int(amount * 100), reason=kwargs.get("reason", "requested_by_customer"))
            return ProviderResponse(success=True, data={"id": rf.id, "status": rf.status, "amount": rf.amount}, provider=self.PROVIDER_NAME, latency_ms=(time.monotonic() - start) * 1000)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def get_balance(self) -> ProviderResponse:
        start = time.monotonic()
        try:
            stripe = self._get_stripe()
            bal = stripe.Balance.retrieve()
            return ProviderResponse(success=True, data={"available": [{"amount": b.amount, "currency": b.currency} for b in bal.available]}, provider=self.PROVIDER_NAME, latency_ms=(time.monotonic() - start) * 1000)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc


# ======================================================================
# M-Pesa (Daraja) Adapter
# ======================================================================


class MPesaAdapter(PaymentProvider):
    """M-Pesa adapter wrapping the existing ``core.services.payment.DarajaAPI``.

    Maps ESL operations to Daraja API calls:

    * ``initialize_payment`` → ``DarajaAPI.stk_push``
    * ``verify_payment``     → ``DarajaAPI.query_stk_status``
    * ``transfer``           → ``DarajaAPI.b2c_payment``
    * ``refund``             → ``DarajaAPI.reverse_transaction``
    """

    PROVIDER_NAME = "mpesa"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(provider_name=self.PROVIDER_NAME, service_type="payment", **kwargs)
        self._daraja = None

    def _get_daraja(self):
        if self._daraja is None:
            from core.services.payment import DarajaAPI
            self._daraja = DarajaAPI
        return self._daraja

    # -- lifecycle --------------------------------------------------------

    def connect(self) -> bool:
        try:
            token = self._get_daraja().get_access_token()
            if token:
                self.is_connected = True
                return True
            raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME, message="Could not obtain Daraja access token")
        except (ProviderUnavailableError,):
            raise
        except Exception as exc:
            raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME) from exc

    def disconnect(self) -> bool:
        self._daraja = None
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            token = self._get_daraja().get_access_token()
            elapsed = (time.monotonic() - start) * 1000
            status = "healthy" if token else "unhealthy"
            return HealthCheckResult(status=status, provider=self.PROVIDER_NAME, response_time_ms=elapsed)
        except Exception:
            return HealthCheckResult(status="unhealthy", provider=self.PROVIDER_NAME)

    def validate_configuration(self) -> ValidationResult:
        errors, warnings = [], []
        required = ["DARAJA_CONSUMER_KEY", "DARAJA_CONSUMER_SECRET", "DARAJA_SHORTCODE", "DARAJA_PASSKEY"]
        for key in required:
            if not getattr(settings, key, ""):
                errors.append(f"{key} is not configured")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    # -- payment operations -----------------------------------------------

    def initialize_payment(self, amount: Decimal, currency: str, reference: str, **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            daraja = self._get_daraja()
            result = daraja.stk_push(
                phone_number=kwargs.get("phone_number", kwargs.get("email", "")),
                amount=float(amount),
                account_reference=reference,
                transaction_desc=kwargs.get("description", f"Payment {reference}"),
                callback_url=kwargs.get("callback_url"),
            )
            elapsed = (time.monotonic() - start) * 1000
            if result.get("status") == "success":
                return ProviderResponse(success=True, data=result, provider=self.PROVIDER_NAME, latency_ms=elapsed)
            return ProviderResponse(success=False, error=result.get("message", "STK Push failed"), data=result, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def verify_payment(self, reference: str) -> ProviderResponse:
        start = time.monotonic()
        try:
            daraja = self._get_daraja()
            result = daraja.query_stk_status(checkout_request_id=reference)
            elapsed = (time.monotonic() - start) * 1000
            success = result.get("status") == "success" and str(result.get("result_code")) == "0"
            return ProviderResponse(success=success, data=result, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def transfer(self, recipient: str, amount: Decimal, **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            daraja = self._get_daraja()
            result = daraja.b2c_payment(phone_number=recipient, amount=float(amount), remarks=kwargs.get("reason", "Escrow payout"))
            elapsed = (time.monotonic() - start) * 1000
            if result.get("status") == "success":
                return ProviderResponse(success=True, data=result, provider=self.PROVIDER_NAME, latency_ms=elapsed)
            return ProviderResponse(success=False, error=result.get("message"), data=result, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def refund(self, reference: str, amount: Decimal, **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            daraja = self._get_daraja()
            result = daraja.reverse_transaction(
                transaction_id=reference, amount=float(amount),
                receiver_party=kwargs.get("receiver_party", getattr(settings, "DARAJA_SHORTCODE", "")),
                remarks=kwargs.get("reason", "Transaction reversal"),
            )
            elapsed = (time.monotonic() - start) * 1000
            if result.get("status") == "success":
                return ProviderResponse(success=True, data=result, provider=self.PROVIDER_NAME, latency_ms=elapsed)
            return ProviderResponse(success=False, error=result.get("message"), data=result, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def get_balance(self) -> ProviderResponse:
        start = time.monotonic()
        try:
            daraja = self._get_daraja()
            result = daraja.query_account_balance(party_a=getattr(settings, "DARAJA_SHORTCODE", ""))
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=result.get("status") == "success", data=result, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc


# ======================================================================
# KCB Bank Adapter
# ======================================================================


class KCBAdapter(PaymentProvider):
    """KCB Bank Open Banking adapter with OAuth2 token management.

    Wraps the existing ``core.services.kcb`` module and maps its
    functions to the ESL :class:`PaymentProvider` interface.

    Configuration (via Django settings):
        ``KCB_API_BASE_URL``, ``KCB_CLIENT_ID``, ``KCB_CLIENT_SECRET``,
        ``KCB_SANDBOX``, ``KCB_COMPANY_CODE``, ``KCB_PLATFORM_ACCOUNT``.
    """

    PROVIDER_NAME = "kcb"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(provider_name=self.PROVIDER_NAME, service_type="payment", **kwargs)
        self._kcb_module = None

    def _get_kcb(self):
        if self._kcb_module is None:
            from core.services import kcb as kcb_mod
            self._kcb_module = kcb_mod
        return self._kcb_module

    # -- lifecycle --------------------------------------------------------

    def connect(self) -> bool:
        try:
            kcb = self._get_kcb()
            if getattr(settings, "KCB_SANDBOX", True):
                self.is_connected = True
                return True
            token = kcb._get_access_token()
            if token:
                self.is_connected = True
                return True
            raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME, message="Could not obtain KCB access token")
        except (ProviderUnavailableError,):
            raise
        except Exception as exc:
            raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME) from exc

    def disconnect(self) -> bool:
        self._kcb_module = None
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            kcb = self._get_kcb()
            if getattr(settings, "KCB_SANDBOX", True):
                return HealthCheckResult(status="healthy", provider=self.PROVIDER_NAME, response_time_ms=(time.monotonic() - start) * 1000)
            token = kcb._get_access_token()
            return HealthCheckResult(status="healthy" if token else "unhealthy", provider=self.PROVIDER_NAME, response_time_ms=(time.monotonic() - start) * 1000)
        except Exception:
            return HealthCheckResult(status="unhealthy", provider=self.PROVIDER_NAME)

    def validate_configuration(self) -> ValidationResult:
        errors = []
        if not getattr(settings, "KCB_CLIENT_ID", ""):
            errors.append("KCB_CLIENT_ID is not configured")
        if not getattr(settings, "KCB_CLIENT_SECRET", ""):
            errors.append("KCB_CLIENT_SECRET is not configured")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    # -- payment operations -----------------------------------------------

    def initialize_payment(self, amount: Decimal, currency: str, reference: str, **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            kcb = self._get_kcb()
            result = kcb.initiate_fund_transfer(
                source_account=kwargs.get("source_account", getattr(settings, "KCB_PLATFORM_ACCOUNT", "")),
                destination_account=kwargs.get("destination_account", ""),
                amount=float(amount),
                reference=reference,
                narration=kwargs.get("narration", "Digiland Escrow Transfer"),
            )
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=result.get("status") == "success", data=result, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def verify_payment(self, reference: str) -> ProviderResponse:
        start = time.monotonic()
        try:
            kcb = self._get_kcb()
            result = kcb.check_transaction_status(reference)
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=result.get("status") == "success", data=result, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def transfer(self, recipient: str, amount: Decimal, **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            kcb = self._get_kcb()
            result = kcb.initiate_b2c_payout(
                destination_account=recipient, amount=float(amount),
                reference=kwargs.get("reference", f"KCB-XFER-{uuid.uuid4().hex[:8]}"),
                beneficiary_name=kwargs.get("beneficiary_name", ""),
                narration=kwargs.get("reason", "Escrow payout"),
            )
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=result.get("status") == "success", data=result, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def refund(self, reference: str, amount: Decimal, **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            kcb = self._get_kcb()
            result = kcb.initiate_fund_transfer(
                source_account=getattr(settings, "KCB_PLATFORM_ACCOUNT", ""),
                destination_account=kwargs.get("destination_account", ""),
                amount=float(amount),
                reference=f"REFUND-{reference}",
                narration=f"Refund for {reference}",
            )
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=result.get("status") == "success", data=result, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def get_balance(self) -> ProviderResponse:
        start = time.monotonic()
        try:
            kcb = self._get_kcb()
            result = kcb.check_account_balance(getattr(settings, "KCB_PLATFORM_ACCOUNT", ""))
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=result.get("status") == "success", data=result, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc


# ======================================================================
# Escrow Wallet Adapter (Internal Ledger)
# ======================================================================


class EscrowWalletAdapter(PaymentProvider):
    """Internal escrow wallet adapter — no external API calls.

    All operations are performed against the Django ORM (transaction
    status updates).  This adapter is the canonical way to hold, release,
    and refund funds within the platform's internal ledger.

    Configuration: none required (uses the Django database directly).
    """

    PROVIDER_NAME = "escrow_wallet"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(provider_name=self.PROVIDER_NAME, service_type="payment", **kwargs)

    # -- lifecycle --------------------------------------------------------

    def connect(self) -> bool:
        self.is_connected = True
        return True

    def disconnect(self) -> bool:
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(status="healthy", provider=self.PROVIDER_NAME, response_time_ms=0.0)

    def validate_configuration(self) -> ValidationResult:
        return ValidationResult(is_valid=True)

    # -- payment operations -----------------------------------------------

    def initialize_payment(self, amount: Decimal, currency: str, reference: str, **kwargs: Any) -> ProviderResponse:
        """Hold payment in escrow — marks transaction as Deposit_Paid."""
        start = time.monotonic()
        try:
            from core.services.payment import hold_payment
            from core.models import Transaction
            txn = Transaction.objects.get(escrow_reference=reference) if reference else None
            if txn:
                hold_payment(txn)
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=True, data={"status": "held", "reference": reference, "amount": str(amount)}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            return ProviderResponse(success=False, error=str(exc), provider=self.PROVIDER_NAME)

    def verify_payment(self, reference: str) -> ProviderResponse:
        start = time.monotonic()
        try:
            from core.models import Transaction
            txn = Transaction.objects.filter(escrow_reference=reference).first()
            elapsed = (time.monotonic() - start) * 1000
            if txn and txn.status in ("Deposit_Paid", "Completed"):
                return ProviderResponse(success=True, data={"status": txn.status, "reference": reference}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
            return ProviderResponse(success=False, error="Transaction not found or not paid", provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            return ProviderResponse(success=False, error=str(exc), provider=self.PROVIDER_NAME)

    def transfer(self, recipient: str, amount: Decimal, **kwargs: Any) -> ProviderResponse:
        """Release payment to seller — marks transaction as Completed."""
        start = time.monotonic()
        try:
            from core.services.payment import release_payment_to_seller
            from core.models import Transaction
            reference = kwargs.get("reference", "")
            txn = Transaction.objects.filter(escrow_reference=reference).first() if reference else None
            if txn:
                release_payment_to_seller(txn)
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=True, data={"status": "released", "recipient": recipient, "amount": str(amount)}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            return ProviderResponse(success=False, error=str(exc), provider=self.PROVIDER_NAME)

    def refund(self, reference: str, amount: Decimal, **kwargs: Any) -> ProviderResponse:
        """Refund payment to buyer — marks transaction as Refunded."""
        start = time.monotonic()
        try:
            from core.services.payment import refund_payment_to_buyer
            from core.models import Transaction
            txn = Transaction.objects.filter(escrow_reference=reference).first() if reference else None
            if txn:
                refund_payment_to_buyer(txn)
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=True, data={"status": "refunded", "reference": reference, "amount": str(amount)}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            return ProviderResponse(success=False, error=str(exc), provider=self.PROVIDER_NAME)

    def get_balance(self) -> ProviderResponse:
        start = time.monotonic()
        try:
            from core.models import Transaction
            held = Transaction.objects.filter(status="Deposit_Paid").count()
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=True, data={"held_transactions": held, "note": "Internal ledger; see Transaction model for balances"}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            return ProviderResponse(success=False, error=str(exc), provider=self.PROVIDER_NAME)
