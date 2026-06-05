"""
Custom exception hierarchy for the External Services Layer (ESL).

Every exception raised by ESL code descends from :class:`ExternalServiceError`,
which carries structured metadata (service type, provider name, request ID,
retryability, HTTP status code) and exposes a :meth:`to_dict` method for
structured logging and API error responses.

Exception Map
-------------

::

    ExternalServiceError                          base – always catch this
    ├── ProviderUnavailableError                  provider is down / unreachable
    ├── CircuitBreakerOpenError                   circuit breaker tripped
    ├── RateLimitExceededError                    rate limit hit (retry_after)
    ├── AuthenticationError                       auth failed with provider
    ├── ValidationError                           request/response validation
    ├── TimeoutError                              request timed out
    ├── WebhookVerificationError                  webhook signature invalid
    ├── ProviderResponseError                     unexpected provider response
    ├── ConfigurationError                        provider misconfigured
    └── DeadLetterError                           message sent to DLQ
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ExternalServiceError(Exception):
    """Base exception for all External Services Layer errors.

    Every subclass carries enough context to produce a structured log entry
    and an API-friendly JSON error body without additional lookups.

    Args:
        message: Human-readable error description.
        service_type: Category of the external service (e.g. ``"payment"``).
        provider_name: Specific provider identifier (e.g. ``"paystack"``).
        request_id: Correlation / request ID for tracing.
        is_retryable: Whether the caller may safely retry the operation.
        status_code: Suggested HTTP status code for API responses.
        cause: The original exception, if this is a wrapper.
    """

    def __init__(
        self,
        message: str = "An external service error occurred",
        service_type: Optional[str] = None,
        provider_name: Optional[str] = None,
        request_id: Optional[str] = None,
        is_retryable: bool = False,
        status_code: int = 502,
        cause: Optional[Exception] = None,
    ) -> None:
        self.message = message
        self.service_type = service_type
        self.provider_name = provider_name
        self.request_id = request_id or str(uuid.uuid4())
        self.is_retryable = is_retryable
        self.status_code = status_code
        self.cause = cause
        self.timestamp = datetime.now(timezone.utc).isoformat()

        super().__init__(self.message)

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Return a dictionary suitable for structured logging and API responses.

        The dictionary always contains at least ``error_type``, ``message``,
        ``request_id``, ``is_retryable``, ``status_code``, and ``timestamp``.
        Optional fields are included only when they are not ``None``.
        """
        result: Dict[str, Any] = {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "request_id": self.request_id,
            "is_retryable": self.is_retryable,
            "status_code": self.status_code,
            "timestamp": self.timestamp,
        }

        if self.service_type is not None:
            result["service_type"] = self.service_type
        if self.provider_name is not None:
            result["provider_name"] = self.provider_name
        if self.cause is not None:
            result["cause"] = str(self.cause)

        return result

    # ------------------------------------------------------------------
    # Django logging integration
    # ------------------------------------------------------------------

    def log_context(self) -> Dict[str, Any]:
        """Return a flat dict suitable for ``logger.extra`` in structured logging.

        Example::

            import logging
            logger = logging.getLogger("external_services")
            try:
                provider.charge(...)
            except ExternalServiceError as exc:
                logger.error(exc.message, extra=exc.log_context())
        """
        ctx: Dict[str, Any] = {
            "esl_error_type": self.__class__.__name__,
            "esl_request_id": self.request_id,
            "esl_retryable": self.is_retryable,
            "esl_status_code": self.status_code,
        }
        if self.service_type:
            ctx["esl_service_type"] = self.service_type
        if self.provider_name:
            ctx["esl_provider_name"] = self.provider_name
        return ctx

    def __str__(self) -> str:
        parts = [f"[{self.__class__.__name__}]", self.message]
        if self.service_type:
            parts.append(f"service={self.service_type}")
        if self.provider_name:
            parts.append(f"provider={self.provider_name}")
        parts.append(f"request_id={self.request_id}")
        return " ".join(parts)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"service_type={self.service_type!r}, "
            f"provider_name={self.provider_name!r}, "
            f"request_id={self.request_id!r}, "
            f"is_retryable={self.is_retryable!r}, "
            f"status_code={self.status_code!r})"
        )


# ======================================================================
# Concrete exception classes
# ======================================================================


class ProviderUnavailableError(ExternalServiceError):
    """The external provider is down or unreachable.

    Typical causes include DNS failures, TCP timeouts, or the provider
    returning a 5xx status.  This error is **retryable** by default.

    Args:
        provider_name: The unreachable provider identifier.
        service_type: The service category.
        message: Optional custom message; defaults to a template.
    """

    def __init__(
        self,
        provider_name: str,
        service_type: Optional[str] = None,
        message: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        message = message or f"Provider '{provider_name}' is unavailable or unreachable"
        super().__init__(
            message=message,
            service_type=service_type,
            provider_name=provider_name,
            is_retryable=True,
            status_code=503,
            **kwargs,
        )


class CircuitBreakerOpenError(ExternalServiceError):
    """The circuit breaker for this provider is in the OPEN state.

    Calls are short-circuited without reaching the provider.  The caller
    should back off until the circuit transitions to HALF_OPEN.

    Args:
        provider_name: Provider whose circuit is open.
        service_type: The service category.
        half_open_after_ms: Estimated time (ms) until the circuit may transition.
    """

    def __init__(
        self,
        provider_name: str,
        service_type: Optional[str] = None,
        half_open_after_ms: Optional[int] = None,
        message: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        message = message or (
            f"Circuit breaker is OPEN for provider '{provider_name}'"
            + (f" — half-open after {half_open_after_ms}ms" if half_open_after_ms else "")
        )
        super().__init__(
            message=message,
            service_type=service_type,
            provider_name=provider_name,
            is_retryable=True,
            status_code=503,
            **kwargs,
        )
        self.half_open_after_ms = half_open_after_ms

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        if self.half_open_after_ms is not None:
            d["half_open_after_ms"] = self.half_open_after_ms
        return d


class RateLimitExceededError(ExternalServiceError):
    """The provider's rate limit has been exceeded.

    The caller should wait at least ``retry_after`` seconds before
    retrying.

    Args:
        provider_name: Provider that rate-limited the request.
        retry_after: Minimum seconds the caller should wait before retrying.
        service_type: The service category.
    """

    def __init__(
        self,
        provider_name: str,
        retry_after: Optional[float] = None,
        service_type: Optional[str] = None,
        message: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        message = message or (
            f"Rate limit exceeded for provider '{provider_name}'"
            + (f" — retry after {retry_after}s" if retry_after else "")
        )
        super().__init__(
            message=message,
            service_type=service_type,
            provider_name=provider_name,
            is_retryable=True,
            status_code=429,
            **kwargs,
        )
        self.retry_after = retry_after

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        if self.retry_after is not None:
            d["retry_after"] = self.retry_after
        return d


class AuthenticationError(ExternalServiceError):
    """Authentication with the external provider failed.

    This usually indicates an expired or invalid API key / token and
    is **not retryable** without manual intervention.

    Args:
        provider_name: Provider that rejected the credentials.
        service_type: The service category.
    """

    def __init__(
        self,
        provider_name: str,
        service_type: Optional[str] = None,
        message: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        message = message or f"Authentication failed for provider '{provider_name}'"
        super().__init__(
            message=message,
            service_type=service_type,
            provider_name=provider_name,
            is_retryable=False,
            status_code=401,
            **kwargs,
        )


class ValidationError(ExternalServiceError):
    """Request or response validation failed.

    Raised when the data sent to a provider does not conform to the
    expected schema, or when the provider's response cannot be parsed.

    Args:
        errors: A list or dict of field-level validation errors.
        provider_name: The provider involved.
        service_type: The service category.
    """

    def __init__(
        self,
        message: str = "Validation failed",
        errors: Optional[Any] = None,
        provider_name: Optional[str] = None,
        service_type: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            message=message,
            service_type=service_type,
            provider_name=provider_name,
            is_retryable=False,
            status_code=400,
            **kwargs,
        )
        self.errors = errors

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        if self.errors is not None:
            d["errors"] = self.errors
        return d


class TimeoutError(ExternalServiceError):
    """A request to an external provider timed out.

    This is retryable by default since transient network issues may resolve.

    Args:
        provider_name: The provider that did not respond in time.
        timeout_seconds: The configured timeout threshold.
        service_type: The service category.
    """

    def __init__(
        self,
        provider_name: str,
        timeout_seconds: Optional[float] = None,
        service_type: Optional[str] = None,
        message: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        message = message or (
            f"Request to provider '{provider_name}' timed out"
            + (f" after {timeout_seconds}s" if timeout_seconds else "")
        )
        super().__init__(
            message=message,
            service_type=service_type,
            provider_name=provider_name,
            is_retryable=True,
            status_code=504,
            **kwargs,
        )
        self.timeout_seconds = timeout_seconds

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        if self.timeout_seconds is not None:
            d["timeout_seconds"] = self.timeout_seconds
        return d


class WebhookVerificationError(ExternalServiceError):
    """A webhook signature could not be verified.

    This indicates a potential security issue — either the signing secret
    is misconfigured or the payload was tampered with in transit.

    Args:
        provider_name: The provider that sent the webhook.
        signature: The (invalid) signature value received.
        service_type: The service category.
    """

    def __init__(
        self,
        provider_name: str,
        signature: Optional[str] = None,
        service_type: Optional[str] = None,
        message: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        message = message or f"Webhook signature verification failed for provider '{provider_name}'"
        super().__init__(
            message=message,
            service_type=service_type,
            provider_name=provider_name,
            is_retryable=False,
            status_code=400,
            **kwargs,
        )
        self.signature = signature

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        if self.signature is not None:
            d["signature"] = self.signature
        return d


class ProviderResponseError(ExternalServiceError):
    """The provider returned an unexpected or erroneous response.

    This is the catch-all for non-2xx responses that do not map to a
    more specific exception (e.g. authentication or rate-limit errors).

    Args:
        provider_name: The provider that returned the error.
        provider_status: HTTP status code returned by the provider.
        provider_message: Error message from the provider response body.
        service_type: The service category.
    """

    def __init__(
        self,
        provider_name: str,
        provider_status: Optional[int] = None,
        provider_message: Optional[str] = None,
        service_type: Optional[str] = None,
        message: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        message = message or (
            f"Provider '{provider_name}' returned an error"
            + (f" (HTTP {provider_status})" if provider_status else "")
        )
        # 5xx from the provider → retryable; 4xx → not retryable
        is_retryable = provider_status is not None and provider_status >= 500
        super().__init__(
            message=message,
            service_type=service_type,
            provider_name=provider_name,
            is_retryable=is_retryable,
            status_code=provider_status or 502,
            **kwargs,
        )
        self.provider_status = provider_status
        self.provider_message = provider_message

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        if self.provider_status is not None:
            d["provider_status"] = self.provider_status
        if self.provider_message is not None:
            d["provider_message"] = self.provider_message
        return d


class ConfigurationError(ExternalServiceError):
    """The provider is misconfigured and cannot operate.

    Typical causes: missing API key, invalid base URL, or an
    unrecognised configuration value.  Never retryable.

    Args:
        provider_name: The misconfigured provider.
        config_key: The specific configuration key that is wrong or missing.
        service_type: The service category.
    """

    def __init__(
        self,
        provider_name: str,
        config_key: Optional[str] = None,
        service_type: Optional[str] = None,
        message: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        message = message or (
            f"Provider '{provider_name}' is misconfigured"
            + (f" — issue with '{config_key}'" if config_key else "")
        )
        super().__init__(
            message=message,
            service_type=service_type,
            provider_name=provider_name,
            is_retryable=False,
            status_code=500,
            **kwargs,
        )
        self.config_key = config_key

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        if self.config_key is not None:
            d["config_key"] = self.config_key
        return d


class DeadLetterError(ExternalServiceError):
    """A message has been moved to the dead-letter queue (DLQ).

    This is raised after all retry attempts have been exhausted or the
    message has been explicitly rejected.

    Args:
        original_error: The error that caused the message to be dead-lettered.
        dead_letter_reason: Human-readable explanation.
        provider_name: The provider involved.
        service_type: The service category.
    """

    def __init__(
        self,
        original_error: Optional[str] = None,
        dead_letter_reason: Optional[str] = None,
        provider_name: Optional[str] = None,
        service_type: Optional[str] = None,
        message: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        message = message or (
            "Message sent to dead-letter queue"
            + (f": {dead_letter_reason}" if dead_letter_reason else "")
        )
        super().__init__(
            message=message,
            service_type=service_type,
            provider_name=provider_name,
            is_retryable=False,
            status_code=500,
            **kwargs,
        )
        self.original_error = original_error
        self.dead_letter_reason = dead_letter_reason

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        if self.original_error is not None:
            d["original_error"] = self.original_error
        if self.dead_letter_reason is not None:
            d["dead_letter_reason"] = self.dead_letter_reason
        return d
