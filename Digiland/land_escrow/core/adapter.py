import logging

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.urls import reverse
from django.shortcuts import redirect
from django.core.mail import send_mail

from .verification import (
    build_verification_link,
    get_email_verification_login_redirect_url,
    get_post_verification_redirect_url,
    issue_one_time_token,
    mark_verification_resend,
    verification_resend_allowed,
    start_pending_verification_session,
)

# Roles that are BANNED from the public /accounts/login/ route
STAFF_ROLES = {'Admin', 'Agent', 'Lawyer'}

logger = logging.getLogger(__name__)

class RoleBasedAccountAdapter(DefaultAccountAdapter):
    def get_from_email(self, request=None):
        """
        Prefer the authenticated SMTP login address when real email delivery
        is configured, so Gmail-based local testing does not send from the
        placeholder noreply address.
        """
        host_user = getattr(settings, "EMAIL_HOST_USER", "").strip()
        default_from = getattr(settings, "DEFAULT_FROM_EMAIL", "").strip()
        backend = getattr(settings, "EMAIL_BACKEND", "").lower()

        if host_user and ("smtp" in backend or default_from.lower().startswith(("noreply@", "no-reply@"))):
            return host_user

        return default_from or host_user or super().get_from_email()

    def _maybe_start_pending_session(self, request, user, *, flow: str) -> None:
        if request is None or not getattr(user, "is_authenticated", False):
            return
        try:
            start_pending_verification_session(request, user, flow=flow)
        except Exception:
            # Pending verification is a UX enhancement; do not break auth
            # if the session store has a transient issue.
            pass

    def _maybe_send_login_verification_email(self, request, user, *, flow: str) -> None:
        if request is None or not getattr(user, "is_authenticated", False):
            return

        allowed, _retry_after = verification_resend_allowed(str(user.id))
        if not allowed:
            return

        token = issue_one_time_token(
            "emailverify",
            {
                "user_id": str(user.id),
                "email": getattr(user, "email", ""),
                "source": flow,
            },
            ttl_seconds=getattr(settings, "EMAIL_VERIFICATION_TOKEN_TTL_SECONDS", 24 * 60 * 60),
        )
        verification_url = build_verification_link(request, token)

        try:
            send_mail(
                subject="Digiland - Verify Your Email",
                message=(
                    f"Click the following link to verify your email address: {verification_url}\n\n"
                    f"This link expires in 24 hours."
                ),
                from_email=self.get_from_email(request),
                recipient_list=[getattr(user, "email", "")],
                fail_silently=False,
            )
            mark_verification_resend(str(user.id))
        except Exception:
            logger.exception("Failed to send verification email during login for %s", getattr(user, "email", ""))

    def get_login_redirect_url(self, request):
        """
        Dynamically route users based on their selected role and onboarding status after login.
        """
        user = request.user
        if user.is_authenticated:
            if not getattr(user, "is_email_verified", False):
                self._maybe_start_pending_session(request, user, flow="allauth-login")
                self._maybe_send_login_verification_email(request, user, flow="allauth-login")
                return reverse("account_verification_pending")
            
            # Un-onboarded users (no role or is_onboarded=False) go to onboarding select-role
            if not user.role or not getattr(user, "is_onboarded", False):
                return reverse("frontend:onboarding_select_role")

            if user.role == 'Buyer':
                return reverse('frontend:buyer_dashboard')
            if user.role == 'Seller':
                return reverse('frontend:seller_dashboard')
            if user.role == 'Agent':
                # Agents should never reach here via public login (blocked in
                # pre_login). If they somehow do (e.g. direct API call),
                # send them to the signup-complete gate.
                return reverse('frontend:agent_signup_complete')
            if user.role == 'Admin':
                return '/admin/'
            return reverse('frontend:parcel_list')
        return super().get_login_redirect_url(request)

    def get_signup_redirect_url(self, request):
        """
        After signup, dynamically route un-onboarded users to onboarding select-role.
        """
        user = request.user
        if user.is_authenticated and not getattr(user, "is_email_verified", False):
            self._maybe_start_pending_session(request, user, flow="allauth-signup")
            return reverse("account_verification_pending")

        # Un-onboarded users (no role or is_onboarded=False) go to onboarding select-role
        if user.is_authenticated and (not user.role or not getattr(user, "is_onboarded", False)):
            return reverse("frontend:onboarding_select_role")

        if user.is_authenticated and getattr(user, 'role', None) == 'Agent':
            return reverse('frontend:agent_signup_complete')
        if user.is_authenticated and getattr(user, 'role', None) == 'Buyer':
            return reverse('frontend:buyer_dashboard')
        if user.is_authenticated and getattr(user, 'role', None) == 'Seller':
            return reverse('frontend:seller_dashboard')
        return super().get_signup_redirect_url(request)

    def get_email_confirmation_url(self, request, emailconfirmation):
        """
        Send email verification links to the dedicated pending-verification page.
        """
        user = getattr(emailconfirmation.email_address, "user", None)
        token = issue_one_time_token(
            "emailverify",
            {
                "user_id": str(getattr(user, "id", "")),
                "email": emailconfirmation.email_address.email,
                "source": "allauth",
            },
            ttl_seconds=getattr(settings, "EMAIL_VERIFICATION_TOKEN_TTL_SECONDS", 24 * 60 * 60),
        )
        if request is not None:
            return build_verification_link(request, token)

        frontend_url = getattr(settings, "FRONTEND_URL", "").strip()
        path = reverse("account_verification_pending")
        if frontend_url:
            return f"{frontend_url.rstrip('/')}{path}?token={token}"
        return f"{path}?token={token}"

    def respond_email_verification_sent(self, request, user):
        """
        Keep the user in the pending verification flow after signup or login.
        """
        self._maybe_start_pending_session(request, user, flow="allauth")
        return redirect(reverse("account_verification_pending"))

    def get_email_verification_redirect_url(self, email_address):
        """
        After confirmation, send the user back to the public login page.
        """
        return get_email_verification_login_redirect_url()

    def pre_login(self, request, user, **kwargs):
        """
        Routing rules for /accounts/login/ (the public login page):
          - Admin:              Direct access to /admin/
          - Agent (any state):  ALWAYS blocked -> must use /staff/login/
          - Buyer / Seller:     ALWAYS allowed
        """
        role = getattr(user, 'role', None)
        block = role == 'Agent'

        if block and '/accounts/login' in request.path:
            from allauth.exceptions import ImmediateHttpResponse
            request.session['staff_blocked'] = True
            raise ImmediateHttpResponse(
                redirect(reverse('frontend:staff_login'))
            )

        if '/accounts/login' in request.path and getattr(user, "is_authenticated", False):
            if not getattr(user, "is_email_verified", False):
                self._maybe_start_pending_session(request, user, flow="allauth-login")
                from allauth.exceptions import ImmediateHttpResponse
                raise ImmediateHttpResponse(
                    redirect(reverse("account_verification_pending"))
                )

        return super().pre_login(request, user, **kwargs)


class RoleBasedSocialAccountAdapter(DefaultSocialAccountAdapter):
    def get_app(self, request, provider, client_id=None, config=None, **kwargs):
        """
        Safely retrieve or provision SocialApp for provider (e.g. google, github).
        Prevents SocialApp.DoesNotExist 500 errors during OAuth callbacks.
        """
        from allauth.socialaccount.models import SocialApp
        from django.contrib.sites.models import Site

        try:
            return super().get_app(request, provider, client_id=client_id, config=config, **kwargs)
        except Exception:
            pass

        provider_config = getattr(settings, 'SOCIALACCOUNT_PROVIDERS', {}).get(provider, {})
        app_config = provider_config.get('APP', {})
        client_id = app_config.get('client_id') or getattr(settings, f'{provider.upper()}_OAUTH_CLIENT_ID', '') or getattr(settings, f'{provider.upper()}_CLIENT_ID', '')
        secret = app_config.get('secret') or getattr(settings, f'{provider.upper()}_OAUTH_CLIENT_SECRET', '') or getattr(settings, f'{provider.upper()}_CLIENT_SECRET', '')

        site, _ = Site.objects.get_or_create(id=1, defaults={'domain': 'digiland-six.vercel.app', 'name': 'Digiland'})

        app, created = SocialApp.objects.get_or_create(
            provider=provider,
            defaults={
                'name': provider.title(),
                'client_id': client_id or 'placeholder-client-id',
                'secret': secret or 'placeholder-secret',
            }
        )
        if client_id and app.client_id != client_id:
            app.client_id = client_id
            app.secret = secret or app.secret
            app.save()

        if site not in app.sites.all():
            app.sites.add(site)
        return app

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        if not user.email and sociallogin.account.extra_data.get('email'):
            user.email = sociallogin.account.extra_data['email']
        user.is_email_verified = True
        return user

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form=form)
        user.is_email_verified = True
        user.save(update_fields=['is_email_verified'])
        return user

