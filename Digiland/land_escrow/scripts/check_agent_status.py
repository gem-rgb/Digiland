#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from core.models import User

print("=== Agent Status Check ===")
agents = User.objects.filter(role='Agent')
print(f"Total agents: {agents.count()}")

for agent in agents:
    print(f"Agent: {agent.email}")
    print(f"  - Verified: {agent.is_identity_verified}")
    print(f"  - Active: {agent.is_active}")
    print(f"  - Has KYC: {hasattr(agent, 'kyc_application')}")
    if hasattr(agent, 'kyc_application'):
        print(f"  - KYC Submitted: {agent.kyc_application.kyc_submitted}")
    print()

print("=== Admin Users ===")
admins = User.objects.filter(role='Admin')
print(f"Total admins: {admins.count()}")
for admin in admins:
    print(f"Admin: {admin.email}, Active: {admin.is_active}")
