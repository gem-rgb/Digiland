"""Signals for email verification lifecycle."""

from __future__ import annotations

import logging

from allauth.account.signals import email_confirmed, user_signed_up
from django.dispatch import receiver

from .verification import clear_pending_verification_session, start_pending_verification_session

logger = logging.getLogger(__name__)


@receiver(user_signed_up)
def on_user_signed_up(request, user, **kwargs):
    """Create the pending verification session for allauth signups."""
    if not request:
        return

    try:
        start_pending_verification_session(request, user, flow="allauth")
    except Exception:
        logger.exception("Failed to create pending verification session for user %s", getattr(user, "email", ""))


@receiver(email_confirmed)
def on_email_confirmed(request, email_address, **kwargs):
    """Clear the pending verification session when the email is confirmed."""
    if not request:
        return

    try:
        clear_pending_verification_session(request)
    except Exception:
        logger.exception("Failed to clear pending verification session after email confirmation")

