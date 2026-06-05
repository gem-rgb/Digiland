"""
Celery application configuration for the Digiland land_escrow project.

This module initialises the Celery app, loads configuration from Django
settings, and auto-discovers task modules in every installed app.
"""

import os

from celery import Celery

# Set the default Django settings module for the Celery program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "land_escrow.settings")

app = Celery("land_escrow")

# Read all CELERY_* prefixed settings from Django's settings module.
# namespace="CELERY" means Celery looks for keys like CELERY_BROKER_URL, etc.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py in every installed Django app.
app.autodiscover_tasks()


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    Register periodic tasks via Celery Beat.

    For production, use django-celery-beat's DatabaseScheduler which reads
    schedules from the Django admin instead of this hard-coded list.
    These entries are only used as a fallback / development convenience.
    """
    from django.conf import settings

    # Only register these when NOT using the database scheduler
    if getattr(settings, "CELERY_BEAT_SCHEDULER", None) != "django_celery_beat.schedulers.DatabaseScheduler":
        # Promotion & ad maintenance — every 30 minutes
        sender.add_periodic_task(1800, expire_promotions.s(), name="expire-promotions")
        sender.add_periodic_task(1800, deactivate_expired_ads.s(), name="deactivate-expired-ads")
        sender.add_periodic_task(1800, deactivate_budget_exhausted_ads.s(), name="deactivate-budget-exhausted-ads")
        sender.add_periodic_task(1800, process_popup_ad_billing.s(), name="process-popup-ad-billing")

        # Plan lifecycle — hourly
        sender.add_periodic_task(3600, auto_renew_expiring_plans.s(), name="auto-renew-expiring-plans")
        sender.add_periodic_task(3600, expire_expired_plans.s(), name="expire-expired-plans")

        # Buyer profiles & fraud — every 6 hours
        sender.add_periodic_task(21600, update_buyer_profiles.s(), name="update-buyer-profiles")
        sender.add_periodic_task(21600, calculate_fraud_scores.s(), name="calculate-fraud-scores")

        # Analytics — daily at midnight
        sender.add_periodic_task(86400, generate_daily_analytics.s(), name="generate-daily-analytics")


# Lazy imports to avoid circular dependencies at module level
def expire_promotions():
    from core.tasks import expire_promotions as _task
    return _task.delay()


def deactivate_expired_ads():
    from core.tasks import deactivate_expired_ads as _task
    return _task.delay()


def deactivate_budget_exhausted_ads():
    from core.tasks import deactivate_budget_exhausted_ads as _task
    return _task.delay()


def auto_renew_expiring_plans():
    from core.tasks import auto_renew_expiring_plans as _task
    return _task.delay()


def update_buyer_profiles():
    from core.tasks import update_buyer_profiles as _task
    return _task.delay()


def calculate_fraud_scores():
    from core.tasks import calculate_fraud_scores as _task
    return _task.delay()


def expire_expired_plans():
    from core.tasks import expire_expired_plans as _task
    return _task.delay()


def generate_daily_analytics():
    from core.tasks import generate_daily_analytics as _task
    return _task.delay()


def process_popup_ad_billing():
    from core.tasks import process_popup_ad_billing as _task
    return _task.delay()
