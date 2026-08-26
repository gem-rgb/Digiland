"""
Domain Routing Middleware for DigiLand Multi-Frontend Architecture.

Differentiates requests based on host domain:
- digiland.co.ke (or www.digiland.co.ke) -> Public Marketing & Discovery Website
- app.digiland.co.ke                     -> User Application Platform (Buyer, Seller, Agent, Lawyer)
- staff.digiland.co.ke                   -> Dedicated Staff Authentication & Operational Hub
- admin.digiland.co.ke                   -> Administrative Command Center

In local development or preview environments (*.vercel.app, localhost),
allows mode switching via ?domain=public|app|staff|admin or defaults to role-appropriate mode.
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
        if 'staff.digiland.co.ke' in host:
            domain_mode = 'staff'
        elif 'admin.digiland.co.ke' in host:
            domain_mode = 'admin'
        elif 'app.digiland.co.ke' in host:
            domain_mode = 'app'
        elif 'digiland.co.ke' in host:
            domain_mode = 'public'
        else:
            # Localhost or Vercel preview deployment
            override = request.GET.get('domain') or request.session.get('domain_mode')
            if override in {'public', 'app', 'staff', 'admin'}:
                domain_mode = override
                request.session['domain_mode'] = override
            elif request.path.startswith('/staff'):
                domain_mode = 'staff'
            elif request.path.startswith('/admin'):
                domain_mode = 'admin'
            elif request.user.is_authenticated and request.path in {'/dashboard/', '/agent/dashboard/', '/buyer/dashboard/', '/seller/dashboard/'}:
                domain_mode = 'app'
            else:
                domain_mode = 'public' if not request.user.is_authenticated else 'app'

        request.domain_mode = domain_mode

        # Security gate for staff / admin domain
        if domain_mode in {'staff', 'admin'}:
            if request.path.startswith('/accounts/login/'):
                return redirect('frontend:staff_login')
            if domain_mode == 'staff' and request.path == '/':
                if not request.user.is_authenticated:
                    return redirect('frontend:staff_login')
                return redirect('frontend:agent_dashboard')
            if not request.path.startswith('/staff/login/') and not request.path.startswith('/static/') and not request.path.startswith('/api/'):
                if not request.user.is_authenticated:
                    return redirect('frontend:staff_login')
                if domain_mode == 'admin' and getattr(request.user, 'role', None) != 'Admin' and not getattr(request.user, 'is_superuser', False):
                    # Unauthorized on admin domain -> redirect to app dashboard
                    return redirect('frontend:agent_dashboard')

        return self.get_response(request)
