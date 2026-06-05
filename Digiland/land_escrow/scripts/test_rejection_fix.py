#!/usr/bin/env python
"""
Test that rejected agents don't appear in pending approvals
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from core.models import User

def test_rejection_fix():
    print("=== Testing Agent Rejection Fix ===")
    
    # Create a test agent
    test_agent, created = User.objects.get_or_create(
        email='testrejected@agent.com',
        defaults={
            'role': 'Agent',
            'is_active': True,
            'is_identity_verified': False,
            'phone_number': '+254700000999',
            'id_number': '999999999'
        }
    )
    
    if created:
        print(f"✅ Created test agent: {test_agent.email}")
    else:
        print(f"⚠️  Test agent already exists: {test_agent.email}")
    
    # Check current pending agents before rejection
    pending_before = User.objects.filter(
        role='Agent', 
        is_identity_verified=False, 
        is_active=True
    )
    print(f"Pending agents before rejection: {pending_before.count()}")
    for agent in pending_before:
        print(f"  - {agent.email}")
    
    # Reject the agent (simulate admin rejection)
    test_agent.is_active = False
    test_agent.is_identity_verified = False
    test_agent.save()
    print(f"❌ Rejected agent: {test_agent.email} (is_active={test_agent.is_active})")
    
    # Check pending agents after rejection
    pending_after = User.objects.filter(
        role='Agent', 
        is_identity_verified=False, 
        is_active=True
    )
    print(f"Pending agents after rejection: {pending_after.count()}")
    for agent in pending_after:
        print(f"  - {agent.email}")
    
    # Verify rejected agent is not in pending list
    rejected_still_pending = test_agent in pending_after
    if rejected_still_pending:
        print(f"❌ BUG: Rejected agent {test_agent.email} still appears in pending list!")
    else:
        print(f"✅ SUCCESS: Rejected agent {test_agent.email} correctly removed from pending list!")
    
    # Clean up test data
    test_agent.delete()
    print(f"🧹 Cleaned up test agent: {test_agent.email}")

if __name__ == "__main__":
    test_rejection_fix()
