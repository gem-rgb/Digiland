#!/usr/bin/env python
"""
Test email configuration for the current environment.

In local development, Django uses the console email backend by default,
so this script checks which backend is active and only attempts an SMTP
send when the backend is actually configured for it.
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings


def test_email_config():
    print("=== Digiland Email Configuration Check ===")

    print(f"\n  Email Backend:  {settings.EMAIL_BACKEND}")
    print(f"  Email Host:     {settings.EMAIL_HOST}")
    print(f"  Email Port:     {settings.EMAIL_PORT}")
    print(f"  Email User:     {settings.EMAIL_HOST_USER or '(not set)'}")
    print(f"  Use TLS:        {settings.EMAIL_USE_TLS}")
    print(f"  Use SSL:        {settings.EMAIL_USE_SSL}")
    print(f"  From Email:     {settings.DEFAULT_FROM_EMAIL}")
    print(f"  Server Email:   {settings.SERVER_EMAIL}")
    print(f"  Admin Email:    {settings.ADMIN_USER_EMAIL or '(not set)'}")

    is_smtp = 'smtp' in settings.EMAIL_BACKEND.lower()
    is_console = 'console' in settings.EMAIL_BACKEND.lower()

    if is_console:
        print("\n  INFO: Using console email backend (default for local dev).")
        print("  Verification emails will be printed to the runserver stdout.")
        print("  No SMTP credentials are required.")
        print("\n  To switch to SMTP for testing real delivery, set in .env:")
        print("    EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend")
        print("    EMAIL_HOST_USER=your-email@gmail.com")
        print("    EMAIL_HOST_PASSWORD=your-app-password")
        print("    DEFAULT_FROM_EMAIL=noreply@your-domain.com")
        return True

    if not is_smtp:
        print(f"\n  WARNING: Unexpected email backend: {settings.EMAIL_BACKEND}")
        return False

    # SMTP backend — check credentials
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        print("\n  ERROR: SMTP backend selected but credentials are missing!")
        print("  Set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in your .env file.")
        return False

    # Attempt a test send
    try:
        recipient = settings.EMAIL_HOST_USER
        print(f"\n  Sending test email to {recipient}...")
        send_mail(
            subject='Digiland Email Test',
            message='This is a test email from the Digiland system to verify SMTP configuration is working properly.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
        print("  Test email sent successfully!")
        return True
    except Exception as e:
        print(f"  SMTP test failed: {str(e)}")
        print("\n  Common fixes:")
        print("  1. Gmail: use an App Password (not your regular password)")
        print("  2. Enable 2FA on the Gmail account first")
        print("  3. For local dev, switch to the console backend instead:")
        print("     EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend")
        return False


if __name__ == "__main__":
    success = test_email_config()

    if success:
        backend = settings.EMAIL_BACKEND.split('.')[-1].replace('EmailBackend', '')
        print(f"\n  Email backend ({backend}) is configured correctly.")
        print("\n  Email-dependent features:")
        print("  - Account signup verification")
        print("  - Password reset flow")
        print("  - Agent approval/rejection notifications")
        print("  - Task assignment emails")
        print("  - Agent rating notifications")
    else:
        print("\n  Email configuration needs attention. See the messages above.")
