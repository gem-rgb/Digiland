"""
Domain Routing Middleware for DigiLand Multi-Frontend Architecture.

Differentiates requests based on host domain:
- digiland.co.ke (or www.digiland.co.ke) -> Public Marketing & Discovery Website
- app.digiland.co.ke                     -> User Application Platform (Buyer, Agent, Seller, Lawyer)
- admin.digiland.co.ke                   -> Administrative Command Center

In local development or preview environments (*.vercel.app, localhost),
allows mode switching via ?domain=public|app|admin or defaults to role-appropriate mode.
"""
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class MultiDomainRoutingMiddleware:
    """Detects and tags domain context on the incoming request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().lower().split(':')[0]
        
        # Determine domain mode
        if 'admin.digiland.co.ke' in host:
            domain_mode = 'admin'
        elif 'app.digiland.co.ke' in host:
            domain_mode = 'app'
        elif 'digiland.co.ke' in host:
            domain_mode = 'public'
        else:
            # Localhost or Vercel preview deployment
            override = request.GET.get('domain') or request.session.get('domain_mode')
            if override in {'public', 'app', 'admin'}:
                domain_mode = override
                request.session['domain_mode'] = override
            elif request.path.startswith('/admin') or request.path.startswith('/staff'):
                domain_mode = 'admin'
            elif request.user.is_authenticated and request.path in {'/dashboard/', '/agent/dashboard/', '/buyer/dashboard/', '/seller/dashboard/'}:
                domain_mode = 'app'
            else:
                domain_mode = 'public' if not request.user.is_authenticated else 'app'

        request.domain_mode = domain_mode

        # Security gate for admin domain
        if domain_mode == 'admin':
            if request.path.startswith('/accounts/login/'):
                return redirect('frontend:staff_login')
            if not request.path.startswith('/staff/login/') and not request.path.startswith('/static/') and not request.path.startswith('/api/'):
                if not request.user.is_authenticated:
                    return redirect('frontend:staff_login')
                if getattr(request.user, 'role', None) != 'Admin' and not getattr(request.user, 'is_superuser', False):
                    # Unauthorized on admin domain -> redirect to app domain
                    return redirect('frontend:agent_dashboard')

        return self.get_response(request)
