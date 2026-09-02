"""DRF serializers for the Digiland Authentication System.

Provides request/response serialization and validation for:
- Login and Registration flows
- MFA setup, verification, and recovery
- Password change and reset
- Token refresh
- OAuth callback processing
- Trusted device and session management
- WebAuthn registration and authentication
"""
import re
from typing import Any, Dict

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import (
    User, UserMFA, TrustedDevice, UserSession,
    OAuthProvider, OAuthAccount,
    Permission, RolePermission, LoginAttempt,
)

User = get_user_model()


# ── Login & Registration ────────────────────────────────────────────────────


class LoginSerializer(serializers.Serializer):
    """Serializer for the login endpoint.

    Accepts email + password and an optional MFA code. If the user has
    MFA enabled and no code is provided, the response includes an MFA
    challenge instead of tokens.
    """

    email = serializers.EmailField(help_text="User email address")
    password = serializers.CharField(write_only=True, help_text="Account password")
    mfa_code = serializers.CharField(
        max_length=20, required=False, allow_blank=True,
        help_text="TOTP code or recovery code (if MFA is enabled)",
    )

    def validate_email(self, value: str) -> str:
        return value.lower().strip()


class RegisterSerializer(serializers.Serializer):
    """Serializer for user registration with full validation.

    Validates email uniqueness, password strength, and creates the user on ``save()``.
    """

    email = serializers.EmailField(help_text="User email address (must be unique)")
    password = serializers.CharField(write_only=True, min_length=10, help_text="Password (min 10 chars)")
    full_name = serializers.CharField(max_length=200, required=False, default="", allow_blank=True, help_text="Full legal name")
    role = serializers.CharField(required=False, allow_null=True, allow_blank=True, help_text="Account role")
    phone_number = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True, help_text="Phone number")
    id_number = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True, help_text="National ID number")
    kra_pin = serializers.CharField(max_length=11, required=False, allow_null=True, allow_blank=True, help_text="KRA PIN")

    def validate_email(self, value: str) -> str:
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower().strip()

    def validate_role(self, value: str) -> str:
        if not value:
            return None
        valid_roles = [r for r, _ in User.ROLE_CHOICES]
        if value == 'Admin':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Admin role cannot be self-assigned.")
        if value not in valid_roles:
            raise serializers.ValidationError("Invalid role assigned.")
        return value

    def validate_phone_number(self, value: str) -> str:
        if not value:
            return None
        if not re.match(r"^(\+254|0)\d{9}$", value):
            raise serializers.ValidationError(
                "Phone number must start with +254 or 0 and have 10 digits total."
            )
        return value

    def validate_id_number(self, value: str) -> str:
        if not value:
            return None
        if not re.match(r"^\d{7,9}$", value):
            raise serializers.ValidationError("ID number must be 7, 8, or 9 digits.")
        return value

    def validate_kra_pin(self, value: str) -> str:
        if not value:
            return None
        if not re.match(r"^[A-Z]\d{9}[A-Z]$", value):
            raise serializers.ValidationError(
                "KRA PIN must be 11 characters: Letter + 9 digits + Letter."
            )
        return value

    def validate_password(self, value: str) -> str:
        try:
            validate_password(value)
        except Exception as exc:
            messages = [str(e) for e in getattr(exc, "messages", [str(exc)])]
            raise serializers.ValidationError(messages)
        return value

    def create(self, validated_data: Dict[str, Any]) -> User:
        full_name = validated_data.pop("full_name", "")
        name_parts = full_name.split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        role = validated_data.get("role")
        is_onboarded = False
        if role in ['Buyer', 'Seller', 'Agent']:
            is_onboarded = True

        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=first_name,
            last_name=last_name,
            role=role,
            is_onboarded=is_onboarded,
            phone_number=validated_data.get("phone_number"),
            id_number=validated_data.get("id_number"),
            kra_pin=validated_data.get("kra_pin"),
        )
        return user


# ── MFA Serializers ─────────────────────────────────────────────────────────


class MFASetupSerializer(serializers.Serializer):
    """Serializer for initiating MFA setup. No input required — user is authenticated."""
    pass


class MFAVerifySerializer(serializers.Serializer):
    """Serializer for verifying a TOTP code and enabling MFA."""

    totp_code = serializers.CharField(
        max_length=6, min_length=6,
        help_text="6-digit TOTP code from authenticator app",
    )

    def validate_totp_code(self, value: str) -> str:
        if not re.match(r"^\d{6}$", value):
            raise serializers.ValidationError("TOTP code must be exactly 6 digits.")
        return value


class MFADisableSerializer(serializers.Serializer):
    """Serializer for disabling MFA."""

    totp_code = serializers.CharField(max_length=6, min_length=6, required=False, help_text="6-digit TOTP code")
    recovery_code = serializers.CharField(max_length=20, required=False, help_text="Recovery code (format: XXXX-XXXX)")

    def validate(self, data):
        if not data.get("totp_code") and not data.get("recovery_code"):
            raise serializers.ValidationError("Either totp_code or recovery_code must be provided.")
        return data


class MFARecoverySerializer(serializers.Serializer):
    """Serializer for using a recovery code when the TOTP device is lost."""

    user_id = serializers.UUIDField(help_text="User ID from the login response")
    recovery_code = serializers.CharField(max_length=20, help_text="Recovery code in format XXXX-XXXX")


class MFARegenerateRecoverySerializer(serializers.Serializer):
    """Serializer for regenerating recovery codes."""

    totp_code = serializers.CharField(max_length=6, min_length=6, help_text="6-digit TOTP code to verify identity")


class MFALoginVerifySerializer(serializers.Serializer):
    """Serializer for MFA verification during login."""

    user_id = serializers.UUIDField(help_text="User ID from login response")
    totp_code = serializers.CharField(max_length=6, min_length=6, required=False, help_text="6-digit TOTP code")
    recovery_code = serializers.CharField(max_length=20, required=False, help_text="Recovery code")
    trust_device = serializers.BooleanField(default=False, help_text="Whether to trust this device for 30 days")

    def validate(self, data):
        if not data.get("totp_code") and not data.get("recovery_code"):
            raise serializers.ValidationError("Either totp_code or recovery_code must be provided.")
        return data


class MFAStatusSerializer(serializers.ModelSerializer):
    """Serializer for MFA status information."""

    has_recovery_codes = serializers.SerializerMethodField()
    recovery_codes_remaining = serializers.SerializerMethodField()

    class Meta:
        model = UserMFA
        fields = [
            "id", "is_enabled", "setup_started_at", "verified_at",
            "has_recovery_codes", "recovery_codes_remaining",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_has_recovery_codes(self, obj):
        return len(obj.recovery_codes) > 0

    def get_recovery_codes_remaining(self, obj):
        return len(obj.recovery_codes)


# ── Password Serializers ────────────────────────────────────────────────────


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing password while logged in."""

    old_password = serializers.CharField(write_only=True, help_text="Current password for verification")
    new_password = serializers.CharField(write_only=True, min_length=10, help_text="New password (min 10 chars)")

    def validate_old_password(self, value: str) -> str:
        user = self.context.get("request").user
        if not check_password(value, user.password):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value: str) -> str:
        try:
            validate_password(value)
        except Exception as exc:
            messages = [str(e) for e in getattr(exc, "messages", [str(exc)])]
            raise serializers.ValidationError(messages)
        return value

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if data.get("old_password") == data.get("new_password"):
            raise serializers.ValidationError(
                {"new_password": "New password must differ from the current password."}
            )
        return data


class ResetPasswordRequestSerializer(serializers.Serializer):
    """Serializer for requesting a password reset email."""

    email = serializers.EmailField(help_text="Registered email address")


# Alias: auth_views expects "PasswordResetRequestSerializer"
PasswordResetRequestSerializer = ResetPasswordRequestSerializer


class ResetPasswordConfirmSerializer(serializers.Serializer):
    """Serializer for confirming a password reset with a token."""

    token = serializers.CharField(help_text="Password reset token from email")
    new_password = serializers.CharField(write_only=True, min_length=10, help_text="New password (min 10 chars)")

    def validate_new_password(self, value: str) -> str:
        try:
            validate_password(value)
        except Exception as exc:
            messages = [str(e) for e in getattr(exc, "messages", [str(exc)])]
            raise serializers.ValidationError(messages)
        return value


# ── Token Refresh ───────────────────────────────────────────────────────────


class TokenRefreshSerializer(serializers.Serializer):
    """Serializer for refreshing JWT tokens."""

    refresh_token = serializers.CharField(help_text="Valid refresh JWT token")


# ── OAuth ───────────────────────────────────────────────────────────────────


class OAuthCallbackSerializer(serializers.Serializer):
    """Serializer for processing OAuth callbacks."""

    provider = serializers.ChoiceField(
        choices=["google", "github", "microsoft"],
        help_text="OAuth provider name",
    )
    code = serializers.CharField(help_text="Authorization code from provider")
    state = serializers.CharField(help_text="CSRF state token")


class OAuthProviderSerializer(serializers.ModelSerializer):
    """Serializer for OAuth provider configuration."""

    provider_display = serializers.CharField(source="get_provider_display", read_only=True)

    class Meta:
        model = OAuthProvider
        fields = [
            "id", "name", "provider", "provider_display",
            "authorization_url", "scope", "is_active",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
        extra_kwargs = {
            "client_id": {"write_only": True},
            "client_secret": {"write_only": True},
            "token_url": {"write_only": True},
            "userinfo_url": {"write_only": True},
        }


class OAuthProviderAdminSerializer(serializers.ModelSerializer):
    """Admin serializer for OAuth provider configuration — includes secrets."""

    provider_display = serializers.CharField(source="get_provider_display", read_only=True)

    class Meta:
        model = OAuthProvider
        fields = [
            "id", "name", "provider", "provider_display",
            "client_id", "client_secret", "authorization_url",
            "token_url", "userinfo_url", "scope", "is_active",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class OAuthAccountSerializer(serializers.ModelSerializer):
    """Serializer for OAuth account links."""

    provider_name = serializers.CharField(source="provider.name", read_only=True)
    provider_type = serializers.CharField(source="provider.provider", read_only=True)

    class Meta:
        model = OAuthAccount
        fields = [
            "id", "provider", "provider_name", "provider_type",
            "provider_user_id", "email", "profile_data",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "access_token", "refresh_token", "token_expires_at",
            "created_at", "updated_at",
        ]
        extra_kwargs = {
            "access_token": {"write_only": True},
            "refresh_token": {"write_only": True},
        }


# ── Trusted Device ──────────────────────────────────────────────────────────


class DeviceTrustSerializer(serializers.Serializer):
    """Serializer for trusting a device."""

    trust_token = serializers.CharField(help_text="Trust token received after MFA login verification")
    device_name = serializers.CharField(max_length=200, default="Unknown Device", required=False)
    device_type = serializers.CharField(max_length=50, default="unknown", required=False)


class TrustedDeviceSerializer(serializers.ModelSerializer):
    """Serializer for listing trusted devices."""

    is_current = serializers.SerializerMethodField()

    class Meta:
        model = TrustedDevice
        fields = [
            "id", "device_name", "device_type", "user_agent",
            "ip_address", "created_at", "last_used_at", "expires_at",
            "is_current",
        ]
        read_only_fields = fields

    def get_is_current(self, obj):
        request = self.context.get("request")
        if request:
            user_agent = request.META.get("HTTP_USER_AGENT", "")
            return obj.user_agent == user_agent
        return False


# ── Session ─────────────────────────────────────────────────────────────────


class UserSessionSerializer(serializers.ModelSerializer):
    """Serializer for user sessions."""

    is_current = serializers.SerializerMethodField()

    class Meta:
        model = UserSession
        fields = [
            "id", "session_key", "ip_address", "user_agent",
            "device_type", "location", "is_active",
            "created_at", "last_activity", "expires_at",
            "is_current",
        ]
        read_only_fields = fields

    def get_is_current(self, obj):
        request = self.context.get("request")
        if request:
            current_jti = getattr(request, "jti", None)
            if current_jti:
                return obj.refresh_token_jti == current_jti
        return False


class SessionListSerializer(serializers.ModelSerializer):
    """Read-only serializer for listing active sessions with extra info."""

    is_current = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = UserSession
        fields = [
            "id", "session_key", "ip_address", "user_agent",
            "device_type", "location", "is_active",
            "created_at", "last_activity", "expires_at",
            "is_current", "is_expired",
        ]
        read_only_fields = fields

    def get_is_current(self, obj) -> bool:
        request = self.context.get("request")
        if request:
            current_jti = getattr(request, "jti", None)
            if current_jti:
                return obj.refresh_token_jti == current_jti
        return False

    def get_is_expired(self, obj) -> bool:
        from django.utils import timezone
        return obj.expires_at < timezone.now()


# ── Permission Serializers ──────────────────────────────────────────────────


class PermissionSerializer(serializers.ModelSerializer):
    """Serializer for granular permissions."""

    class Meta:
        model = Permission
        fields = ["id", "codename", "name", "description", "resource_type", "action", "is_active", "created_at"]
        read_only_fields = ["created_at"]


class RolePermissionSerializer(serializers.ModelSerializer):
    """Serializer for role-permission mappings."""

    permission_codename = serializers.CharField(source="permission.codename", read_only=True)
    permission_name = serializers.CharField(source="permission.name", read_only=True)
    resource_type = serializers.CharField(source="permission.resource_type", read_only=True)
    action = serializers.CharField(source="permission.action", read_only=True)

    class Meta:
        model = RolePermission
        fields = [
            "id", "role", "permission", "permission_codename",
            "permission_name", "resource_type", "action",
            "conditions", "created_at",
        ]
        read_only_fields = ["created_at"]


# ── Login Attempt Serializer ────────────────────────────────────────────────


class LoginAttemptSerializer(serializers.ModelSerializer):
    """Serializer for login attempts (admin view)."""

    class Meta:
        model = LoginAttempt
        fields = ["id", "email", "ip_address", "user_agent", "success", "failure_reason", "created_at"]
        read_only_fields = fields


# ── Email Verification ──────────────────────────────────────────────────────


class EmailVerifySerializer(serializers.Serializer):
    """Serializer for email verification."""

    token = serializers.CharField(help_text="Email verification token")


# ── Step-Up Auth ────────────────────────────────────────────────────────────


class StepUpAuthSerializer(serializers.Serializer):
    """Serializer for step-up authentication."""

    operation = serializers.CharField(help_text="The sensitive operation being performed")
    totp_code = serializers.CharField(max_length=6, min_length=6, help_text="6-digit TOTP code")

    def validate_totp_code(self, value: str) -> str:
        if not re.match(r"^\d{6}$", value):
            raise serializers.ValidationError("TOTP code must be exactly 6 digits.")
        return value

    def validate_operation(self, value: str) -> str:
        from .auth_mfa import StepUpAuthService
        if value not in StepUpAuthService.SENSITIVE_OPERATIONS:
            raise serializers.ValidationError(
                f"Unknown operation. Valid: {', '.join(StepUpAuthService.SENSITIVE_OPERATIONS)}"
            )
        return value


# ── WebAuthn Serializers ────────────────────────────────────────────────────


class WebAuthnRegistrationSerializer(serializers.Serializer):
    """Serializer for WebAuthn registration challenge/response.

    Used for both the 'begin' step (no fields) and the 'finish' step
    (credential response).
    """

    credential = serializers.JSONField(
        required=False,
        help_text="WebAuthn credential response from the browser",
    )
    device_name = serializers.CharField(
        max_length=200, required=False, default="WebAuthn Device",
        help_text="Human-readable name for the registered authenticator",
    )


class WebAuthnAuthenticationSerializer(serializers.Serializer):
    """Serializer for WebAuthn authentication challenge/response.

    Used for both the 'begin' step (user_id required) and the
    'finish' step (credential assertion required).
    """

    user_id = serializers.UUIDField(
        required=False, help_text="User ID for generating the auth challenge",
    )
    credential = serializers.JSONField(
        required=False, help_text="WebAuthn assertion response from the browser",
    )


# ── Multi-Method MFA & Session Serializers ──────────────────────────────────


class MFAVerifyChallengeSerializer(serializers.Serializer):
    """Unified multi-method MFA challenge verification serializer."""

    method = serializers.ChoiceField(
        choices=['authenticator', 'passkey', 'otp', 'recovery_code'],
        default='authenticator',
        help_text="The selected MFA verification method",
    )
    code = serializers.CharField(
        max_length=64,
        required=False,
        allow_blank=True,
        help_text="Verification code (6-digit TOTP, OTP, or recovery code)",
    )
    challenge_token = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        help_text="Temporary password-authenticated stage 1 token",
    )
    credential = serializers.JSONField(
        required=False,
        help_text="WebAuthn credential assertion for passkey verification",
    )


class SessionHeartbeatSerializer(serializers.Serializer):
    """Serializer for updating session activity and extending session lifetime."""

    extend_session = serializers.BooleanField(
        default=True,
        help_text="If true, extends the user session activity timer",
    )

