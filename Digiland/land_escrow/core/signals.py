"""Signals for email verification lifecycle."""

from __future__ import annotations

import logging

from allauth.account.signals import email_confirmed, user_signed_up
from django.dispatch import receiver

from .verification import clear_pending_verification_session, start_pending_verification_session

logger = logging.getLogger(__name__)


def _sociallogin_has_verified_email(sociallogin) -> bool:
    """Return True when the provider has already verified the user's email."""
    if not sociallogin:
        return False

    email_addresses = getattr(sociallogin, "email_addresses", []) or []
    if any(getattr(address, "verified", False) for address in email_addresses):
        return True

    account = getattr(sociallogin, "account", None)
    extra_data = getattr(account, "extra_data", {}) or {}
    return bool(extra_data.get("email_verified") or extra_data.get("verified_email"))


@receiver(user_signed_up)
def on_user_signed_up(request, user, sociallogin=None, **kwargs):
    """Create the pending verification session for allauth signups."""
    verified_social_email = _sociallogin_has_verified_email(sociallogin)

    if verified_social_email:
        if not getattr(user, "is_email_verified", False):
            user.is_email_verified = True
            user.save(update_fields=["is_email_verified"])

        try:
            from .auth_views import _sync_allauth_email_address

            _sync_allauth_email_address(user, email=getattr(user, "email", ""), verified=True)
        except Exception:
            logger.exception("Failed to sync verified social email for %s", getattr(user, "email", ""))
        return

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
