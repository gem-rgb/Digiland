"""Multi-Factor Authentication service for Digiland.

Implements:
- TOTP (Time-based One-Time Password) setup, verification, and disabling
- Recovery codes generation and verification
- Device trust management
- Step-up authentication for sensitive operations
"""
import pyotp
import qrcode
import io
import base64
import secrets
import logging
from datetime import timedelta
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


class MFAService:
    """Handles all MFA operations."""
    
    TOTP_ISSUER = "Digiland"
    RECOVERY_CODE_COUNT = 8
    RECOVERY_CODE_LENGTH = 8
    
    @staticmethod
    def generate_totp_secret():
        """Generate a new TOTP secret for a user."""
        return pyotp.random_base32()
    
    @staticmethod
    def get_totp_uri(secret, email):
        """Get the otpauth:// URI for QR code generation."""
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=email, issuer_name=MFAService.TOTP_ISSUER)
    
    @staticmethod
    def generate_qr_code_base64(uri):
        """Generate QR code as base64 image for TOTP setup."""
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue()).decode()
    
    @staticmethod
    def verify_totp(secret, code, valid_window=1):
        """Verify a TOTP code. valid_window allows for clock drift."""
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=valid_window)
    
    @staticmethod
    def generate_recovery_codes():
        """Generate a set of recovery codes."""
        codes = []
        for _ in range(MFAService.RECOVERY_CODE_COUNT):
            code = secrets.token_hex(MFAService.RECOVERY_CODE_LENGTH // 2).upper()
            codes.append('-'.join([code[:4], code[4:]]))
        return codes
    
    @staticmethod
    def hash_recovery_code(code):
        """Hash a recovery code for secure storage."""
        from django.contrib.auth.hashers import make_password
        return make_password(code)
    
    @staticmethod
    def verify_recovery_code(hashed_code, plain_code):
        """Verify a recovery code against its hash."""
        from django.contrib.auth.hashers import check_password
        return check_password(plain_code, hashed_code)
    
    @staticmethod
    def setup_mfa(user):
        """Initialize MFA setup for a user. Returns secret and QR code."""
        from .models import UserMFA
        
        secret = MFAService.generate_totp_secret()
        
        # Create or update MFA record
        mfa, created = UserMFA.objects.update_or_create(
            user=user,
            defaults={
                'totp_secret': secret,
                'is_enabled': False,  # Not enabled until verified
                'setup_started_at': timezone.now(),
            }
        )
        
        uri = MFAService.get_totp_uri(secret, user.email)
        qr_code_base64 = MFAService.generate_qr_code_base64(uri)
        
        return {
            'secret': secret,
            'uri': uri,
            'qr_code_base64': qr_code_base64,
            'mfa_id': str(mfa.id),
        }
    
    @staticmethod
    def enable_mfa(user, totp_code):
        """Verify TOTP code and enable MFA for the user."""
        from .models import UserMFA, AuditLog
        
        try:
            mfa = UserMFA.objects.get(user=user)
        except UserMFA.DoesNotExist:
            raise ValueError("MFA setup not initiated. Call setup_mfa first.")
        
        if mfa.is_enabled:
            raise ValueError("MFA is already enabled for this user.")
        
        if not mfa.totp_secret:
            raise ValueError("No TOTP secret found. Call setup_mfa first.")
        
        if not MFAService.verify_totp(mfa.totp_secret, totp_code):
            raise ValueError("Invalid TOTP code. Please try again.")
        
        # Generate recovery codes
        recovery_codes = MFAService.generate_recovery_codes()
        hashed_codes = [MFAService.hash_recovery_code(code) for code in recovery_codes]
        
        mfa.is_enabled = True
        mfa.totp_enabled = True
        mfa.verified_at = timezone.now()
        mfa.recovery_codes = hashed_codes
        mfa.save()
        
        # Log the event
        AuditLog.objects.create(
            user=user,
            action='MFA_ENABLED',
            metadata={'method': 'totp'},
        )
        
        return {
            'enabled': True,
            'recovery_codes': recovery_codes,  # Only shown once!
        }
    
    @staticmethod
    def get_available_methods(user):
        """Return configured MFA methods available for a user."""
        from .models import UserMFA
        from django.core.cache import cache

        mfa = UserMFA.objects.filter(user=user).first()
        methods = []

        has_totp = bool(mfa and mfa.totp_secret and (mfa.is_enabled or mfa.totp_enabled))
        if has_totp:
            methods.append({
                'id': 'authenticator',
                'name': 'Authenticator App',
                'description': 'Use 6-digit code from Google Authenticator, Authy, etc.',
                'icon': 'lock',
                'configured': True,
            })

        # Check WebAuthn / Passkeys
        has_passkey = False
        try:
            from admin_control_plane.models import AdminWebAuthnCredential
            has_passkey = AdminWebAuthnCredential.objects.filter(user=user, is_active=True).exists()
        except Exception:
            has_passkey = bool(mfa and mfa.passkey_enabled)

        if has_passkey or (mfa and mfa.passkey_enabled):
            methods.append({
                'id': 'passkey',
                'name': 'Passkey / Hardware Key',
                'description': 'Use fingerprint, Face ID, or security key.',
                'icon': 'key',
                'configured': True,
            })

        # Email / SMS OTP as recovery / access channel
        if user.email:
            # Mask email e.g. a***b@domain.com
            parts = user.email.split('@')
            masked_name = parts[0][0] + '***' + parts[0][-1] if len(parts[0]) > 2 else parts[0][0] + '***'
            masked_email = f"{masked_name}@{parts[1]}" if len(parts) > 1 else user.email
            methods.append({
                'id': 'otp',
                'name': 'One-Time Password (OTP)',
                'description': f'Send temporary code to {masked_email}',
                'icon': 'mail',
                'configured': True,
            })

        default_method = 'authenticator' if has_totp else ('passkey' if has_passkey else 'otp')

        mfa_enabled = getattr(settings, 'MFA_ENABLED', False)
        return {
            'methods': methods,
            'default_method': default_method,
            'requires_mfa': mfa_enabled and bool(has_totp or has_passkey or user.is_staff or user.role in [
                'Admin', 'Agent', 'Lawyer', 'Surveyor', 'Land_Official'
            ]),
        }

    @staticmethod
    def send_mfa_otp(user):
        """Generate and dispatch a short-lived 6-digit OTP code to the user's email."""
        from django.core.cache import cache
        from django.core.mail import send_mail
        from .models import AuditLog

        cache_key = f"mfa_otp_{user.id}"
        attempts_key = f"mfa_otp_attempts_{user.id}"

        # Rate-limiting check: max 5 requests per 10 mins
        rate_key = f"mfa_otp_rate_{user.id}"
        req_count = cache.get(rate_key, 0)
        if req_count >= 5:
            raise ValueError("Too many OTP requests. Please wait a few minutes before trying again.")
        cache.set(rate_key, req_count + 1, timeout=600)

        # Generate cryptographically secure 6-digit OTP
        otp_code = f"{secrets.randbelow(1000000):06d}"
        cache.set(cache_key, otp_code, timeout=300)  # 5 minutes
        cache.set(attempts_key, 0, timeout=300)

        # Send via Email
        subject = "DigiLand Security Verification Code"
        message = (
            f"Hello,\n\nYour temporary DigiLand verification code is: {otp_code}\n\n"
            f"This code will expire in 5 minutes. If you did not request this, please contact DigiLand Security immediately."
        )
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'security@digiland.co.ke'),
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception as e:
            logger.error("Failed to send MFA OTP email to %s: %s", user.email, str(e))
            raise ValueError("Failed to deliver verification code. Please try again.")

        AuditLog.objects.create(
            user=user,
            action='MFA_OTP_SENT',
            metadata={'delivery_channel': 'email'},
        )

        return {'sent': True, 'expires_in_seconds': 300}

    @staticmethod
    def verify_mfa_otp(user, code):
        """Verify an OTP code submitted by the user."""
        from django.core.cache import cache
        from .models import AuditLog

        cache_key = f"mfa_otp_{user.id}"
        attempts_key = f"mfa_otp_attempts_{user.id}"

        stored_otp = cache.get(cache_key)
        attempts = cache.get(attempts_key, 0)

        if not stored_otp:
            raise ValueError("Verification code expired or not requested. Please request a new code.")

        if attempts >= 5:
            cache.delete(cache_key)
            cache.delete(attempts_key)
            AuditLog.objects.create(
                user=user,
                action='MFA_OTP_LOCKED',
                metadata={'reason': 'exceeded_attempts'},
            )
            raise ValueError("Too many invalid attempts. This code is now invalid. Request a new code.")

        if code.strip() != stored_otp:
            cache.set(attempts_key, attempts + 1, timeout=300)
            AuditLog.objects.create(
                user=user,
                action='MFA_OTP_FAILURE',
                metadata={'attempt': attempts + 1},
            )
            return False

        # Success - consume code
        cache.delete(cache_key)
        cache.delete(attempts_key)

        AuditLog.objects.create(
            user=user,
            action='MFA_OTP_SUCCESS',
            metadata={'delivery_channel': 'email'},
        )
        return True
    
    @staticmethod
    def disable_mfa(user, totp_code=None, recovery_code=None):
        """Disable MFA for the user. Requires either TOTP code or recovery code."""
        from .models import UserMFA, AuditLog
        
        try:
            mfa = UserMFA.objects.get(user=user)
        except UserMFA.DoesNotExist:
            raise ValueError("MFA is not set up for this user.")
        
        if not mfa.is_enabled:
            raise ValueError("MFA is not enabled for this user.")
        
        # Verify with TOTP or recovery code
        verified = False
        if totp_code and mfa.totp_secret:
            verified = MFAService.verify_totp(mfa.totp_secret, totp_code)
        elif recovery_code and mfa.recovery_codes:
            for hashed in mfa.recovery_codes:
                if MFAService.verify_recovery_code(hashed, recovery_code):
                    verified = True
                    # Remove used recovery code
                    mfa.recovery_codes.remove(hashed)
                    break
        
        if not verified:
            raise ValueError("Verification failed. Provide valid TOTP code or recovery code.")
        
        # Check last-method protection
        if not mfa.can_disable_method('totp'):
            raise ValueError("Configure another authentication method before removing your last active security method.")

        mfa.is_enabled = False
        mfa.totp_enabled = False
        mfa.totp_secret = ''
        mfa.recovery_codes = []
        mfa.save()

        # Invalidate all trusted devices
        from .models import TrustedDevice
        TrustedDevice.objects.filter(user=user).delete()

        AuditLog.objects.create(
            user=user,
            action='MFA_DISABLED',
            metadata={'method': 'totp_code' if totp_code else 'recovery_code'},
        )

        MFAService.trigger_security_alert(user, 'MFA_REMOVED', {'method': 'totp'})

        return {'disabled': True}

    @staticmethod
    def trigger_security_alert(user, alert_type, metadata=None):
        """Dispatch email security alert via Resend integration for authentication events."""
        from django.core.mail import send_mail
        from django.conf import settings

        metadata = metadata or {}
        subject_map = {
            'NEW_LOGIN': "New DigiLand Staff Sign-In Alert",
            'PASSKEY_ADDED': "New Security Passkey Registered",
            'PASSKEY_REMOVED': "DigiLand Security Alert — Passkey Removed",
            'MFA_ADDED': "New Security Method Added",
            'MFA_REMOVED': "Security Method Removed",
            'SESSION_REVOKED': "DigiLand Session Terminated",
        }
        subject = subject_map.get(alert_type, "DigiLand Account Security Notification")

        body = f"Hello {user.get_full_name() or user.email},\n\n"
        body += f"Security Notification: {subject}\n"
        body += f"Event: {alert_type}\n"
        if metadata.get('ip_address'):
            body += f"IP Address: {metadata.get('ip_address')}\n"
        if metadata.get('user_agent'):
            body += f"Device: {metadata.get('user_agent')[:100]}\n"
        body += "\nIf you did not initiate this action, please log into DigiLand immediately and revoke active sessions or contact DigiLand Security."

        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'security@digiland.co.ke'),
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception as e:
            logger.warning("Failed sending security alert email to %s: %s", user.email, str(e))
    
    @staticmethod
    def verify_mfa(user, totp_code):
        """Verify MFA during login."""
        from .models import UserMFA
        
        try:
            mfa = UserMFA.objects.get(user=user, is_enabled=True)
        except UserMFA.DoesNotExist:
            # MFA not enabled, allow login
            return True
        
        if MFAService.verify_totp(mfa.totp_secret, totp_code):
            return True
        
        return False
    
    @staticmethod
    def use_recovery_code(user, recovery_code):
        """Use a recovery code for MFA login."""
        from .models import UserMFA, AuditLog
        
        try:
            mfa = UserMFA.objects.get(user=user, is_enabled=True)
        except UserMFA.DoesNotExist:
            return False
        
        for i, hashed in enumerate(mfa.recovery_codes):
            if MFAService.verify_recovery_code(hashed, recovery_code):
                # Remove used code
                mfa.recovery_codes.pop(i)
                mfa.save()
                
                AuditLog.objects.create(
                    user=user,
                    action='MFA_RECOVERY_CODE_USED',
                    metadata={'remaining_codes': len(mfa.recovery_codes)},
                )
                return True
        
        return False
    
    @staticmethod
    def regenerate_recovery_codes(user, totp_code):
        """Regenerate recovery codes. Requires TOTP verification."""
        from .models import UserMFA
        
        try:
            mfa = UserMFA.objects.get(user=user, is_enabled=True)
        except UserMFA.DoesNotExist:
            raise ValueError("MFA is not enabled for this user.")
        
        if not MFAService.verify_totp(mfa.totp_secret, totp_code):
            raise ValueError("Invalid TOTP code.")
        
        recovery_codes = MFAService.generate_recovery_codes()
        hashed_codes = [MFAService.hash_recovery_code(code) for code in recovery_codes]
        
        mfa.recovery_codes = hashed_codes
        mfa.save()
        
        return {'recovery_codes': recovery_codes}


class DeviceTrustService:
    """Manages trusted device tokens for MFA bypass."""
    
    TRUST_DURATION_DAYS = 30
    TOKEN_LENGTH = 64
    
    @staticmethod
    def create_trust_token(user, device_info):
        """Create a trust token for a device."""
        from .models import TrustedDevice
        
        token = secrets.token_hex(DeviceTrustService.TOKEN_LENGTH)
        expires_at = timezone.now() + timedelta(days=DeviceTrustService.TRUST_DURATION_DAYS)
        
        device = TrustedDevice.objects.create(
            user=user,
            trust_token=token,
            device_name=device_info.get('name', 'Unknown Device'),
            device_type=device_info.get('type', 'unknown'),
            user_agent=device_info.get('user_agent', ''),
            ip_address=device_info.get('ip_address', ''),
            expires_at=expires_at,
        )
        
        return {
            'trust_token': token,
            'expires_at': expires_at.isoformat(),
        }
    
    @staticmethod
    def verify_trust_token(user, trust_token):
        """Verify if a trust token is valid."""
        from .models import TrustedDevice
        
        try:
            device = TrustedDevice.objects.get(
                user=user,
                trust_token=trust_token,
                expires_at__gt=timezone.now(),
            )
            device.last_used_at = timezone.now()
            device.save(update_fields=['last_used_at'])
            return True
        except TrustedDevice.DoesNotExist:
            return False
    
    @staticmethod
    def revoke_trust_token(user, trust_token):
        """Revoke a trusted device token."""
        from .models import TrustedDevice
        TrustedDevice.objects.filter(user=user, trust_token=trust_token).delete()
    
    @staticmethod
    def list_trusted_devices(user):
        """List all trusted devices for a user."""
        from .models import TrustedDevice
        
        devices = TrustedDevice.objects.filter(
            user=user,
            expires_at__gt=timezone.now(),
        )
        return [
            {
                'id': str(d.id),
                'device_name': d.device_name,
                'device_type': d.device_type,
                'created_at': d.created_at.isoformat(),
                'last_used_at': d.last_used_at.isoformat() if d.last_used_at else None,
                'expires_at': d.expires_at.isoformat(),
            }
            for d in devices
        ]


class StepUpAuthService:
    """Step-up authentication for sensitive operations."""
    
    STEP_UP_DURATION = timedelta(minutes=5)
    
    SENSITIVE_OPERATIONS = [
        'payment_release',
        'payment_refund',
        'transaction_reverse',
        'admin_user_delete',
        'admin_role_change',
        'mfa_disable',
        'organization_settings_change',
        'escrow_withdrawal',
    ]
    
    @staticmethod
    def require_step_up(user, operation):
        """Check if step-up authentication is required for the operation."""
        from .models import UserMFA
        
        # If MFA is not enabled, no step-up required
        if not UserMFA.objects.filter(user=user, is_enabled=True).exists():
            return False
        
        if operation in StepUpAuthService.SENSITIVE_OPERATIONS:
            return True
        
        return False
    
    @staticmethod
    def verify_step_up(user, totp_code, operation):
        """Verify step-up authentication for a sensitive operation."""
        if not StepUpAuthService.require_step_up(user, operation):
            return True
        
        return MFAService.verify_mfa(user, totp_code)
