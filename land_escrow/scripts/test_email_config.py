#!/usr/bin/env python
"""
Test Gmail email configuration
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

def test_email_config():
    print("=== Testing Gmail Email Configuration ===")
    
    print(f"Email Backend: {settings.EMAIL_BACKEND}")
    print(f"Email Host: {settings.EMAIL_HOST}")
    print(f"Email Port: {settings.EMAIL_PORT}")
    print(f"Email User: {settings.EMAIL_HOST_USER}")
    print(f"Use TLS: {settings.EMAIL_USE_TLS}")
    print(f"Use SSL: {settings.EMAIL_USE_SSL}")
    print(f"From Email: {settings.DEFAULT_FROM_EMAIL}")
    print(f"Admin Email: {settings.ADMIN_USER_EMAIL}")
    
    # Test sending a simple email to your email
    try:
        print("\n📧 Sending test email to trickytaitumu@gmail.com...")
        send_mail(
            subject='Digiland Email Test',
            message='This is a test email from the Digiland system to verify Gmail SMTP configuration is working properly.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=['trickytaitumu@gmail.com'],
            fail_silently=False,
        )
        print("✅ Test email sent successfully!")
        return True
    except Exception as e:
        print(f"❌ Email test failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_email_config()
    
    if success:
        print("\n🎉 Gmail integration is working!")
        print("\nEmail features now available:")
        print("1. ✅ Agent approval notifications")
        print("2. ✅ Agent rejection notifications") 
        print("3. ✅ Task assignment emails")
        print("4. ✅ Agent rating notifications")
        print("5. ✅ Admin bulk messaging")
        print("6. ✅ Custom email campaigns")
        print("\n📧 Check your inbox at trickytaitumu@gmail.com for the test email!")
    else:
        print("\n❌ Gmail integration failed!")
        print("Please check:")
        print("1. Gmail app password is correct")
        print("2. 2-factor authentication is enabled")
        print("3. 'Less secure apps' is allowed for Gmail")
        print("4. Network/firewall allows SMTP traffic")
        print("5. EMAIL_HOST_USER and EMAIL_HOST_PASSWORD are set in .env")
