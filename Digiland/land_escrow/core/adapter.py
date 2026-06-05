from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse
from django.shortcuts import redirect

# Roles that are BANNED from the public /accounts/login/ route
STAFF_ROLES = {'Admin', 'Agent'}

class RoleBasedAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        """
        Dynamically route users based on their selected role after login.
        Only called by allauth's public login/signup flow.
        The staff_login view handles its own redirect independently.
        """
        user = request.user
        if user.is_authenticated:
            if user.role == 'Buyer' and not getattr(user, 'buyer_account_type', None):
                return reverse('frontend:buyer_account_choice')
            if user.role == 'Agent':
                # Agents should never reach here via public login (blocked in
                # pre_login). If they somehow do (e.g. direct API call),
                # send them to the signup-complete gate.
                return reverse('frontend:agent_signup_complete')
            if user.role == 'Admin':
                return reverse('frontend:agent_dashboard')
            return reverse('frontend:parcel_list')
        return super().get_login_redirect_url(request)

    def get_signup_redirect_url(self, request):
        """
        After a successful signup, agents are sent to the 'signup complete'
        gate which logs them out and directs them to the Staff Login portal.
        Buyers are sent to their onboarding choice page so they can select
        joint or individual account mode.
        """
        user = request.user
        if user.is_authenticated and getattr(user, 'role', None) == 'Agent':
            return reverse('frontend:agent_signup_complete')
        if user.is_authenticated and getattr(user, 'role', None) == 'Buyer':
            return reverse('frontend:buyer_account_choice')
        return super().get_signup_redirect_url(request)

    def pre_login(self, request, user, **kwargs):
        """
        Routing rules for /accounts/login/ (the public login page):
          - Admin:              ALWAYS blocked -> must use /staff/login/
          - Agent (any state):  ALWAYS blocked -> must use /staff/login/
            (unverified agents go through KYC/onboarding only after
             authenticating via the staff portal)
          - Buyer / Seller:     ALWAYS allowed
        """
        role = getattr(user, 'role', None)

        block = (role == 'Admin') or (role == 'Agent')

        if block and '/accounts/login' in request.path:
            from allauth.exceptions import ImmediateHttpResponse
            request.session['staff_blocked'] = True
            raise ImmediateHttpResponse(
                redirect(reverse('frontend:staff_login'))
            )

        return super().pre_login(request, user, **kwargs)
