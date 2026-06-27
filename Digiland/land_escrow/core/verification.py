"""Shared helpers for email verification and pending-verification sessions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta
from hashlib import sha256
from typing import Any, Optional
import secrets
import urllib.parse

from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import logout as auth_logout
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime


PENDING_VERIFICATION_SESSION_KEY = "pending_verification"


def _pending_session_ttl() -> int:
    return getattr(settings, "EMAIL_VERIFICATION_PENDING_SESSION_AGE", 3 * 24 * 60 * 60)


def _verification_token_ttl() -> int:
    return getattr(settings, "EMAIL_VERIFICATION_TOKEN_TTL_SECONDS", 24 * 60 * 60)


def _password_reset_token_ttl() -> int:
    return getattr(settings, "PASSWORD_RESET_TOKEN_TTL_SECONDS", 20 * 60)


def _resend_cooldown_seconds() -> int:
    return getattr(settings, "EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS", 60)


def _daily_resend_limit() -> int:
    return getattr(settings, "EMAIL_VERIFICATION_RESEND_DAILY_LIMIT", 5)


def _token_digest(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _iso_now() -> str:
    return timezone.now().isoformat()


def _parse_iso(value: str):
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


@dataclass(slots=True)
class PendingVerificationSession:
    user_id: str
    email: str
    verification_status: str = "pending"
    created_at: str = ""
    expires_at: str = ""
    flow: str = "api"
    resend_count: int = 0
    last_sent_at: str = ""
    last_seen_at: str = ""
    last_verified_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PendingVerificationSession":
        return cls(
            user_id=str(data.get("user_id", "")),
            email=str(data.get("email", "")),
            verification_status=str(data.get("verification_status", "pending")),
            created_at=str(data.get("created_at", "")),
            expires_at=str(data.get("expires_at", "")),
            flow=str(data.get("flow", "api")),
            resend_count=int(data.get("resend_count", 0) or 0),
            last_sent_at=str(data.get("last_sent_at", "")),
            last_seen_at=str(data.get("last_seen_at", "")),
            last_verified_at=str(data.get("last_verified_at", "")),
        )

    @classmethod
    def from_request(cls, request) -> "PendingVerificationSession | None":
        data = request.session.get(PENDING_VERIFICATION_SESSION_KEY)
        if not data:
            return None
        try:
            session = cls.from_dict(data)
        except Exception:
            return None
        if session.is_expired():
            return None
        return session

    def is_expired(self) -> bool:
        expires_at = _parse_iso(self.expires_at)
        if expires_at is None:
            return False
        return timezone.now() >= expires_at

    def refresh(self) -> None:
        now = timezone.now()
        self.last_seen_at = now.isoformat()
        self.expires_at = (now + timedelta(seconds=_pending_session_ttl())).isoformat()

    def mark_verified(self) -> None:
        now = timezone.now().isoformat()
        self.verification_status = "verified"
        self.last_verified_at = now


def _create_pending_session_payload(user, *, flow: str, previous: Optional[PendingVerificationSession] = None) -> PendingVerificationSession:
    now = timezone.now()
    expires_at = now + timedelta(seconds=_pending_session_ttl())
    if previous and str(previous.user_id) == str(user.id):
        created_at = previous.created_at or now.isoformat()
        resend_count = previous.resend_count
        last_sent_at = previous.last_sent_at or now.isoformat()
    else:
        created_at = now.isoformat()
        resend_count = 0
        last_sent_at = now.isoformat()

    return PendingVerificationSession(
        user_id=str(user.id),
        email=str(user.email),
        verification_status="pending",
        created_at=created_at,
        expires_at=expires_at.isoformat(),
        flow=flow,
        resend_count=resend_count,
        last_sent_at=last_sent_at,
        last_seen_at=now.isoformat(),
    )


def start_pending_verification_session(request, user, *, flow: str = "api") -> PendingVerificationSession:
    """Create or refresh a browser session for email verification."""
    existing = PendingVerificationSession.from_request(request)
    pending = _create_pending_session_payload(user, flow=flow, previous=existing)

    request.session.cycle_key()
    request.session[PENDING_VERIFICATION_SESSION_KEY] = pending.to_dict()
    request.session.set_expiry(_pending_session_ttl())
    request.session.modified = True
    return pending


def get_pending_verification_session(request) -> PendingVerificationSession | None:
    session = PendingVerificationSession.from_request(request)
    if not session:
        if PENDING_VERIFICATION_SESSION_KEY in request.session:
            request.session.pop(PENDING_VERIFICATION_SESSION_KEY, None)
            request.session.modified = True
        return None
    return session


def refresh_pending_verification_session(request) -> PendingVerificationSession | None:
    session = get_pending_verification_session(request)
    if not session:
        return None
    session.refresh()
    request.session[PENDING_VERIFICATION_SESSION_KEY] = session.to_dict()
    request.session.set_expiry(_pending_session_ttl())
    request.session.modified = True
    return session


def update_pending_verification_session(request, *, status: str | None = None, email: str | None = None) -> PendingVerificationSession | None:
    session = get_pending_verification_session(request)
    if not session:
        return None
    if status:
        session.verification_status = status
    if email:
        session.email = email
    session.refresh()
    request.session[PENDING_VERIFICATION_SESSION_KEY] = session.to_dict()
    request.session.set_expiry(_pending_session_ttl())
    request.session.modified = True
    return session


def clear_pending_verification_session(request) -> None:
    request.session.pop(PENDING_VERIFICATION_SESSION_KEY, None)
    request.session.modified = True


def token_cache_key(namespace: str, token: str) -> str:
    return f"{namespace}:token:{_token_digest(token)}"


def current_token_cache_key(namespace: str, user_id: str) -> str:
    return f"{namespace}:current:{user_id}"


def issue_one_time_token(
    namespace: str,
    payload: dict[str, Any],
    *,
    ttl_seconds: int,
    track_latest: bool = True,
) -> str:
    token = secrets.token_urlsafe(48)
    cache.set(token_cache_key(namespace, token), payload, timeout=ttl_seconds)
    if track_latest and payload.get("user_id"):
        cache.set(current_token_cache_key(namespace, str(payload["user_id"])), _token_digest(token), timeout=ttl_seconds)
    return token


def consume_one_time_token(namespace: str, token: str, *, user_id: str | None = None) -> dict[str, Any] | None:
    digest = _token_digest(token)
    payload = cache.get(f"{namespace}:token:{digest}")
    legacy_key = f"{namespace}:{token}"
    legacy_payload = None
    if payload is None:
        legacy_payload = cache.get(legacy_key)
        payload = legacy_payload

    if not payload:
        return None

    if user_id:
        current_digest = cache.get(current_token_cache_key(namespace, str(user_id)))
        if current_digest and current_digest != digest:
            return None

    cache.delete(f"{namespace}:token:{digest}")
    if legacy_payload is not None:
        cache.delete(legacy_key)
    if user_id:
        cache.delete(current_token_cache_key(namespace, str(user_id)))
    return payload


def build_verification_link(request, token: str) -> str:
    """Return a browser-facing verification URL."""
    base_url = request.build_absolute_uri(reverse("account_verification_pending")).split("?", 1)[0]
    return f"{base_url}?token={urllib.parse.quote(token)}"


def build_password_reset_link(request, token: str) -> str:
    """Return the current frontend reset URL, falling back to the host app."""
    frontend_url = getattr(settings, "FRONTEND_URL", "").strip()
    if frontend_url:
        return f"{frontend_url.rstrip('/')}/reset-password?token={urllib.parse.quote(token)}"
    return f"{request.build_absolute_uri('/').rstrip('/')}/reset-password?token={urllib.parse.quote(token)}"


def get_post_verification_redirect_url(user) -> str:
    """Mirror the browser redirect logic used after verification/login."""
    from django.urls import reverse

    if getattr(user, "role", None) == "Buyer" and not getattr(user, "buyer_account_type", None):
        return reverse("frontend:buyer_account_choice")
    if getattr(user, "role", None) == "Agent":
        return reverse("frontend:agent_signup_complete")
    if getattr(user, "role", None) == "Admin":
        return reverse("frontend:agent_dashboard")
    return reverse("frontend:parcel_list")


def get_email_verification_login_redirect_url() -> str:
    """Send users back to the public login page after email verification."""
    return reverse("account_login")


def promote_verified_session(request, user, *, backend: str = "core.auth_backends.EmailOrUsernameModelBackend") -> str:
    """Finalize email verification and send the browser back to login."""
    del backend
    clear_pending_verification_session(request)
    auth_logout(request)
    return get_email_verification_login_redirect_url()


def verification_resend_allowed(user_id: str) -> tuple[bool, int]:
    """Return whether a resend is allowed and the retry-after seconds."""
    cooldown_key = f"emailverify:cooldown:{user_id}"
    cooldown = cache.get(cooldown_key)
    if cooldown:
        return False, int(cooldown.get("retry_after", _resend_cooldown_seconds()))

    daily_key = f"emailverify:daily:{user_id}"
    daily = cache.get(daily_key, 0)
    if daily >= _daily_resend_limit():
        return False, 24 * 60 * 60

    return True, 0


def mark_verification_resend(user_id: str) -> None:
    cooldown_key = f"emailverify:cooldown:{user_id}"
    daily_key = f"emailverify:daily:{user_id}"
    cache.set(cooldown_key, {"retry_after": _resend_cooldown_seconds()}, timeout=_resend_cooldown_seconds())
    cache.set(daily_key, cache.get(daily_key, 0) + 1, timeout=24 * 60 * 60)


def queue_email_message(
    subject: str,
    body: str,
    from_email: str,
    recipient_list: list[str],
    *,
    html_message: str | None = None,
    reply_to: list[str] | None = None,
    headers: dict[str, str] | None = None,
) -> None:
    """Enqueue an email for asynchronous delivery."""
    from .tasks import send_email_message_task

    send_email_message_task.delay(
        subject=subject,
        body=body,
        from_email=from_email,
        recipient_list=recipient_list,
        html_message=html_message,
        reply_to=reply_to or [],
        headers=headers or {},
    )
