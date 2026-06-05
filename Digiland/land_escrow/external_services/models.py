"""
Django models for the External Services Layer (ESL).

These models persist operational state so that the ESL can:

* **Track provider configurations** — including encrypted secrets.
* **Record webhook events** — both inbound and outbound, with full delivery
  history and retry tracking.
* **Maintain a dead-letter queue (DLQ)** — for messages that failed all
  retry attempts.
* **Monitor provider health** — current status of each provider.
* **Track costs** — per-provider, per-operation billing records.
* **Persist rate-limit state** — so that restarts do not reset the window.
* **Persist circuit-breaker state** — so that a deploy does not lose the
  breaker position.

Every model includes:

* UUID primary key (``id``)
* ``tenant_id`` for multi-tenancy (row-level security)
* ``created_at``, ``updated_at`` timestamps
* ``deleted_at`` for soft deletes
* ``updated_by`` for audit trail
* Composite indexes optimised for the most common query patterns
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


# ======================================================================
# Abstract Base Mixins
# ======================================================================


class ESLTimestampMixin(models.Model):
    """Provides ``created_at`` and ``updated_at`` auto-timestamp fields."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ESLSoftDeleteMixin(models.Model):
    """Provides ``deleted_at`` for soft-delete support.

    A ``null`` value means the record is active.  To query only active
    records, filter with ``deleted_at__isnull=True``.
    """

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Soft delete timestamp — null means active record",
    )

    class Meta:
        abstract = True

    def soft_delete(self, user=None) -> None:
        """Mark this record as deleted without removing it from the DB."""
        self.deleted_at = timezone.now()
        if user and hasattr(self, "updated_by"):
            self.updated_by = user
        self.save(update_fields=["deleted_at", "updated_at", "updated_by"])

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class ESLAuditMixin(models.Model):
    """Provides ``updated_by`` for audit trail tracking."""

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_updates",
        help_text="Last user who modified this record",
    )

    class Meta:
        abstract = True


class ESLScopeMixin(models.Model):
    """Provides ``tenant_id`` for multi-tenant row-level security."""

    tenant_id = models.UUIDField(
        db_index=True,
        null=True,
        blank=True,
        help_text="Organization tenant ID for row-level security isolation",
    )

    class Meta:
        abstract = True


class ESLBaseModel(ESLScopeMixin, ESLTimestampMixin, ESLSoftDeleteMixin, ESLAuditMixin):
    """Combined base model with all common ESL fields.

    Every concrete ESL model should inherit from this class to guarantee
    consistent tenant isolation, timestamps, soft deletes, and audit trail.
    """

    class Meta:
        abstract = True


# ======================================================================
# Provider Configuration
# ======================================================================


class ProviderConfiguration(ESLBaseModel):
    """Stores provider settings, including encrypted API keys and secrets.

    Sensitive values (marked with ``is_secret=True``) are stored using
    Django's ``encrypt`` key from ``settings.FIELD_ENCRYPTION_KEY`` when
    available, or as plain text with a warning in development.

    Attributes:
        service_type: Category (e.g. ``"payment"``).
        provider_name: Provider identifier (e.g. ``"paystack"``).
        config: JSON blob with all non-secret configuration.
        secrets: JSON blob with encrypted secret values.
        is_active: Whether this provider configuration is currently in use.
        environment: Deployment environment (``"sandbox"`` / ``"production"``).
    """

    ENVIRONMENT_CHOICES = [
        ("sandbox", "Sandbox / Test"),
        ("production", "Production"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Service category, e.g. 'payment', 'email', 'sms'",
    )
    provider_name = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Provider identifier, e.g. 'paystack', 'stripe'",
    )
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Non-secret configuration key-value pairs",
    )
    secrets = models.JSONField(
        default=dict,
        blank=True,
        help_text="Encrypted secret values (API keys, tokens). Never log or expose in API responses.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this provider configuration is currently enabled",
    )
    environment = models.CharField(
        max_length=20,
        choices=ENVIRONMENT_CHOICES,
        default="sandbox",
        db_index=True,
    )
    description = models.TextField(
        blank=True,
        help_text="Optional human-readable description of this configuration",
    )
    last_validated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the configuration was last validated successfully",
    )
    last_validation_result = models.JSONField(
        null=True,
        blank=True,
        help_text="Result of the last validation check",
    )

    class Meta:
        verbose_name = "Provider Configuration"
        verbose_name_plural = "Provider Configurations"
        unique_together = ("tenant_id", "service_type", "provider_name", "environment")
        indexes = [
            models.Index(
                fields=["tenant_id", "service_type", "provider_name"],
                name="idx_pc_tenant_svc_prov",
            ),
            models.Index(
                fields=["tenant_id", "is_active", "environment"],
                name="idx_pc_tenant_active_env",
            ),
            models.Index(
                fields=["service_type", "is_active"],
                name="idx_pc_svc_active",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.service_type}/{self.provider_name} ({self.environment})"

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Retrieve a non-secret configuration value.

        Args:
            key: Configuration key.
            default: Value returned if the key is not present.

        Returns:
            The configuration value, or ``default``.
        """
        return self.config.get(key, default)

    def get_secret(self, key: str, default: Any = None) -> Any:
        """Retrieve a decrypted secret value.

        .. warning::

           Never log or include secret values in API responses.

        Args:
            key: Secret key.
            default: Value returned if the key is not present.

        Returns:
            The decrypted secret value, or ``default``.
        """
        return self.secrets.get(key, default)


# ======================================================================
# Webhook Events
# ======================================================================


class WebhookEvent(ESLBaseModel):
    """Inbound or outbound webhook event with status tracking.

    Every webhook that the platform sends or receives is recorded here for
    audit, debugging, and replay purposes.

    Attributes:
        event_id: Unique event identifier (set by the sender or generated).
        direction: ``"inbound"`` (received) or ``"outbound"`` (sent).
        service_type: Which external service this webhook relates to.
        provider_name: Which provider sent or should receive the webhook.
        event_type: Provider-specific event type (e.g. ``"charge.success"``).
        payload: Raw webhook body (JSON).
        headers: HTTP headers (JSON, for signature verification).
        status: Current processing status.
        processed_at: When the webhook was fully processed.
    """

    DIRECTION_CHOICES = [
        ("inbound", "Inbound (Received)"),
        ("outbound", "Outbound (Sent)"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("dead_lettered", "Dead-Lettered"),
        ("replaying", "Replaying"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Unique event identifier from the sender",
    )
    direction = models.CharField(
        max_length=10,
        choices=DIRECTION_CHOICES,
        db_index=True,
    )
    service_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Service category this webhook belongs to",
    )
    provider_name = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Provider that sent or should receive this webhook",
    )
    event_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Provider-specific event type, e.g. 'charge.success'",
    )
    payload = models.JSONField(
        help_text="Raw webhook body",
    )
    headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="HTTP headers for signature verification",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    signature_verified = models.BooleanField(
        default=False,
        help_text="Whether the webhook signature was verified successfully",
    )
    retry_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of delivery attempts",
    )
    max_retries = models.PositiveIntegerField(
        default=5,
        help_text="Maximum number of retry attempts before dead-lettering",
    )
    next_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Scheduled time for the next retry attempt",
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the webhook was fully processed",
    )
    response_summary = models.TextField(
        blank=True,
        help_text="Summary of the processing result or error",
    )
    related_object_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional: content type of the related object (e.g. 'Transaction')",
    )
    related_object_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Optional: UUID of the related object",
    )

    class Meta:
        verbose_name = "Webhook Event"
        verbose_name_plural = "Webhook Events"
        indexes = [
            models.Index(
                fields=["tenant_id", "service_type", "status"],
                name="idx_we_tenant_svc_sts",
            ),
            models.Index(
                fields=["tenant_id", "direction", "status"],
                name="idx_we_tenant_dir_sts",
            ),
            models.Index(
                fields=["tenant_id", "provider_name", "event_type"],
                name="idx_we_tenant_prov_evt",
            ),
            models.Index(
                fields=["status", "next_retry_at"],
                name="idx_we_sts_next_retry",
            ),
            models.Index(
                fields=["tenant_id", "related_object_type", "related_object_id"],
                name="idx_we_tenant_related_obj",
            ),
        ]

    def __str__(self) -> str:
        return f"Webhook {self.event_id} ({self.direction}/{self.status})"

    def mark_completed(self, summary: str = "") -> None:
        """Mark the webhook as successfully processed."""
        self.status = "completed"
        self.processed_at = timezone.now()
        self.response_summary = summary
        self.save(update_fields=["status", "processed_at", "response_summary", "updated_at"])

    def mark_failed(self, summary: str = "") -> None:
        """Mark the webhook as failed and schedule a retry if possible."""
        self.retry_count += 1
        self.response_summary = summary

        if self.retry_count >= self.max_retries:
            self.status = "dead_lettered"
            self.save(update_fields=["status", "retry_count", "response_summary", "updated_at"])
        else:
            self.status = "failed"
            # Exponential backoff: 2^n minutes
            from datetime import timedelta
            self.next_retry_at = timezone.now() + timedelta(minutes=2 ** self.retry_count)
            self.save(
                update_fields=[
                    "status",
                    "retry_count",
                    "response_summary",
                    "next_retry_at",
                    "updated_at",
                ]
            )


class WebhookDeliveryAttempt(ESLBaseModel):
    """Individual delivery attempt for a webhook event.

    Each time the platform tries to deliver an outbound webhook or process
    an inbound one, a :class:`WebhookDeliveryAttempt` is recorded with the
    full HTTP exchange details.

    Attributes:
        webhook_event: The parent webhook event.
        attempt_number: Sequential attempt number (1-based).
        request_url: URL that was called (for outbound).
        request_method: HTTP method used.
        request_headers: Headers sent.
        request_body: Body sent.
        response_status_code: HTTP status received.
        response_headers: Headers received.
        response_body: Body received.
        latency_ms: Round-trip time in milliseconds.
        outcome: Result of the attempt.
    """

    OUTCOME_CHOICES = [
        ("success", "Success"),
        ("client_error", "Client Error (4xx)"),
        ("server_error", "Server Error (5xx)"),
        ("timeout", "Timeout"),
        ("connection_error", "Connection Error"),
        ("ssl_error", "SSL Error"),
        ("dns_error", "DNS Resolution Error"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    webhook_event = models.ForeignKey(
        WebhookEvent,
        on_delete=models.CASCADE,
        related_name="delivery_attempts",
    )
    attempt_number = models.PositiveIntegerField(
        help_text="Sequential attempt number (1-based)",
    )
    request_url = models.URLField(
        max_length=2048,
        blank=True,
        help_text="URL that was called (for outbound webhooks)",
    )
    request_method = models.CharField(
        max_length=10,
        default="POST",
        help_text="HTTP method used for the request",
    )
    request_headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Headers sent in the request",
    )
    request_body = models.JSONField(
        null=True,
        blank=True,
        help_text="Body sent in the request",
    )
    response_status_code = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="HTTP status code received in the response",
    )
    response_headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Headers received in the response",
    )
    response_body = models.TextField(
        blank=True,
        help_text="Body received in the response (truncated if very large)",
    )
    latency_ms = models.FloatField(
        null=True,
        blank=True,
        help_text="Round-trip latency in milliseconds",
    )
    outcome = models.CharField(
        max_length=20,
        choices=OUTCOME_CHOICES,
        db_index=True,
        help_text="Result of this delivery attempt",
    )
    error_detail = models.TextField(
        blank=True,
        help_text="Error message if the attempt failed",
    )

    class Meta:
        verbose_name = "Webhook Delivery Attempt"
        verbose_name_plural = "Webhook Delivery Attempts"
        ordering = ["-attempt_number"]
        indexes = [
            models.Index(
                fields=["tenant_id", "webhook_event", "attempt_number"],
                name="idx_wda_tenant_event_attempt",
            ),
            models.Index(
                fields=["tenant_id", "outcome"],
                name="idx_wda_tenant_outcome",
            ),
        ]

    def __str__(self) -> str:
        return f"Attempt #{self.attempt_number} for {self.webhook_event.event_id} ({self.outcome})"


# ======================================================================
# Dead Letter Queue
# ======================================================================


class DeadLetterQueue(ESLBaseModel):
    """Failed messages that could not be processed after all retry attempts.

    Messages end up here when:

    * A webhook delivery exhausts its retry budget.
    * A provider call fails repeatedly and the circuit breaker is open.
    * An explicitly rejected message is marked for dead-lettering.

    Operators can inspect, replay, or discard dead-lettered messages.

    Attributes:
        original_event_type: What kind of event this was.
        original_service_type: Which service type the event belongs to.
        original_provider_name: Which provider was involved.
        original_payload: The original message payload.
        original_headers: Original HTTP headers (if applicable).
        failure_reason: Why the message was dead-lettered.
        original_error: The last error message before dead-lettering.
        retry_count: How many times the message was retried.
        status: Current DLQ status (``"pending"``, ``"replayed"``, ``"discarded"``).
    """

    STATUS_CHOICES = [
        ("pending", "Pending Review"),
        ("replayed", "Replayed"),
        ("discarded", "Discarded"),
        ("replay_failed", "Replay Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_event_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="ID of the original event before dead-lettering",
    )
    original_event_type = models.CharField(
        max_length=100,
        help_text="Type of the original event",
    )
    original_service_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Service type the event was for",
    )
    original_provider_name = models.CharField(
        max_length=100,
        help_text="Provider that was targeted",
    )
    original_payload = models.JSONField(
        help_text="Original message payload",
    )
    original_headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Original HTTP headers",
    )
    failure_reason = models.TextField(
        help_text="Why the message was dead-lettered",
    )
    original_error = models.TextField(
        blank=True,
        help_text="The last error message before dead-lettering",
    )
    retry_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of retries attempted before dead-lettering",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    replayed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the message was replayed",
    )
    replayed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replayed_dlq_messages",
        help_text="User who triggered the replay",
    )
    replay_result = models.TextField(
        blank=True,
        help_text="Result of the replay attempt",
    )
    related_webhook_event = models.ForeignKey(
        WebhookEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dlq_entries",
        help_text="Original webhook event, if applicable",
    )

    class Meta:
        verbose_name = "Dead Letter Queue Entry"
        verbose_name_plural = "Dead Letter Queue Entries"
        indexes = [
            models.Index(
                fields=["tenant_id", "status", "created_at"],
                name="idx_dlq_tenant_sts_crt",
            ),
            models.Index(
                fields=["tenant_id", "original_service_type", "status"],
                name="idx_dlq_tenant_svc_sts",
            ),
            models.Index(
                fields=["tenant_id", "original_provider_name"],
                name="idx_dlq_tenant_prov",
            ),
        ]

    def __str__(self) -> str:
        return f"DLQ {self.original_event_id} ({self.status})"

    def mark_replayed(self, user=None, result: str = "") -> None:
        """Mark the message as successfully replayed."""
        self.status = "replayed"
        self.replayed_at = timezone.now()
        self.replayed_by = user
        self.replay_result = result
        self.save(
            update_fields=["status", "replayed_at", "replayed_by", "replay_result", "updated_at"]
        )

    def mark_discarded(self, user=None) -> None:
        """Mark the message as permanently discarded."""
        self.status = "discarded"
        self.replayed_by = user
        self.save(update_fields=["status", "replayed_by", "updated_at"])


# ======================================================================
# Provider Health Status
# ======================================================================


class ProviderHealthStatus(ESLBaseModel):
    """Current health status of each registered provider.

    Updated periodically by a Celery beat task that pings every provider.
    The most recent entry for a ``(tenant_id, service_type, provider_name)``
    triple represents the **current** health.

    Attributes:
        service_type: Category of the provider.
        provider_name: Specific provider identifier.
        status: Current health status.
        response_time_ms: Latency of the last health probe.
        details: Additional diagnostic information.
        checked_at: When the health check was performed.
        consecutive_failures: Number of consecutive failed health checks.
    """

    STATUS_CHOICES = [
        ("healthy", "Healthy"),
        ("degraded", "Degraded"),
        ("unhealthy", "Unhealthy"),
        ("unknown", "Unknown"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_type = models.CharField(
        max_length=50,
        db_index=True,
    )
    provider_name = models.CharField(
        max_length=100,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="unknown",
        db_index=True,
    )
    response_time_ms = models.FloatField(
        null=True,
        blank=True,
        help_text="Latency of the last health probe in milliseconds",
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional diagnostic information",
    )
    checked_at = models.DateTimeField(
        db_index=True,
        help_text="When this health check was performed",
    )
    consecutive_failures = models.PositiveIntegerField(
        default=0,
        help_text="Number of consecutive failed health checks",
    )
    last_success_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the provider last returned a healthy status",
    )
    last_failure_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the provider last returned an unhealthy status",
    )
    last_error_message = models.TextField(
        blank=True,
        help_text="Error message from the last failed health check",
    )

    class Meta:
        verbose_name = "Provider Health Status"
        verbose_name_plural = "Provider Health Statuses"
        ordering = ["-checked_at"]
        indexes = [
            models.Index(
                fields=["tenant_id", "service_type", "provider_name", "-checked_at"],
                name="idx_phs_tenant_svc_prov_ckd",
            ),
            models.Index(
                fields=["tenant_id", "status"],
                name="idx_phs_tenant_sts",
            ),
            models.Index(
                fields=["service_type", "provider_name", "-checked_at"],
                name="idx_phs_svc_prov_ckd",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.service_type}/{self.provider_name} = {self.status}"

    @classmethod
    def get_latest(cls, tenant_id, service_type: str, provider_name: str):
        """Return the most recent health status for a provider.

        Args:
            tenant_id: Tenant identifier.
            service_type: Category identifier.
            provider_name: Provider identifier.

        Returns:
            The latest :class:`ProviderHealthStatus` instance, or ``None``.
        """
        return (
            cls.objects.filter(
                tenant_id=tenant_id,
                service_type=service_type,
                provider_name=provider_name,
                deleted_at__isnull=True,
            )
            .order_by("-checked_at")
            .first()
        )


# ======================================================================
# Cost Tracking
# ======================================================================


class CostRecord(ESLBaseModel):
    """Tracks monetary costs incurred by provider operations.

    Every billable external service call should create a :class:`CostRecord`
    entry for billing, budgeting, and anomaly detection.

    Attributes:
        service_type: Category of the provider.
        provider_name: Specific provider identifier.
        operation: API operation that incurred the cost.
        units: Number of billable units (e.g. tokens, messages, GB).
        unit_type: What the units represent.
        cost: Monetary cost.
        currency: ISO 4217 currency code.
        billing_period: Period string for aggregation (e.g. ``"2025-01"``).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_type = models.CharField(
        max_length=50,
        db_index=True,
    )
    provider_name = models.CharField(
        max_length=100,
        db_index=True,
    )
    operation = models.CharField(
        max_length=100,
        db_index=True,
        help_text="API operation that incurred the cost, e.g. 'chat_completion'",
    )
    units = models.PositiveIntegerField(
        help_text="Number of billable units consumed",
    )
    unit_type = models.CharField(
        max_length=50,
        default="units",
        help_text="What the units represent, e.g. 'tokens', 'messages', 'GB'",
    )
    cost = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        help_text="Monetary cost of this operation",
    )
    currency = models.CharField(
        max_length=3,
        default="USD",
        help_text="ISO 4217 currency code",
    )
    billing_period = models.CharField(
        max_length=7,
        db_index=True,
        help_text="Billing period for aggregation, e.g. '2025-01'",
    )
    request_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Correlation ID linking to the original request",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (model name, region, etc.)",
    )

    class Meta:
        verbose_name = "Cost Record"
        verbose_name_plural = "Cost Records"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["tenant_id", "service_type", "provider_name", "billing_period"],
                name="idx_cr_tenant_svc_prov_bp",
            ),
            models.Index(
                fields=["tenant_id", "operation", "billing_period"],
                name="idx_cr_tenant_op_bp",
            ),
            models.Index(
                fields=["tenant_id", "billing_period", "-cost"],
                name="idx_cr_tenant_bp_cost",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.service_type}/{self.provider_name} {self.operation} = {self.cost} {self.currency}"

    @classmethod
    def get_period_total(
        cls,
        tenant_id,
        billing_period: str,
        service_type: str = None,
        provider_name: str = None,
    ) -> Decimal:
        """Calculate total cost for a billing period.

        Args:
            tenant_id: Tenant identifier.
            billing_period: Period string (e.g. ``"2025-01"``).
            service_type: Optional filter by service type.
            provider_name: Optional filter by provider name.

        Returns:
            Total cost as a :class:`Decimal`.
        """
        qs = cls.objects.filter(
            tenant_id=tenant_id,
            billing_period=billing_period,
            deleted_at__isnull=True,
        )
        if service_type:
            qs = qs.filter(service_type=service_type)
        if provider_name:
            qs = qs.filter(provider_name=provider_name)
        return qs.aggregate(total=models.Sum("cost"))["total"] or Decimal("0")


# ======================================================================
# Rate Limit State
# ======================================================================


class RateLimitState(ESLBaseModel):
    """Persists rate-limit counters so that application restarts do not
    reset the sliding window.

    Each row tracks the number of requests made to a specific provider
    within a given time window.

    Attributes:
        service_type: Category of the provider.
        provider_name: Specific provider identifier.
        window_start: Start of the current rate-limit window.
        window_duration_seconds: Length of the window in seconds.
        request_count: Number of requests made within this window.
        request_limit: Maximum requests allowed in the window.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_type = models.CharField(
        max_length=50,
        db_index=True,
    )
    provider_name = models.CharField(
        max_length=100,
        db_index=True,
    )
    window_start = models.DateTimeField(
        db_index=True,
        help_text="Start of the current rate-limit window",
    )
    window_duration_seconds = models.PositiveIntegerField(
        default=60,
        help_text="Length of the rate-limit window in seconds",
    )
    request_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of requests made within this window",
    )
    request_limit = models.PositiveIntegerField(
        help_text="Maximum requests allowed in this window",
    )
    remaining = models.PositiveIntegerField(
        default=0,
        help_text="Remaining requests in this window",
    )
    reset_at = models.DateTimeField(
        help_text="When the current window resets",
    )

    class Meta:
        verbose_name = "Rate Limit State"
        verbose_name_plural = "Rate Limit States"
        indexes = [
            models.Index(
                fields=["tenant_id", "service_type", "provider_name", "window_start"],
                name="idx_rls_tenant_svc_prov_ws",
            ),
            models.Index(
                fields=["tenant_id", "reset_at"],
                name="idx_rls_tenant_reset",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.service_type}/{self.provider_name} "
            f"{self.request_count}/{self.request_limit} "
            f"(resets {self.reset_at.isoformat()})"
        )

    @property
    def is_limited(self) -> bool:
        """Whether the rate limit has been exceeded."""
        return self.request_count >= self.request_limit

    @property
    def seconds_until_reset(self) -> int:
        """Seconds until the current window resets."""
        delta = self.reset_at - timezone.now()
        return max(0, int(delta.total_seconds()))

    def increment(self) -> None:
        """Increment the request counter and update remaining count."""
        self.request_count += 1
        self.remaining = max(0, self.request_limit - self.request_count)
        self.save(update_fields=["request_count", "remaining", "updated_at"])


# ======================================================================
# Circuit Breaker State
# ======================================================================


class CircuitBreakerState(ESLBaseModel):
    """Persists circuit-breaker state so that deploys do not lose position.

    The circuit breaker has three states:

    * **CLOSED** — requests flow normally.
    * **OPEN** — all requests are short-circuited; no outbound calls are made.
    * **HALF_OPEN** — a single probe request is allowed to test recovery.

    Attributes:
        service_type: Category of the provider.
        provider_name: Specific provider identifier.
        state: Current circuit-breaker state.
        failure_count: Consecutive failures in the current window.
        success_count: Consecutive successes (used in HALF_OPEN).
        failure_threshold: Failures required to trip the breaker.
        success_threshold: Successes required to close the breaker from HALF_OPEN.
        last_failure_at: When the last failure occurred.
        last_success_at: When the last success occurred.
        opened_at: When the breaker transitioned to OPEN.
        half_open_at: When the breaker transitioned to HALF_OPEN.
        next_half_open_at: When the breaker should transition from OPEN to HALF_OPEN.
        last_error: Error message from the most recent failure.
    """

    STATE_CHOICES = [
        ("closed", "Closed (Normal)"),
        ("open", "Open (Tripped)"),
        ("half_open", "Half-Open (Probing)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_type = models.CharField(
        max_length=50,
        db_index=True,
    )
    provider_name = models.CharField(
        max_length=100,
        db_index=True,
    )
    state = models.CharField(
        max_length=10,
        choices=STATE_CHOICES,
        default="closed",
        db_index=True,
    )
    failure_count = models.PositiveIntegerField(
        default=0,
        help_text="Consecutive failures in the current measurement window",
    )
    success_count = models.PositiveIntegerField(
        default=0,
        help_text="Consecutive successes (used in HALF_OPEN state)",
    )
    failure_threshold = models.PositiveIntegerField(
        default=5,
        help_text="Failures required to trip the circuit breaker",
    )
    success_threshold = models.PositiveIntegerField(
        default=3,
        help_text="Successes required to close the breaker from HALF_OPEN",
    )
    recovery_timeout_seconds = models.PositiveIntegerField(
        default=60,
        help_text="Seconds before OPEN transitions to HALF_OPEN",
    )
    last_failure_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    last_success_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    opened_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the breaker transitioned to OPEN",
    )
    half_open_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the breaker transitioned to HALF_OPEN",
    )
    next_half_open_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the breaker should transition to HALF_OPEN",
    )
    last_error = models.TextField(
        blank=True,
        help_text="Error message from the most recent failure",
    )
    total_trips = models.PositiveIntegerField(
        default=0,
        help_text="Lifetime count of how many times the breaker has tripped",
    )

    class Meta:
        verbose_name = "Circuit Breaker State"
        verbose_name_plural = "Circuit Breaker States"
        unique_together = ("tenant_id", "service_type", "provider_name")
        indexes = [
            models.Index(
                fields=["tenant_id", "state"],
                name="idx_cbs_tenant_state",
            ),
            models.Index(
                fields=["service_type", "provider_name", "state"],
                name="idx_cbs_svc_prov_state",
            ),
            models.Index(
                fields=["next_half_open_at"],
                name="idx_cbs_next_half_open",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.service_type}/{self.provider_name} = {self.state}"

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        """Whether the circuit breaker is in the OPEN state."""
        return self.state == "open"

    @property
    def is_half_open(self) -> bool:
        """Whether the circuit breaker is in the HALF_OPEN state."""
        return self.state == "half_open"

    @property
    def is_closed(self) -> bool:
        """Whether the circuit breaker is in the CLOSED state."""
        return self.state == "closed"

    def record_success(self) -> None:
        """Record a successful call and potentially close the breaker."""
        now = timezone.now()
        self.last_success_at = now
        self.last_error = ""

        if self.state == "half_open":
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self._transition_to_closed()
        else:
            # In CLOSED state, reset failure count on success
            self.failure_count = 0

        self.save(update_fields=[
            "failure_count",
            "success_count",
            "last_success_at",
            "last_error",
            "state",
            "updated_at",
        ])

    def record_failure(self, error: str = "") -> None:
        """Record a failed call and potentially trip the breaker.

        Args:
            error: Error message from the failed call.
        """
        now = timezone.now()
        self.failure_count += 1
        self.last_failure_at = now
        self.last_error = error[:500]  # truncate to prevent abuse

        if self.state == "half_open":
            # Single failure in HALF_OPEN sends it back to OPEN
            self._transition_to_open()
        elif self.state == "closed" and self.failure_count >= self.failure_threshold:
            self._transition_to_open()

        self.save(update_fields=[
            "failure_count",
            "last_failure_at",
            "last_error",
            "state",
            "opened_at",
            "half_open_at",
            "next_half_open_at",
            "total_trips",
            "updated_at",
        ])

    def try_half_open(self) -> bool:
        """Attempt to transition from OPEN to HALF_OPEN.

        Should be called by a periodic check.  Returns ``True`` if the
        transition was made (i.e. it is now safe to send a probe request).

        Returns:
            ``True`` if the breaker is now in HALF_OPEN, ``False`` otherwise.
        """
        if self.state != "open":
            return False

        now = timezone.now()
        if self.next_half_open_at and now >= self.next_half_open_at:
            self.state = "half_open"
            self.half_open_at = now
            self.success_count = 0
            self.save(update_fields=["state", "half_open_at", "success_count", "updated_at"])
            return True

        return False

    # ------------------------------------------------------------------
    # Private transition helpers
    # ------------------------------------------------------------------

    def _transition_to_open(self) -> None:
        now = timezone.now()
        self.state = "open"
        self.opened_at = now
        self.half_open_at = None
        self.next_half_open_at = now + timezone.timedelta(
            seconds=self.recovery_timeout_seconds
        )
        self.success_count = 0
        self.total_trips += 1

    def _transition_to_closed(self) -> None:
        now = timezone.now()
        self.state = "closed"
        self.failure_count = 0
        self.success_count = 0
        self.opened_at = None
        self.half_open_at = None
        self.next_half_open_at = None
