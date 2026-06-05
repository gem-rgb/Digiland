# Provider Abstraction

## Interface Design

The ESL's provider abstraction is built on a hierarchy of abstract base classes (ABCs) that define the contract between the application layer and external service providers. The root of the hierarchy is `ExternalProvider`, which establishes the four lifecycle methods that every provider must implement: `connect`, `disconnect`, `health_check`, and `validate_configuration`. These methods form the minimal viable contract — they ensure that the registry can manage any provider's lifecycle without knowing its type.

On top of `ExternalProvider`, the ESL defines service-type-specific interfaces: `PaymentProvider`, `EmailProvider`, `SmsProvider`, `CRMProviderInterface`, `ERPProviderInterface`, `AccountingProviderInterface`, and so on. Each of these interfaces adds the domain-specific methods that providers of that type must implement. This design follows the Interface Segregation Principle — a payment provider does not need to implement email methods, and a CRM adapter does not need to implement payment methods.

Every method in every interface returns a `ProviderResponse` object. This standardised return type ensures that callers always have a uniform interface regardless of the underlying provider. The `ProviderResponse` carries a `success` flag, a `data` payload, an optional `error` message, the `provider` name, a unique `request_id` for tracing, the `latency_ms` of the call, and an extensible `metadata` dict for provider-specific extras. This design eliminates the need for callers to handle provider-specific response formats.

The interface design also mandates that all methods are fully typed with Python type hints and documented with comprehensive docstrings. This is not merely a style preference — it enables static analysis tools (mypy, pyright) to catch signature mismatches at development time, and it allows IDEs to provide autocomplete and inline documentation. Every method parameter, return type, and exception is documented so that developers implementing a new adapter have a clear specification to work against.

The interfaces use `**kwargs` strategically to allow provider-specific options without polluting the shared contract. For example, `PaymentProvider.initialize_payment` accepts `amount`, `currency`, and `reference` as required parameters, but also accepts `**kwargs` for provider-specific options like `email` (Paystack), `idempotency_key` (Stripe), or `phone_number` (M-Pesa). This ensures that the shared interface remains stable while still allowing adapters to expose the full power of their underlying provider.

## Adapter Pattern

The adapter pattern is the foundational design pattern of the ESL. Each concrete adapter class wraps a specific external service provider and translates between the ESL's standardised interface and the provider's proprietary API. The adapter owns the full lifecycle of the provider interaction, from authentication to request construction to response parsing to error translation.

The adapter pattern in the ESL follows a strict template that every adapter must adhere to:

1. **Class declaration** — The adapter extends the appropriate service-type interface (e.g. `CRMProviderInterface`) and sets a `PROVIDER_NAME` class attribute. The `__init__` method reads configuration from Django settings and initialises internal state (sessions, tokens, etc.).

2. **Lifecycle methods** — The adapter implements `connect` (establish sessions, obtain tokens), `disconnect` (release resources), `health_check` (lightweight probe), and `validate_configuration` (check settings). These methods follow a consistent error-handling pattern: they raise specific ESL exceptions rather than returning error codes or letting raw exceptions propagate.

3. **Domain methods** — The adapter implements each method defined by the service-type interface. Each method follows the same structure: measure start time, construct the provider request, send the request, measure elapsed time, parse the response, and return a `ProviderResponse` or raise an appropriate ESL exception.

4. **Error translation** — The adapter catches all provider-specific exceptions and translates them into the ESL exception hierarchy. HTTP 401 → `AuthenticationError`, HTTP 429 → `RateLimitExceededError`, timeout → `TimeoutError`, and all other errors → `ProviderResponseError`. This translation is always explicit — the adapter never lets a raw `requests.ConnectionError` or `json.JSONDecodeError` escape.

5. **Private helpers** — Adapters typically include private helper methods for authentication (e.g. `_authenticate`, `_refresh_access_token`), request construction (e.g. `_request`, `_api_url`), and data mapping. These helpers keep the public methods clean and focused on their domain responsibility.

The adapter pattern ensures that adding a new provider is a purely additive operation. No existing code needs to be modified — the developer creates a new adapter class, registers it in the adapter registry, and adds the necessary Django settings. The registry and factory functions handle the rest.

## Factory Pattern

The ESL uses the factory pattern extensively to decouple caller code from specific adapter classes. Each service category exposes a factory function (e.g. `create_crm_provider`, `create_erp_provider`, `create_accounting_provider`) that accepts a provider name string and returns an adapter instance. This design offers several important benefits:

- **Configuration-driven selection** — The choice of provider is determined by configuration (Django settings, environment variables) rather than by import statements. Deployments can switch from Salesforce to HubSpot by changing a single setting value, without modifying any application code.

- **Lazy instantiation** — Factory functions return instances that are initialised but not yet connected. The connection is established lazily on first use (or eagerly during start-up if preferred). This keeps start-up fast and avoids unnecessary network calls to providers that may not be used in a given request path.

- **Validation at creation time** — The factory function validates the provider name against the registry of known providers and raises a `ConfigurationError` if an unknown name is provided. This catches configuration typos at start-up rather than at runtime.

- **Consistent interface** — Regardless of which provider is selected, the returned instance always implements the same interface. Callers can write code against `CRMProviderInterface` without knowing or caring whether the underlying provider is Salesforce, HubSpot, or Zoho.

The factory functions also serve as documentation — they enumerate the supported providers in their docstrings and error messages, making it easy for developers to discover what providers are available. The `list_crm_providers`, `list_erp_providers`, and `list_accounting_providers` helper functions provide a programmatic way to query the registry.

At the global registry level, the `get_adapter_class` function in `external_services.adapters` provides a similar factory capability using dotted-path strings. This allows the registry to import adapter classes on demand, keeping start-up fast and avoiding unnecessary dependency imports.

## Registry

The `ServiceRegistry` is the central authority for provider management in the ESL. It is a thread-safe singleton that maps `(service_type, provider_name)` pairs to provider classes and instances. The registry supports the following operations:

- **Registration** — Providers are registered with `registry.register(service_type, provider_name, provider_class, config, is_default, priority)`. Registration is typically done automatically by the `auto_register_providers` function, which reads the `EXTERNAL_SERVICES` setting from Django configuration.

- **Lookup** — Providers are retrieved with `registry.get_service(service_type, provider_name, use_fallback)`. When `provider_name` is omitted, the default provider is returned. When `use_fallback` is `True` (the default), the registry walks the fallback chain if the primary provider is unhealthy.

- **Default management** — Each service type has a default provider, set explicitly with `registry.set_default` or implicitly when the first provider for a type is registered. The default is used when callers do not specify a provider name.

- **Fallback chains** — The registry maintains an ordered list of providers for each service type, sorted by priority. When the primary provider's circuit breaker is OPEN, the registry tries each provider in the chain until a healthy one is found. Fallback chains are rebuilt automatically when providers are registered, unregistered, or reprioritised.

- **Health checking** — The `registry.health_check` method probes all registered providers (or a specific service type) and returns a structured dict of health results. This is used by monitoring dashboards and automated alerting systems.

- **Thread safety** — All registry mutations are protected by a `threading.RLock`, ensuring that concurrent registration and lookup operations are safe. This is critical in a Django application that may handle requests in multiple threads.

The registry is designed to be the single source of truth for provider availability. Application code should never hold references to provider instances across requests — instead, it should call `get_service` each time to ensure it gets a healthy, up-to-date instance.

## Configuration-Driven Selection

The ESL's configuration-driven selection mechanism allows the platform to switch providers, adjust priorities, and modify fallback chains without changing any application code. All provider configuration is externalised into Django settings, environment variables, and (in advanced deployments) a dynamic configuration service.

The primary configuration mechanism is the `EXTERNAL_SERVICES` setting in Django. This is a nested dict that maps service types to provider configurations. Each provider entry specifies the Python class path, configuration parameters, priority, and whether it is the default. The `auto_register_providers` function reads this setting at start-up and registers all declared providers.

Configuration-driven selection is particularly valuable in multi-tenant deployments where different tenants may require different providers. For example, a Kenyan brokerage might use Paystack and M-Pesa for payments, while a US-based firm might use Stripe and ACH. The configuration system allows per-tenant provider overrides without forking the codebase.

The configuration system also supports environment-specific settings. In development, the ESL may use sandbox API keys, lower rate limits, and relaxed timeout thresholds. In production, the same code uses live API keys, production rate limits, and tighter timeouts. This is handled through Django's standard settings hierarchy (local_settings.py, environment variables, etc.) without any ESL-specific configuration layer.

At runtime, the configuration can be partially overridden through the `config` parameter passed to factory functions and the registry's `register` method. This allows for dynamic reconfiguration in response to provider outages — for example, an operations script can unregister a failing provider and promote the fallback to primary without restarting the application.
