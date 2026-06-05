"""
ESL Provider Implementations
=============================

This sub-package contains all concrete provider implementations.  Each module
corresponds to a service type and exposes one or more provider classes.

The :func:`~external_services.registry.auto_register_providers` function
reads ``settings.EXTERNAL_SERVICES`` and imports the classes listed there,
so this package does **not** auto-import every module at start-up.  Instead,
individual provider modules are imported on demand based on configuration.

Available service-type modules (to be implemented):

* :mod:`~external_services.providers.payment` — Paystack, Stripe, M-Pesa/Daraja, KCB
* :mod:`~external_services.providers.email` — SMTP, SendGrid, AWS SES
* :mod:`~external_services.providers.sms` — Twilio, Africa's Talking
* :mod:`~external_services.providers.push` — Firebase, OneSignal
* :mod:`~external_services.providers.storage` — AWS S3, Cloudflare R2, MinIO
* :mod:`~external_services.providers.ai` — OpenAI, Anthropic, Gemini
* :mod:`~external_services.providers.search` — Elasticsearch, Algolia
* :mod:`~external_services.providers.analytics` — PostHog, Mixpanel
* :mod:`~external_services.providers.identity` — Google OAuth, GitHub OAuth
* :mod:`~external_services.providers.maps` — Google Maps, Mapbox
* :mod:`~external_services.providers.fraud` — Sift, Signifyd
* :mod:`~external_services.providers.webhook` — Generic webhook framework
"""
