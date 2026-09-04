"""
Provider adapter registry for the External Services Layer.

Auto-discovers and maps adapter classes to service types.  Every adapter
is registered as a *dotted path* string so the module is only imported
when the adapter is actually requested — keeping start-up fast and
avoiding unnecessary dependency imports.

Usage::

    from external_services.adapters import get_adapter_class

    PaystackAdapter = get_adapter_class('payment', 'paystack')
    adapter = PaystackAdapter(api_key='...')

The registry is the single source of truth for which providers are
available in the platform.  Adding a new provider only requires
registering its path here; no other wiring is necessary.
"""

ADAPTER_REGISTRY = {
    'payment': {
        'paystack': 'external_services.adapters.payment.PaystackAdapter',
        'stripe': 'external_services.adapters.payment.StripeAdapter',
        'mpesa': 'external_services.adapters.payment.MPesaAdapter',
        'kcb': 'external_services.adapters.payment.KCBAdapter',
    },
    'email': {
        'smtp': 'external_services.adapters.email.SMTPAdapter',
        'sendgrid': 'external_services.adapters.email.SendGridAdapter',
    },
    'sms': {
        'africas_talking': 'external_services.adapters.sms.AfricasTalkingAdapter',
    },
    'push_notification': {
        'firebase': 'external_services.adapters.push.FirebaseAdapter',
    },
    'storage': {
        's3': 'external_services.adapters.storage.S3Adapter',
        'r2': 'external_services.adapters.storage.R2Adapter',
        'minio': 'external_services.adapters.storage.MinIOAdapter',
    },
    'ai': {
        'openai': 'external_services.adapters.ai.OpenAIAdapter',
        'anthropic': 'external_services.adapters.ai.AnthropicAdapter',
    },
    'identity': {
        'google': 'external_services.adapters.identity.GoogleOAuthAdapter',
        'github': 'external_services.adapters.identity.GitHubOAuthAdapter',
        'microsoft': 'external_services.adapters.identity.MicrosoftOAuthAdapter',
    },
    'search': {
        'elasticsearch': 'external_services.adapters.search.ElasticsearchAdapter',
    },
    'analytics': {
        'posthog': 'external_services.adapters.analytics.PostHogAdapter',
    },
    'maps': {
        'google_maps': 'external_services.adapters.maps.GoogleMapsAdapter',
    },
    'fraud_detection': {
        'internal': 'external_services.adapters.fraud_detection.InternalFraudAdapter',
    },
}


def get_adapter_class(service_type: str, provider_name: str):
    """Lazy-load and return an adapter class from the registry.

    Args:
        service_type: Category of service (e.g. ``"payment"``, ``"email"``).
        provider_name: Specific provider (e.g. ``"paystack"``, ``"stripe"``).

    Returns:
        The adapter **class** (not an instance).

    Raises:
        ValueError: If the service_type/provider_name combination is not
            registered.
    """
    import importlib

    adapters = ADAPTER_REGISTRY.get(service_type, {})
    class_path = adapters.get(provider_name)
    if not class_path:
        raise ValueError(
            f"No adapter registered for {service_type}/{provider_name}"
        )
    module_path, class_name = class_path.rsplit('.', 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def list_adapters() -> dict:
    """Return a shallow copy of the full registry mapping.

    Useful for admin dashboards or diagnostics.
    """
    return dict(ADAPTER_REGISTRY)
