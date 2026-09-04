# Digiland Threat Model

**Version**: 1.0  
**Date**: 2026-06-03  
**Classification**: Confidential  
**Author**: Security Engineering Team

---

## 1. System Overview

Digiland is a Kenyan land platform providing secure verification and non-custodial direct settlement built with Django (DRF) backend, React/TypeScript frontend, PostgreSQL/PostGIS database, Redis cache, Celery task queue, and integrates with Paystack, M-Pesa Daraja, KCB Bank, and GavaConnect KRA APIs.

### 1.1 Architecture Components

| Component | Technology | Trust Level |
|-----------|-----------|-------------|
| Frontend SPA | React + TypeScript + Tailwind | Untrusted (Client-side) |
| Django Backend | Django 6.0 + DRF | Trusted (Server-side) |
| Database | PostgreSQL 16 + PostGIS | Trusted |
| Cache/Broker | Redis 7 | Trusted |
| Task Queue | Celery + Redis | Trusted |
| File Storage | Cloudinary / Local | Semi-Trusted |
| Reverse Proxy | Nginx | Trusted |
| Payment Gateways | Paystack, M-Pesa, Stripe, KCB | Trusted (External) |
| Identity APIs | GavaConnect (KRA) | Trusted (External) |
| Search | Elasticsearch | Semi-Trusted |

---

## 2. Trust Boundaries

### TB-1: Internet ↔ Nginx Reverse Proxy
- **Type**: Network boundary
- **Risk**: DDoS, request flooding, protocol abuse
- **Controls**: Rate limiting (partial), TLS termination

### TB-2: Nginx ↔ Django Application
- **Type**: Process boundary
- **Risk**: Header injection, request smuggling
- **Controls**: Gunicorn request validation

### TB-3: Django ↔ PostgreSQL Database
- **Type**: Data store boundary
- **Risk**: SQL injection, credential exposure
- **Controls**: ORM (Django), parameterized queries (partial)

### TB-4: Django ↔ Redis Cache
- **Type**: Data store boundary
- **Risk**: Cache poisoning, session hijacking
- **Controls**: Password authentication, network isolation

### TB-5: Django ↔ External APIs (Paystack, M-Pesa, KRA)
- **Type**: External service boundary
- **Risk**: API key exposure, SSRF, callback forgery
- **Controls**: HTTPS, API key auth (partial)

### TB-6: Client Browser ↔ Django (Session/API)
- **Type**: User boundary
- **Risk**: XSS, CSRF, session fixation, credential theft
- **Controls**: CSRF middleware (partial), session cookies

### TB-7: Django ↔ Cloudinary (File Storage)
- **Type**: External storage boundary
- **Risk**: Malicious file upload, data exfiltration
- **Controls**: Cloudinary API (minimal validation)

### TB-8: Celery Workers ↔ Redis Broker
- **Type**: Internal service boundary
- **Risk**: Task injection, message tampering
- **Controls**: Network isolation (Docker)

---

## 3. STRIDE Analysis

### S - Spoofing

| ID | Threat | Risk | Exploitability | Impact | Mitigation |
|----|--------|------|----------------|--------|------------|
| SP-01 | Login endpoint returns full user data without JWT/token | **Critical** | High | High | Implement JWT token issuance at login |
| SP-02 | M-Pesa callback has no signature verification | **Critical** | High | Critical | Verify callback signatures using Daraja public key |
| SP-03 | Stripe webhook has no signature verification | **Critical** | High | Critical | Verify Stripe webhook signatures |
| SP-04 | Mock identity verification marks users verified | **High** | Medium | High | Disable mock in production; require real verification |
| SP-05 | Admin finance PIN is hardcoded ("admin2026") | **Critical** | High | Critical | Remove PIN auth; use proper admin RBAC |

### T - Tampering

| ID | Threat | Risk | Exploitability | Impact | Mitigation |
|----|--------|------|----------------|--------|------------|
| TM-01 | Transaction status can be updated via PATCH without authorization | **Critical** | High | Critical | Add ownership/role checks on status updates |
| TM-02 | CSRF exempt on M-Pesa, KRA, and payment views | **High** | Medium | High | Use HMAC signing for callbacks instead of @csrf_exempt |
| TM-03 | Lowest negotiable price exposed in API serializer | **Medium** | Low | High | Remove from serializer; server-side only |
| TM-04 | Buyer signature stored as plain Base64 with no verification | **High** | Medium | High | Cryptographically sign signatures |
| TM-05 | PopupAd metrics (impressions, clicks) can be manipulated via API | **Medium** | Medium | Medium | Server-side only metric updates |

### R - Repudiation

| ID | Threat | Risk | Exploitability | Impact | Mitigation |
|----|--------|------|----------------|--------|------------|
| RP-01 | Audit log IP address not consistently captured | **Medium** | Low | Medium | Add IP capture middleware |
| RP-02 | Payment callback processing lacks idempotency | **High** | Medium | High | Implement idempotency keys |
| RP-03 | No audit trail for admin finance dashboard access | **Medium** | Low | Medium | Log all admin dashboard access |

### I - Information Disclosure

| ID | Threat | Risk | Exploitability | Impact | Mitigation |
|----|--------|------|----------------|--------|------------|
| ID-01 | SECRET_KEY has insecure default in settings.py | **Critical** | High | Critical | Remove default; require env var |
| ID-02 | CORS_ALLOW_ALL_ORIGINS = True in development settings | **High** | High | High | Restrict even in development |
| ID-03 | Face embedding data exposed via KYCProfile serializer | **High** | Medium | Critical | Make write_only; never read |
| ID-04 | ID number hash readable in KYCProfile serializer | **Medium** | Low | Medium | Already write_only; verify |
| ID-05 | Debug mode may leak stack traces | **High** | Medium | High | Ensure DEBUG=False in production |
| ID-06 | Paystack secret key in settings without validation | **Medium** | Low | High | Add key format validation |
| ID-07 | .env.example contains default passwords | **Medium** | Low | Medium | Use placeholder values only |
| ID-08 | User email + role exposed in public APIs without auth | **Medium** | Medium | Medium | Restrict user data to authenticated requests |

### D - Denial of Service

| ID | Threat | Risk | Exploitability | Impact | Mitigation |
|----|--------|------|----------------|--------|------------|
| DO-01 | Rate limiting middleware not in MIDDLEWARE list | **High** | High | High | Add RateLimitMiddleware to MIDDLEWARE |
| DO-02 | RBACMiddleware not in MIDDLEWARE list | **High** | High | Medium | Add RBACMiddleware to MIDDLEWARE |
| DO-03 | No request body size limits on API endpoints | **Medium** | Medium | Medium | Configure DATA_UPLOAD_MAX_MEMORY_SIZE |
| DO-04 | SQLite used in development (no concurrent writes) | **Low** | Low | Low | PostgreSQL in production |

### E - Elevation of Privilege

| ID | Threat | Risk | Exploitability | Impact | Mitigation |
|----|--------|------|----------------|--------|------------|
| EP-01 | DEFAULT_PERMISSION_CLASSES = [AllowAny] in dev settings | **Critical** | High | Critical | Change to IsAuthenticated |
| EP-02 | RegisterSerializer allows "Admin" role assignment via API | **High** | Medium | Critical | Restrict role choices in serializer |
| EP-03 | TransactionViewSet has no permission_classes | **Critical** | High | Critical | Add IsAuthenticated + ownership checks |
| EP-04 | LandParcelViewSet has no permission_classes | **Critical** | High | Critical | Add IsAuthenticated + ownership checks |
| EP-05 | DocumentViewSet has no permission_classes | **Critical** | High | Critical | Add IsAuthenticated + ownership checks |
| EP-06 | No IDOR protection on transaction/parcel endpoints | **Critical** | High | Critical | Validate user ownership of resources |
| EP-07 | Admin role can be self-assigned during registration | **Critical** | High | Critical | Remove Admin from public role choices |

---

## 4. Entry Points & Attack Surface

### 4.1 Public Endpoints (No Authentication Required)

| Endpoint | Method | Risk |
|----------|--------|------|
| `/api/v1/auth/register` | POST | Mass assignment, role escalation |
| `/api/v1/auth/login` | POST | Brute force, credential stuffing |
| `/api/v1/recommendations/popular/` | GET | Data scraping |
| `/api/v1/recommendations/trending/` | GET | Data scraping |
| `/api/v1/recommendations/sponsored/` | GET | Data scraping |
| `/api/v1/land-parcels/` | GET | Data enumeration |
| `/api/v1/transactions/` | GET | **CRITICAL**: Unauthenticated transaction access |
| `/api/v1/documents/` | GET | **CRITICAL**: Unauthenticated document access |
| `/api/v1/payments/callback` | GET/POST | Callback forgery |
| `/api/v1/mpesa/callback` | POST | Callback forgery |
| `/api/v1/verification/kra-pin` | POST | KRA API abuse |
| `/api/v1/verification/identity` | POST | Identity API abuse |
| `/api/v1/verification/business` | POST | Business API abuse |
| `/api/v1/mpesa/*` | POST | Payment API abuse |
| `/api/v1/stripe/webhook/` | POST | Webhook forgery |

### 4.2 Authenticated Endpoints (Missing Authorization)

| Endpoint | Method | Risk |
|----------|--------|------|
| `/api/v1/land-parcels/{id}/` | GET/PUT/PATCH/DELETE | IDOR |
| `/api/v1/transactions/{id}/` | GET/PUT/PATCH/DELETE | IDOR |
| `/api/v1/documents/{id}/` | GET/PUT/PATCH/DELETE | IDOR |
| `/api/v1/transactions/{id}/status` | PATCH | Unauthorized status change |
| `/api/v1/payments/release` | POST | Unauthorized fund release |
| `/api/v1/payments/refund` | POST | Unauthorized refund |

### 4.3 Admin Endpoints

| Endpoint | Method | Risk |
|----------|--------|------|
| `/api/v1/admin/dashboard/` | GET | Admin bypass |
| `/api/v1/admin/revenue/` | GET | Financial data exposure |
| `/api/v1/admin/fraud/*` | GET/POST | Fraud system manipulation |
| `/admin/` | All | Django admin access |

---

## 5. Data Flow Analysis

### 5.1 Payment Flow (Critical)

```
Buyer → Frontend → /api/v1/payments/deposit → Paystack/M-Pesa → Callback → Transaction Update
```

**Vulnerabilities**:
- Callback endpoints lack signature verification
- No idempotency on payment processing
- Payment status update not atomic with callback processing

### 5.2 Identity Verification Flow

```
User → /api/v1/verification/kra-pin → GavaConnect → User.is_identity_verified = True
```

**Vulnerabilities**:
- Mock verification auto-approves in development
- Verification ID is predictable (GVK-PIN-{first4chars})
- No rate limiting on verification endpoints

### 5.3 File Upload Flow

```
User → Form → Django FileField → Cloudinary/Local
```

**Vulnerabilities**:
- File type validation only in Django forms (not in API views)
- No virus scanning
- No file content validation (MIME sniffing)
- Upload paths are predictable

---

## 6. Risk Summary

| Severity | Count |
|----------|-------|
| Critical | 11 |
| High | 14 |
| Medium | 10 |
| Low | 3 |
| **Total** | **38** |

---

## 7. Priority Remediation Order

1. **P0 - Immediate**: Fix DEFAULT_PERMISSION_CLASSES, add auth to all ViewSets, remove Admin from registration, verify payment callbacks
2. **P1 - This Sprint**: Implement JWT token issuance at login, add RBACMiddleware/RateLimitMiddleware, remove hardcoded PIN
3. **P2 - Next Sprint**: Implement MFA, add IDOR protections, implement payment idempotency, add security headers
4. **P3 - Ongoing**: Dependency updates, penetration testing, compliance documentation
