"""URL configuration for the Digiland Authentication System.

Maps auth-related API endpoints to their corresponding views.
All paths are intended to be included under a prefix like ``api/v1/auth/``.
"""

from django.urls import path

from .auth_views import (
    # Core auth
    login_view,
    register_view,
    logout_view,
    # MFA
    mfa_setup_view,
    mfa_verify_view,
    mfa_recovery_view,
    mfa_disable_view,
    mfa_regenerate_recovery_view,
    mfa_login_verify_view,
    mfa_status_view,
    mfa_available_methods_view,
    mfa_send_otp_view,
    mfa_verify_challenge_view,
    # Password
    change_password_view,
    reset_password_request_view,
    reset_password_confirm_view,
    # Token
    token_refresh_view,
    # OAuth
    oauth_init_view,
    oauth_callback_view,
    oauth_providers_list_view,
    oauth_accounts_list_view,
    oauth_account_unlink_view,
    oauth_provider_admin_list_view,
    oauth_provider_admin_detail_view,
    # WebAuthn
    webauthn_registration_begin_view,
    webauthn_registration_finish_view,
    webauthn_authentication_begin_view,
    webauthn_authentication_finish_view,
    # Security Methods & Passkey Lifecycle
    security_methods_summary_view,
    passkey_register_start_view,
    passkey_register_finish_view,
    passkey_remove_view,
    stepup_challenge_verify_view,
    # Devices
    trusted_device_list_view,
    trusted_device_revoke_view,
    device_trust_view,
    # Sessions
    active_sessions_view,
    active_session_revoke_view,
    session_heartbeat_view,
    session_revoke_all_view,
    # Email verification
    account_verification_pending_view,
    email_verify_view,
    email_verification_status_view,
    email_verification_resend_view,
    email_verification_change_view,
    email_verification_logout_view,
    # Step-up auth
    step_up_auth_view,
    # Permissions
    permissions_list_view,
    role_permissions_view,
    role_permission_assign_view,
    role_permission_remove_view,
    # Login attempts
    login_attempts_view,
)

urlpatterns = [
    # Core auth
    path("login/", login_view, name="auth-login"),
    path("register/", register_view, name="auth-register"),
    path("logout/", logout_view, name="auth-logout"),

    # MFA
    path("mfa/setup/", mfa_setup_view, name="auth-mfa-setup"),
    path("mfa/verify/", mfa_verify_view, name="auth-mfa-verify"),
    path("mfa/recovery/", mfa_recovery_view, name="auth-mfa-recovery"),
    path("mfa/disable/", mfa_disable_view, name="auth-mfa-disable"),
    path("mfa/recovery-codes/", mfa_regenerate_recovery_view, name="auth-mfa-regenerate-recovery"),
    path("mfa/login-verify/", mfa_login_verify_view, name="auth-mfa-login-verify"),
    path("mfa/status/", mfa_status_view, name="auth-mfa-status"),
    path("mfa/available-methods/", mfa_available_methods_view, name="auth-mfa-available-methods"),
    path("mfa/send-otp/", mfa_send_otp_view, name="auth-mfa-send-otp"),
    path("mfa/verify-challenge/", mfa_verify_challenge_view, name="auth-mfa-verify-challenge"),

    # Password
    path("password/change/", change_password_view, name="auth-password-change"),
    path("password/reset/", reset_password_request_view, name="auth-password-reset"),
    path("password/reset/confirm/", reset_password_confirm_view, name="auth-password-reset-confirm"),

    # Token
    path("token/refresh/", token_refresh_view, name="auth-token-refresh"),

    # OAuth
    path("oauth/<str:provider>/", oauth_init_view, name="auth-oauth-init"),
    path("oauth/<str:provider>/callback/", oauth_callback_view, name="auth-oauth-callback"),
    path("oauth/providers/", oauth_providers_list_view, name="auth-oauth-providers"),
    path("oauth/accounts/", oauth_accounts_list_view, name="auth-oauth-accounts"),
    path("oauth/accounts/<uuid:pk>/", oauth_account_unlink_view, name="auth-oauth-unlink"),
    path("oauth/admin/providers/", oauth_provider_admin_list_view, name="auth-oauth-admin-list"),
    path("oauth/admin/providers/<uuid:pk>/", oauth_provider_admin_detail_view, name="auth-oauth-admin-detail"),

    # WebAuthn
    path("webauthn/register/begin/", webauthn_registration_begin_view, name="auth-webauthn-register-begin"),
    path("webauthn/register/finish/", webauthn_registration_finish_view, name="auth-webauthn-register-finish"),
    path("webauthn/auth/begin/", webauthn_authentication_begin_view, name="auth-webauthn-auth-begin"),
    path("webauthn/auth/finish/", webauthn_authentication_finish_view, name="auth-webauthn-auth-finish"),

    # Security Methods & Passkey Lifecycle
    path("security/methods/", security_methods_summary_view, name="auth-security-methods-summary"),
    path("security/passkey/register/start/", passkey_register_start_view, name="auth-security-passkey-register-start"),
    path("security/passkey/register/finish/", passkey_register_finish_view, name="auth-security-passkey-register-finish"),
    path("security/passkey/remove/", passkey_remove_view, name="auth-security-passkey-remove"),
    path("security/step-up/", stepup_challenge_verify_view, name="auth-security-stepup-verify"),

    # Devices
    path("devices/", trusted_device_list_view, name="auth-devices-list"),
    path("devices/trust/", device_trust_view, name="auth-device-trust"),
    path("devices/<uuid:pk>/revoke/", trusted_device_revoke_view, name="auth-device-revoke"),

    # Sessions
    path("sessions/", active_sessions_view, name="auth-sessions-list"),
    path("sessions/<uuid:pk>/revoke/", active_session_revoke_view, name="auth-session-revoke"),
    path("session/heartbeat/", session_heartbeat_view, name="auth-session-heartbeat"),
    path("session/revoke-all/", session_revoke_all_view, name="auth-session-revoke-all"),

    # Email verification
    path("verification/pending/", account_verification_pending_view, name="account_verification_pending"),
    path("email/verify/", email_verify_view, name="auth-email-verify"),
    path("email/verification/status/", email_verification_status_view, name="auth-email-verification-status"),
    path("email/verification/resend/", email_verification_resend_view, name="auth-email-verification-resend"),
    path("email/verification/change/", email_verification_change_view, name="auth-email-verification-change"),
    path("email/verification/logout/", email_verification_logout_view, name="auth-email-verification-logout"),

    # Step-up auth
    path("step-up/", step_up_auth_view, name="auth-step-up"),

    # Permissions
    path("permissions/", permissions_list_view, name="auth-permissions-list"),
    path("roles/permissions/", role_permissions_view, name="auth-role-permissions"),
    path("roles/permissions/assign/", role_permission_assign_view, name="auth-role-permission-assign"),
    path("roles/permissions/<uuid:pk>/", role_permission_remove_view, name="auth-role-permission-remove"),

    # Login attempts
    path("login-attempts/", login_attempts_view, name="auth-login-attempts"),
]
