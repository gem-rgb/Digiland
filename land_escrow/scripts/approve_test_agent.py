#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from core.models import User, AgentKYCApplication

def approve_agent_email(email):
    try:
        agent = User.objects.get(email=email, role='Agent')
        print(f"Found agent: {agent.email}")
        print(f"Current status - Verified: {agent.is_identity_verified}, Active: {agent.is_active}")
        
        # Check if KYC application exists
        kyc_app = None
        try:
            kyc_app = agent.kyc_application
            print(f"KYC application exists: {kyc_app.kyc_submitted}")
        except AgentKYCApplication.DoesNotExist:
            print("No KYC application found - creating one...")
            kyc_app = AgentKYCApplication.objects.create(
                agent=agent,
                kra_pin="TEST_PIN",
                id_number="TEST_ID",
                kyc_submitted=True,
                status='Approved'
            )
            print("Created test KYC application")
        
        # Approve the agent
        agent.is_identity_verified = True
        agent.is_active = True
        agent.save()
        
        print(f"✅ Agent {agent.email} has been approved!")
        print(f"New status - Verified: {agent.is_identity_verified}, Active: {agent.is_active}")
        
    except User.DoesNotExist:
        print(f"❌ No agent found with email: {email}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Try to approve the test agent email
    agent_email = "tatetricky@gmail.com"  # Change this to your agent email
    approve_agent_email(agent_email)
