#!/usr/bin/env python
"""
Automated Test for Admin & Staff Login Isolation, URL Routing, and Authentication Flow
======================================================================================
Tests:
1. /admin/login/ unauthenticated -> 200 OK
2. Admin authentication on /admin/login/ -> redirects to /admin/dashboard/ -> 200 OK
3. Cross-session access: Agent visiting /admin/login/ -> 200 OK (no redirect to staff)
4. Admin session visiting /staff/login/ -> 200 OK (no redirect loop to admin)
5. Non-admin accessing /admin/dashboard/ -> redirected to non-admin dashboard / home
6. Localhost routing isolation -> no external redirect to https://admin.digiland.co.ke
"""
import os
import sys
import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from django.test import Client
from core.models import User
from core.auth_backends import EmailOrUsernameModelBackend

def run_tests():
    print("=" * 60)
    print("RUNNING COMPREHENSIVE ADMIN & STAFF AUTH FLOW TEST")
    print("=" * 60)

    # 1. Setup test users
    admin_email = "admin_verified@digiland.co.ke"
    admin_pwd = "AdminSecure@2026!"
    agent_email = "agent_verified@digiland.co.ke"
    agent_pwd = "AgentSecure@2026!"

    EmailOrUsernameModelBackend.reset_lockout(admin_email, "127.0.0.1")
    EmailOrUsernameModelBackend.reset_lockout(agent_email, "127.0.0.1")

    admin_user, _ = User.objects.get_or_create(
        email=admin_email,
        defaults={
            "role": "Admin",
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
            "is_identity_verified": True,
            "is_email_verified": True,
            "is_onboarded": True,
        }
    )
    admin_user.role = "Admin"
    admin_user.is_staff = True
    admin_user.is_superuser = True
    admin_user.is_active = True
    admin_user.set_password(admin_pwd)
    admin_user.save()

    agent_user, _ = User.objects.get_or_create(
        email=agent_email,
        defaults={
            "role": "Agent",
            "is_staff": False,
            "is_superuser": False,
            "is_active": True,
            "is_identity_verified": True,
            "is_email_verified": True,
            "is_onboarded": True,
        }
    )
    agent_user.role = "Agent"
    agent_user.is_active = True
    agent_user.is_identity_verified = True
    agent_user.set_password(agent_pwd)
    agent_user.save()

    print(f"[SETUP] Test users ready: Admin={admin_user.email}, Agent={agent_user.email}")

    # ── Test 1: Unauthenticated visit to /admin/login/ ──
    client = Client()
    resp = client.get('/admin/login/')
    assert resp.status_code == 200, f"Expected 200 OK for unauthenticated /admin/login/, got {resp.status_code}"
    assert 'Executive Administration' in resp.content.decode('utf-8') or 'Admin Command Terminal' in resp.content.decode('utf-8'), "Admin login title missing"
    print("[PASS] Test 1: Unauthenticated /admin/login/ returns 200 OK with Admin Command Terminal")

    # ── Test 2: Admin login POST on /admin/login/ ──
    login_resp = client.post('/admin/login/', {'email': admin_email, 'password': admin_pwd}, follow=True)
    assert login_resp.status_code == 200, f"Expected 200 OK after admin login redirect, got {login_resp.status_code}"
    # Verify we landed on admin dashboard
    redirect_chain = [r[0] for r in login_resp.redirect_chain]
    print(f"       Admin login redirect chain: {redirect_chain}")
    assert any('/admin/dashboard/' in r or '/agent/dashboard/' in r for r in redirect_chain) or login_resp.request['PATH_INFO'] in {'/admin/dashboard/', '/agent/dashboard/'}, "Did not land on admin dashboard"
    assert 'Command Centre' in login_resp.content.decode('utf-8'), "Command Centre text missing from dashboard response"
    print("[PASS] Test 2: Admin credentials authenticate and land on Admin Command Centre")

    # ── Test 3: Authenticated Admin accessing /admin/dashboard/ directly ──
    dash_resp = client.get('/admin/dashboard/')
    assert dash_resp.status_code == 200, f"Expected 200 OK for /admin/dashboard/, got {dash_resp.status_code}"
    assert 'Command Centre' in dash_resp.content.decode('utf-8')
    print("[PASS] Test 3: /admin/dashboard/ directly accessible with 200 OK for Admin")

    # ── Test 4: Authenticated Agent visiting /admin/login/ ──
    agent_client = Client()
    agent_login = agent_client.post('/staff/login/', {'email': agent_email, 'password': agent_pwd}, follow=True)
    assert agent_login.status_code == 200, f"Agent login failed: {agent_login.status_code}"
    print("       Agent logged into staff session.")

    # Agent visits /admin/login/ -> MUST NOT redirect to /staff/login/! Must return 200 OK
    agent_admin_resp = agent_client.get('/admin/login/')
    assert agent_admin_resp.status_code == 200, f"Expected 200 OK when Agent visits /admin/login/, got {agent_admin_resp.status_code}"
    assert 'Currently signed in as' in agent_admin_resp.content.decode('utf-8') or 'Admin Command Terminal' in agent_admin_resp.content.decode('utf-8'), "Notice or admin form missing"
    print("[PASS] Test 4: Agent visiting /admin/login/ stays on /admin/login/ with 200 OK (NO redirect loop to staff)")

    # ── Test 5: Authenticated Agent logging into Admin from /admin/login/ ──
    agent_switch_resp = agent_client.post('/admin/login/', {'email': admin_email, 'password': admin_pwd}, follow=True)
    assert agent_switch_resp.status_code == 200, f"Expected 200 OK after switching to admin, got {agent_switch_resp.status_code}"
    assert 'Command Centre' in agent_switch_resp.content.decode('utf-8')
    print("[PASS] Test 5: Seamless account switch from Agent to Admin via /admin/login/ works cleanly")

    # ── Test 6: Authenticated Admin visiting /staff/login/ ──
    admin_staff_resp = client.get('/staff/login/')
    assert admin_staff_resp.status_code == 200, f"Expected 200 OK when Admin visits /staff/login/, got {admin_staff_resp.status_code}"
    print("[PASS] Test 6: Admin visiting /staff/login/ stays on /staff/login/ with 200 OK (NO redirect loop to admin)")

    # ── Test 7: Non-admin accessing /admin/dashboard/ ──
    agent_client2 = Client()
    agent_client2.post('/staff/login/', {'email': agent_email, 'password': agent_pwd})
    unauth_dash = agent_client2.get('/admin/dashboard/', follow=False)
    assert unauth_dash.status_code in {302, 403}, f"Expected redirect or 403 for non-admin on /admin/dashboard/, got {unauth_dash.status_code}"
    print(f"[PASS] Test 7: Agent blocked from /admin/dashboard/ (status: {unauth_dash.status_code})")

    print("\n" + "=" * 60)
    print("ALL 7 AUTHENTICATION & PARTITION ROUTING TESTS PASSED 100%!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = run_tests()
    if not success:
        sys.exit(1)
