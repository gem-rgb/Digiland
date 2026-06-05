# Failure Handling

## Circuit Breaker States

The ESL implements the circuit breaker pattern to prevent cascading failures when an external provider becomes unresponsive. Each provider instance has its own circuit breaker, which operates independently and transitions between three states: CLOSED, OPEN, and HALF_OPEN.

**CLOSED state** — In the CLOSED state, the circuit breaker allows all requests to pass through to the provider. A rolling window of recent call outcomes is tracked. If the failure rate (defined as the ratio of failed calls to total calls within the window) exceeds the configured threshold (default 50%), the circuit breaker transitions to OPEN. The failure window is configurable per provider — a typical configuration uses a 60-second window with a minimum of 10 calls before evaluating the failure rate. This prevents the circuit from tripping on a single transient error.

**OPEN state** — In the OPEN state, the circuit breaker immediately rejects all requests without attempting to call the provider. This is the short-circuit behaviour that protects the platform from wasting resources on a known-unhealthy provider. Requests that are rejected in the OPEN state raise a `CircuitBreakerOpenError`, which includes the `half_open_after_ms` value indicating when the circuit may transition to HALF_OPEN. The OPEN state persists for a configurable cooldown period (default 30 seconds), after which the circuit transitions to HALF_OPEN to test whether the provider has recovered.

**HALF_OPEN state** — In the HALF_OPEN state, the circuit breaker allows a limited number of probe requests through to the provider (default 3). If these probe requests succeed, the circuit transitions back to CLOSED, and normal traffic resumes. If any probe request fails, the circuit immediately transitions back to OPEN, and the cooldown timer restarts. The HALF_OPEN state is critical for automatic recovery — it allows the system to detect when a provider has been restored without requiring manual intervention.

The circuit breaker's state is exposed through the provider's `circuit_breaker_open` attribute, which the registry checks during provider lookup. This allows the registry to skip unhealthy providers in fallback chains without making a network call. The circuit breaker also emits state-transition events to the observability layer, which triggers Prometheus counters and structured log entries. Operations teams can monitor the `esl_circuit_breaker_state` metric (1 = OPEN, 0 = CLOSED) and set up alerts for circuits that remain OPEN for more than 5 minutes.

## Retry Strategies

The ESL implements a sophisticated retry strategy that balances reliability with resource conservation. Retries are applied at multiple levels, each with its own configuration:

**Per-call retries** — Individual adapter methods may retry transient errors automatically before raising an exception to the caller. For example, the Salesforce adapter retries OAuth2 token refresh once on a 401 response before raising `AuthenticationError`. These intra-method retries are limited to safe, idempotent operations — they are never applied to operations that could cause side effects if duplicated.

**Infrastructure-level retries** — The ESL's retry infrastructure wraps every outbound call with a configurable retry policy. The default policy uses exponential backoff with jitter: the first retry waits 1 second (±500ms jitter), the second waits 2 seconds (±1 second jitter), the third waits 4 seconds (±2 seconds jitter), and so on up to a maximum of 5 retries. The jitter prevents thundering-herd effects when multiple instances of the application retry simultaneously after a provider outage.

**Retry budget** — The ESL enforces a global retry budget to prevent retry storms from overwhelming a recovering provider. The retry budget is defined as a percentage of total request capacity (default 10%). When the budget is exhausted, new retries are dropped and the original error is propagated immediately. This ensures that retries improve reliability without becoming a reliability problem themselves.

**Retryability classification** — Not all errors are retryable. The ESL's exception hierarchy includes an `is_retryable` flag on every exception. `ProviderUnavailableError`, `CircuitBreakerOpenError`, `RateLimitExceededError`, and `TimeoutError` are retryable by default. `AuthenticationError`, `ValidationError`, `WebhookVerificationError`, and `ConfigurationError` are not retryable — retrying these would be futile and would waste resources. The retry infrastructure checks the `is_retryable` flag before attempting a retry.

**Idempotency awareness** — The retry infrastructure is aware of operation idempotency. For idempotent operations (e.g. payment verification, CRM contact retrieval), retries are applied aggressively. For non-idempotent operations (e.g. payment initialisation, invoice creation), retries are applied only if the adapter confirms that the previous attempt did not produce a side effect (e.g. by checking for a duplicate reference). Advertisers signal idempotency through the `idempotency_key` parameter.

## Fallback Chains

Fallback chains are the ESL's primary mechanism for maintaining service availability during provider outages. Each service type has an ordered list of providers that the registry walks when the primary provider is unavailable. The chain is ordered by priority, with lower-priority values tried first.

**Automatic fallback** — When `registry.get_service` is called with `use_fallback=True` (the default), the registry first tries the requested provider. If the provider's circuit breaker is OPEN or the provider instance cannot be created, the registry walks the fallback chain, trying each provider in order until a healthy one is found. If a healthy provider is found through fallback, a WARNING-level log entry is emitted with the original provider name and the fallback provider name, so that operations teams can track fallback frequency.

**Fallback chain construction** — Fallback chains are constructed automatically based on provider priority. When providers are registered, they are assigned a priority value (lower = tried first). The registry sorts providers by priority to build the chain. Chains can also be set explicitly using `registry.set_fallback_chain`, which is useful for complex fallback scenarios where priority alone is insufficient.

**Provider-specific fallback behaviour** — Some service types have specialised fallback logic. For example, the payment fallback chain may include the internal `EscrowWalletAdapter` as a last resort, which holds funds in the internal ledger when no external payment processor is available. The CRM fallback chain may include a "no-op" adapter that queues operations for later batch sync when no CRM provider is available.

**Fallback metrics** — The ESL emits Prometheus metrics for fallback events: `esl_fallback_total{service_type, from_provider, to_provider}` counts the number of times a fallback was activated, and `esl_fallback_duration_seconds` tracks the additional latency introduced by falling back. These metrics are visualised on the ESL dashboard and trigger alerts when fallback rates exceed 5% of total traffic.

## Dead Letter Queues

When an operation fails after exhausting all retries and fallback options, it is moved to a dead-letter queue (DLQ). The DLQ is a persistent store (backed by the Django database) that preserves the original operation details, error context, and retry history. DLQ entries are never automatically discarded — they require manual review and resolution.

**DLQ schema** — Each DLQ entry contains: the service type, provider name, operation name, original request payload, the final error that caused the dead-lettering, the number of retry attempts, timestamps for first attempt and last attempt, and a `status` field (pending, resolved, replayed). Entries are partitioned by service type for efficient querying.

**DLQ processing** — Operations staff can review DLQ entries through the Django admin interface or a dedicated CLI tool. Each entry can be resolved (discarded as expected), replayed (retried with the original payload), or edited and replayed (correcting invalid data before retry). When a DLQ entry is replayed successfully, it is marked as `replayed` and the success response is logged. If the replay fails, the entry remains in the DLQ with an incremented retry count.

**DLQ monitoring** — The `esl_dlq_entries_total` Prometheus counter tracks the number of entries added to the DLQ, and `esl_dlq_entries_pending` tracks the current backlog. An alert fires when the DLQ backlog exceeds 100 entries or when the entry rate exceeds 10 per hour — these thresholds indicate a systemic problem that requires investigation.

**Dead letter error** — When an operation is dead-lettered, a `DeadLetterError` is raised to the caller. This exception includes the `original_error`, `dead_letter_reason`, and the DLQ entry ID, allowing the caller to provide user-facing feedback and support staff to locate the entry for investigation.

## Graceful Degradation

The ESL is designed to degrade gracefully under failure conditions, ensuring that the Digiland platform remains usable even when individual external services are unavailable. Graceful degradation is implemented at multiple levels:

**Read-only fallback** — For read operations (e.g. fetching a contact from CRM, retrieving a balance sheet), the ESL can serve cached data when the provider is unavailable. The caching layer is configured with a staleness threshold per service type (e.g. 5 minutes for CRM contacts, 1 hour for financial reports). Cached responses are tagged with a `served_from_cache` flag and their original timestamp, so that callers can decide whether the data is fresh enough for their use case.

**Async queueing** — For write operations that cannot be completed immediately, the ESL can enqueue the operation for later execution. This is particularly useful for CRM sync operations, where a delay of a few minutes is acceptable. The queue is backed by a durable store (Django database or Celery) and processed by a background worker that retries with exponential backoff.

**Feature toggles** — The ESL supports per-service-type feature toggles that can disable external provider calls entirely. When a service type is toggled off, all calls to that service type return a `ProviderUnavailableError` immediately, without making any outbound requests. This is useful during planned maintenance or when a provider is experiencing a prolonged outage. Feature toggles are managed through Django settings and can be updated at runtime through a management command.

**User-facing feedback** — When a degraded experience is unavoidable, the ESL provides structured error information that the frontend can use to display appropriate messages. For example, if CRM sync fails, the user sees "Your data has been saved locally and will be synced to [CRM] when the service is restored" rather than a generic error message. This is achieved by the `DeadLetterError` and `CircuitBreakerOpenError` exceptions, which include human-readable messages and estimated recovery times.

## Recovery Workflows

Recovery from provider failures follows a structured workflow that minimises manual intervention and ensures data consistency:

**Automatic recovery** — The circuit breaker's HALF_OPEN state handles the most common recovery scenario: a transient provider outage that resolves on its own. When the circuit transitions to HALF_OPEN, probe requests test the provider's health. Successful probes close the circuit and resume normal traffic. This automatic recovery handles 90%+ of provider outages without human intervention.

**Manual circuit reset** — For providers that are known to have recovered (e.g. after a scheduled maintenance window), operations staff can manually reset the circuit breaker using the `esl_reset_circuit_breaker` management command. This immediately transitions the circuit to CLOSED, allowing traffic to resume without waiting for the HALF_OPEN probe cycle.

**DLQ replay** — After a provider recovers, operations staff review the DLQ and replay any entries that accumulated during the outage. The `esl_replay_dlq` management command supports bulk replay with filtering by service type, provider, and date range. Replayed operations are processed in order, with idempotency checks to prevent duplicates.

**Data reconciliation** — For write operations that were queued or dead-lettered during an outage, a reconciliation process runs after recovery to compare the Digiland database with the external provider's state. Discrepancies are flagged for manual review. The reconciliation process is implemented as a management command that can be scheduled as a cron job or triggered on-demand.

**Post-incident review** — After any provider outage that triggers the circuit breaker or DLQ, a post-incident review is conducted to identify root causes, evaluate the effectiveness of the fallback strategy, and identify any data inconsistencies that require correction. Findings are documented in the incident management system and used to improve the ESL's resilience configuration.
