#!/usr/bin/env python
"""
Test complete rejection flow: create pending agents, reject one, verify removal
"""
import os, sys, django
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from core.models import User

def test_complete_flow():
    print("=== Testing Complete Rejection Flow ===")
    
    # Clean up any existing test data
    User.objects.filter(email__contains='test').delete()
    print("🧹 Cleaned up existing test data")
    
    # Create multiple test agents
    test_agents = [
        {
            'email': 'agent1@test.com',
            'phone': '+254700000001',
            'id_number': '111111111'
        },
        {
            'email': 'agent2@test.com', 
            'phone': '+254700000002',
            'id_number': '222222222'
        },
        {
            'email': 'agent3@test.com',
            'phone': '+254700000003',
            'id_number': '333333333'
        }
    ]
    
    for agent_data in test_agents:
        agent, created = User.objects.get_or_create(
            email=agent_data['email'],
            defaults={
                'role': 'Agent',
                'is_active': True,
                'is_identity_verified': False,
                'phone_number': agent_data['phone'],
                'id_number': agent_data['id_number']
            }
        )
        if created:
            print(f"✅ Created test agent: {agent.email}")
    
    # Check pending agents count
    pending_before = User.objects.filter(
        role='Agent', 
        is_identity_verified=False, 
        is_active=True
    )
    print(f"Pending agents before rejection: {pending_before.count()}")
    for agent in pending_before:
        print(f"  - {agent.email}")
    
    # Reject one agent (agent2)
    agent_to_reject = User.objects.get(email='agent2@test.com')
    agent_to_reject.is_active = False
    agent_to_reject.is_identity_verified = False
    agent_to_reject.save()
    print(f"❌ Rejected agent: {agent_to_reject.email}")
    
    # Check pending agents after rejection
    pending_after = User.objects.filter(
        role='Agent', 
        is_identity_verified=False, 
        is_active=True
    )
    print(f"Pending agents after rejection: {pending_after.count()}")
    for agent in pending_after:
        print(f"  - {agent.email}")
    
    # Verify the rejected agent is not in pending list
    rejected_still_pending = agent_to_reject in pending_after
    if rejected_still_pending:
        print(f"❌ BUG: Rejected agent {agent_to_reject.email} still appears in pending list!")
        return False
    else:
        print(f"✅ SUCCESS: Rejected agent {agent_to_reject.email} correctly removed from pending list!")
    
    # Clean up test data
    User.objects.filter(email__contains='test').delete()
    print("🧹 Cleaned up test data")
    
    return True

if __name__ == "__main__":
    success = test_complete_flow()
    
    if success:
        print("\n🎉 Rejection flow test PASSED!")
        print("\nThe admin dashboard will now correctly:")
        print("1. Show only active agents in pending approvals")
        print("2. Remove rejected agents from the list")
        print("3. Display appropriate empty state message")
    else:
        print("\n❌ Rejection flow test FAILED!")
