# Integration Architecture

## System Overview

The External Services Layer (ESL) is the central integration hub for the Digiland real-estate escrow platform. It provides a unified, provider-agnostic interface between the core Digiland application and all external service providers. The ESL abstracts away the complexity of dealing with multiple third-party APIs, each with its own authentication mechanisms, data formats, rate limits, and failure modes. By introducing a clean separation between the business logic layer and the external service boundary, the ESL ensures that the core application remains decoupled from vendor-specific implementation details and can evolve independently of any single provider's roadmap or API changes.

The ESL is designed as a Django application module living under `land_escrow.external_services`. It follows a layered architecture with three principal tiers: the **adapter layer** (concrete provider implementations), the **base interface layer** (abstract contracts and shared data classes), and the **infrastructure layer** (circuit breakers, retry logic, rate limiting, observability, cost management, and the service registry). Each tier has well-defined responsibilities and communicates through typed interfaces, making the system both testable and extensible.

At runtime, the ESL is accessed through the `ServiceRegistry` singleton. Application code requests a service by type (e.g. `"payment"`, `"crm"`, `"accounting"`) and optionally by provider name (e.g. `"paystack"`, `"salesforce"`). The registry resolves the request to a concrete adapter instance, applying fallback logic if the primary provider is unhealthy. This design ensures that the rest of the Digiland codebase never imports adapter classes directly and never manages provider lifecycle — all of that is encapsulated within the ESL.

The ESL currently integrates with providers across twelve service categories: payment processing, email delivery, SMS delivery, push notifications, object storage, AI/LLM services, identity/OAuth, search indexing, analytics, maps/geolocation, fraud detection, and webhook delivery. The three new categories — CRM, ERP, and accounting — expand the platform's ability to synchronise data with enterprise systems that real-estate brokerages and financial institutions already rely on.

## Data Flows

Data flows through the ESL in a consistent, well-instrumented pattern regardless of the service type or provider. The canonical flow begins when a caller in the core application or a background task invokes a method on a provider instance obtained from the registry. The ESL wraps this invocation with several cross-cutting concerns before the request reaches the external provider:

1. **Rate limiting** — The ESL checks its internal token-bucket or sliding-window rate limiter before allowing the request to proceed. If the limit has been exceeded, a `RateLimitExceededError` is raised immediately, avoiding wasted outbound calls.

2. **Circuit breaker evaluation** — The ESL consults the per-provider circuit breaker. If the circuit is in the OPEN state, the call is short-circuited and a `CircuitBreakerOpenError` is raised. If the circuit is in HALF_OPEN, a limited number of probe requests are allowed through to test recovery.

3. **Request construction** — The adapter translates the method arguments into the provider's wire format (HTTP request body, query parameters, headers). This is where Digiland's domain model is mapped to each provider's specific field names, data types, and conventions.

4. **Outbound call** — The adapter sends the request to the provider. A per-call timeout deadline is enforced. The ESL records the start time for latency measurement.

5. **Response processing** — The adapter receives the provider's response and maps it back to a standardised `ProviderResponse` object. All provider-specific error codes, HTTP status codes, and error messages are translated into ESL exception types (`AuthenticationError`, `ProviderResponseError`, `RateLimitExceededError`, etc.).

6. **Observability emission** — The ESL emits structured log entries, Prometheus metrics (latency histograms, error counters, active-request gauges), and OpenTelemetry spans for every call. A `CostRecord` is created for billable operations.

7. **Circuit breaker update** — Success or failure is reported to the circuit breaker, which updates its internal counters and may transition the circuit state.

For synchronous flows (payment verification, CRM contact creation), the caller receives the `ProviderResponse` directly. For asynchronous flows (webhook delivery, bulk email), the ESL enqueues the operation and returns a tracking ID. Inbound webhooks from providers follow a different path: they are received at the ESL's webhook endpoint, their signatures are verified, and the payload is transformed into an internal event that is published to the Django signal bus or a message queue for downstream processing.

## Trust Boundaries

The ESL enforces strict trust boundaries between the Digiland platform and external providers. No external entity is trusted by default; every inbound request must be authenticated and every outbound response must be validated. The trust boundaries are enforced at the following points:

- **Inbound webhooks** — All webhook payloads are verified using HMAC-SHA256 signature validation before any data is accepted. The signing secret is stored in Django settings and rotated periodically. Webhooks that fail verification are logged and discarded; they never reach the application layer.

- **Outbound API calls** — All outbound requests are made over TLS (HTTPS). Provider credentials (API keys, OAuth2 tokens) are stored in Django settings and never logged, exposed in error messages, or included in debug output. The ESL validates the TLS certificate chain and rejects connections to hosts with expired or self-signed certificates in production.

- **Data validation** — All data received from external providers is treated as untrusted. The ESL validates response schemas before passing data to the application layer. Unknown or malformed fields are stripped or logged as warnings, preventing injection of unexpected data into the Digiland domain model.

- **Configuration isolation** — Provider configuration (API keys, base URLs, timeouts) is isolated per provider instance. A misconfigured or compromised provider cannot affect the configuration of other providers. The ESL's `validate_configuration` method is called during start-up to catch configuration errors early.

- **Internal data boundary** — The ESL never exposes raw provider responses to the application layer. All responses are wrapped in `ProviderResponse` objects with standardised fields. Provider-specific metadata is confined to the `metadata` dict and is never automatically persisted to the database.

## Provider Responsibilities

Each provider adapter in the ESL has a well-defined set of responsibilities that go beyond simple API translation. A provider adapter is the single owner of all interactions with its external service, and it must fulfil the following obligations:

- **Lifecycle management** — The adapter must implement `connect`, `disconnect`, `health_check`, and `validate_configuration`. These methods allow the registry and operations teams to manage the provider's lifecycle without understanding its internals. The `connect` method should establish sessions, obtain tokens, and validate credentials. The `disconnect` method should release all resources gracefully.

- **Authentication and token management** — The adapter must handle all authentication concerns, including OAuth2 token refresh, session management, and credential rotation. Token refresh must be automatic and transparent to callers. If a token expires mid-session, the adapter must refresh it and retry the request once before raising an error.

- **Data mapping** — The adapter must translate between Digiland's domain model and the provider's data format in both directions. This includes field name mapping, type conversion (e.g. converting Decimal to float for JSON serialisation), and handling of provider-specific required fields that have no Digiland equivalent.

- **Error translation** — The adapter must catch all provider-specific exceptions and translate them into the ESL's exception hierarchy. HTTP status codes, provider error codes, and error messages must be mapped to the appropriate ESL exception type so that callers can handle errors uniformly.

- **Idempotency** — Where supported by the provider API, the adapter must pass idempotency keys to prevent duplicate operations on retry. The adapter should also be resilient to receiving duplicate responses from providers that lack idempotency guarantees.

- **Rate limit awareness** — The adapter must detect rate-limit responses (HTTP 429) from the provider and raise `RateLimitExceededError` with the `retry_after` value, allowing the ESL's retry infrastructure to back off appropriately.

- **Timeout enforcement** — The adapter must enforce per-call timeout deadlines and raise `TimeoutError` if the provider does not respond within the configured threshold. Different operations may have different timeout requirements (e.g. health checks should be fast, while report generation may need longer timeouts).

## Fallback Strategies

The ESL implements a multi-layered fallback strategy to maximise service availability even when individual providers experience outages. Fallback is handled at the registry level and at the application level:

- **Registry-level fallback chains** — Each service type has an ordered fallback chain determined by provider priority. When the primary provider's circuit breaker is OPEN, the registry automatically walks the chain to find a healthy provider. For example, if the primary payment provider (Paystack) is down, the registry will fall back to Stripe, then to M-Pesa, and finally to the internal escrow wallet adapter. Fallback decisions are logged at WARNING level for audit purposes.

- **Graceful degradation** — When all providers for a service type are unavailable, the ESL does not crash. Instead, it raises a `ProviderUnavailableError` with a descriptive message listing the exhausted fallback chain. The application layer is responsible for handling this gracefully — for example, by showing a user-friendly message, enqueuing the operation for later retry, or falling back to a manual process.

- **Stale data caching** — For read-only operations (e.g. retrieving a CRM contact or fetching a financial report), the ESL's caching layer can serve stale data when the provider is unreachable. The staleness threshold is configurable per service type. Cached responses are tagged with their original latency and a `served_from_cache` flag so that callers can make informed decisions about data freshness.

- **Asynchronous retry with DLQ** — For write operations that cannot be served by any provider, the ESL enqueues the operation in a persistent retry queue. If the operation fails after the maximum number of retries, it is moved to a dead-letter queue (DLQ) and a `DeadLetterError` is raised. Operations in the DLQ can be inspected and replayed by operations staff once the provider recovers.

- **Provider-specific fallbacks** — Some adapters implement their own internal fallback logic. For example, the CRM adapter may fall back from a real-time API call to a batch sync queue if the provider's API is returning transient errors. These provider-specific fallbacks are documented in each adapter's module docstring.

## SLA Expectations

The ESL defines service-level agreements (SLAs) for each service category. These SLAs are measured and reported through the observability infrastructure (Prometheus metrics, Grafana dashboards, and PagerDuty alerts):

| Service Category | Availability Target | Latency P99 | Error Rate Threshold |
|---|---|---|---|
| Payment | 99.95% | 5 seconds | 0.1% |
| Email | 99.9% | 3 seconds | 0.5% |
| SMS | 99.9% | 3 seconds | 0.5% |
| CRM | 99.5% | 10 seconds | 1.0% |
| ERP | 99.5% | 15 seconds | 1.0% |
| Accounting | 99.5% | 10 seconds | 1.0% |
| Storage | 99.99% | 2 seconds | 0.01% |
| AI | 99.0% | 30 seconds | 2.0% |

These SLA targets assume that the external provider itself is operating within its published SLA. When a provider experiences an outage that exceeds its own SLA, the ESL's fallback mechanism is expected to maintain the platform-level SLA by routing traffic to an alternative provider. SLA breaches are escalated to the on-call engineering team via PagerDuty within 5 minutes of detection. Monthly SLA reports are generated from Prometheus data and reviewed in the platform reliability review meeting.
