"""
Base provider interfaces and data classes for the External Services Layer (ESL).

This module defines:

* **Data classes** — :class:`HealthCheckResult`, :class:`ValidationResult`,
  :class:`ProviderResponse`, :class:`CostRecord` — structured value objects
  returned by provider methods.
* **Abstract base classes** — :class:`ExternalProvider` and a suite of
  service-type–specific interfaces (``PaymentProvider``, ``EmailProvider``,
  etc.) that every concrete integration must implement.

Design principles
-----------------

1. **Interface segregation** — each service type has its own ABC so a
   provider only needs to implement the methods it actually supports.
2. **Built-in resilience** — every provider is expected to integrate with
   the ESL circuit breaker, retry, timeout, rate-limiting, and observability
   infrastructure.  Concrete implementations inherit this behaviour from
   :class:`ExternalProvider`.
3. **Explicit contracts** — abstract methods are fully typed and documented
   so that linters and IDEs catch signature mismatches early.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence


# ======================================================================
# Data Classes
# ======================================================================


@dataclass(frozen=True)
class HealthCheckResult:
    """Structured result returned by :meth:`ExternalProvider.health_check`.

    Attributes:
        status: One of ``"healthy"``, ``"degraded"``, or ``"unhealthy"``.
        provider: Name of the provider that was checked.
        response_time_ms: Round-trip time of the health probe in milliseconds.
        details: Optional dict with extra diagnostic information.
        checked_at: UTC timestamp when the check was performed.
    """

    status: str  # "healthy" | "degraded" | "unhealthy"
    provider: str
    response_time_ms: float = 0.0
    details: Optional[Dict[str, Any]] = None
    checked_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.checked_at is None:
            # frozen=True requires object.__setattr__
            object.__setattr__(self, "checked_at", datetime.now(timezone.utc))

    @property
    def is_healthy(self) -> bool:
        """Convenience boolean — ``True`` when ``status == "healthy"``."""
        return self.status == "healthy"


@dataclass(frozen=True)
class ValidationResult:
    """Structured result returned by :meth:`ExternalProvider.validate_configuration`.

    Attributes:
        is_valid: ``True`` when the provider's configuration is complete and correct.
        errors: List of error strings (blocking issues).
        warnings: List of warning strings (non-blocking issues).
    """

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.is_valid


@dataclass(frozen=True)
class ProviderResponse:
    """Standardised wrapper for every external service call result.

    All provider methods return a :class:`ProviderResponse` so that callers
    have a uniform interface regardless of the underlying provider.

    Attributes:
        success: Whether the operation completed without errors.
        data: The parsed response payload on success.
        error: Error message on failure.
        provider: Name of the provider that handled the call.
        request_id: Correlation ID for tracing.
        latency_ms: End-to-end latency in milliseconds.
        metadata: Optional dict for provider-specific extras.
    """

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    provider: Optional[str] = None
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    latency_ms: float = 0.0
    metadata: Optional[Dict[str, Any]] = None

    def __bool__(self) -> bool:
        return self.success


@dataclass(frozen=True)
class CostRecord:
    """Tracks cost incurred by a single provider operation.

    Attributes:
        provider: Provider identifier (e.g. ``"openai"``).
        service_type: Category (e.g. ``"ai"``).
        operation: Specific API call (e.g. ``"chat_completion"``).
        units: Number of billable units (e.g. tokens, messages).
        cost: Monetary cost.
        currency: ISO 4217 currency code.
        timestamp: UTC timestamp of the billable event.
    """

    provider: str
    service_type: str
    operation: str
    units: int
    cost: Decimal
    currency: str = "USD"
    timestamp: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.timestamp is None:
            object.__setattr__(self, "timestamp", datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict suitable for JSON logging or DB storage."""
        return {
            "provider": self.provider,
            "service_type": self.service_type,
            "operation": self.operation,
            "units": self.units,
            "cost": str(self.cost),
            "currency": self.currency,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


# ======================================================================
# Base Provider Interface
# ======================================================================


class ExternalProvider(ABC):
    """Abstract base class that **every** ESL integration must extend.

    Concrete subclasses must implement the four lifecycle methods:
    :meth:`connect`, :meth:`disconnect`, :meth:`health_check`, and
    :meth:`validate_configuration`.

    Built-in features that concrete providers inherit (via mixins or
    decorators applied at the registry level):

    * **Circuit breaker** — wraps every outbound call; trips on repeated
      failures.
    * **Retry logic** — configurable back-off strategies.
    * **Timeout handling** — per-call deadlines.
    * **Observability** — OpenTelemetry tracing, Prometheus metrics,
      structured logging.
    * **Rate limiting** — token-bucket or sliding-window enforcement.
    * **Cost tracking** — per-operation cost recording via :class:`CostRecord`.

    Attributes:
        provider_name: Human-readable identifier for this provider instance.
        service_type: Category of service (set by the registry).
        is_connected: Whether :meth:`connect` has been called successfully.
    """

    def __init__(self, provider_name: str = "", service_type: str = "", **kwargs: Any) -> None:
        self.provider_name = provider_name or self.__class__.__name__
        self.service_type = service_type
        self.is_connected: bool = False

    # ------------------------------------------------------------------
    # Lifecycle methods (required)
    # ------------------------------------------------------------------

    @abstractmethod
    def connect(self) -> bool:
        """Initialise the connection to the external provider.

        This is called lazily on first use or eagerly during application
        start-up.  It should validate credentials, warm caches, and set
        ``self.is_connected = True`` on success.

        Returns:
            ``True`` if the connection was established successfully.

        Raises:
            ProviderUnavailableError: If the provider cannot be reached.
            AuthenticationError: If credentials are invalid.
        """

    @abstractmethod
    def disconnect(self) -> bool:
        """Gracefully tear down the connection to the external provider.

        Should release sockets, HTTP sessions, and other resources.
        Sets ``self.is_connected = False`` on success.

        Returns:
            ``True`` if the disconnect was clean.
        """

    @abstractmethod
    def health_check(self) -> HealthCheckResult:
        """Perform a lightweight health probe against the provider.

        Should **not** perform expensive operations — a simple ping or
        read-only API call is sufficient.

        Returns:
            A :class:`HealthCheckResult` indicating the current state.
        """

    @abstractmethod
    def validate_configuration(self) -> ValidationResult:
        """Verify that the provider's configuration is complete and correct.

        Called during start-up and before :meth:`connect`.  Should check
        for required API keys, valid URLs, etc.

        Returns:
            A :class:`ValidationResult` with any errors or warnings.
        """

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} provider={self.provider_name!r} connected={self.is_connected}>"


# ======================================================================
# Service-Type-Specific Provider Interfaces
# ======================================================================


class PaymentProvider(ExternalProvider):
    """Interface for payment and escrow service providers.

    Implementations: Paystack, Stripe, M-Pesa/Daraja, KCB Bank.
    """

    @abstractmethod
    def initialize_payment(
        self,
        amount: Decimal,
        currency: str,
        reference: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Initiate a payment transaction.

        Args:
            amount: The payment amount in the smallest currency unit or
                major unit depending on the provider convention.
            currency: ISO 4217 currency code (e.g. ``"KES"``, ``"USD"``).
            reference: Unique reference for idempotency.
            **kwargs: Provider-specific options (e.g. ``email``, ``metadata``).

        Returns:
            :class:`ProviderResponse` with checkout URL or redirect data.
        """

    @abstractmethod
    def verify_payment(self, reference: str) -> ProviderResponse:
        """Verify that a payment was completed successfully.

        Args:
            reference: The reference returned by :meth:`initialize_payment`.

        Returns:
            :class:`ProviderResponse` with verification details.
        """

    @abstractmethod
    def transfer(
        self,
        recipient: str,
        amount: Decimal,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Transfer funds to a recipient account.

        Args:
            recipient: Recipient identifier (account number, phone, etc.).
            amount: Transfer amount.
            **kwargs: Provider-specific options.

        Returns:
            :class:`ProviderResponse` with transfer receipt.
        """

    @abstractmethod
    def refund(
        self,
        reference: str,
        amount: Decimal,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Issue a full or partial refund.

        Args:
            reference: Original payment reference.
            amount: Refund amount (partial if less than original).
            **kwargs: Provider-specific options.

        Returns:
            :class:`ProviderResponse` with refund confirmation.
        """

    @abstractmethod
    def get_balance(self) -> ProviderResponse:
        """Retrieve the current account balance.

        Returns:
            :class:`ProviderResponse` with balance information.
        """


class EmailProvider(ExternalProvider):
    """Interface for email delivery providers.

    Implementations: SMTP, SendGrid, AWS SES.
    """

    @abstractmethod
    def send(
        self,
        to: str,
        subject: str,
        body: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Send a single email.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            body: Plain-text or HTML body.
            **kwargs: ``cc``, ``bcc``, ``reply_to``, ``from_email``, etc.

        Returns:
            :class:`ProviderResponse` with message ID.
        """

    @abstractmethod
    def send_template(
        self,
        to: str,
        template_id: str,
        context: Dict[str, Any],
        **kwargs: Any,
    ) -> ProviderResponse:
        """Send an email using a provider-side template.

        Args:
            to: Recipient email address.
            template_id: Template identifier registered with the provider.
            context: Variables to render inside the template.
            **kwargs: Additional delivery options.

        Returns:
            :class:`ProviderResponse` with message ID.
        """

    @abstractmethod
    def send_bulk(
        self,
        recipients: Sequence[str],
        subject: str,
        body: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Send the same email to multiple recipients.

        Args:
            recipients: List of email addresses.
            subject: Email subject line.
            body: Email body.
            **kwargs: Additional delivery options.

        Returns:
            :class:`ProviderResponse` with batch ID or count.
        """


class SmsProvider(ExternalProvider):
    """Interface for SMS delivery providers.

    Implementations: Twilio, Africa's Talking.
    """

    @abstractmethod
    def send(
        self,
        to: str,
        message: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Send a single SMS message.

        Args:
            to: Recipient phone number (E.164 format preferred).
            message: SMS body text.
            **kwargs: ``sender_id``, ``schedule``, etc.

        Returns:
            :class:`ProviderResponse` with message ID.
        """

    @abstractmethod
    def send_bulk(
        self,
        recipients: Sequence[str],
        message: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Send the same SMS to multiple recipients.

        Args:
            recipients: List of phone numbers.
            message: SMS body text.
            **kwargs: Additional delivery options.

        Returns:
            :class:`ProviderResponse` with batch ID or count.
        """

    @abstractmethod
    def get_delivery_status(self, message_id: str) -> ProviderResponse:
        """Check the delivery status of a previously sent message.

        Args:
            message_id: The ID returned by :meth:`send`.

        Returns:
            :class:`ProviderResponse` with delivery status details.
        """


class PushNotificationProvider(ExternalProvider):
    """Interface for push notification providers.

    Implementations: Firebase Cloud Messaging, OneSignal.
    """

    @abstractmethod
    def send(
        self,
        user_id: str,
        title: str,
        body: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Send a push notification to a single user.

        Args:
            user_id: Internal user identifier (mapped to device tokens internally).
            title: Notification title.
            body: Notification body text.
            **kwargs: ``icon``, ``click_action``, ``data``, etc.

        Returns:
            :class:`ProviderResponse` with notification ID.
        """

    @abstractmethod
    def send_bulk(
        self,
        user_ids: Sequence[str],
        title: str,
        body: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Send the same push notification to multiple users.

        Args:
            user_ids: List of internal user identifiers.
            title: Notification title.
            body: Notification body text.
            **kwargs: Additional notification options.

        Returns:
            :class:`ProviderResponse` with batch count.
        """

    @abstractmethod
    def send_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Send a push notification to a topic/subscription.

        Args:
            topic: Topic name (e.g. ``"parcel_updates"``).
            title: Notification title.
            body: Notification body text.
            **kwargs: Additional notification options.

        Returns:
            :class:`ProviderResponse` with message ID.
        """


class StorageProvider(ExternalProvider):
    """Interface for cloud object storage providers.

    Implementations: AWS S3, Cloudflare R2, GCS, Azure Blob, MinIO.
    """

    @abstractmethod
    def upload(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        **kwargs: Any,
    ) -> ProviderResponse:
        """Upload an object to the storage bucket.

        Args:
            key: Object key / path within the bucket.
            data: Raw bytes to store.
            content_type: MIME type of the object.
            **kwargs: ``metadata``, ``acl``, ``cache_control``, etc.

        Returns:
            :class:`ProviderResponse` with the object URL or ETag.
        """

    @abstractmethod
    def download(self, key: str) -> ProviderResponse:
        """Download an object from the storage bucket.

        Args:
            key: Object key / path within the bucket.

        Returns:
            :class:`ProviderResponse` with the object bytes in ``data``.
        """

    @abstractmethod
    def delete(self, key: str) -> ProviderResponse:
        """Delete an object from the storage bucket.

        Args:
            key: Object key / path within the bucket.

        Returns:
            :class:`ProviderResponse` confirming deletion.
        """

    @abstractmethod
    def get_presigned_url(
        self,
        key: str,
        expiration: int = 3600,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Generate a pre-signed URL for temporary access.

        Args:
            key: Object key / path.
            expiration: URL validity duration in seconds.
            **kwargs: ``http_method`` (``"GET"`` or ``"PUT"``), etc.

        Returns:
            :class:`ProviderResponse` with the signed URL in ``data``.
        """

    @abstractmethod
    def list_objects(self, prefix: str) -> ProviderResponse:
        """List objects under a given prefix.

        Args:
            prefix: Key prefix to filter by.

        Returns:
            :class:`ProviderResponse` with a list of object keys in ``data``.
        """


class AIProvider(ExternalProvider):
    """Interface for AI / LLM service providers.

    Implementations: OpenAI, Anthropic, Google Gemini, Azure OpenAI.
    """

    @abstractmethod
    def chat_completion(
        self,
        messages: Sequence[Dict[str, str]],
        **kwargs: Any,
    ) -> ProviderResponse:
        """Request a chat completion from the LLM.

        Args:
            messages: Conversation history as a list of ``{"role": ..., "content": ...}`` dicts.
            **kwargs: ``model``, ``temperature``, ``max_tokens``, etc.

        Returns:
            :class:`ProviderResponse` with the completion text in ``data``.
        """

    @abstractmethod
    def generate_embedding(
        self,
        text: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Generate a vector embedding for the given text.

        Args:
            text: Input text to embed.
            **kwargs: ``model``, ``dimensions``, etc.

        Returns:
            :class:`ProviderResponse` with the embedding vector in ``data``.
        """

    @abstractmethod
    def count_tokens(self, text: str) -> ProviderResponse:
        """Count the number of tokens in the given text.

        Args:
            text: Input text.

        Returns:
            :class:`ProviderResponse` with ``token_count`` in ``data``.
        """

    @abstractmethod
    def get_available_models(self) -> ProviderResponse:
        """List models available on the provider.

        Returns:
            :class:`ProviderResponse` with a list of model identifiers in ``data``.
        """


class SearchProvider(ExternalProvider):
    """Interface for search engine / index providers.

    Implementations: Elasticsearch, Algolia, Meilisearch.
    """

    @abstractmethod
    def index_document(
        self,
        index: str,
        doc_id: str,
        document: Dict[str, Any],
    ) -> ProviderResponse:
        """Index (create or update) a single document.

        Args:
            index: Index name.
            doc_id: Unique document identifier.
            document: Document body as a dict.

        Returns:
            :class:`ProviderResponse` confirming the operation.
        """

    @abstractmethod
    def search(
        self,
        index: str,
        query: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Execute a search query against an index.

        Args:
            index: Index name.
            query: Search query string.
            **kwargs: ``filters``, ``page``, ``page_size``, ``sort``, etc.

        Returns:
            :class:`ProviderResponse` with search hits in ``data``.
        """

    @abstractmethod
    def delete_document(self, index: str, doc_id: str) -> ProviderResponse:
        """Remove a document from the index.

        Args:
            index: Index name.
            doc_id: Document identifier to delete.

        Returns:
            :class:`ProviderResponse` confirming deletion.
        """

    @abstractmethod
    def bulk_index(
        self,
        index: str,
        documents: Sequence[Dict[str, Any]],
    ) -> ProviderResponse:
        """Index multiple documents in a single batch.

        Args:
            index: Index name.
            documents: Iterable of documents, each with an ``id`` field.

        Returns:
            :class:`ProviderResponse` with bulk operation statistics.
        """


class AnalyticsProvider(ExternalProvider):
    """Interface for analytics and event-tracking providers.

    Implementations: Google Analytics, Mixpanel, PostHog.
    """

    @abstractmethod
    def track_event(
        self,
        event_name: str,
        properties: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> ProviderResponse:
        """Record a custom analytics event.

        Args:
            event_name: Event identifier (e.g. ``"payment_completed"``).
            properties: Event metadata.
            user_id: Optional user identifier for attribution.

        Returns:
            :class:`ProviderResponse` confirming the event was recorded.
        """

    @abstractmethod
    def track_page_view(
        self,
        url: str,
        user_id: Optional[str] = None,
    ) -> ProviderResponse:
        """Record a page view event.

        Args:
            url: The URL of the page viewed.
            user_id: Optional user identifier.

        Returns:
            :class:`ProviderResponse` confirming the page view was recorded.
        """

    @abstractmethod
    def identify_user(
        self,
        user_id: str,
        traits: Dict[str, Any],
    ) -> ProviderResponse:
        """Associate traits with a user for analytics segmentation.

        Args:
            user_id: Internal user identifier.
            traits: User attributes (e.g. ``{"plan": "professional"}``).

        Returns:
            :class:`ProviderResponse` confirming identification.
        """

    @abstractmethod
    def get_metrics(
        self,
        metric_name: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Retrieve aggregated metrics from the analytics provider.

        Args:
            metric_name: Metric to query.
            **kwargs: ``start_date``, ``end_date``, ``granularity``, ``filters``, etc.

        Returns:
            :class:`ProviderResponse` with metric data in ``data``.
        """


class IdentityProvider(ExternalProvider):
    """Interface for OAuth / SSO identity providers.

    Implementations: Google OAuth, GitHub OAuth, Microsoft OAuth.
    """

    @abstractmethod
    def get_authorize_url(
        self,
        scopes: Sequence[str],
        redirect_uri: str,
        state: str,
    ) -> ProviderResponse:
        """Build the OAuth 2.0 authorisation URL.

        Args:
            scopes: OAuth scopes to request.
            redirect_uri: URL the provider redirects to after consent.
            state: Anti-CSRF state token.

        Returns:
            :class:`ProviderResponse` with ``authorize_url`` in ``data``.
        """

    @abstractmethod
    def exchange_code(
        self,
        code: str,
        redirect_uri: str,
    ) -> ProviderResponse:
        """Exchange an authorisation code for access and refresh tokens.

        Args:
            code: Authorisation code received from the provider.
            redirect_uri: Must match the URI used in :meth:`get_authorize_url`.

        Returns:
            :class:`ProviderResponse` with ``access_token`` and ``refresh_token`` in ``data``.
        """

    @abstractmethod
    def get_user_info(self, access_token: str) -> ProviderResponse:
        """Fetch the authenticated user's profile from the provider.

        Args:
            access_token: Valid OAuth access token.

        Returns:
            :class:`ProviderResponse` with user profile data in ``data``.
        """

    @abstractmethod
    def refresh_token(self, refresh_token: str) -> ProviderResponse:
        """Obtain a new access token using a refresh token.

        Args:
            refresh_token: The refresh token to exchange.

        Returns:
            :class:`ProviderResponse` with new ``access_token`` in ``data``.
        """

    @abstractmethod
    def revoke_token(self, token: str) -> ProviderResponse:
        """Revoke an access or refresh token.

        Args:
            token: The token to revoke.

        Returns:
            :class:`ProviderResponse` confirming revocation.
        """


class MapsProvider(ExternalProvider):
    """Interface for maps and geolocation providers.

    Implementations: Google Maps, Mapbox.
    """

    @abstractmethod
    def geocode(self, address: str) -> ProviderResponse:
        """Convert a street address to geographic coordinates.

        Args:
            address: Street address string.

        Returns:
            :class:`ProviderResponse` with ``lat`` and ``lng`` in ``data``.
        """

    @abstractmethod
    def reverse_geocode(self, lat: float, lng: float) -> ProviderResponse:
        """Convert geographic coordinates to a street address.

        Args:
            lat: Latitude.
            lng: Longitude.

        Returns:
            :class:`ProviderResponse` with address components in ``data``.
        """

    @abstractmethod
    def get_distance(
        self,
        origin: str,
        destination: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Calculate the distance between two locations.

        Args:
            origin: Origin address or coordinates string.
            destination: Destination address or coordinates string.
            **kwargs: ``mode`` (``"driving"``, ``"walking"``), ``units``, etc.

        Returns:
            :class:`ProviderResponse` with ``distance`` and ``duration`` in ``data``.
        """

    @abstractmethod
    def get_directions(
        self,
        origin: str,
        destination: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Get turn-by-turn directions between two locations.

        Args:
            origin: Origin address or coordinates string.
            destination: Destination address or coordinates string.
            **kwargs: ``mode``, ``waypoints``, ``avoid``, etc.

        Returns:
            :class:`ProviderResponse` with route steps in ``data``.
        """


class FraudDetectionProvider(ExternalProvider):
    """Interface for fraud detection and risk scoring providers.

    Implementations: Sift, Signifyd.
    """

    @abstractmethod
    def evaluate_risk(
        self,
        event: str,
        user_id: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Evaluate the risk level of a transaction or user action.

        Args:
            event: Event type (e.g. ``"payment"``, ``"login"``).
            user_id: Internal user identifier.
            **kwargs: ``amount``, ``ip_address``, ``device_fingerprint``, etc.

        Returns:
            :class:`ProviderResponse` with ``risk_score`` and ``recommendation`` in ``data``.
        """

    @abstractmethod
    def get_risk_score(self, user_id: str) -> ProviderResponse:
        """Retrieve the current aggregate risk score for a user.

        Args:
            user_id: Internal user identifier.

        Returns:
            :class:`ProviderResponse` with ``risk_score`` in ``data``.
        """

    @abstractmethod
    def flag_event(self, event_id: str, reason: str) -> ProviderResponse:
        """Manually flag an event for fraud review.

        Args:
            event_id: Identifier of the event to flag.
            reason: Human-readable explanation.

        Returns:
            :class:`ProviderResponse` confirming the flag was recorded.
        """


class WebhookProvider(ExternalProvider):
    """Interface for outbound webhook delivery and inbound verification.

    This is a generic framework — specific providers (e.g. Stripe webhooks)
    should extend the relevant typed provider as well.
    """

    @abstractmethod
    def send_webhook(
        self,
        url: str,
        payload: Dict[str, Any],
        secret: str,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Deliver a webhook payload to an external URL.

        The implementation must sign the payload with ``secret`` using
        HMAC-SHA256 and include the signature in the ``X-Webhook-Signature``
        header.

        Args:
            url: Target URL.
            payload: JSON-serialisable body.
            secret: Signing secret.
            **kwargs: ``timeout``, ``headers``, ``idempotency_key``, etc.

        Returns:
            :class:`ProviderResponse` with the HTTP status from the target.
        """

    @abstractmethod
    def verify_signature(
        self,
        payload: bytes,
        signature: str,
        secret: str,
    ) -> ProviderResponse:
        """Verify the HMAC-SHA256 signature of an inbound webhook.

        Args:
            payload: Raw request body bytes.
            signature: Signature from the ``X-Webhook-Signature`` header.
            secret: Expected signing secret.

        Returns:
            :class:`ProviderResponse` with ``is_valid`` in ``data``.
        """

    @abstractmethod
    def replay_webhook(self, webhook_id: str) -> ProviderResponse:
        """Re-deliver a previously sent webhook.

        Args:
            webhook_id: Identifier of the webhook event to replay.

        Returns:
            :class:`ProviderResponse` confirming the replay was initiated.
        """
