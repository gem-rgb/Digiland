from django.shortcuts import redirect
from django.urls import reverse

# Paths that Agent users (verified or not) can always access without gating
AGENT_EXEMPT_PATHS = {
    '/agent/kyc/',
    '/agent/onboarding/',
    '/agent/dashboard/',
    '/agent/tasks/',
    '/transactions/',
    '/messages/',
    '/staff/login/',
    '/accounts/logout/',
    '/accounts/login/',
    '/accounts/signup/',
    '/admin/',
}


class AgentKYCGateMiddleware:
    """
    Enforces the two-phase Agent flow on every request:

    Phase 1 — Unverified Agent (KYC not yet approved):
      • No KYC submitted yet  → /agent/kyc/
      • KYC submitted, awaiting admin review → /agent/onboarding/

    Phase 2 — Verified (approved) Agent accessing site via public session:
      • They should be using /staff/login/, not the public auth.
      • Redirect to /agent/onboarding/ which will show them the
        "You're approved — use Staff Login" message.
      • Exempt: /staff/login/, /agent/onboarding/, /accounts/logout/
      • The /agent/dashboard/ is protected by is_verified_agent_or_admin
        so a verified-but-public-session agent is blocked there anyway.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user

        if user.is_authenticated and getattr(user, 'role', None) == 'Agent':
            path = request.path

            # Always let static / media through
            if path.startswith('/static/') or path.startswith('/media/'):
                return self.get_response(request)

            is_exempt = any(path.startswith(p) for p in AGENT_EXEMPT_PATHS)

            if user.is_identity_verified:
                # Approved agent — must only work through the staff portal.
                # If they're on an exempt path (staff_login, onboarding,
                # logout) let them through; otherwise show them the onboarding
                # page which tells them to use /staff/login/.
                if not is_exempt:
                    return redirect(reverse('frontend:agent_onboarding'))

            else:
                # Unverified agent — enforce KYC gate
                if not is_exempt:
                    try:
                        from core.models import AgentKYCApplication
                        app = AgentKYCApplication.objects.get(agent=user)
                        if app.kyc_submitted:
                            return redirect(reverse('frontend:agent_onboarding'))
                        return redirect(reverse('frontend:agent_kyc'))
                    except Exception:
                        return redirect(reverse('frontend:agent_kyc'))

        return self.get_response(request)

