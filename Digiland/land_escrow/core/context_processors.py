"""Template context processors for auth state."""

from __future__ import annotations

from django.urls import reverse

from .verification import get_pending_verification_session


def pending_verification(request):
    session = get_pending_verification_session(request)
    return {
        "pending_verification": {
            "active": bool(session),
            "email": session.email if session else "",
            "verification_status": session.verification_status if session else "",
            "created_at": session.created_at if session else "",
            "expires_at": session.expires_at if session else "",
            "flow": session.flow if session else "",
            "resend_count": session.resend_count if session else 0,
            "status_url": reverse("auth-email-verification-status"),
            "resend_url": reverse("auth-email-verification-resend"),
            "change_email_url": reverse("auth-email-verification-change"),
            "logout_url": reverse("auth-email-verification-logout"),
            "verification_page_url": reverse("account_verification_pending"),
        }
    }
