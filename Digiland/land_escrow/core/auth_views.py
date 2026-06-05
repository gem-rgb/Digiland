"""API views for the Digiland Authentication System.

Provides production-grade endpoints for:
- Login and registration with JWT token issuance
- TOTP-based MFA setup, verification, and disabling
- Recovery code management
- Trusted device management
- Session listing and revocation
- OAuth/SSO authorization and callback
- Password change and reset flows
- Email verification
- Step-up authentication
- WebAuthn registration and authentication ceremonies
- Token refresh and logout
- Brute-force login protection with rate limiting
- Comprehensive audit logging
"""
import hashlib
import secrets
import logging
import urllib.parse

from datetime import timedelta

import requests as http_requests

from django.utils import timezone
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
from django.core.cache import cache
from django.db import transaction

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from .auth_mfa import MFAService, DeviceTrustService, StepUpAuthService
from .auth_services import (
    JWTService, MFAService as AuthMFAService,
    OAuthService, WebAuthnService, PasswordService,
    SessionService, AuditService,
    _get_client_ip, _get_device_type,
)
from .auth_serializers import (
    LoginSerializer, RegisterSerializer,
    MFASetupSerializer, MFAVerifySerializer,
    MFADisableSerializer, MFARegenerateRecoverySerializer,
    MFALoginVerifySerializer, MFARecoverySerializer, MFAStatusSerializer,
    DeviceTrustSerializer, TrustedDeviceSerializer,
    UserSessionSerializer, SessionListSerializer,
    OAuthProviderSerializer, OAuthProviderAdminSerializer,
    OAuthAccountSerializer, OAuthCallbackSerializer,
    PermissionSerializer, RolePermissionSerializer,
    LoginAttemptSerializer,
    PasswordResetRequestSerializer, ResetPasswordConfirmSerializer,
    ChangePasswordSerializer,
    EmailVerifySerializer, StepUpAuthSerializer,
    TokenRefreshSerializer,
    WebAuthnRegistrationSerializer, WebAuthnAuthenticationSerializer,
)
from .models import (
    UserMFA, TrustedDevice, UserSession, OAuthProvider, OAuthAccount,
    Permission, RolePermission, LoginAttempt, AuditLog,
)

User = get_user_model()
logger = logging.getLogger(__name__)


# ── Rate limit helper ──────────────────────────────────────────────────────


class LoginRateThrottle(AnonRateThrottle):
    """Rate limit for login/register endpoints: 5 req/min per IP."""
    rate = "5/min"


class PasswordResetRateThrottle(AnonRateThrottle):
    """Rate limit for password reset: 3 req/min per IP."""
    rate = "3/min"


# ── Brute-force helpers ────────────────────────────────────────────────────


def _check_brute_force(email, ip_address):
    """Check if login should be blocked due to too many failed attempts."""
    max_attempts = getattr(settings, "BRUTE_FORCE_MAX_ATTEMPTS", 5)
    window_minutes = getattr(settings, "BRUTE_FORCE_WINDOW_MINUTES", 15)

    email_key = f"bf:email:{email}"
    email_attempts = cache.get(email_key, 0)
    if email_attempts >= max_attempts:
        return True, "Too many failed login attempts. Please try again later."

    ip_key = f"bf:ip:{ip_address}"
    ip_attempts = cache.get(ip_key, 0)
    if ip_attempts >= max_attempts * 2:
        return True, "Too many failed login attempts from this IP. Please try again later."

    return False, None


def _record_failed_attempt(email, ip_address):
    """Record a failed login attempt for brute-force protection."""
    window_minutes = getattr(settings, "BRUTE_FORCE_WINDOW_MINUTES", 15)
    email_key = f"bf:email:{email}"
    ip_key = f"bf:ip:{ip_address}"
    cache.set(email_key, cache.get(email_key, 0) + 1, timeout=window_minutes * 60)
    cache.set(ip_key, cache.get(ip_key, 0) + 1, timeout=window_minutes * 60)


def _clear_brute_force(email, ip_address):
    """Clear brute-force counters after successful login."""
    cache.delete(f"bf:email:{email}")
    cache.delete(f"bf:ip:{ip_address}")


# ==================== LOGIN VIEW ====================


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def login_view(request):
    """Authenticate a user and return JWT tokens.

    POST /api/v1/auth/login/

    Body: { "email": "...", "password": "...", "mfa_code": "..." }

    If the user has MFA enabled and no mfa_code is provided, returns
    an MFA challenge instead of tokens.
    """
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data["email"]
    password = serializer.validated_data["password"]
    mfa_code = serializer.validated_data.get("mfa_code", "")
    ip_address = _get_client_ip(request)

    # Check brute-force
    locked, msg = _check_brute_force(email, ip_address)
    if locked:
        return Response({"error": msg}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    # Authenticate
    user = authenticate(request, username=email, password=password)
    if not user:
        _record_failed_attempt(email, ip_address)
        AuditService.log_event("LOGIN_FAILURE", ip_address=ip_address, metadata={"email": email})
        LoginAttempt.objects.create(
            email=email, ip_address=ip_address,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
            success=False, failure_reason="INVALID_CREDENTIALS",
        )
        return Response(
            {"error": "Invalid email or password."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        return Response({"error": "Account is disabled."}, status=status.HTTP_403_FORBIDDEN)

    # Check MFA
    try:
        mfa = UserMFA.objects.get(user=user, is_enabled=True)
        if not mfa_code:
            # SECURITY: Return opaque MFA challenge token instead of user_id
            # to prevent user_id leakage and brute-force attacks
            mfa_token = secrets.token_urlsafe(32)
            cache.set(f"mfa_challenge:{mfa_token}", {"user_id": str(user.id)}, timeout=300)
            return Response({
                "mfa_required": True,
                "mfa_token": mfa_token,
                "message": "MFA code required. Provide mfa_token and mfa_code to complete login.",
            }, status=status.HTTP_200_OK)

        # Verify MFA code
        if len(mfa_code) == 6 and mfa_code.isdigit():
            if not AuthMFAService.verify_totp_code(mfa.totp_secret, mfa_code):
                _record_failed_attempt(email, ip_address)
                return Response({"error": "Invalid MFA code."}, status=status.HTTP_401_UNAUTHORIZED)
        else:
            valid, idx = AuthMFAService.validate_recovery_code(mfa.recovery_codes, mfa_code)
            if not valid:
                _record_failed_attempt(email, ip_address)
                return Response({"error": "Invalid recovery code."}, status=status.HTTP_401_UNAUTHORIZED)
            mfa.recovery_codes.pop(idx)
            mfa.save()

    except UserMFA.DoesNotExist:
        pass  # MFA not enabled, proceed

    # Generate tokens — use single token generation to avoid orphaned tokens
    tokens = JWTService.generate_tokens(user)

    # Create session
    SessionService.create_session(user, request)

    # Audit log
    _clear_brute_force(email, ip_address)
    AuditService.log_login(user, ip_address)
    LoginAttempt.objects.create(
        email=email, ip_address=ip_address,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        success=True,
    )

    return Response({
        "message": "Login successful.",
        "user": {
            "id": str(user.id), "email": user.email,
            "role": user.role, "first_name": user.first_name,
            "last_name": user.last_name,
            "is_identity_verified": user.is_identity_verified,
        },
        "tokens": tokens,
    }, status=status.HTTP_200_OK)


# ==================== REGISTER VIEW ====================


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def register_view(request):
    """Register a new user and send a verification email.

    POST /api/v1/auth/register/

    Returns the created user data and a verification email is sent.
    """
    serializer = RegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        user = serializer.save()

    # Send verification email
    verify_token = secrets.token_urlsafe(48)
    cache.set(f"emailverify:{verify_token}", {"user_id": str(user.id)}, timeout=86400)
    try:
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
        verify_url = f"{frontend_url}/verify-email?token={verify_token}"
        send_mail(
            subject="Digiland - Verify Your Email",
            message=f"Click the following link to verify your email: {verify_url}\n\nThis link expires in 24 hours.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception as e:
        logger.error("Failed to send verification email: %s", str(e))

    ip_address = _get_client_ip(request)
    AuditService.log_event("USER_REGISTERED", user=user, ip_address=ip_address, metadata={"email": user.email})

    return Response({
        "message": "Registration successful. Please check your email to verify your account.",
        "user": {
            "id": str(user.id), "email": user.email, "role": user.role,
        },
    }, status=status.HTTP_201_CREATED)


# ==================== MFA VIEWS ====================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mfa_setup_view(request):
    """Initialize MFA setup for the authenticated user.

    POST /api/v1/auth/mfa/setup/

    Returns TOTP secret and QR code for authenticator app setup.
    """
    try:
        result = MFAService.setup_mfa(request.user)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("MFA setup failed for %s: %s", request.user.email, str(e))
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mfa_verify_view(request):
    """Verify TOTP code and enable MFA for the authenticated user.

    POST /api/v1/auth/mfa/verify/

    Body: { "totp_code": "123456" }

    Returns recovery codes on success (shown only once).
    """
    serializer = MFAVerifySerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = MFAService.enable_mfa(request.user, serializer.validated_data["totp_code"])
        ip_address = _get_client_ip(request)
        AuditService.log_mfa_event("ENABLED", request.user, ip_address)
        return Response(result, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MFARecoveryRateThrottle(AnonRateThrottle):
    """Rate limit for MFA recovery: 3 req/min per IP."""
    rate = "3/min"


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([MFARecoveryRateThrottle])
def mfa_recovery_view(request):
    """Use a recovery code when the TOTP device is lost.

    POST /api/v1/auth/mfa/recovery/

    Body: { "user_id": "uuid", "recovery_code": "XXXX-XXXX" }
    """
    serializer = MFARecoverySerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user_id = serializer.validated_data["user_id"]
    recovery_code = serializer.validated_data["recovery_code"]
    ip_address = _get_client_ip(request)

    # SECURITY: Brute-force lockout for MFA recovery attempts
    bf_key = f"mfa_recovery_bf:{user_id}:{ip_address}"
    if cache.get(bf_key, 0) >= 5:
        return Response(
            {"error": "Too many MFA recovery attempts. Please try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    try:
        user = User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        return Response({"error": "Invalid user."}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        mfa = UserMFA.objects.get(user=user, is_enabled=True)
    except UserMFA.DoesNotExist:
        return Response({"error": "MFA not enabled."}, status=status.HTTP_400_BAD_REQUEST)

    valid, idx = AuthMFAService.validate_recovery_code(mfa.recovery_codes, recovery_code)
    if not valid:
        # SECURITY: Increment brute-force counter on failure
        cache.set(bf_key, cache.get(bf_key, 0) + 1, timeout=900)
        return Response({"error": "Invalid recovery code."}, status=status.HTTP_401_UNAUTHORIZED)

    mfa.recovery_codes.pop(idx)
    mfa.save()

    # Issue tokens
    tokens = JWTService.generate_tokens(user)
    ip_address = _get_client_ip(request)
    AuditService.log_mfa_event("RECOVERY_CODE_USED", user, ip_address, remaining_codes=len(mfa.recovery_codes))

    return Response({
        "message": "Recovery code accepted. Please set up MFA again.",
        "tokens": tokens,
        "mfa_reset_required": True,
    }, status=status.HTTP_200_OK)


# ==================== MFA ADDITIONAL VIEWS ====================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mfa_disable_view(request):
    """Disable MFA for the authenticated user.

    POST /api/v1/auth/mfa/disable/

    Body: { "totp_code": "123456" } or { "recovery_code": "ABCD-EFGH" }
    """
    serializer = MFADisableSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = MFAService.disable_mfa(
            request.user,
            totp_code=serializer.validated_data.get("totp_code"),
            recovery_code=serializer.validated_data.get("recovery_code"),
        )
        ip_address = _get_client_ip(request)
        AuditService.log_mfa_event("DISABLED", request.user, ip_address)
        return Response(result, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mfa_regenerate_recovery_view(request):
    """Regenerate recovery codes. Requires TOTP verification.

    POST /api/v1/auth/mfa/recovery-codes/
    """
    serializer = MFARegenerateRecoverySerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = MFAService.regenerate_recovery_codes(request.user, serializer.validated_data["totp_code"])
        return Response(result, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def mfa_login_verify_view(request):
    """Verify MFA during login flow.

    POST /api/v1/auth/mfa/login-verify/
    """
    serializer = MFALoginVerifySerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # SECURITY: Support both opaque mfa_token (new) and direct user_id (legacy)
    mfa_token = request.data.get("mfa_token")
    user_id = serializer.validated_data.get("user_id")

    # If mfa_token provided, resolve user_id from cache (preferred flow)
    if mfa_token:
        challenge_data = cache.get(f"mfa_challenge:{mfa_token}")
        if not challenge_data:
            return Response({"error": "Invalid or expired MFA challenge."}, status=status.HTTP_400_BAD_REQUEST)
        cache.delete(f"mfa_challenge:{mfa_token}")  # Single-use
        user_id = challenge_data["user_id"]

    totp_code = serializer.validated_data.get("totp_code")
    recovery_code = serializer.validated_data.get("recovery_code")
    trust_device = serializer.validated_data.get("trust_device", False)

    if not user_id:
        return Response({"error": "MFA token or user_id required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        return Response({"error": "Invalid user."}, status=status.HTTP_401_UNAUTHORIZED)

    trust_token = request.data.get("trust_token")
    if trust_token and DeviceTrustService.verify_trust_token(user, trust_token):
        refresh = RefreshToken.for_user(user)
        return Response({
            "message": "Login successful (trusted device)",
            "user": {"id": str(user.id), "email": user.email, "role": user.role},
            "tokens": {"refresh": str(refresh), "access": str(refresh.access_token)},
        }, status=status.HTTP_200_OK)

    verified = False
    if totp_code:
        verified = MFAService.verify_mfa(user, totp_code)
    elif recovery_code:
        verified = MFAService.use_recovery_code(user, recovery_code)

    if not verified:
        ip_address = _get_client_ip(request)
        LoginAttempt.objects.create(
            email=user.email, ip_address=ip_address,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
            success=False, failure_reason="MFA_VERIFICATION_FAILED",
        )
        return Response({"error": "MFA verification failed."}, status=status.HTTP_401_UNAUTHORIZED)

    refresh = RefreshToken.for_user(user)
    ip_address = _get_client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    device_type = _get_device_type(user_agent)

    UserSession.objects.create(
        user=user,
        session_key=hashlib.sha256(str(refresh).encode()).hexdigest()[:64],
        refresh_token_jti=str(refresh.get("jti", "")),
        ip_address=ip_address,
        user_agent=user_agent[:500],
        device_type=device_type,
        is_active=True,
        expires_at=timezone.now() + timedelta(days=1),
    )

    response_data = {
        "message": "MFA verification successful",
        "user": {
            "id": str(user.id), "email": user.email,
            "role": user.role, "is_identity_verified": user.is_identity_verified,
        },
        "tokens": {"refresh": str(refresh), "access": str(refresh.access_token)},
    }

    if trust_device:
        trust_result = DeviceTrustService.create_trust_token(user, {
            "name": request.data.get("device_name", "Unknown Device"),
            "type": device_type, "user_agent": user_agent[:500],
            "ip_address": ip_address,
        })
        response_data["trust_token"] = trust_result["trust_token"]
        response_data["trust_expires_at"] = trust_result["expires_at"]

    AuditService.log_mfa_event("LOGIN_SUCCESS", user, ip_address, method="totp" if totp_code else "recovery_code")
    LoginAttempt.objects.create(email=user.email, ip_address=ip_address,
                                user_agent=user_agent[:500], success=True)
    _clear_brute_force(user.email, ip_address)

    return Response(response_data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def mfa_status_view(request):
    """Get MFA status for the authenticated user."""
    try:
        mfa = UserMFA.objects.get(user=request.user)
        serializer = MFAStatusSerializer(mfa)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except UserMFA.DoesNotExist:
        return Response({
            "is_enabled": False, "has_recovery_codes": False, "recovery_codes_remaining": 0,
        }, status=status.HTTP_200_OK)


# ==================== PASSWORD VIEWS ====================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    """Change password for the authenticated user.

    POST /api/v1/auth/password/change/

    SECURITY: After password change, all other active sessions are invalidated
    to evict any potential attacker who may have stolen a session token.
    """
    serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    request.user.set_password(serializer.validated_data["new_password"])
    request.user.save()

    # SECURITY: Invalidate all sessions except the current one
    current_jti = ""
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if auth_header.startswith("Bearer "):
        try:
            from rest_framework_simplejwt.authentication import JWTAuthentication
            validated = JWTAuthentication().get_validated_token(auth_header.split(" ")[1])
            current_jti = str(validated.get("jti", ""))
        except Exception:
            pass

    revoked_count = SessionService.revoke_all_sessions(request.user, exclude_jti=current_jti)

    ip_address = _get_client_ip(request)
    AuditService.log_password_change(request.user, ip_address)

    return Response({
        "message": "Password changed successfully.",
        "sessions_revoked": revoked_count,
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetRateThrottle])
def reset_password_request_view(request):
    """Request a password reset email.

    POST /api/v1/auth/password/reset/

    Always returns success to prevent email enumeration.
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data["email"]

    try:
        user = User.objects.get(email=email, is_active=True)
    except User.DoesNotExist:
        return Response(
            {"message": "If an account with that email exists, a reset link has been sent."},
            status=status.HTTP_200_OK,
        )

    token = secrets.token_urlsafe(48)
    # SECURITY: 20-minute expiry per production readiness requirement
    cache.set(f"pwreset:{token}", {"user_id": str(user.id), "email": user.email}, timeout=1200)

    try:
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
        reset_url = f"{frontend_url}/reset-password?token={token}"
        send_mail(
            subject="Digiland - Password Reset Request",
            message=f"Click to reset your password: {reset_url}\n\nThis link expires in 20 minutes.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True,
        )
    except Exception as e:
        logger.error("Failed to send password reset email: %s", str(e))

    return Response(
        {"message": "If an account with that email exists, a reset link has been sent."},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def reset_password_confirm_view(request):
    """Confirm a password reset with the token and new password.

    POST /api/v1/auth/password/reset/confirm/
    """
    serializer = ResetPasswordConfirmSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    token = serializer.validated_data["token"]
    token_data = cache.get(f"pwreset:{token}")

    if not token_data:
        return Response({"error": "Invalid or expired reset token."}, status=status.HTTP_400_BAD_REQUEST)

    cache.delete(f"pwreset:{token}")

    try:
        user = User.objects.get(id=token_data["user_id"], is_active=True)
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(serializer.validated_data["new_password"])
    user.save()

    # Invalidate all sessions
    UserSession.objects.filter(user=user, is_active=True).update(is_active=False)

    AuditService.log_event("PASSWORD_RESET_COMPLETED", user=user, metadata={"method": "email_token"})

    return Response(
        {"message": "Password reset successful. Please log in with your new password."},
        status=status.HTTP_200_OK,
    )


# ==================== TOKEN REFRESH VIEW ====================


@api_view(["POST"])
@permission_classes([AllowAny])
def token_refresh_view(request):
    """Refresh JWT tokens.

    POST /api/v1/auth/token/refresh/

    Body: { "refresh_token": "..." }
    """
    serializer = TokenRefreshSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    tokens = JWTService.refresh_tokens(serializer.validated_data["refresh_token"])
    if not tokens:
        return Response(
            {"error": "Invalid or expired refresh token."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    return Response(tokens, status=status.HTTP_200_OK)


# ==================== OAUTH VIEWS ====================


@api_view(["GET"])
@permission_classes([AllowAny])
def oauth_init_view(request, provider):
    """Redirect to OAuth provider for authorization.

    GET /api/v1/auth/oauth/<provider>/
    """
    if provider not in OAuthService.PROVIDER_CONFIGS:
        return Response({"error": f"Unsupported OAuth provider: {provider}"}, status=status.HTTP_400_BAD_REQUEST)

    # Get client credentials from DB or settings
    try:
        oauth_provider = OAuthProvider.objects.get(provider=provider, is_active=True)
        client_id = oauth_provider.client_id
        redirect_uri = request.query_params.get("redirect_uri", "")
    except OAuthProvider.DoesNotExist:
        return Response(
            {"error": f"OAuth provider '{provider}' not configured."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    cache.set(
        f"oauth:state:{state}",
        {"provider": provider, "redirect_uri": redirect_uri},
        timeout=600,
    )

    auth_url = OAuthService.get_authorization_url(provider, client_id, redirect_uri, state)

    return Response({
        "authorization_url": auth_url,
        "state": state,
        "provider": provider,
    }, status=status.HTTP_200_OK)


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def oauth_callback_view(request, provider):
    """Handle OAuth callback from the provider.

    GET/POST /api/v1/auth/oauth/<provider>/callback/
    """
    if request.method == "GET":
        code = request.query_params.get("code")
        state = request.query_params.get("state")
    else:
        code = request.data.get("code")
        state = request.data.get("state")

    if not code or not state:
        return Response({"error": "Missing code or state parameter."}, status=status.HTTP_400_BAD_REQUEST)

    # Verify state
    state_data = cache.get(f"oauth:state:{state}")
    if not state_data or state_data.get("provider") != provider:
        return Response({"error": "Invalid or expired state parameter."}, status=status.HTTP_400_BAD_REQUEST)
    cache.delete(f"oauth:state:{state}")

    redirect_uri = state_data.get("redirect_uri", "")

    try:
        oauth_provider = OAuthProvider.objects.get(provider=provider, is_active=True)
    except OAuthProvider.DoesNotExist:
        return Response({"error": f"OAuth provider '{provider}' not found."}, status=status.HTTP_404_NOT_FOUND)

    # Exchange code for tokens
    token_data = OAuthService.exchange_code_for_token(
        provider, code, oauth_provider.client_id, oauth_provider.client_secret, redirect_uri,
    )
    if not token_data:
        return Response({"error": "Failed to exchange authorization code."}, status=status.HTTP_400_BAD_REQUEST)

    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 3600)

    # Fetch user profile
    profile = OAuthService.fetch_user_profile(provider, access_token)
    if not profile or not profile.get("sub"):
        return Response({"error": "Could not determine user identity from OAuth provider."}, status=status.HTTP_400_BAD_REQUEST)

    provider_user_id = profile["sub"]
    email = profile.get("email", "")
    first_name = profile.get("first_name", "")
    last_name = profile.get("last_name", "")

    # Find or create OAuth account
    with transaction.atomic():
        try:
            oauth_account = OAuthAccount.objects.get(
                provider=oauth_provider, provider_user_id=str(provider_user_id),
            )
            user = oauth_account.user
            oauth_account.access_token = access_token
            oauth_account.refresh_token = refresh_token
            oauth_account.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
            oauth_account.email = email
            oauth_account.profile_data = profile
            oauth_account.save()
        except OAuthAccount.DoesNotExist:
            user = None
            if email:
                try:
                    user = User.objects.get(email=email)
                except User.DoesNotExist:
                    temp_password = secrets.token_urlsafe(32)
                    user = User.objects.create_user(
                        email=email, password=temp_password,
                        first_name=first_name, last_name=last_name,
                        role="Buyer", id_number="00000000",
                        phone_number="+254700000000", kra_pin="A000000000Z",
                    )

            if user:
                OAuthAccount.objects.create(
                    user=user, provider=oauth_provider,
                    provider_user_id=str(provider_user_id),
                    email=email, access_token=access_token,
                    refresh_token=refresh_token,
                    token_expires_at=timezone.now() + timedelta(seconds=expires_in),
                    profile_data=profile,
                )
            else:
                return Response({"error": "Could not create or link user account."}, status=status.HTTP_400_BAD_REQUEST)

    # Generate JWT tokens
    tokens = JWTService.generate_tokens(user)
    ip_address = _get_client_ip(request)

    AuditService.log_oauth_link(user, ip_address, provider=provider)
    AuditService.log_login(user, ip_address, method=f"oauth_{provider}")
    LoginAttempt.objects.create(email=user.email, ip_address=ip_address,
                                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500], success=True)

    return Response({
        "message": f"OAuth login successful via {provider}",
        "user": {
            "id": str(user.id), "email": user.email, "role": user.role,
            "first_name": user.first_name, "last_name": user.last_name,
        },
        "tokens": tokens,
    }, status=status.HTTP_200_OK)


# ==================== WEBAUTHN VIEWS ====================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def webauthn_registration_begin_view(request):
    """Start WebAuthn registration by generating a challenge.

    POST /api/v1/auth/webauthn/register/begin/
    """
    rp_id = request.get_host().split(":")[0]
    challenge = WebAuthnService.generate_registration_challenge(
        user_id=str(request.user.id),
        email=request.user.email,
        rp_id=rp_id,
    )
    return Response(challenge, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def webauthn_registration_finish_view(request):
    """Complete WebAuthn registration by verifying the credential.

    POST /api/v1/auth/webauthn/register/finish/
    """
    serializer = WebAuthnRegistrationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    credential = serializer.validated_data.get("credential")
    if not credential:
        return Response({"error": "Credential response is required."}, status=status.HTTP_400_BAD_REQUEST)

    rp_id = request.get_host().split(":")[0]
    origin = request.build_absolute_uri("/").rstrip("/")
    result = WebAuthnService.verify_registration(
        str(request.user.id), credential, rp_id, origin,
    )

    if not result:
        return Response({"error": "WebAuthn registration verification failed."}, status=status.HTTP_400_BAD_REQUEST)

    # Store credential (in a real app, persist to DB)
    ip_address = _get_client_ip(request)
    AuditService.log_event("WEBAUTHN_REGISTERED", user=request.user, ip_address=ip_address,
                           metadata={"credential_id": result.get("credential_id", "")})

    return Response({
        "message": "WebAuthn authenticator registered successfully.",
        "credential_id": result.get("credential_id"),
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
def webauthn_authentication_begin_view(request):
    """Start WebAuthn authentication by generating a challenge.

    POST /api/v1/auth/webauthn/auth/begin/
    """
    serializer = WebAuthnAuthenticationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user_id = serializer.validated_data.get("user_id")
    if not user_id:
        return Response({"error": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST)

    rp_id = request.get_host().split(":")[0]
    # In a real app, retrieve stored credential IDs for the user
    credential_ids = []

    challenge = WebAuthnService.generate_authentication_challenge(
        user_id=str(user_id), rp_id=rp_id, credential_ids=credential_ids,
    )
    return Response(challenge, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
def webauthn_authentication_finish_view(request):
    """Complete WebAuthn authentication by verifying the assertion.

    POST /api/v1/auth/webauthn/auth/finish/
    """
    serializer = WebAuthnAuthenticationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    credential = serializer.validated_data.get("credential")
    user_id = serializer.validated_data.get("user_id")

    if not credential or not user_id:
        return Response({"error": "user_id and credential are required."}, status=status.HTTP_400_BAD_REQUEST)

    rp_id = request.get_host().split(":")[0]
    origin = request.build_absolute_uri("/").rstrip("/")

    if not WebAuthnService.verify_authentication(str(user_id), credential, rp_id, origin):
        return Response({"error": "WebAuthn authentication failed."}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        user = User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=status.HTTP_401_UNAUTHORIZED)

    tokens = JWTService.generate_tokens(user)
    ip_address = _get_client_ip(request)
    AuditService.log_login(user, ip_address, method="webauthn")

    return Response({
        "message": "WebAuthn authentication successful.",
        "user": {"id": str(user.id), "email": user.email, "role": user.role},
        "tokens": tokens,
    }, status=status.HTTP_200_OK)


# ==================== TRUSTED DEVICE VIEWS ====================


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def trusted_device_list_view(request):
    """List all trusted devices for the authenticated user.

    GET /api/v1/auth/devices/
    """
    devices = TrustedDevice.objects.filter(
        user=request.user, expires_at__gt=timezone.now(),
    ).order_by("-last_used_at", "-created_at")

    serializer = TrustedDeviceSerializer(devices, many=True, context={"request": request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def trusted_device_revoke_view(request, pk):
    """Revoke a trusted device.

    DELETE /api/v1/auth/devices/<uuid:pk>/revoke/
    """
    device = get_object_or_404(TrustedDevice, id=pk, user=request.user)
    device_name = device.device_name
    device.delete()

    ip_address = _get_client_ip(request)
    AuditService.log_event("TRUSTED_DEVICE_REVOKED", user=request.user, ip_address=ip_address,
                           metadata={"device_name": device_name, "device_id": str(pk)})

    return Response({"message": "Trusted device revoked successfully."}, status=status.HTTP_200_OK)


# ==================== SESSION VIEWS ====================


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def active_sessions_view(request):
    """List active sessions for the authenticated user.

    GET /api/v1/auth/sessions/
    """
    sessions = SessionService.list_active_sessions(request.user)
    serializer = SessionListSerializer(sessions, many=True, context={"request": request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def active_session_revoke_view(request):
    """Revoke all sessions except the current one.

    DELETE /api/v1/auth/sessions/
    """
    current_jti = ""
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if auth_header.startswith("Bearer "):
        try:
            from rest_framework_simplejwt.authentication import JWTAuthentication
            validated = JWTAuthentication().get_validated_token(auth_header.split(" ")[1])
            current_jti = str(validated.get("jti", ""))
        except Exception:
            pass

    revoked_count = SessionService.revoke_all_sessions(request.user, exclude_jti=current_jti)
    ip_address = _get_client_ip(request)
    AuditService.log_event("ALL_SESSIONS_REVOKED", user=request.user, ip_address=ip_address,
                           metadata={"revoked_count": revoked_count})

    return Response({
        "message": f"Revoked {revoked_count} session(s).",
        "revoked_count": revoked_count,
    }, status=status.HTTP_200_OK)


# ==================== SESSION DETAIL REVOKE VIEW ====================


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def session_detail_revoke_view(request, pk):
    """Revoke a specific session by its ID.

    DELETE /api/v1/auth/sessions/<uuid:pk>/
    """
    session = get_object_or_404(UserSession, id=pk, user=request.user)
    session.is_active = False
    session.save(update_fields=["is_active"])

    ip_address = _get_client_ip(request)
    AuditService.log_event("SESSION_REVOKED", user=request.user, ip_address=ip_address,
                           metadata={"session_id": str(pk)})

    return Response({"message": "Session revoked successfully."}, status=status.HTTP_200_OK)


# ==================== LOGOUT VIEW ====================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Logout: blacklist the current refresh token and clear session.

    POST /api/v1/auth/logout/

    Body: { "refresh_token": "..." }
    """
    refresh_token = request.data.get("refresh_token")
    if refresh_token:
        JWTService.blacklist_token(refresh_token)

    ip_address = _get_client_ip(request)
    AuditService.log_logout(request.user, ip_address)

    return Response({"message": "Logged out successfully."}, status=status.HTTP_200_OK)


# ==================== DEVICE TRUST VIEW ====================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def device_trust_view(request):
    """Trust a device for MFA bypass.

    POST /api/v1/auth/devices/trust/
    """
    serializer = DeviceTrustSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    trust_token = serializer.validated_data["trust_token"]
    if not DeviceTrustService.verify_trust_token(request.user, trust_token):
        return Response({"error": "Invalid trust token."}, status=status.HTTP_400_BAD_REQUEST)

    ip_address = _get_client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "")

    result = DeviceTrustService.create_trust_token(request.user, {
        "name": serializer.validated_data.get("device_name", "Unknown Device"),
        "type": serializer.validated_data.get("device_type", _get_device_type(user_agent)),
        "user_agent": user_agent[:500], "ip_address": ip_address,
    })

    AuditService.log_device_trust(request.user, ip_address, serializer.validated_data.get("device_name", ""))
    return Response(result, status=status.HTTP_200_OK)


# ==================== EMAIL VERIFICATION VIEW ====================


@api_view(["POST"])
@permission_classes([AllowAny])
def email_verify_view(request):
    """Verify user email with a verification token.

    POST /api/v1/auth/email/verify/
    """
    serializer = EmailVerifySerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    token = serializer.validated_data["token"]
    token_data = cache.get(f"emailverify:{token}")

    if not token_data:
        return Response({"error": "Invalid or expired verification token."}, status=status.HTTP_400_BAD_REQUEST)

    cache.delete(f"emailverify:{token}")

    try:
        user = User.objects.get(id=token_data["user_id"], is_active=True)
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=status.HTTP_400_BAD_REQUEST)

    # SECURITY: Email verification should only confirm email ownership,
    # NOT grant full identity verification (which requires KRA PIN / ID check)
    user.is_email_verified = True
    user.save(update_fields=["is_email_verified"])

    AuditService.log_event("EMAIL_VERIFIED", user=user, metadata={"email": user.email})

    return Response({"message": "Email verified successfully."}, status=status.HTTP_200_OK)


# ==================== STEP-UP AUTH VIEW ====================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def step_up_auth_view(request):
    """Perform step-up authentication for a sensitive operation.

    POST /api/v1/auth/step-up/
    """
    serializer = StepUpAuthSerializer(data=request.data, context={"request": request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    operation = serializer.validated_data["operation"]
    totp_code = serializer.validated_data["totp_code"]

    if StepUpAuthService.require_step_up(request.user, operation):
        if not StepUpAuthService.verify_step_up(request.user, totp_code, operation):
            return Response({"error": "Step-up authentication failed."}, status=status.HTTP_401_UNAUTHORIZED)

    step_up_token = secrets.token_urlsafe(32)
    cache.set(f"stepup:{step_up_token}", {"user_id": str(request.user.id), "operation": operation}, timeout=300)

    ip_address = _get_client_ip(request)
    AuditService.log_event("STEP_UP_AUTH_COMPLETED", user=request.user, ip_address=ip_address,
                           metadata={"operation": operation})

    return Response({"step_up_token": step_up_token, "operation": operation, "expires_in": 300},
                    status=status.HTTP_200_OK)


# ==================== OAUTH ADMIN VIEWS ====================


@api_view(["GET"])
@permission_classes([AllowAny])
def oauth_providers_list_view(request):
    """List available OAuth providers."""
    providers = OAuthProvider.objects.filter(is_active=True)
    serializer = OAuthProviderSerializer(providers, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def oauth_accounts_list_view(request):
    """List OAuth accounts linked to the authenticated user."""
    accounts = OAuthAccount.objects.filter(user=request.user)
    serializer = OAuthAccountSerializer(accounts, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def oauth_account_unlink_view(request, pk):
    """Unlink an OAuth account from the authenticated user."""
    account = get_object_or_404(OAuthAccount, id=pk, user=request.user)
    provider_name = account.provider.name
    account.delete()

    ip_address = _get_client_ip(request)
    AuditService.log_event("OAUTH_ACCOUNT_UNLINKED", user=request.user, ip_address=ip_address,
                           metadata={"provider": provider_name})

    return Response({"message": f"Unlinked {provider_name} account."}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def oauth_provider_admin_list_view(request):
    """Admin: list all OAuth provider configurations."""
    providers = OAuthProvider.objects.all()
    serializer = OAuthProviderAdminSerializer(providers, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAdminUser])
def oauth_provider_admin_detail_view(request, pk):
    """Admin: retrieve or update an OAuth provider configuration."""
    provider = get_object_or_404(OAuthProvider, id=pk)
    if request.method == "GET":
        serializer = OAuthProviderAdminSerializer(provider)
        return Response(serializer.data, status=status.HTTP_200_OK)

    serializer = OAuthProviderAdminSerializer(provider, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== PERMISSION MANAGEMENT VIEWS ====================


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def permissions_list_view(request):
    """List all active permissions."""
    permissions = Permission.objects.filter(is_active=True)
    serializer = PermissionSerializer(permissions, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def role_permissions_view(request):
    """List permissions for a specific role."""
    role = request.query_params.get("role", request.user.role)
    role_perms = RolePermission.objects.filter(role=role)
    serializer = RolePermissionSerializer(role_perms, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAdminUser])
def role_permission_assign_view(request):
    """Assign a permission to a role (Admin only)."""
    role = request.data.get("role")
    permission_id = request.data.get("permission_id")

    if not role or not permission_id:
        return Response({"error": "role and permission_id are required."}, status=status.HTTP_400_BAD_REQUEST)

    valid_roles = [r[0] for r in User.ROLE_CHOICES]
    if role not in valid_roles:
        return Response({"error": f"Invalid role. Valid roles: {', '.join(valid_roles)}"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        permission = Permission.objects.get(id=permission_id, is_active=True)
    except Permission.DoesNotExist:
        return Response({"error": "Permission not found."}, status=status.HTTP_404_NOT_FOUND)

    role_perm, created = RolePermission.objects.get_or_create(
        role=role, permission=permission,
        defaults={"conditions": request.data.get("conditions", {})},
    )

    if not created:
        return Response({"error": "This permission is already assigned to this role."}, status=status.HTTP_409_CONFLICT)

    ip_address = _get_client_ip(request)
    AuditService.log_event("ROLE_PERMISSION_ASSIGNED", user=request.user, ip_address=ip_address,
                           metadata={"role": role, "permission": permission.codename})

    serializer = RolePermissionSerializer(role_perm)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsAdminUser])
def role_permission_remove_view(request, pk):
    """Remove a permission from a role (Admin only)."""
    role_perm = get_object_or_404(RolePermission, id=pk)
    role = role_perm.role
    perm_codename = role_perm.permission.codename
    role_perm.delete()

    ip_address = _get_client_ip(request)
    AuditService.log_event("ROLE_PERMISSION_REMOVED", user=request.user, ip_address=ip_address,
                           metadata={"role": role, "permission": perm_codename})

    return Response({"message": f"Removed {perm_codename} from {role}."}, status=status.HTTP_200_OK)


# ==================== LOGIN ATTEMPTS VIEW ====================


@api_view(["GET"])
@permission_classes([IsAdminUser])
def login_attempts_view(request):
    """List recent login attempts (Admin only)."""
    queryset = LoginAttempt.objects.all()

    email = request.query_params.get("email")
    if email:
        queryset = queryset.filter(email__icontains=email)

    ip = request.query_params.get("ip_address")
    if ip:
        queryset = queryset.filter(ip_address=ip)

    success = request.query_params.get("success")
    if success is not None:
        queryset = queryset.filter(success=success.lower() == "true")

    queryset = queryset[:100]
    serializer = LoginAttemptSerializer(queryset, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
