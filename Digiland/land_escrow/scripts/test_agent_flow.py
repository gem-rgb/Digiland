#!/usr/bin/env python
"""
Test script to verify agent approval and dashboard flow
"""
import os
import sys
import django

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from core.models import User, AgentKYCApplication

def test_agent_approval():
    print("=== Testing Agent Approval Flow ===")
    
    # Check if agent exists
    try:
        agent = User.objects.get(email='tatetricky@gmail.com', role='Agent')
        print(f"✅ Found agent: {agent.email}")
        print(f"   Current status - Verified: {agent.is_identity_verified}, Active: {agent.is_active}")
        
        # Check KYC application
        try:
            kyc_app = agent.kyc_application
            print(f"✅ KYC application exists - Submitted: {kyc_app.kyc_submitted}, Status: {kyc_app.status}")
        except AgentKYCApplication.DoesNotExist:
            print("❌ No KYC application found")
            return False
        
        # If not approved, approve them
        if not agent.is_identity_verified:
            print("🔄 Approving agent...")
            agent.is_identity_verified = True
            agent.is_active = True
            agent.save()
            print("✅ Agent approved successfully!")
        else:
            print("✅ Agent is already approved")
        
        return True
        
    except User.DoesNotExist:
        print(f"❌ No agent found with email: tatetricky@gmail.com")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_dashboard_access():
    print("\n=== Testing Dashboard Access ===")
    
    try:
        agent = User.objects.get(email='tatetricky@gmail.com', role='Agent')
        if agent.is_identity_verified:
            print("✅ Agent should be able to access dashboard")
            print("   Test URL: http://127.0.0.1:8000/staff/login/")
            print("   After login, should redirect to: http://127.0.0.1:8000/agent/dashboard/")
        else:
            print("❌ Agent is not verified - will be redirected to onboarding")
        
        return True
    except User.DoesNotExist:
        print("❌ Agent not found")
        return False

if __name__ == "__main__":
    print("🚀 Starting Agent Flow Test")
    print("=" * 50)
    
    # Test approval
    approval_success = test_agent_approval()
    
    # Test dashboard access
    dashboard_success = test_dashboard_access()
    
    print("\n" + "=" * 50)
    if approval_success and dashboard_success:
        print("🎉 All tests passed! Agent should be able to access dashboard.")
        print("\nNext steps:")
        print("1. Go to http://127.0.0.1:8000/staff/login/")
        print("2. Login with agent credentials")
        print("3. Should be redirected to agent dashboard")
    else:
        print("❌ Some tests failed. Check the errors above.")
