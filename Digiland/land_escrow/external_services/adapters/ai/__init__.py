"""
AI / LLM provider adapters for the External Services Layer.

Implements the :class:`~external_services.base.AIProvider` interface
for two LLM backends:

* **OpenAIAdapter** — OpenAI GPT models via the REST API.
* **AnthropicAdapter** — Anthropic Claude models via the Messages API.
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any, Dict, Optional, Sequence

import requests
from django.conf import settings

from external_services.base import (
    AIProvider,
    CostRecord,
    HealthCheckResult,
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
# OpenAI Adapter
# ======================================================================

# Cost per 1K tokens (USD) — update as pricing changes
_OPENAI_PRICING = {
    "gpt-4o": {"input": Decimal("0.0025"), "output": Decimal("0.01")},
    "gpt-4o-mini": {"input": Decimal("0.00015"), "output": Decimal("0.0006")},
    "gpt-4-turbo": {"input": Decimal("0.01"), "output": Decimal("0.03")},
    "gpt-3.5-turbo": {"input": Decimal("0.0005"), "output": Decimal("0.0015")},
    "text-embedding-3-small": {"input": Decimal("0.00002")},
    "text-embedding-3-large": {"input": Decimal("0.00013")},
}


class OpenAIAdapter(AIProvider):
    """OpenAI API adapter with token tracking and cost calculation.

    Supports chat completions, embeddings, and token counting.
    Rate-limit information is extracted from response headers for
    observability.

    Configuration (via Django settings):
        ``OPENAI_API_KEY``    — API key.
        ``OPENAI_BASE_URL``   — Defaults to ``https://api.openai.com/v1``.
        ``OPENAI_DEFAULT_MODEL`` — Defaults to ``"gpt-4o-mini"``.
    """

    PROVIDER_NAME = "openai"
    _BASE_URL = "https://api.openai.com/v1"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(provider_name=self.PROVIDER_NAME, service_type="ai", **kwargs)
        self._api_key: str = getattr(settings, "OPENAI_API_KEY", "")
        self._base_url: str = getattr(settings, "OPENAI_BASE_URL", self._BASE_URL)
        self._default_model: str = getattr(settings, "OPENAI_DEFAULT_MODEL", "gpt-4o-mini")
        self._session: Optional[requests.Session] = None

    # -- lifecycle --------------------------------------------------------

    def connect(self) -> bool:
        try:
            self._session = requests.Session()
            self._session.headers.update({
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            })
            resp = self._session.get(f"{self._base_url}/models", timeout=10)
            if resp.status_code == 200:
                self.is_connected = True
                return True
            if resp.status_code == 401:
                raise AuthenticationError(provider_name=self.PROVIDER_NAME)
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
            resp = requests.get(f"{self._base_url}/models", headers={"Authorization": f"Bearer {self._api_key}"}, timeout=5)
            elapsed = (time.monotonic() - start) * 1000
            return HealthCheckResult(status="healthy" if resp.status_code == 200 else "degraded", provider=self.PROVIDER_NAME, response_time_ms=elapsed)
        except Exception:
            return HealthCheckResult(status="unhealthy", provider=self.PROVIDER_NAME)

    def validate_configuration(self) -> ValidationResult:
        errors = []
        if not self._api_key:
            errors.append("OPENAI_API_KEY is not configured")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    # -- helpers ----------------------------------------------------------

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> Optional[CostRecord]:
        pricing = _OPENAI_PRICING.get(model)
        if not pricing:
            return None
        input_cost = (Decimal(input_tokens) / 1000) * pricing.get("input", Decimal("0"))
        output_cost = (Decimal(output_tokens) / 1000) * pricing.get("output", Decimal("0"))
        return CostRecord(
            provider=self.PROVIDER_NAME,
            service_type="ai",
            operation="chat_completion",
            units=input_tokens + output_tokens,
            cost=input_cost + output_cost,
        )

    # -- AI operations ----------------------------------------------------

    def chat_completion(self, messages: Sequence[Dict[str, str]], **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            model = kwargs.get("model", self._default_model)
            payload: Dict[str, Any] = {
                "model": model,
                "messages": list(messages),
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 1024),
            }
            resp = self._session.post(f"{self._base_url}/chat/completions", json=payload, timeout=60)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()

            if resp.status_code == 200:
                usage = data.get("usage", {})
                cost_record = self._calculate_cost(model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
                content = data["choices"][0]["message"]["content"] if data.get("choices") else ""
                metadata = {
                    "model": model,
                    "usage": usage,
                    "rate_limit_remaining": resp.headers.get("x-ratelimit-remaining"),
                    "rate_limit_reset": resp.headers.get("x-ratelimit-reset"),
                }
                if cost_record:
                    metadata["cost"] = cost_record.to_dict()
                return ProviderResponse(success=True, data=content, metadata=metadata, provider=self.PROVIDER_NAME, latency_ms=elapsed)

            if resp.status_code == 401:
                raise AuthenticationError(provider_name=self.PROVIDER_NAME)
            if resp.status_code == 429:
                retry_after = resp.headers.get("retry-after")
                raise RateLimitExceededError(provider_name=self.PROVIDER_NAME, retry_after=float(retry_after) if retry_after else None)
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, provider_status=resp.status_code, provider_message=data.get("error", {}).get("message", ""))
        except (AuthenticationError, RateLimitExceededError, ProviderResponseError):
            raise
        except requests.Timeout:
            raise ESLTimeoutError(provider_name=self.PROVIDER_NAME, timeout_seconds=60)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def generate_embedding(self, text: str, **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            model = kwargs.get("model", "text-embedding-3-small")
            payload = {"model": model, "input": text}
            if kwargs.get("dimensions"):
                payload["dimensions"] = kwargs["dimensions"]
            resp = self._session.post(f"{self._base_url}/embeddings", json=payload, timeout=30)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code == 200:
                embedding = data["data"][0]["embedding"] if data.get("data") else []
                usage = data.get("usage", {})
                return ProviderResponse(success=True, data=embedding, metadata={"model": model, "usage": usage}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, provider_status=resp.status_code)
        except requests.Timeout:
            raise ESLTimeoutError(provider_name=self.PROVIDER_NAME, timeout_seconds=30)
        except ProviderResponseError:
            raise
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def count_tokens(self, text: str) -> ProviderResponse:
        """Estimate token count using a heuristic approximation.

        For exact counts, the ``tiktoken`` library should be used, but
        we keep it optional to avoid a hard dependency.
        """
        start = time.monotonic()
        try:
            try:
                import tiktoken
                enc = tiktoken.encoding_for_model(self._default_model)
                token_count = len(enc.encode(text))
            except ImportError:
                # Rough approximation: ~4 chars per token for English text
                token_count = max(1, len(text) // 4)
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=True, data={"token_count": token_count, "method": "tiktoken" if "tiktoken" in dir() else "approximation"}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            return ProviderResponse(success=False, error=str(exc), provider=self.PROVIDER_NAME)

    def get_available_models(self) -> ProviderResponse:
        start = time.monotonic()
        try:
            resp = self._session.get(f"{self._base_url}/models", timeout=10)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if resp.status_code == 200:
                models = [m["id"] for m in data.get("data", []) if "gpt" in m.get("id", "") or "embedding" in m.get("id", "")]
                return ProviderResponse(success=True, data=models, provider=self.PROVIDER_NAME, latency_ms=elapsed)
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, provider_status=resp.status_code)
        except ProviderResponseError:
            raise
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc


# ======================================================================
# Anthropic Adapter
# ======================================================================

_ANTHROPIC_PRICING = {
    "claude-3-5-sonnet-20241022": {"input": Decimal("0.003"), "output": Decimal("0.015")},
    "claude-3-haiku-20240307": {"input": Decimal("0.00025"), "output": Decimal("0.00125")},
}


class AnthropicAdapter(AIProvider):
    """Anthropic Claude adapter via the Messages API.

    Configuration (via Django settings):
        ``ANTHROPIC_API_KEY``       — API key.
        ``ANTHROPIC_DEFAULT_MODEL`` — Defaults to ``"claude-3-5-sonnet-20241022"``.
    """

    PROVIDER_NAME = "anthropic"
    _BASE_URL = "https://api.anthropic.com/v1"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(provider_name=self.PROVIDER_NAME, service_type="ai", **kwargs)
        self._api_key: str = getattr(settings, "ANTHROPIC_API_KEY", "")
        self._default_model: str = getattr(settings, "ANTHROPIC_DEFAULT_MODEL", "claude-3-5-sonnet-20241022")
        self._session: Optional[requests.Session] = None

    # -- lifecycle --------------------------------------------------------

    def connect(self) -> bool:
        try:
            self._session = requests.Session()
            self._session.headers.update({
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            })
            # There is no lightweight "list models" endpoint; do a minimal request
            self.is_connected = True
            return True
        except Exception as exc:
            raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME) from exc

    def disconnect(self) -> bool:
        if self._session:
            self._session.close()
            self._session = None
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        # Anthropic has no health-check endpoint; assume healthy if connected
        return HealthCheckResult(
            status="healthy" if self.is_connected else "unhealthy",
            provider=self.PROVIDER_NAME,
        )

    def validate_configuration(self) -> ValidationResult:
        errors = []
        if not self._api_key:
            errors.append("ANTHROPIC_API_KEY is not configured")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    # -- AI operations ----------------------------------------------------

    def chat_completion(self, messages: Sequence[Dict[str, str]], **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            model = kwargs.get("model", self._default_model)
            system_msg = kwargs.get("system", "")
            # Separate system message from conversation
            api_messages = [m for m in messages if m.get("role") != "system"]
            payload: Dict[str, Any] = {
                "model": model,
                "messages": list(api_messages),
                "max_tokens": kwargs.get("max_tokens", 1024),
            }
            if system_msg:
                payload["system"] = system_msg
            if kwargs.get("temperature") is not None:
                payload["temperature"] = kwargs["temperature"]

            resp = self._session.post(f"{self._BASE_URL}/messages", json=payload, timeout=60)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()

            if resp.status_code == 200:
                content = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
                usage = data.get("usage", {})
                pricing = _ANTHROPIC_PRICING.get(model, {})
                cost = None
                if pricing:
                    input_cost = (Decimal(usage.get("input_tokens", 0)) / 1000) * pricing.get("input", Decimal("0"))
                    output_cost = (Decimal(usage.get("output_tokens", 0)) / 1000) * pricing.get("output", Decimal("0"))
                    cost = CostRecord(provider=self.PROVIDER_NAME, service_type="ai", operation="chat_completion", units=usage.get("input_tokens", 0) + usage.get("output_tokens", 0), cost=input_cost + output_cost)
                metadata = {"model": model, "usage": usage, "stop_reason": data.get("stop_reason")}
                if cost:
                    metadata["cost"] = cost.to_dict()
                return ProviderResponse(success=True, data=content, metadata=metadata, provider=self.PROVIDER_NAME, latency_ms=elapsed)

            if resp.status_code == 401:
                raise AuthenticationError(provider_name=self.PROVIDER_NAME)
            if resp.status_code == 429:
                raise RateLimitExceededError(provider_name=self.PROVIDER_NAME)
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, provider_status=resp.status_code, provider_message=data.get("error", {}).get("message", ""))
        except (AuthenticationError, RateLimitExceededError, ProviderResponseError):
            raise
        except requests.Timeout:
            raise ESLTimeoutError(provider_name=self.PROVIDER_NAME, timeout_seconds=60)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def generate_embedding(self, text: str, **kwargs: Any) -> ProviderResponse:
        """Anthropic does not currently offer an embeddings API.

        Returns an error response indicating the operation is unsupported.
        """
        return ProviderResponse(
            success=False,
            error="Anthropic does not provide an embeddings API. Use OpenAI or another provider.",
            provider=self.PROVIDER_NAME,
        )

    def count_tokens(self, text: str) -> ProviderResponse:
        start = time.monotonic()
        try:
            # Use Anthropic's token counting endpoint if available,
            # otherwise fall back to approximation (~3.5 chars/token for Claude)
            try:
                payload = {"model": kwargs.get("model", self._default_model), "messages": [{"role": "user", "content": text}]}
                resp = self._session.post(f"{self._BASE_URL}/messages/count_tokens", json=payload, timeout=15)
                if resp.status_code == 200:
                    token_count = resp.json().get("input_tokens", 0)
                    elapsed = (time.monotonic() - start) * 1000
                    return ProviderResponse(success=True, data={"token_count": token_count, "method": "api"}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
            except Exception:
                pass
            # Fallback approximation
            token_count = max(1, len(text) // 3)
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=True, data={"token_count": token_count, "method": "approximation"}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            return ProviderResponse(success=False, error=str(exc), provider=self.PROVIDER_NAME)

    def get_available_models(self) -> ProviderResponse:
        """Return a static list of known Anthropic models.

        Anthropic does not have a model-listing API endpoint.
        """
        models = ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-haiku-20240307"]
        return ProviderResponse(success=True, data=models, provider=self.PROVIDER_NAME)
