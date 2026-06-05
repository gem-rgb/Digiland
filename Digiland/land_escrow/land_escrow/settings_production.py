"""
Production settings for the Digiland land_escrow project.

Override the base development settings with secure, production-grade values.
All sensitive values are pulled from environment variables via python-decouple.

Usage:
    DJANGO_SETTINGS_MODULE=land_escrow.settings_production
"""

import os
from decouple import config

from .settings import *  # noqa: F401,F403

# ── Security ──────────────────────────────────────────────────────────────────
DEBUG = False

SECRET_KEY = config("SECRET_KEY")  # No default — must be set in prod

ALLOWED_HOSTS = [
    h.strip()
    for h in config("ALLOWED_HOSTS", default="").split(",")
    if h.strip()
]

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in config("CSRF_TRUSTED_ORIGINS", default="").split(",")
    if o.strip()
]

# ── SSL / TLS ─────────────────────────────────────────────────────────────────
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# HSTS — only enable once you are confident TLS is stable
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True, cast=bool
)
SECURE_HSTS_PRELOAD = config("SECURE_HSTS_PRELOAD", default=True, cast=bool)

# ── Database — PostgreSQL ─────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="digiland"),
        "USER": config("DB_USER", default="digiland"),
        "PASSWORD": config("DB_PASSWORD", default=""),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
        "CONN_MAX_AGE": config("DB_CONN_MAX_AGE", default=60, cast=int),
        "OPTIONS": {
            "sslmode": config("DB_SSL_MODE", default="prefer"),
        },
    }
}

# ── Cache — Redis ─────────────────────────────────────────────────────────────
REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "digiland",
        "TIMEOUT": 300,
        "OPTIONS": {
            "CLIENT_CLASS": "django.core.cache.backends.redis.RedisCacheClient",
        },
    }
}

# ── Celery — Redis broker ────────────────────────────────────────────────────
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_ALWAYS_EAGER = config("CELERY_TASK_ALWAYS_EAGER", default=False, cast=bool)
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000
CELERY_WORKER_PREFETCH_MULTIPLIER = 4
CELERY_TASK_SOFT_TIME_LIMIT = 300
CELERY_TASK_TIME_LIMIT = 600

# ── Elasticsearch (optional) ─────────────────────────────────────────────────
ELASTICSEARCH_DSL = {
    "default": {
        "hosts": config("ELASTICSEARCH_URL", default=""),
    }
}
# Only enable Elasticsearch when a URL is configured
if not ELASTICSEARCH_DSL["default"]["hosts"]:
    ELASTICSEARCH_DSL = None

# ── REST Framework — Production profile ───────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/hour",
        "user": "300/hour",
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_EXCEPTION_HANDLER": "rest_framework.views.exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# ── Email — SMTP in production ────────────────────────────────────────────────
# Production MUST use authenticated SMTP for real email delivery.
# The dev default (console backend) is overridden here.
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", cast=int, default=587)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")  # MUST be set in prod
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")  # MUST be set in prod
EMAIL_USE_TLS = config("EMAIL_USE_TLS", cast=bool, default=True)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", cast=bool, default=False)

# The "From" address for outgoing emails — must be a real, deliverable address.
# Falls back to EMAIL_HOST_USER if not explicitly set, then to a safe default.
DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL",
    default="",
) or config(
    "EMAIL_HOST_USER",
    default="",
) or "noreply@digiland.co.ke"
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# ── CORS — restricted origins in production ───────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in config("CORS_ALLOWED_ORIGINS", default="").split(",")
    if o.strip()
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS',
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-request-id',
    'x-mpesa-secret',
]

# M-PESA callback secret — MUST be set in production
MPESA_CALLBACK_SECRET = config('MPESA_CALLBACK_SECRET', default='')

# ── Stripe API Keys ──────────────────────────────────────────────────────────
STRIPE_PUBLIC_KEY = config("STRIPE_PUBLIC_KEY", default="")
STRIPE_SECRET_KEY = config("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = config("STRIPE_WEBHOOK_SECRET", default="")

# ── Logging — file handlers for production ────────────────────────────────────
LOG_DIR = config("LOG_DIR", default="/var/log/digiland")
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[%(asctime)s] %(levelname)s %(name)s request_id=%(request_id)s %(process)d %(thread)d %(message)s",
        },
        "simple": {
            "format": "[%(asctime)s] %(levelname)s %(message)s",
        },
        "json": {
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(request_id)s %(process)d %(message)s",
        },
    },
    "filters": {
        "request_id": {
            "()": "core.log_filters.RequestIDFilter",
        },
        "pii_scrubber": {
            "()": "core.log_filters.PIIScrubberFilter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "filters": ["request_id", "pii_scrubber"],
        },
        "file_general": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "digiland.log"),
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 10,
            "formatter": "verbose",
            "filters": ["request_id", "pii_scrubber"],
        },
        "file_errors": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "errors.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 10,
            "formatter": "verbose",
            "level": "ERROR",
            "filters": ["request_id", "pii_scrubber"],
        },
        "file_celery": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "celery.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
            "filters": ["request_id", "pii_scrubber"],
        },
    },
    "root": {
        "handlers": ["console", "file_general"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file_general", "file_errors"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["file_errors"],
            "level": "ERROR",
            "propagate": False,
        },
        "core": {
            "handlers": ["console", "file_general", "file_errors"],
            "level": "INFO",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console", "file_celery"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ── Sentry Integration ────────────────────────────────────────────────────────
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration(), CeleryIntegration()],
            traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
            environment=SENTRY_ENVIRONMENT,
            send_default_pii=False,  # SECURITY: Never send PII to Sentry
        )
    except ImportError:
        pass  # sentry-sdk not installed, skip initialization
