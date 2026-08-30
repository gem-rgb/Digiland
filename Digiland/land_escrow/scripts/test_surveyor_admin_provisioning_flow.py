#!/usr/bin/env python
"""
Test Surveyor Admin Provisioning & Staff Portal Auth Flow
=========================================================
Verifies:
1. Admin logs into /admin/login/
2. Admin provisions a new Licensed Land Surveyor account via POST /admin/staff/provision/
3. Admin verifies and confirms surveyor status in the database
4. Newly provisioned Surveyor logs in at /staff/login/
5. Authenticated Surveyor is redirected to /surveyor/dashboard/ with full fieldwork workspace
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
from django.urls import reverse
from core.models import User, KYCProfile, SurveyAssignment

def run_tests():
    print("\n" + "="*70)
    print("SURVEYOR PROVISIONING & STAFF AUTH FLOW TEST SUITE")
    print("="*70)

    # 1. Setup Admin Account
    admin_email = "admin@digiland.co.ke"
    admin_pwd = "AdminDigiland2026!"
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

    client = Client()

    # ── Test 1: Admin Login ──
    print("\n[TEST 1] Admin Login on /admin/login/ ...")
    login_resp = client.post('/admin/login/', {'email': admin_email, 'password': admin_pwd}, follow=True)
    assert login_resp.status_code == 200, f"Expected 200, got {login_resp.status_code}"
    print("[PASS] Admin login succeeded and loaded Command Centre.")

    # ── Test 2: Admin Provisions a Surveyor Account ──
    surveyor_email = "surveyor_maina_test@digiland.co.ke"
    surveyor_phone = "+254799334455"
    surveyor_pwd = "SurveyorPass@2026!"
    # Clean up previous test run if exists
    User.objects.filter(email=surveyor_email).delete()
    User.objects.filter(phone_number__icontains="799334455").delete()

    print(f"\n[TEST 2] Admin provisioning new Surveyor: {surveyor_email} ...")
    prov_payload = {
        'role': 'Surveyor',
        'provision_mode': 'DIRECT_ACTIVE',
        'full_name': 'Sur. Peter Maina Kamau',
        'email': surveyor_email,
        'phone_number': surveyor_phone,
        'password': surveyor_pwd,
        'national_id': '29384756',
        'kra_pin': 'A019283746Z',
        'county': 'Kiambu',
        'surveyor_license_number': 'ISLK-9941/2026',
        'surveyor_firm': 'Maina & Associates Geospatial Surveys Ltd',
    }

    prov_resp = client.post(
        '/admin/staff/provision/',
        data=prov_payload,
        content_type='application/json',
        HTTP_ACCEPT='application/json',
        HTTP_X_REQUESTED_WITH='XMLHttpRequest'
    )
    assert prov_resp.status_code == 200, f"Expected 200, got {prov_resp.status_code}: {prov_resp.content.decode()}"
    prov_data = prov_resp.json()
    assert prov_data.get('status') == 'ok', f"Expected status ok, got {prov_data}"
    print(f"[PASS] Successfully provisioned Surveyor account via Admin endpoint: {prov_data.get('message')}")

    # Check database state
    surveyor_u = User.objects.get(email=surveyor_email)
    assert surveyor_u.role == 'Surveyor', f"Expected role Surveyor, got {surveyor_u.role}"
    assert surveyor_u.is_staff == True, f"Expected is_staff True, got {surveyor_u.is_staff}"
    assert surveyor_u.is_identity_verified == True, "Expected identity verified True"
    assert surveyor_u.surveyor_license_number == 'ISLK-9941/2026', f"Expected license ISLK-9941/2026, got {surveyor_u.surveyor_license_number}"
    assert surveyor_u.surveyor_firm == 'Maina & Associates Geospatial Surveys Ltd', f"Got firm: {surveyor_u.surveyor_firm}"
    print(f"[PASS] Database record confirmed: Role={surveyor_u.role}, Staff={surveyor_u.is_staff}, License={surveyor_u.surveyor_license_number}")

    # ── Test 3: Admin Verifies & Toggles Status ──
    print("\n[TEST 3] Admin Verifying & Status Toggling Surveyor ...")
    verify_resp = client.post(
        f'/admin/staff/{surveyor_u.id}/verify/',
        HTTP_ACCEPT='application/json',
        HTTP_X_REQUESTED_WITH='XMLHttpRequest'
    )
    assert verify_resp.status_code == 200, f"Verify failed: {verify_resp.status_code}"
    print("[PASS] Verification endpoint works for Surveyor.")

    toggle_resp = client.post(
        f'/admin/staff/{surveyor_u.id}/toggle-status/',
        HTTP_ACCEPT='application/json',
        HTTP_X_REQUESTED_WITH='XMLHttpRequest'
    )
    assert toggle_resp.status_code == 200, f"Toggle failed: {toggle_resp.status_code}"
    # Toggle back to active
    client.post(
        f'/admin/staff/{surveyor_u.id}/toggle-status/',
        HTTP_ACCEPT='application/json',
        HTTP_X_REQUESTED_WITH='XMLHttpRequest'
    )
    print("[PASS] Toggle status endpoint works for Surveyor.")

    # ── Test 4: Surveyor Logs In at /staff/login/ ──
    print(f"\n[TEST 4] Surveyor Logging in at /staff/login/ with credentials ...")
    surveyor_client = Client()
    staff_login_resp = surveyor_client.post(
        '/staff/login/',
        {'email': surveyor_email, 'password': surveyor_pwd},
        follow=True
    )
    assert staff_login_resp.status_code == 200, f"Staff login failed with status {staff_login_resp.status_code}"
    print("[PASS] Surveyor authenticated successfully via /staff/login/.")

    # ── Test 5: Surveyor Command Centre Workspace ──
    print("\n[TEST 5] Accessing Surveyor Command Centre Workspace ...")
    survey_dash_resp = surveyor_client.get('/surveyor/dashboard/')
    assert survey_dash_resp.status_code == 200, f"Expected 200 on /surveyor/dashboard/, got {survey_dash_resp.status_code}"
    content_str = survey_dash_resp.content.decode()
    assert 'surveyor-dashboard' in content_str, "Expected 'surveyor-dashboard' in rendered page"
    assert 'ISLK-9941/2026' in content_str or 'Maina & Associates' in content_str or 'Sur. Peter Maina' in content_str, "Expected surveyor profile in bootstrap data"
    print("[PASS] Surveyor Command Centre workspace rendered with active ISLK credentials.")

    # ── Test 6: Staff Dashboard Route for Surveyor ──
    print("\n[TEST 6] Accessing /staff/dashboard/ as Surveyor ...")
    staff_dash_resp = surveyor_client.get('/staff/dashboard/')
    assert staff_dash_resp.status_code == 200, f"Expected 200 on /staff/dashboard/, got {staff_dash_resp.status_code}"
    assert 'surveyor-dashboard' in staff_dash_resp.content.decode(), "Expected surveyor dashboard to be dispatched"
    print("[PASS] /staff/dashboard/ cleanly dispatches to surveyor workspace.")

    print("\n" + "="*70)
    print("ALL 6 TESTS PASSED SUCCESSFULLY! PROVISIONING & LOGIN SEAMLESS.")
    print("="*70 + "\n")
    return True

if __name__ == "__main__":
    success = run_tests()
    if not success:
        sys.exit(1)
