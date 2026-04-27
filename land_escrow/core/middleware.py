from django.shortcuts import redirect
from django.urls import reverse

# ── Path prefixes that are ALWAYS accessible to Agent users ──────────────────
# Phase 1 (unverified): only KYC, onboarding, auth, and static paths
AGENT_UNVERIFIED_EXEMPT = {
    '/agent/kyc/',
    '/agent/onboarding/',
    '/staff/login/',
    '/accounts/logout/',
    '/accounts/login/',
    '/accounts/signup/',
    '/admin/',
}

# Phase 2 (verified): all operational work pages the agent needs
AGENT_VERIFIED_EXEMPT = {
    # Auth & onboarding
    '/agent/kyc/',
    '/agent/onboarding/',
    '/staff/login/',
    '/accounts/logout/',
    '/accounts/login/',
    '/accounts/signup/',
    '/admin/',
    # Agent command-centre and work views
    '/agent/dashboard/',
    '/agent/tasks/',
    '/agent/applications/',
    '/agent/users/',
    '/agent/approvals/',
    '/agent/send-message/',
    '/agent/assign-task/',
    '/agent/unassign-task/',
    '/agent/rate/',
    '/agent/parcel/',
    '/agent/transaction/',
    '/agent/signup-complete/',
    # Core operational pages
    '/parcels/',
    '/transactions/',
    '/messages/',
    '/support/',
    '/recommendations/',
    '/price-prediction/',
    # Informational pages
    '/about/',
    '/architecture/',
    '/investors/',
    '/terms/',
    '/privacy/',
    '/escrow-acts/',
    # Home page
    '/',
}


class AgentKYCGateMiddleware:
    """
    Enforces the two-phase Agent flow on every request:

    Phase 1 — Unverified Agent (KYC not yet approved):
      • No KYC submitted yet  → /agent/kyc/
      • KYC submitted, awaiting admin review → /agent/onboarding/

    Phase 2 — Verified (approved) Agent accessing site via public session
               without staff authentication:
      • Redirect to /agent/onboarding/ which shows the
        "You're approved — use Staff Login" message.
      • All agent operational paths (parcels, transactions, approvals,
        messaging, etc.) are whitelisted so the dashboard is functional
        once the agent is logged in through the staff portal.
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

            if user.is_identity_verified:
                # Verified agent — allow all operational paths
                is_exempt = any(path.startswith(p) for p in AGENT_VERIFIED_EXEMPT)
                # Also allow the exact home path '/'
                if path == '/':
                    is_exempt = True
                if not is_exempt:
                    return redirect(reverse('frontend:agent_onboarding'))

            else:
                # Unverified agent — strict KYC gate
                is_exempt = any(path.startswith(p) for p in AGENT_UNVERIFIED_EXEMPT)
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

