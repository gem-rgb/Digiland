# Digiland Attack Surface Map

**Version**: 1.0 | **Date**: 2026-06-03 | **Classification**: Confidential

---

## 1. External Attack Surface

### 1.1 Web Application (Port 80/443 → Nginx → Django:8000)

| Surface | Entry Point | Protocol | Auth Required | Risk Level |
|---------|------------|----------|---------------|------------|
| Homepage | `/` | HTTPS | No | Low |
| User Registration | `/api/v1/auth/register` | HTTPS | No | **Critical** |
| User Login | `/api/v1/auth/login` | HTTPS | No | High |
| Identity Verification | `/api/v1/verification/*` | HTTPS | No | **Critical** |
| M-Pesa Payments | `/api/v1/mpesa/*` | HTTPS | No | **Critical** |
| Stripe Webhooks | `/api/v1/payments/stripe/webhook/` | HTTPS | No | **Critical** |
| Payment Callbacks | `/api/v1/payments/callback` | HTTPS | No | **Critical** |
| Land Parcels API | `/api/v1/land-parcels/` | HTTPS | No | **Critical** |
| Transactions API | `/api/v1/transactions/` | HTTPS | No | **Critical** |
| Documents API | `/api/v1/documents/` | HTTPS | No | **Critical** |
| Recommendations | `/api/v1/recommendations/*` | HTTPS | Partial | Medium |
| Popup Ads | `/api/v1/popup-ads/` | HTTPS | No | Medium |
| Service Fees | `/api/v1/service-fees/*` | HTTPS | Partial | Medium |
| Analytics | `/api/v1/analytics/*` | HTTPS | Partial | High |
| Admin Dashboard | `/api/v1/admin/*` | HTTPS | Partial | **Critical** |
| Django Admin | `/admin/` | HTTPS | Staff | High |
| Allauth Auth | `/accounts/*` | HTTPS | Partial | Medium |

### 1.2 Payment Gateway Callbacks

| Gateway | Callback URL | Verification | Risk |
|---------|-------------|--------------|------|
| Paystack | `/api/v1/payments/callback` | Reference check only | **Critical** |
| M-Pesa STK | `/api/v1/mpesa/callback` | None | **Critical** |
| M-Pesa B2C | `/api/v1/mpesa/callback` | None | **Critical** |
| Stripe | `/api/v1/payments/stripe/webhook/` | None | **Critical** |

### 1.3 External API Integrations

| API | Purpose | Auth Method | Key Storage |
|-----|---------|------------|-------------|
| Paystack | Payment processing | Bearer token | Settings/env vars |
| M-Pesa Daraja | Mobile payments | OAuth2 + STK password | Settings/env vars |
| GavaConnect | KRA verification | OAuth2 per product | Settings/env vars |
| KCB Bank | Bank transfers | OAuth2 | Settings/env vars |
| Cloudinary | File storage | API key/secret | Settings/env vars |
| Stripe | Card payments | Bearer token | Settings/env vars |

---

## 2. Internal Attack Surface

### 2.1 Database (PostgreSQL:5432)

- Exposed port in docker-compose (5432:5432)
- Default password: `digiland_secret`
- No SSL required for internal connections
- No connection pooling limits

### 2.2 Redis (6er6379)

- Exposed port in docker-compose (6379:6379)
- Default password: `redis_secret`
- No TLS for internal connections
- Cache keys lack namespace collision protection

### 2.3 Celery Workers

- No task authentication
- No task result encryption
- JSON serialization (acceptable)
- No rate limiting on task dispatch

### 2.4 Elasticsearch (9200)

- Optional profile
- No authentication (`xpack.security.enabled=false`)
- No TLS
- Exposed port

---

## 3. Client-Side Attack Surface

### 3.1 React SPA

| Surface | Type | Risk |
|---------|------|------|
| JSX rendering | XSS via dangerouslySetInnerHTML | Low |
| URL parameters | Open redirect | Low |
| Local storage | Token storage | Medium |
| API calls | CORS misconfiguration | High |

### 3.2 Session Management

| Issue | Risk |
|-------|------|
| No session rotation after login | Medium |
| No concurrent session limits | Medium |
| No device fingerprinting | Low |
| JWT tokens in localStorage | Medium |

---

## 4. File Upload Attack Surface

### 4.1 Upload Endpoints

| Endpoint | Accepted Types | Validation | Max Size |
|----------|---------------|------------|----------|
| Agent KYC (id_photo) | JPEG, PNG, WebP | Content-type only | 10MB |
| Agent KYC (resume) | PDF + images | Content-type only | 10MB |
| Agent KYC (certificates) | PDF + images | Content-type only | 10MB |
| KYC Profile (id_front) | Any | None | None |
| KYC Profile (selfie) | Any | None | None |
| Land images | Any (ImageField) | Extension only | None |
| Popup ad images | Any (ImageField) | Extension only | None |
| Documents | Any (FileField) | None | None |

### 4.2 Missing Protections

- No MIME type validation beyond content-type header
- No virus/malware scanning
- No file content analysis (polyglot detection)
- No image dimension validation
- No SVG sanitization
- Cloudinary storage provides some isolation
- Local fallback storage is in `/media/` (potentially web-accessible)

---

## 5. Third-Party Dependency Attack Surface

### 5.1 Critical Dependencies

| Package | Version | Known Issues |
|---------|---------|-------------|
| cryptography | 41.0.7 | Outdated; current is 44.x |
| Django | 6.0.3 | Current |
| djangorestframework | 3.17.0 | Current |
| stripe | 11.5.0 | Check for updates |
| requests | 2.32.5 | Current |
| Pillow | 12.1.1 | Check for CVEs |

### 5.2 Missing Security Dependencies

- No `argon2-cffi` for password hashing
- No `django-axes` for account lockout
- No `django-csp` for Content Security Policy
- No `django-ratelimit` for granular rate limiting
- No `bleach` for HTML sanitization
- No `pyotp` for TOTP MFA
- No `qrcode` for MFA setup

---

## 6. Network Attack Surface

### 6.1 Docker Network

```
Internet → [Nginx:80/443] → [Django:8000] → [PostgreSQL:5432]
                                     ↓
                               [Redis:6379]
                                     ↓
                              [Celery Workers]
```

### 6.2 Exposed Ports

| Service | Port | External Access | Risk |
|---------|------|----------------|------|
| Nginx | 80, 443 | Yes | Expected |
| Django | 8000 | Yes (should be internal only) | **High** |
| PostgreSQL | 5432 | Yes (should be internal only) | **Critical** |
| Redis | 6379 | Yes (should be internal only) | **Critical** |
| Elasticsearch | 9200 | Yes (should be internal only) | **High** |

---

## 7. Attack Surface Reduction Recommendations

1. **Remove external port mappings** for PostgreSQL, Redis, Elasticsearch, and Django
2. **Add authentication** to ALL API endpoints (remove AllowAny default)
3. **Implement webhook signature verification** for all payment callbacks
4. **Add file upload validation** with virus scanning
5. **Enable Elasticsearch security** or remove the profile
6. **Add CSP headers** via django-csp
7. **Implement request signing** for inter-service communication
8. **Add TLS** for Redis and PostgreSQL connections
9. **Restrict CORS** to known origins only
10. **Remove debug information** from error responses
