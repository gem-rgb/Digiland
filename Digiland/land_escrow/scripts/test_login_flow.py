#!/usr/bin/env python
"""
Test the complete agent login flow
"""
import os, sys, django
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from core.models import User
from django.test import RequestFactory, Client
from django.contrib.auth import login, authenticate
from core.middleware import AgentKYCGateMiddleware

def test_complete_flow():
    print("=== Testing Complete Agent Login Flow ===")
    
    # Get the agent
    agent = User.objects.get(email='tatetricky@gmail.com')
    print(f"✅ Agent found: {agent.email}")
    print(f"   Status: Active={agent.is_active}, Verified={agent.is_identity_verified}")
    
    # Test authentication
    user = authenticate(email='tatetricky@gmail.com', password='Teddy@2050!!!')
    if user:
        print(f"✅ Authentication successful for: {user.email}")
    else:
        print("❌ Authentication failed")
        return False
    
    # Test middleware access to dashboard
    factory = RequestFactory()
    request = factory.get('/agent/dashboard/')
    request.user = user
    
    middleware = AgentKYCGateMiddleware(lambda req: None)
    response = middleware(request)
    
    if response is None:
        print("✅ Middleware allows access to /agent/dashboard/")
    else:
        print(f"❌ Middleware blocks access: {response.url}")
        return False
    
    # Test client login flow
    client = Client()
    login_success = client.login(email='tatetricky@gmail.com', password='Teddy@2050!!!')
    
    if login_success:
        print("✅ Client login successful")
        
        # Test accessing dashboard
        response = client.get('/agent/dashboard/')
        if response.status_code == 200:
            print("✅ Dashboard accessible (200 OK)")
        elif response.status_code == 302:
            print(f"⚠️  Dashboard redirects to: {response.url}")
        else:
            print(f"❌ Dashboard access failed: {response.status_code}")
            return False
    else:
        print("❌ Client login failed")
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 Testing Complete Agent Login Flow")
    print("=" * 50)
    
    success = test_complete_flow()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Login flow test passed!")
        print("\nManual testing steps:")
        print("1. Open browser to: http://127.0.0.1:8000/staff/login/")
        print("2. Enter email: tatetricky@gmail.com")
        print("3. Enter password: Teddy@2050!!!")
        print("4. Click 'Authenticate'")
        print("5. Should redirect to agent dashboard")
    else:
        print("❌ Login flow test failed")
