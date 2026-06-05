# Digiland Risk Assessment

**Version**: 1.0 | **Date**: 2026-06-03 | **Classification**: Confidential

---

## Risk Scoring Methodology

**Risk = Impact x Likelihood**

| Score | Impact | Likelihood |
|-------|--------|------------|
| 5 | Critical: Complete system compromise, financial loss >$100K | Almost certain |
| 4 | High: Significant data breach, financial loss $10K-$100K | Likely |
| 3 | Medium: Limited data exposure, financial loss $1K-$10K | Possible |
| 2 | Low: Minor data leak, financial loss <$1K | Unlikely |
| 1 | Negligible: No significant impact | Rare |

---

## Risk Register

### CRITICAL RISKS

| ID | Risk | Impact | Likelihood | Score | Status | Owner |
|----|------|--------|------------|-------|--------|-------|
| R-001 | Unauthenticated API access to transactions, documents, parcels | 5 | 5 | **25** | Open | Backend |
| R-002 | Payment callback forgery (no signature verification) | 5 | 4 | **20** | Open | Backend |
| R-003 | Hardcoded admin finance PIN ("admin2026") | 5 | 5 | **25** | Open | Backend |
| R-004 | DEFAULT_PERMISSION_CLASSES = AllowAny | 5 | 5 | **25** | Open | Backend |
| R-005 | Admin role self-assignment during registration | 5 | 4 | **20** | Open | Backend |
| R-006 | Insecure SECRET_KEY default in settings.py | 4 | 5 | **20** | Open | DevOps |
| R-007 | CORS_ALLOW_ALL_ORIGINS = True | 4 | 4 | **16** | Open | Backend |

### HIGH RISKS

| ID | Risk | Impact | Likelihood | Score | Status | Owner |
|----|------|--------|------------|-------|--------|-------|
| R-008 | Login endpoint returns user data without JWT token | 4 | 4 | **16** | Open | Backend |
| R-009 | No IDOR protection on any endpoint | 4 | 5 | **20** | Open | Backend |
| R-010 | Rate limiting middleware not active in MIDDLEWARE | 4 | 4 | **16** | Open | Backend |
| R-011 | RBACMiddleware not active in MIDDLEWARE | 4 | 3 | **12** | Open | Backend |
| R-012 | Mock identity verification auto-approves users | 4 | 3 | **12** | Open | Backend |
| R-013 | Transaction status changeable without authorization | 5 | 3 | **15** | Open | Backend |
| R-014 | No file content validation (only content-type check) | 4 | 3 | **12** | Open | Backend |
| R-015 | Database and Redis ports exposed externally | 4 | 3 | **12** | Open | DevOps |
| R-016 | Payment processing lacks idempotency | 4 | 3 | **12** | Open | Backend |
| R-017 | KYC face embedding exposed in serializer | 4 | 2 | **8** | Open | Backend |

### MEDIUM RISKS

| ID | Risk | Impact | Likelihood | Score | Status | Owner |
|----|------|--------|------------|-------|--------|-------|
| R-018 | No Argon2id password hashing (using Django default PBKDF2) | 3 | 3 | **9** | Open | Backend |
| R-019 | No MFA for admin or financial operations | 3 | 4 | **12** | Open | Backend |
| R-020 | No account lockout mechanism | 3 | 4 | **12** | Open | Backend |
| R-021 | No password breach checking | 2 | 3 | **6** | Open | Backend |
| R-022 | No Content Security Policy headers | 3 | 3 | **9** | Open | Backend |
| R-023 | No CSP, X-Content-Type-Options in dev settings | 2 | 4 | **8** | Open | Backend |
| R-024 | Elasticsearch running without authentication | 3 | 3 | **9** | Open | DevOps |
| R-025 | No HTML sanitization for user input | 3 | 3 | **9** | Open | Backend |
| R-026 | No audit logging for security events | 3 | 2 | **6** | Open | Backend |
| R-027 | Lowest negotiable price exposed in API | 3 | 2 | **6** | Open | Backend |

### LOW RISKS

| ID | Risk | Impact | Likelihood | Score | Status | Owner |
|----|------|--------|------------|-------|--------|-------|
| R-028 | No password history enforcement | 2 | 2 | **4** | Open | Backend |
| R-029 | Docker container health check exposes admin URL | 1 | 2 | **2** | Open | DevOps |
| R-030 | Superuser creation via shell in entrypoint (SQL injection risk) | 3 | 1 | **3** | Open | DevOps |

---

## Risk Heat Map

```
              LIKELIHOOD
         1    2    3    4    5
      ┌────┬────┬────┬────┬────┐
   5  │    │    │R01 │R02 │R03 │  CRITICAL
      ├────┼────┼────┼────┼────┤
   4  │    │R17 │R14 │R07 │R04 │  HIGH
      ├────┼────┼────┼────┼────┤
I  3  │R30 │R26 │R18 │R19 │R09 │  MEDIUM
M      ├────┼────┼────┼────┼────┤
P  2  │    │R28 │R21 │R23 │    │  LOW
A      ├────┼────┼────┼────┼────┤
C  1  │    │R29 │    │    │    │  NEGLIGIBLE
T      └────┴────┴────┴────┴────┘
```

---

## Residual Risk After Remediation

After implementing all recommended controls, the residual risk profile should be:

| Severity | Current | Target | Delta |
|----------|---------|--------|-------|
| Critical | 7 | 0 | -7 |
| High | 10 | 0 | -10 |
| Medium | 10 | 3 | -7 |
| Low | 3 | 2 | -1 |
| **Total** | **30** | **5** | **-25** |

Remaining residual risks (accepted):
- R-024: Elasticsearch auth (mitigated by disabling in production unless needed)
- R-028: Password history (mitigated by Argon2id + minimum length)
- R-029: Health check URL (accepted - internal only)
