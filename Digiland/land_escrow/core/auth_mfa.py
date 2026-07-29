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
        
        mfa.is_enabled = False
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
        
        return {'disabled': True}
    
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
