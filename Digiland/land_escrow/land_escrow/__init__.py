"""Digiland land_escrow project — Celery app registration."""

# This will make sure the Celery app is always imported when
# Django starts so that shared_task will find it.
from land_escrow.celery import app as celery_app  # noqa: F401

__all__ = ("celery_app",)
