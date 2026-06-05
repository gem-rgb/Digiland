# Digiland Authentication Architecture

## Overview

The Digiland authentication system provides secure, scalable, and auditable access control for all platform users. The system supports multiple authentication methods, multi-factor authentication, OAuth/SSO integration, and a hybrid RBAC/ABAC authorization model.

## Authentication Flow

### Standard Login Flow

```
User ──▶ POST /api/v1/auth/login ──▶ Validate Credentials
                                          │
                                    ┌─────┴─────┐
                                    │ MFA Enabled?│
                                    └─────┬─────┘
                                   No     │     Yes
                                   ▼      │      ▼
                          Return JWT     │   Return MFA Required
                          (access+refresh)│   (mfa_token)
                                         │
                            POST /api/v1/auth/mfa/login-verify/
                            (totp_code + mfa_token)
                                         │
                                    ┌─────┴─────┐
                                    │  TOTP Valid? │
                                    └─────┬─────┘
                                   Yes    │    No
                                   ▼      │    ▼
                          Return JWT     │   401 Unauthorized
                          (access+refresh)│
```

### Token Lifecycle

| Token Type | Lifetime | Purpose | Storage |
|-----------|----------|---------|---------|
| Access Token | 15 minutes | API authentication | Memory (frontend) |
| Refresh Token | 1 day | Obtain new access tokens | HttpOnly cookie |
| MFA Token | 5 minutes | MFA verification step | Memory |
| Trust Token | 30 days | Skip MFA on trusted device | HttpOnly cookie |

### Token Rotation

Refresh tokens are rotated on every use. The old refresh token is blacklisted immediately after a new pair is issued. This prevents token replay attacks and limits the damage window if a refresh token is compromised.

## Multi-Factor Authentication (MFA)

### TOTP Implementation

MFA uses the Time-based One-Time Password (TOTP) algorithm as defined in RFC 6238. The implementation uses the `pyotp` library with the following parameters:

- **Algorithm**: SHA-1 (per TOTP RFC)
- **Time Step**: 30 seconds
- **Code Length**: 6 digits
- **Valid Window**: 1 (allows ±30 seconds clock drift)

### Recovery Codes

When MFA is enabled, 8 recovery codes are generated. Each code is 8 hexadecimal characters formatted as `XXXX-XXXX`. Recovery codes are hashed using Django's password hasher (Argon2id) before storage. A recovery code can only be used once and is removed after successful verification.

### Device Trust

Users can mark a device as "trusted" after completing MFA, which skips MFA for 30 days on that device. Trust tokens are stored as HttpOnly, Secure, SameSite=Strict cookies. Users can view and revoke trusted devices at any time through the account settings.

### Step-Up Authentication

Sensitive operations require re-authentication even if the user has a valid session:

- Payment release/refund
- Transaction reversal
- Admin user deletion
- Role changes
- MFA disable
- Organization settings changes
- Escrow withdrawal

## OAuth/SSO Integration

### Supported Providers

| Provider | Protocol | Use Case |
|----------|----------|----------|
| Google | OAuth2/OIDC | Consumer and enterprise users |
| GitHub | OAuth2 | Developer community |
| Microsoft | OAuth2/OIDC | Enterprise customers |
| OIDC | OpenID Connect | Custom identity providers |
| SAML | SAML 2.0 | Enterprise SSO (future) |

### OAuth Flow

1. User clicks "Sign in with [Provider]"
2. Frontend redirects to `/api/v1/auth/oauth/{provider}/authorize/`
3. Backend redirects to provider authorization URL
4. User authenticates with provider
5. Provider redirects to callback URL
6. Backend exchanges authorization code for tokens
7. Backend creates/links local user account
8. Backend issues Digiland JWT tokens

## Authorization Model

### Hybrid RBAC/ABAC

Digiland uses a hybrid Role-Based Access Control (RBAC) and Attribute-Based Access Control (ABAC) model:

**RBAC Layer**: Users are assigned roles (Super Admin, Admin, Manager, Support, User) that provide baseline permissions.

**ABAC Layer**: Permissions can have conditions that evaluate attributes such as:
- Resource ownership (user can only edit their own parcels)
- Organization membership (user can only see tenant-scoped data)
- Time-based restrictions (no admin actions outside business hours)
- Risk score (high-risk users have reduced permissions)

### Permission Structure

Each permission is defined by:
- `resource_type`: The model/entity (parcel, transaction, promotion, etc.)
- `action`: The operation (create, read, update, delete, manage)
- `conditions`: ABAC conditions for this role-permission mapping

### Role Hierarchy

```
Super Admin ─── Full system access, bypasses all checks
    │
Admin ─── Organization management, user management
    │
Manager ─── Team management, content moderation
    │
Support ─── Read-only access, ticket management
    │
User ─── Standard user permissions (Buyer/Seller/Agent)
```

## Security Controls

### Brute Force Protection

- Account lockout after 5 failed login attempts
- Progressive delay between attempts (1s, 2s, 4s, 8s, 16s)
- IP-based rate limiting via middleware
- Login attempt tracking in `LoginAttempt` model
- Admin notification after 10 failed attempts from same IP

### Session Security

- All session cookies: HttpOnly, Secure, SameSite=Lax
- Session expires at browser close
- Maximum session age: 1 hour
- Concurrent session management via `UserSession` model
- Users can revoke individual sessions or all other sessions

### Token Security

- JWT signing key separate from Django SECRET_KEY
- Access tokens contain: user_id, role, tenant_id, is_mfa_verified
- Refresh tokens contain: jti (unique identifier) for revocation
- Token blacklisting via `rest_framework_simplejwt.token_blacklist`

## Audit Logging

All authentication and authorization events are logged to the `AuditLog` model:

| Event | Data Logged |
|-------|------------|
| Login Success | User ID, IP, method (password/OAuth) |
| Login Failure | Email (partial), IP, reason |
| Logout | User ID, IP |
| MFA Enabled | User ID, method |
| MFA Disabled | User ID, method (TOTP/recovery) |
| MFA Verification | User ID, success/failure |
| Password Change | User ID, IP |
| Password Reset | User ID, email |
| Role Change | User ID, old role, new role, changed by |
| Permission Denied | User ID, resource, action, IP |
| OAuth Link/Unlink | User ID, provider |
| Session Revocation | User ID, session ID |
