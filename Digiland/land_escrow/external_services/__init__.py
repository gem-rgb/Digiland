"""
External Services Layer (ESL) - Digiland Platform
===================================================

The single integration point between the application and all third-party systems.

Architecture Principles:
- No application component directly communicates with external services
- All communication passes through this layer
- Providers are abstracted behind interfaces
- Provider swapping requires no business logic changes
- Circuit breakers and retries function transparently
- Full observability on every external request

Supported Provider Categories:
- Payment Providers (Paystack, Stripe, M-Pesa/Daraja, KCB Bank)
- Email Providers (SMTP, SendGrid, AWS SES)
- SMS Providers (Twilio, Africa's Talking)
- Push Notification Providers (Firebase, OneSignal)
- Cloud Storage Providers (AWS S3, Cloudflare R2, GCS, Azure Blob, MinIO)
- AI Providers (OpenAI, Anthropic, Google Gemini, Azure OpenAI)
- Analytics Platforms (Google Analytics, Mixpanel, PostHog)
- Identity Providers (Google OAuth, GitHub OAuth, Microsoft OAuth)
- Maps & Geolocation Services (Google Maps, Mapbox)
- Search Providers (Elasticsearch, Algolia)
- CRM Systems (HubSpot, Salesforce)
- ERP Systems (SAP, Odoo)
- Accounting Systems (QuickBooks, Xero)
- Fraud Detection Systems (Sift, Signifyd)
- Webhook Consumers (Generic framework)

Usage:
    from external_services import get_service

    # Get a payment service
    payment_service = get_service('payment')
    result = payment_service.charge(amount=1000, currency='KES', ...)

    # Get an email service
    email_service = get_service('email')
    email_service.send(to='user@example.com', template='welcome', context={...})
"""

__version__ = '1.0.0'
__all__ = [
    'get_service',
    'ServiceRegistry',
    'ExternalServiceError',
    'ProviderUnavailableError',
    'CircuitBreakerOpenError',
    'RateLimitExceededError',
]

from .registry import ServiceRegistry
from .exceptions import (
    ExternalServiceError,
    ProviderUnavailableError,
    CircuitBreakerOpenError,
    RateLimitExceededError,
)

# Global registry instance
_registry = ServiceRegistry()


def get_service(service_type: str, provider_name: str = None):
    """
    Get an external service instance by type and optional provider name.

    Args:
        service_type: The category of service (e.g., 'payment', 'email', 'sms')
        provider_name: Optional specific provider (e.g., 'paystack', 'stripe')

    Returns:
        An instance of the requested service

    Raises:
        ExternalServiceError: If the service type or provider is not registered
    """
    return _registry.get_service(service_type, provider_name)


def register_provider(service_type: str, provider_name: str, provider_class, config: dict = None):
    """
    Register a provider implementation for a service type.

    Args:
        service_type: The category of service
        provider_name: The specific provider name
        provider_class: The provider class (must implement the appropriate interface)
        config: Optional configuration dictionary
    """
    _registry.register(service_type, provider_name, provider_class, config)


def get_registry() -> ServiceRegistry:
    """Get the global service registry instance."""
    return _registry


default_app_config = 'external_services.apps.ExternalServicesConfig'
