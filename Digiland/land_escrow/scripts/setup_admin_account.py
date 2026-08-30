#!/usr/bin/env python
"""
Admin Account Setup & Password Reset Script
===========================================
Ensures the platform Administrator account exists, has full superuser and
Admin role privileges, valid Argon2 password, and clears any failed login cache locks.
"""
import os
import sys
import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from django.core.cache import cache
from django.contrib.auth import authenticate
from core.models import User
from core.auth_backends import EmailOrUsernameModelBackend

def setup_admin(email="karanitaitumu@gmail.com", password="AdminPassword@2026!"):
    print(f"=== Configuring Admin Account: {email} ===")
    
    # Clear any lockout cache
    EmailOrUsernameModelBackend.reset_lockout(email, "127.0.0.1")
    EmailOrUsernameModelBackend.reset_lockout(email, "0.0.0.0")
    cache.delete(f"auth_fail:email:{email.lower()}")
    cache.delete(f"auth_fail:ip:127.0.0.1")
    print("[CLEARED] Brute-force lockout cache keys.")

    user, created = User.objects.get_or_create(
        email=email.lower().strip(),
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

    user.role = "Admin"
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.is_identity_verified = True
    user.is_email_verified = True
    user.is_onboarded = True
    user.set_password(password)
    user.save()

    print(f"[OK] Admin user {'created' if created else 'updated'}: {user.email}")
    print(f"     Role: {user.role}, Staff: {user.is_staff}, Superuser: {user.is_superuser}, Active: {user.is_active}")

    # Verify password authentication
    auth_user = authenticate(username=email, password=password)
    if auth_user:
        print(f"[PASS] Authentication test passed for: {auth_user.email}")
    else:
        print("[FAIL] Authentication test failed")
        return False

    return True

if __name__ == "__main__":
    email_arg = sys.argv[1] if len(sys.argv) > 1 else "karanitaitumu@gmail.com"
    pwd_arg = sys.argv[2] if len(sys.argv) > 2 else "AdminPassword@2026!"
    success = setup_admin(email_arg, pwd_arg)
    if success:
        print(f"\nAdmin credentials ready for login:")
        print(f"Portal: http://127.0.0.1:8000/admin/login/")
        print(f"Email: {email_arg}")
        print(f"Password: {pwd_arg}")
