# JWT Token Lifecycle

## Overview

The Digiland platform uses JSON Web Tokens (JWT) for stateless API authentication. This document describes the complete lifecycle of JWT tokens from creation to expiration, including refresh mechanisms, blacklisting, and security considerations.

## Token Architecture

### Token Types

| Token | Type | Lifetime | Storage | Purpose |
|-------|------|----------|---------|---------|
| Access Token | JWT | 15 minutes | Memory (SPA) | API request authorization |
| Refresh Token | JWT | 7 days | HttpOnly Cookie / Encrypted Storage | Obtain new access tokens |
| Session ID | Django Session | 30 min idle / 12 hr absolute | Server-side (cached_db) | Web template views |

### JWT Claims

**Access Token Claims**:
```json
{
  "token_type": "access",
  "exp": 1710000000,
  "iat": 1709999100,
  "jti": "unique-token-identifier",
  "user_id": 42,
  "email": "user@example.com",
  "role": "Buyer",
  "is_staff": false
}
```

**Refresh Token Claims**:
```json
{
  "token_type": "refresh",
  "exp": 1710604800,
  "iat": 1709999100,
  "jti": "unique-refresh-token-id",
  "user_id": 42
}
```

## Token Lifecycle Flow

### 1. Token Creation (Login)

```
┌─────────┐      ┌───────────┐      ┌──────────┐
│  Client  │─────▶│  API      │─────▶│  Django  │
│  (SPA)   │      │  Gateway  │      │  Auth    │
└─────────┘      └───────────┘      └──────────┘
     │                                       │
     │  POST /api/v1/auth/token/             │
     │  {email, password}                    │
     │──────────────────────────────────────▶│
     │                                       │ 1. Validate credentials
     │                                       │ 2. Check account status
     │                                       │ 3. Verify MFA if enabled
     │                                       │ 4. Generate access token
     │                                       │ 5. Generate refresh token
     │                                       │ 6. Store refresh token hash
     │  {access, refresh}                    │
     │◀──────────────────────────────────────│
     │                                       │
     │  Store access in memory               │
     │  Store refresh in cookie/storage      │
```

### 2. Token Usage (API Requests)

```
┌─────────┐      ┌───────────┐      ┌──────────┐
│  Client  │─────▶│  Nginx    │─────▶│  Django  │
│  (SPA)   │      │  Proxy    │      │  DRF     │
└─────────┘      └───────────┘      └──────────┘
     │                                       │
     │  GET /api/v1/parcels/                 │
     │  Authorization: Bearer <access_token> │
     │──────────────────────────────────────▶│
     │                                       │ 1. Extract token from header
     │                                       │ 2. Verify signature
     │                                       │ 3. Check expiration
     │                                       │ 4. Validate JTI not blacklisted
     │                                       │ 5. Load user from claims
     │                                       │ 6. Check user is active
     │  {parcels data}                       │
     │◀──────────────────────────────────────│
```

### 3. Token Refresh

```
┌─────────┐      ┌───────────┐
│  Client  │─────▶│  Django   │
│  (SPA)   │      │  Auth     │
└─────────┘      └───────────┘
     │                          │
     │  POST /api/v1/auth/token/refresh/
     │  {refresh: "<refresh_token>"}
     │────────────────────────▶│
     │                          │ 1. Verify refresh token signature
     │                          │ 2. Check expiration
     │                          │ 3. Verify not blacklisted
     │                          │ 4. Blacklist old refresh token
     │                          │ 5. Generate new access token
     │                          │ 6. Generate new refresh token (rotation)
     │                          │ 7. Store new refresh token hash
     │  {access, refresh}       │
     │◀─────────────────────────│
     │                          │
     │  Update stored tokens    │
```

### 4. Token Expiration

Access tokens expire after 15 minutes. When an expired token is used:

```
1. Client sends request with expired access token
2. Server returns 401 Unauthorized with detail "Token is expired"
3. Client automatically attempts token refresh using stored refresh token
4. If refresh succeeds, client retries the original request with new access token
5. If refresh fails (refresh token also expired), client redirects to login
```

### 5. Token Blacklisting (Logout)

```
┌─────────┐      ┌───────────┐
│  Client  │─────▶│  Django   │
│  (SPA)   │      │  Auth     │
└─────────┘      └───────────┘
     │                          │
     │  POST /api/v1/auth/logout/
     │  Authorization: Bearer <access_token>
     │────────────────────────▶│
     │                          │ 1. Blacklist access token JTI
     │                          │ 2. Blacklist refresh token JTI
     │                          │ 3. Clear server-side session
     │                          │ 4. Clear refresh cookie
     │  200 OK                  │
     │◀─────────────────────────│
     │                          │
     │  Clear stored tokens     │
     │  Redirect to login       │
```

## Token Security

### Signing Algorithm

Tokens are signed using HS256 (HMAC-SHA256) with the Django `SECRET_KEY` as the signing key. In production, the `SECRET_KEY` is stored in AWS Secrets Manager and rotated periodically.

### Token Validation Checklist

Every token is validated against the following criteria:

1. **Signature Verification**: Token was signed by our secret key
2. **Expiration Check**: Token has not expired (`exp` claim)
3. **Not Before Check**: Token is valid from `iat` (issued at)
4. **Type Check**: `token_type` matches expected type (access/refresh)
5. **JTI Blacklist**: Token's `jti` is not in the blacklist
6. **User Active**: The user referenced by `user_id` is still active
7. **Issuer Check**: Token was issued by our system (if `iss` claim is set)

### Refresh Token Rotation

Refresh tokens are rotated on each use. When a refresh token is used to obtain a new access token, the old refresh token is immediately blacklisted and a new refresh token is issued. This prevents replay attacks.

### Token Storage Security

| Storage Location | Security Level | Use Case |
|-----------------|---------------|----------|
| JavaScript variable (memory) | High | Access tokens |
| HttpOnly Secure cookie | High | Refresh tokens (recommended) |
| Encrypted localStorage | Medium | Refresh tokens (fallback) |
| URL parameter | Low | Never use |

### Token Revocation Events

Tokens are revoked (blacklisted) when:
- User explicitly logs out
- User changes password
- Admin deactivates user account
- MFA is enabled or disabled
- Suspicious activity is detected
- Refresh token rotation occurs

## Configuration

### Django Settings

```python
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': settings.SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'TOKEN_OBTAIN_SERIALIZER': 'core.serializers.CustomTokenObtainPairSerializer',
    'TOKEN_BLACKLIST_SERIALIZER': 'rest_framework_simplejwt.serializers.TokenBlacklistSerializer',
}
```

### Frontend Token Handling

The React SPA implements the following token management:

1. **Axios Interceptor**: Automatically attaches access token to requests
2. **Refresh Interceptor**: On 401 response, automatically refreshes token and retries
3. **Token Queue**: Prevents multiple simultaneous refresh requests
4. **Cleanup**: Clears tokens on logout or when refresh fails
