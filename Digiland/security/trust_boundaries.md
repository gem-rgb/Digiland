# Digiland Trust Boundaries

**Version**: 1.0 | **Date**: 2026-06-03 | **Classification**: Confidential

---

## Trust Boundary Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        UNTRUSTED ZONE                                │
│                                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐                  │
│  │  Browser  │    │  Mobile  │    │  Attacker    │                  │
│  └────┬─────┘    └────┬─────┘    └──────┬───────┘                  │
│       │               │                │                            │
═══════╪═══════════════╪════════════════╪══════════ TB-1 (Internet) ═
       │               │                │                            │
│  ┌───┴───────────────┴────────────────┴───┐                       │
│  │          Nginx Reverse Proxy           │                       │
│  │          (TLS Termination)             │                       │
│  └──────────────────┬────────────────────┘                        │
│                     │                                                 │
═════════════════════╪══════════════════ TB-2 (DMZ) ════════════════
│                     │                                                 │
│  ┌──────────────────┴────────────────────┐                        │
│  │        Django Application             │                        │
│  │        (Gunicorn Workers)             │                        │
│  │                                        │                        │
│  │  ┌─────────┐  ┌──────────┐  ┌──────┐ │                        │
│  │  │  Views   │  │  Serial. │  │ Auth │ │                        │
│  │  └────┬────┘  └────┬─────┘  └──┬───┘ │                        │
│  │       │             │           │      │                        │
│  │  ┌────┴─────────────┴───────────┴───┐ │                        │
│  │  │           ORM Layer               │ │                        │
│  │  └────────────────┬─────────────────┘ │                        │
│  └───────────────────┼───────────────────┘                        │
│                      │                                              │
══════════════════════╪═══════════════ TB-3 (Data Store) ════════════
│                      │                                              │
│  ┌───────────────────┼───────────────────┐                        │
│  │  ┌────────┐  ┌────┴───┐  ┌─────────┐ │                        │
│  │  │  PG/   │  │ Redis  │  │Elastic  │ │     TRUSTED ZONE       │
│  │  │PostGIS │  │ Cache  │  │ Search  │ │                        │
│  │  └────────┘  └────────┘  └─────────┘ │                        │
│  └───────────────────────────────────────┘                        │
│                                                                     │
│  ┌───────────────────────────────────────┐                        │
│  │  ┌──────────┐  ┌──────────────────┐   │                        │
│  │  │  Celery   │  │  Celery Beat     │   │                        │
│  │  │  Workers  │  │  Scheduler       │   │                        │
│  │  └──────────┘  └──────────────────┘   │                        │
│  └───────────────────────────────────────┘                        │
│                                                                     │
═══════════════════════════════════════════ TB-5 (External) ═════════
│                                                                     │
│  ┌──────────┐ ┌────────┐ ┌──────────┐ ┌────────┐                  │
│  │ Paystack │ │ M-Pesa │ │   KRA    │ │  KCB   │                  │
│  │          │ │ Daraja │ │GavaConn. │ │  Bank  │                  │
│  └──────────┘ └────────┘ └──────────┘ └────────┘                  │
│                                                                     │
│  ┌──────────┐ ┌────────┐                                           │
│  │ Cloudinary│ │ Stripe │                                           │
│  │          │ │        │                                           │
│  └──────────┘ └────────┘                                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Trust Boundary Details

### TB-1: Internet ↔ Application (Nginx)

**Boundary Type**: Network perimeter  
**Threats**: DDoS, protocol abuse, request smuggling, TLS downgrade  
**Current Controls**:
- Nginx TLS termination (production)
- Basic health checks
- No WAF
- No DDoS protection

**Required Controls**:
- Web Application Firewall (WAF)
- DDoS mitigation (Cloudflare/AWS Shield)
- Rate limiting at Nginx level
- Request size limits
- Security headers (HSTS, X-Frame-Options, CSP)

### TB-2: Nginx ↔ Django

**Boundary Type**: Process boundary  
**Threats**: Request smuggling, header injection  
**Current Controls**:
- Gunicorn request validation
- Whitenoise for static files

**Required Controls**:
- Proxy header validation
- Request timeout enforcement
- Connection limits

### TB-3: Django ↔ Data Stores

**Boundary Type**: Data access  
**Threats**: SQL injection, cache poisoning, data exfiltration  
**Current Controls**:
- Django ORM (parameterized queries)
- Redis password authentication
- No TLS for internal connections

**Required Controls**:
- TLS for all data store connections
- Connection pooling with limits
- Query timeout enforcement
- Data encryption at rest

### TB-4: Django ↔ External APIs

**Boundary Type**: External service  
**Threats**: API key exposure, SSRF, callback forgery, service unavailability  
**Current Controls**:
- HTTPS for all external calls
- API key authentication
- Request timeouts (30s)

**Required Controls**:
- Webhook signature verification
- Circuit breaker pattern
- API key rotation mechanism
- Request/response logging (sanitized)
- Idempotency for payment operations

### TB-5: Client ↔ Django (User Trust Boundary)

**Boundary Type**: User authentication  
**Threats**: Session hijacking, CSRF, XSS, credential theft  
**Current Controls**:
- Django CSRF middleware (partial - @csrf_exempt used)
- Session cookies (partial security)
- Allauth for account management

**Required Controls**:
- Secure cookie attributes (HttpOnly, SameSite, Secure)
- Session rotation on login/privilege change
- MFA for sensitive operations
- CSP headers
- Output encoding
- JWT with short expiry + refresh tokens

---

## Data Classification Across Boundaries

| Data Type | Classification | Storage | Transit | Access Control |
|-----------|---------------|---------|---------|----------------|
| Passwords | Secret | Hashed (Argon2id needed) | TLS | Never readable |
| API Keys | Secret | Environment variables | TLS | Admin only |
| KRA PIN | PII | Encrypted hash | TLS | Owner + Admin |
| ID Number | PII | Database | TLS | Owner + Admin |
| Phone Number | PII | Database | TLS | Owner + Admin |
| Face Embedding | Biometric | Database (JSON) | TLS | Write-only, never exposed |
| Bank Account | Financial | Database | TLS | Owner + Admin |
| Transaction Amount | Financial | Database | TLS | Parties + Admin |
| Payment / Settlement Reference | Financial | Database | TLS | Parties + Admin |
| Land Coordinates | Operational | Database | TLS | Authenticated users |
| Signatures | Legal | Base64 text | TLS | Parties + Admin |
