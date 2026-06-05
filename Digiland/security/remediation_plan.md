# Digiland Remediation Plan

**Version**: 1.0 | **Date**: 2026-06-03 | **Classification**: Confidential

---

## Phase 1: Critical Fixes (P0 - Immediate)

### REM-001: Fix DEFAULT_PERMISSION_CLASSES
- **Risk**: R-004 (AllowAny default)
- **File**: `land_escrow/land_escrow/settings.py` line 173-175
- **Fix**: Change `AllowAny` to `IsAuthenticated`
- **Verification**: All unauthenticated requests to protected endpoints return 401

### REM-002: Add Permission Classes to All ViewSets
- **Risk**: R-001, R-009 (Unauthenticated API access)
- **Files**: `land_escrow/core/views.py`, `land_escrow/core/api_views.py`
- **Fix**: Add `permission_classes = [IsAuthenticated]` to all ViewSets; add ownership validation
- **Verification**: Cannot access other users' resources via IDOR

### REM-003: Remove Admin from Registration Roles
- **Risk**: R-005 (Admin role self-assignment)
- **File**: `land_escrow/core/forms.py` line 13-17
- **Fix**: Already restricted in CustomSignupForm (only Buyer/Seller/Agent), but RegisterSerializer in `views.py` allows any role
- **Verification**: Cannot create Admin account via API

### REM-004: Implement Payment Callback Signature Verification
- **Risk**: R-002 (Payment callback forgery)
- **Files**: `land_escrow/core/api_views.py` (Stripe webhook, M-Pesa callback)
- **Fix**: 
  - Stripe: Verify `stripe-signature` header using webhook secret
  - M-Pesa: Validate callback origin + HTTPS + checksum
  - Paystack: Verify signature header
- **Verification**: Forged callbacks are rejected

### REM-005: Remove Hardcoded Admin Finance PIN
- **Risk**: R-003 (Hardcoded PIN)
- **File**: `land_escrow/land_escrow/settings.py` line 346
- **Fix**: Remove PIN-based auth; use Django admin RBAC with MFA
- **Verification**: Finance dashboard requires proper admin + MFA

### REM-006: Fix SECRET_KEY Default
- **Risk**: R-006 (Insecure default key)
- **File**: `land_escrow/land_escrow/settings.py` line 24
- **Fix**: Remove default value; raise error if not set
- **Verification**: Application fails to start without SECRET_KEY env var

### REM-007: Restrict CORS
- **Risk**: R-007 (CORS_ALLOW_ALL_ORIGINS)
- **File**: `land_escrow/land_escrow/settings.py` line 287
- **Fix**: Set `CORS_ALLOW_ALL_ORIGINS = False` even in development; use allowed origins list
- **Verification**: Cross-origin requests from unknown origins are blocked

---

## Phase 2: High Priority (P1 - This Sprint)

### REM-008: Implement JWT Token Issuance at Login
- **Risk**: R-008 (Login returns data without token)
- **File**: `land_escrow/core/views.py` line 26-34
- **Fix**: Issue JWT access + refresh tokens on successful login
- **Verification**: Login returns tokens; subsequent requests use Bearer token

### REM-009: Add IDOR Protection
- **Risk**: R-009 (No ownership validation)
- **Files**: All ViewSets in `views.py` and `api_views.py`
- **Fix**: Override `get_queryset()` to filter by user; add ownership checks on update/delete
- **Verification**: Cannot access/modify other users' resources

### REM-010: Activate Rate Limiting Middleware
- **Risk**: R-010 (No rate limiting)
- **File**: `land_escrow/land_escrow/settings.py`
- **Fix**: Add `RateLimitMiddleware` to MIDDLEWARE list with proper config
- **Verification**: Rate-limited requests return 429

### REM-011: Activate RBAC Middleware
- **Risk**: R-011 (No RBAC enforcement)
- **File**: `land_escrow/land_escrow/settings.py`
- **Fix**: Add `RBACMiddleware` to MIDDLEWARE list with RBAC_RULES
- **Verification**: Role-based access enforced on protected paths

### REM-012: Disable Mock Verification in Production
- **Risk**: R-012 (Mock auto-approval)
- **File**: `land_escrow/core/services/identity.py`
- **Fix**: Remove mock fallback; raise error if credentials not configured
- **Verification**: No mock verification paths in production

### REM-013: Fix Transaction Status Authorization
- **Risk**: R-013 (Unauthorized status changes)
- **File**: `land_escrow/core/views.py` line 79-87
- **Fix**: Add role-based checks; only admins can change status; validate valid transitions
- **Verification**: Non-admin users cannot change transaction status

### REM-014: Enhance File Upload Security
- **Risk**: R-014 (Insufficient file validation)
- **Files**: `land_escrow/core/api_views.py`, models
- **Fix**: Add magic byte validation, size limits, virus scanning, extension allowlist
- **Verification**: Malicious files are rejected

### REM-015: Close External Database/Redis Ports
- **Risk**: R-015 (Exposed internal services)
- **File**: `docker-compose.yml`
- **Fix**: Remove port mappings for db and redis services; only expose nginx
- **Verification**: Cannot connect to db/redis from external network

### REM-016: Implement Payment Idempotency
- **Risk**: R-016 (Duplicate payment processing)
- **Files**: Payment callback views
- **Fix**: Use transaction reference as idempotency key; check if already processed
- **Verification**: Duplicate callbacks don't double-process payments

### REM-017: Fix KYC Serializer Data Exposure
- **Risk**: R-017 (Face embedding exposed)
- **File**: `land_escrow/core/serializers.py` line 638-648
- **Fix**: Ensure face_embedding and id_number_hash are write_only
- **Verification**: API responses don't contain biometric data

---

## Phase 3: Medium Priority (P2 - Next Sprint)

### REM-018: Implement Argon2id Password Hashing
- **Risk**: R-018 (Weak password hashing)
- **Files**: `settings.py`, `requirements.txt`
- **Fix**: Add `argon2-cffi`, set `PASSWORD_HASHERS` to prefer Argon2id
- **Verification**: New passwords use Argon2id

### REM-019: Implement MFA
- **Risk**: R-019 (No MFA)
- **Fix**: Add TOTP-based MFA using `pyotp`; require for admin + financial ops
- **Verification**: Admin login requires MFA

### REM-020: Implement Account Lockout
- **Risk**: R-020 (No brute force protection)
- **Fix**: Add `django-axes` for account lockout after failed attempts
- **Verification**: Account locked after N failed attempts

### REM-021: Add CSP and Security Headers
- **Risk**: R-022 (No CSP)
- **Fix**: Add `django-csp`, configure security headers
- **Verification**: CSP header present in all responses

### REM-022: Add HTML Sanitization
- **Risk**: R-025 (No output encoding)
- **Fix**: Add `bleach` for HTML sanitization; use Django's `escape` filter
- **Verification**: XSS payloads are neutralized

### REM-023: Add Security Event Logging
- **Risk**: R-026 (No security logging)
- **Fix**: Add security event logging middleware; log auth events, admin actions
- **Verification**: Security events logged with appropriate detail

### REM-024: Remove Sensitive Fields from Serializers
- **Risk**: R-027 (Lowest negotiable price exposed)
- **File**: `land_escrow/core/serializers.py`
- **Fix**: Remove `lowest_negotiable_price` from public serializers
- **Verification**: Price not visible in API responses

---

## Phase 4: Ongoing (P3)

### REM-025: Dependency Scanning
- Set up `pip-audit` or `safety` in CI/CD
- Update `cryptography` from 41.0.7 to 44.x
- Regular dependency review

### REM-026: Penetration Testing
- Annual third-party penetration test
- Quarterly automated scans

### REM-027: Compliance Documentation
- PCI-DSS self-assessment
- GDPR data processing documentation
- ISO 27001 gap analysis

---

## Implementation Order

```
Week 1: REM-001 → REM-002 → REM-003 → REM-004 → REM-005 → REM-006 → REM-007
Week 2: REM-008 → REM-009 → REM-010 → REM-011 → REM-012 → REM-013
Week 3: REM-014 → REM-015 → REM-016 → REM-017
Week 4: REM-018 → REM-019 → REM-020 → REM-021 → REM-022 → REM-023 → REM-024
Ongoing: REM-025 → REM-026 → REM-027
```
