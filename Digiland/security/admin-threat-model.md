# Admin Control Plane Threat Model

**Document Version:** 1.0  
**Classification:** Confidential — Internal Use Only  
**Last Updated:** 2025-01-15  
**Owner:** Security Engineering Team  
**Review Cycle:** Quarterly  

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Threat Actors](#threat-actors)
3. [Threat Catalog (STRIDE)](#threat-catalog-stride)
4. [Attack Trees](#attack-trees)
5. [Risk Summary Matrix](#risk-summary-matrix)
6. [Appendices](#appendices)

---

## System Overview

### Architecture Description

The Digiland Admin Control Plane is a segregated management layer that provides authorized administrators with oversight and control over the Digiland land platform. It manages critical operations including user KYC verification, direct settlement milestone approval, payout monitoring, dispute resolution, platform configuration, and audit logging. Digiland operates strictly non-custodial direct settlement where purchase funds flow directly between buyer and seller accounts.

The control plane operates as a separate deployment from the public-facing application, with its own authentication pipeline, session management, authorization rules, and monitoring infrastructure. It interfaces with the same backend data stores as the public application but through restricted service accounts with elevated privileges.

**Key Components:**

| Component | Description | Trust Level |
|-----------|-------------|-------------|
| Admin Dashboard UI | React-based SPA for admin operations | Semi-trusted (browser context) |
| Admin API Gateway | Rate-limited, authenticated API entry point | Trusted |
| Auth Service | MFA-enforced authentication with step-up capability | Trusted |
| Authorization Engine | RBAC + ABAC policy evaluation service | Trusted |
| Financial Approval Service | Dual-approval workflow for monetary operations | Critical Trust |
| KYC Review Service | Document review and identity verification | Trusted |
| Audit Log Service | Append-only, hash-chained event logging | Critical Trust |
| Session Manager | Device-bound, anomaly-detected session lifecycle | Trusted |
| Emergency Controls | Withdrawal freeze, session revocation, lockdown | Critical Trust |
| Admin Database | Separate schema with admin-specific tables | Trusted |

### Trust Boundaries Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PUBLIC INTERNET                                 │
│                                                                         │
│   ┌──────────────┐                    ┌──────────────┐                  │
│   │  Attacker     │                    │  Legitimate   │                  │
│   │  (External)   │                    │  Admin User   │                  │
│   └──────┬───────┘                    └──────┬───────┘                  │
│          │                                    │                          │
└──────────┼────────────────────────────────────┼──────────────────────────┘
           │                                    │
     ══════╪════════════════════════════════════╪════════  TRUST BOUNDARY 1
           │         (WAF / DDoS Protection)    │          (Network Edge)
           │                                    │
   ┌───────┴────────────────────────────────────┴───────┐
   │              ADMIN API GATEWAY                      │
   │   ┌─────────────────────────────────────────┐      │
   │   │  - TLS Termination                       │      │
   │   │  - Rate Limiting                         │      │
   │   │  - Request Validation                    │      │
   │   │  - IP Allowlist Enforcement              │      │
   │   └─────────────────────────────────────────┘      │
   └───────────────────────┬────────────────────────────┘
                           │
     ══════════════════════╪══════════════════════  TRUST BOUNDARY 2
                           │    (Authentication Layer)
                           │
   ┌───────────────────────┴────────────────────────────┐
   │           AUTHENTICATION SERVICE                    │
   │   ┌─────────────────────────────────────────┐      │
   │   │  - Password Verification                 │      │
   │   │  - TOTP / Hardware Key Verification      │      │
   │   │  - Step-Up Authentication                │      │
   │   │  - Session Token Issuance                │      │
   │   └─────────────────────────────────────────┘      │
   └───────────────────────┬────────────────────────────┘
                           │
     ══════════════════════╪══════════════════════  TRUST BOUNDARY 3
                           │    (Authorization Layer)
                           │
   ┌───────────────────────┴────────────────────────────┐
   │          AUTHORIZATION ENGINE                       │
   │   ┌─────────────────────────────────────────┐      │
   │   │  - RBAC Policy Evaluation                │      │
   │   │  - ABAC Context Checks                   │      │
   │   │  - Permission Scoping                    │      │
   │   │  - Dual-Approval Gate                    │      │
   │   └─────────────────────────────────────────┘      │
   └───────────────────────┬────────────────────────────┘
                           │
     ══════════════════════╪══════════════════════  TRUST BOUNDARY 4
                           │    (Service Layer)
                           │
   ┌───────────────────────┴────────────────────────────┐
   │              ADMIN SERVICES                         │
   │                                                     │
   │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
   │  │ Financial │ │   KYC    │ │  Emergency       │   │
   │  │ Approval  │ │  Review  │ │  Controls        │   │
   │  │ Service   │ │ Service  │ │  Service         │   │
   │  └─────┬────┘ └────┬─────┘ └────────┬─────────┘   │
   │        │            │                │              │
   │  ┌─────┴────────────┴────────────────┴─────────┐   │
   │  │            AUDIT LOG SERVICE                  │   │
   │  │   (Append-Only, Hash-Chained)                │   │
   │  └──────────────────────┬───────────────────────┘   │
   └─────────────────────────┼───────────────────────────┘
                             │
     ════════════════════════╪════════════════════  TRUST BOUNDARY 5
                             │   (Data Layer)
                             │
   ┌─────────────────────────┴───────────────────────────┐
   │              DATA TIER                              │
   │   ┌────────────┐  ┌────────────┐  ┌─────────────┐  │
   │   │  Admin DB   │  │  Audit DB  │  │  KYC Docs   │  │
   │   │  (Encrypted)│  │ (Immutable)│  │  (Encrypted)│  │
   │   └────────────┘  └────────────┘  └─────────────┘  │
   └─────────────────────────────────────────────────────┘
```

### Data Classification for Admin-Accessible Resources

| Data Category | Classification | Admin Access Level | Storage | Encryption |
|---------------|---------------|-------------------|---------|------------|
| User PII (names, emails, phone) | Confidential | All admins (read) | PostgreSQL (RLS) | AES-256 at rest |
| KYC Documents (ID scans, selfies) | Highly Confidential | KYC reviewers only | S3 + CloudFront | AES-256 at rest, TLS in transit |
| Financial records (transactions, balances) | Highly Confidential | Finance admins | PostgreSQL (RLS) | AES-256 at rest |
| Settlement banking details | Critical | Finance + Super admins | PostgreSQL (RLS) | AES-256 at rest |
| Admin credentials (passwords, MFA secrets) | Critical | System only (hashed) | PostgreSQL | Argon2id + AES-256 |
| Audit logs | Highly Confidential | Auditors (read-only) | PostgreSQL (append-only) | AES-256 at rest |
| Platform configuration | Internal | Super admins | PostgreSQL | TLS in transit |
| API keys and secrets | Critical | System only (vault) | HashiCorp Vault | Vault encryption |
| Session tokens | Confidential | System only | Redis (encrypted) | AES-256 at rest |

---

## Threat Actors

### 1. External Attacker (No Access)

**Profile:** Unauthenticated adversary with no insider knowledge or credentials. May range from opportunistic script kiddie to sophisticated cybercriminal.

**Capabilities:**
- Network reconnaissance and port scanning
- Credential stuffing and brute force attacks
- Phishing campaigns targeting admin staff
- Exploitation of publicly known vulnerabilities
- DDoS attacks against admin endpoints
- Social engineering via external channels

**Motivation:** Financial gain, data theft, reputation damage, notoriety

**Sophistication:** Low to High

### 2. Compromised User Account

**Profile:** A regular platform user whose account has been compromised. They have no inherent admin privileges but may exploit vulnerabilities to escalate access.

**Capabilities:**
- Authenticated access to public APIs
- Knowledge of platform functionality and data flows
- Ability to test for IDOR and privilege escalation
- Potential to exploit shared infrastructure vulnerabilities

**Motivation:** Financial gain, unauthorized access to other users' data

**Sophistication:** Medium to High

### 3. Compromised Admin Account

**Profile:** An administrator whose credentials or session have been compromised through phishing, malware, or session hijacking. The attacker now operates with legitimate admin privileges.

**Capabilities:**
- Full or partial admin dashboard access (depending on role)
- Ability to approve/reject KYC applications
- Ability to approve financial transactions (within role)
- Access to user PII and financial data
- Ability to modify platform configurations
- Ability to create other admin accounts (if super admin)

**Motivation:** Financial theft, data exfiltration, platform manipulation

**Sophistication:** Medium to Very High

### 4. Malicious Insider (Admin)

**Profile:** A trusted administrator who intentionally abuses their access for personal gain or to cause harm. This is one of the most dangerous threat actors due to legitimate access and insider knowledge.

**Capabilities:**
- Legitimate admin credentials and MFA tokens
- Full knowledge of internal systems and processes
- Ability to bypass security controls from within
- Ability to manipulate audit trails (if not properly protected)
- Social engineering of other admins for dual-approval bypass
- Timing attacks on approval workflows

**Motivation:** Financial gain, revenge, coercion, ideology

**Sophistication:** High to Very High

### 5. Supply Chain Attacker

**Profile:** An adversary who compromises a third-party dependency, tool, or service used by the admin control plane to inject malicious code or exfiltrate data.

**Capabilities:**
- Code injection via compromised npm/PyPI packages
- Backdoor insertion via compromised CI/CD pipeline
- Data exfiltration via compromised third-party API
- Keylogging or screen capture via compromised endpoint tools
- Dependency confusion attacks

**Motivation:** Mass compromise, targeted data theft, financial gain

**Sophistication:** Very High

### 6. Nation-State Attacker

**Profile:** Advanced persistent threat (APT) groups with significant resources, patience, and capabilities. They target high-value financial platforms for economic espionage, sanctions evasion, or strategic disruption.

**Capabilities:**
- Zero-day vulnerability exploitation
- Advanced social engineering (spear phishing, whaling)
- Physical access attempts (surveillance, burglary)
- Supply chain compromise at hardware/firmware level
- Long-term persistence and lateral movement
- Covert exfiltration channels
- Coordinated multi-vector attacks

**Motivation:** Strategic advantage, economic espionage, sanctions evasion, disruption

**Sophistication:** Very High (state-level resources)

---

## Threat Catalog (STRIDE)

### Scoring Legend

| Score | Likelihood | Impact |
|-------|-----------|--------|
| 1 | Rare — Unlikely to occur | Negligible — Minimal effect |
| 2 | Unlikely — Could occur in exceptional circumstances | Minor — Limited effect, recoverable |
| 3 | Possible — Could occur at some point | Moderate — Notable effect, partially recoverable |
| 4 | Likely — Will probably occur | Major — Significant effect, difficult recovery |
| 5 | Almost Certain — Expected to occur | Severe — Catastrophic, business-threatening |

**Risk Score = Likelihood × Impact**

| Risk Score | Level | Action Required |
|-----------|-------|-----------------|
| 1-4 | Low | Accept, monitor |
| 5-9 | Medium | Mitigate within standard timeline |
| 10-15 | High | Priority mitigation required |
| 16-25 | Critical | Immediate mitigation required |

---

### ADM-001: Admin Credential Theft

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-001 |
| **Category** | Spoofing |
| **Description** | An attacker steals admin credentials through phishing, keylogging, credential stuffing, or social engineering, enabling unauthorized access to the admin control plane. |
| **Affected Component** | Auth Service, Admin Dashboard |
| **Attack Vector** | Phishing emails mimicking Digiland admin portals; credential stuffing using leaked password databases; keylogger malware on admin workstations; social engineering via phone/email |
| **Likelihood** | 5 |
| **Impact** | 5 |
| **Risk Score** | 25 (Critical) |
| **Mitigations** | 1. Mandatory MFA (TOTP + hardware key) for all admin accounts<br>2. Phishing-resistant FIDO2/WebAuthn as primary auth factor<br>3. Password complexity policy (min 16 chars, no dictionary words)<br>4. Credential leak monitoring via Have I Been Pwned API<br>5. Regular security awareness training for admin staff<br>6. Dedicated admin workstations with endpoint protection<br>7. Password rotation every 90 days with history enforcement |

---

### ADM-002: Session Hijacking

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-002 |
| **Category** | Spoofing |
| **Description** | An attacker compromises an active admin session token through XSS, network interception, or session fixation, gaining unauthorized access without needing credentials. |
| **Affected Component** | Session Manager, Admin Dashboard UI |
| **Attack Vector** | XSS exploitation in admin dashboard; session token theft via browser vulnerability; MITM on unsecured network; session fixation via manipulated session IDs; cookie theft via browser extension malware |
| **Likelihood** | 3 |
| **Impact** | 5 |
| **Risk Score** | 15 (High) |
| **Mitigations** | 1. HTTP-only, Secure, SameSite=Strict cookie attributes<br>2. Device fingerprint binding for session tokens<br>3. Session token rotation every 15 minutes<br>4. IP consistency checks during session lifetime<br>5. Concurrent session limits (max 1 active session per admin)<br>6. Content Security Policy (CSP) headers preventing XSS<br>7. Mandatory HTTPS with certificate pinning for admin subdomain |

---

### ADM-003: CSRF on Admin Actions

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-003 |
| **Category** | Tampering |
| **Description** | An attacker tricks an authenticated admin into performing unintended actions by submitting forged requests from a malicious website, leveraging the admin's active session. |
| **Affected Component** | Admin API Gateway, all state-changing admin endpoints |
| **Attack Vector** | Malicious website loaded in admin's browser while authenticated; crafted HTML forms targeting admin API endpoints; XSS payload injecting cross-origin requests; image tags with admin action URLs |
| **Likelihood** | 3 |
| **Impact** | 4 |
| **Risk Score** | 12 (High) |
| **Mitigations** | 1. Anti-CSRF tokens on all state-changing requests (double-submit pattern)<br>2. SameSite=Strict cookie attribute<br>3. Custom X-Admin-Request header required for all admin API calls<br>4. Origin/Referer header validation<br>5. Step-up re-authentication for critical actions (financial, user modification)<br>6. Action confirmation dialogs with user-initiated intent verification |

---

### ADM-004: Privilege Escalation via Role Manipulation

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-004 |
| **Category** | Elevation of Privilege |
| **Description** | An admin with limited permissions manipulates the role assignment system to grant themselves or others elevated privileges beyond their authorized scope. |
| **Affected Component** | Authorization Engine, Admin User Management |
| **Attack Vector** | Direct API manipulation of role assignment endpoints; exploiting IDOR in user management APIs; race condition in role update logic; horizontal privilege escalation via parameter tampering; exploiting flawed ABAC policy evaluation |
| **Likelihood** | 3 |
| **Impact** | 5 |
| **Risk Score** | 15 (High) |
| **Mitigations** | 1. Role assignments require dual approval from two super admins<br>2. Role changes logged with immutable audit trail<br>3. Server-side enforcement of role hierarchy (no self-role-escalation)<br>4. Separation of duties: role admins cannot assign roles to themselves<br>5. API endpoint authorization validated against OPA policy engine<br>6. Periodic access reviews (monthly) with automated anomaly detection<br>7. Break-glass procedures with enhanced monitoring for emergency role changes |

---

### ADM-005: Financial Fraud via Withdrawal Approval

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-005 |
| **Category** | Tampering |
| **Description** | A compromised or malicious admin approves fraudulent withdrawal/disbursement requests, releasing platform fees or unauthorized payout approvals to attacker-controlled destinations. Note that non-custodial direct settlement inherently prevents platform-wide escrow pool drainage. |
| **Affected Component** | Financial Approval Service, Settlement Management |
| **Attack Vector** | Single-admin approval of high-value withdrawals; social engineering of second approver; creating fake transactions then approving them; modifying withdrawal destination after approval (TOCTOU); bypassing amount thresholds for dual approval |
| **Likelihood** | 4 |
| **Impact** | 5 |
| **Risk Score** | 20 (Critical) |
| **Mitigations** | 1. Mandatory dual approval for ALL withdrawals regardless of amount<br>2. Two-person integrity (2PI) — approvers must be from different organizational units<br>3. Transaction signing with hardware tokens (approve button + hardware key tap)<br>4. Withdrawal destination locked after first approval (no modification)<br>5. Real-time anomaly detection on approval patterns<br>6. Automatic freeze on withdrawals exceeding configurable thresholds<br>7. Time-delayed execution for high-value withdrawals (24-hour cooling period)<br>8. Real-time Slack/PagerDuty alerts on withdrawal approvals |

---

### ADM-006: Insider Threat — Unauthorized Financial Transfer

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-006 |
| **Category** | Tampering |
| **Description** | A trusted admin with legitimate financial access intentionally processes unauthorized transfers, potentially colluding with external parties or creating fictitious transactions. |
| **Affected Component** | Financial Approval Service, Settlement Management |
| **Attack Vector** | Collusion between two admins for dual-approval bypass; creating shell user accounts with KYC bypass; modifying transaction records post-execution; exploiting emergency override controls; gradual small-amount theft below alerting thresholds (salami attack) |
| **Likelihood** | 3 |
| **Impact** | 5 |
| **Risk Score** | 15 (High) |
| **Mitigations** | 1. Mandatory cooling-off period for transactions above KES 500,000<br>2. Automated volume and pattern analysis with ML-based anomaly detection<br>3. Cross-verification of beneficiary details against KYC records<br>4. Segregation of duties: transaction creator ≠ approver<br>5. Periodic reconciliation with independent bank statements<br>6. Whistleblower channel for reporting suspicious admin behavior<br>7. Random audit sampling of approved transactions (10% monthly) |

---

### ADM-007: KYC Approval Bypass

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-007 |
| **Category** | Elevation of Privilege |
| **Description** | An attacker or malicious admin bypasses the KYC verification process to grant verified status to unverified or fraudulent accounts, enabling them to conduct transactions that require verified identity. |
| **Affected Component** | KYC Review Service, User Management |
| **Attack Vector** | Direct API call to KYC approval endpoint; modifying user verification_status in database; exploiting race condition between document upload and review; creating admin account with KYC review privileges; AI-generated deepfake documents passing automated checks |
| **Likelihood** | 3 |
| **Impact** | 4 |
| **Risk Score** | 12 (High) |
| **Mitigations** | 1. KYC approval requires dual review from separate KYC officers<br>2. All KYC decisions logged with document snapshots and reviewer rationale<br>3. Automated liveness detection and document authenticity checks<br>4. Periodic re-verification of KYC-approved accounts (6-month cycle)<br>5. Cross-reference against government verification APIs (e.g., IPRS Kenya)<br>6. KYC rejection rate monitoring per reviewer (insider detection)<br>7. Immutable KYC document storage with tamper detection |

---

### ADM-008: User Impersonation

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-008 |
| **Category** | Spoofing |
| **Description** | An admin uses impersonation features (if available for support) or exploits authentication weaknesses to operate as another user, performing actions that appear to come from the impersonated user. |
| **Affected Component** | Auth Service, Admin User Management |
| **Attack Vector** | Abusing legitimate impersonation/support features; session token manipulation; password reset exploitation; creating parallel sessions as target user; exploiting SSO token generation flaws |
| **Likelihood** | 3 |
| **Impact** | 5 |
| **Risk Score** | 15 (High) |
| **Mitigations** | 1. Impersonation feature disabled by default; enablement requires super admin approval<br>2. All impersonation sessions logged with original admin identity<br>3. Impersonation sessions time-limited (max 15 minutes)<br>4. Impersonated user receives notification of admin access<br>5. Impersonation cannot perform financial actions (read-only mode)<br>6. Step-up authentication required before initiating impersonation<br>7. Real-time alerting on all impersonation events |

---

### ADM-009: Audit Log Tampering

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-009 |
| **Category** | Tampering |
| **Description** | An attacker or malicious admin modifies, deletes, or corrupts audit log entries to cover unauthorized actions, hamper investigations, or destroy evidence of financial fraud. |
| **Affected Component** | Audit Log Service, Audit Database |
| **Attack Vector** | Direct database access to modify log entries; exploiting admin log management APIs; SQL injection in log search functionality; destroying logs via disk-level access; tampering with hash chain to hide modifications |
| **Likelihood** | 2 |
| **Impact** | 5 |
| **Risk Score** | 10 (High) |
| **Mitigations** | 1. Append-only database with no UPDATE/DELETE grants for any role<br>2. Hash chain integrity (each log entry includes hash of previous entry)<br>3. Periodic hash chain verification (automated, hourly)<br>4. Audit logs replicated to separate, air-gapped storage (WORM)<br>5. No admin API for log modification — only search and export<br>6. Database-level row security policies preventing mutation<br>7. Separate audit log database with distinct credentials from admin DB<br>8. Tampering detection triggers immediate P0 alert |

---

### ADM-010: Mass User Data Exfiltration

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-010 |
| **Category** | Information Disclosure |
| **Description** | An attacker or compromised admin extracts large volumes of user PII, financial data, or KYC documents from the platform through bulk API access, database queries, or export features. |
| **Affected Component** | All admin services with data access, Export features |
| **Attack Vector** | Abusing bulk export/data-download admin features; automated API scraping with pagination; direct database query access; screenshot/copy of paginated user lists; dumping KYC document storage; exploiting search/filter to systematically extract data |
| **Likelihood** | 3 |
| **Impact** | 5 |
| **Risk Score** | 15 (High) |
| **Mitigations** | 1. Rate limiting on all data-accessing admin API endpoints<br>2. Maximum page size of 50 records with enforced pagination<br>3. Bulk export feature requires dual approval and generates audited report<br>4. Data access patterns monitored with ML-based anomaly detection<br>5. KYC document access logged with full audit trail<br>6. DLP controls on admin workstations (clipboard, print, USB restrictions)<br>7. Automated alerts on unusual data access volumes (> 500 records/hour)<br>8. Data masking for non-essential fields (partial phone, partial ID number) |

---

### ADM-011: Admin Account Takeover via Password Reset

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-011 |
| **Category** | Spoofing |
| **Description** | An attacker exploits the password reset flow to gain control of an admin account, either by compromising the admin's email account, intercepting reset tokens, or exploiting flaws in the reset mechanism. |
| **Affected Component** | Auth Service, Password Reset Flow |
| **Attack Vector** | Email account compromise to capture reset links; predictability of reset tokens; reset token reuse; race condition in token validation; bypassing MFA requirement during reset; social engineering support team for manual reset |
| **Likelihood** | 3 |
| **Impact** | 5 |
| **Risk Score** | 15 (High) |
| **Mitigations** | 1. Password reset requires MFA verification BEFORE issuing reset token<br>2. Reset tokens are single-use, time-limited (15 minutes), cryptographically random<br>3. Password reset triggers notification to admin's registered devices<br>4. Reset tokens delivered via secondary channel (SMS + email)<br>5. No manual password resets by support — all resets go through automated flow<br>6. Previous session invalidated on password reset<br>7. 24-hour cooldown on repeated reset attempts for same account |

---

### ADM-012: MFA Bypass

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-012 |
| **Category** | Elevation of Privilege |
| **Description** | An attacker bypasses multi-factor authentication through technical exploitation, social engineering, or process weaknesses to gain access with only a compromised password. |
| **Affected Component** | Auth Service, MFA Implementation |
| **Attack Vector** | SIM swapping to intercept TOTP seed/SMS codes; real-time phishing proxy (Adversary-in-the-Middle); exploiting MFA bypass codes; brute forcing TOTP within validity window; session token theft post-MFA; exploiting MFA recovery flow weaknesses |
| **Likelihood** | 3 |
| **Impact** | 5 |
| **Risk Score** | 15 (High) |
| **Mitigations** | 1. FIDO2/WebAuthn as primary MFA (phishing-resistant)<br>2. TOTP as secondary fallback only, no SMS for admin accounts<br>3. No MFA bypass/recovery codes for admin accounts<br>4. Real-time phishing detection via origin binding (WebAuthn)<br>5. MFA challenge on every session, no "remember this device" for admins<br>6. Step-up MFA required for critical operations within active session<br>7. Monitoring for MFA failure patterns (brute force detection)<br>8. Account lockout after 5 consecutive MFA failures (manual unlock required) |

---

### ADM-013: API Key Leakage

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-013 |
| **Category** | Information Disclosure |
| **Description** | API keys, secrets, or credentials used by the admin control plane are exposed through code repositories, configuration files, logs, or compromised development environments. |
| **Affected Component** | CI/CD Pipeline, Source Code, Configuration Management |
| **Attack Vector** | Accidental commit of secrets to Git repository; secrets in Docker image layers; leaked environment variables in debug pages; secrets in error messages or logs; compromised developer workstation; third-party dependency accessing env vars |
| **Likelihood** | 3 |
| **Impact** | 4 |
| **Risk Score** | 12 (High) |
| **Mitigations** | 1. All secrets stored in HashiCorp Vault, never in source code<br>2. Pre-commit hooks scanning for secret patterns (gitleaks)<br>3. GitHub secret scanning enabled on all repositories<br>4. Runtime secret injection via Vault sidecar (no env vars in CI)<br>5. API keys rotated automatically every 30 days<br>6. Separate API keys per environment with scoped permissions<br>7. Secret access audit logging in Vault<br>8. Docker image scanning for leaked credentials before deployment |

---

### ADM-014: DNS Hijacking of Admin Domain

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-014 |
| **Category** | Spoofing |
| **Description** | An attacker compromises DNS records for the admin control plane domain, redirecting admin traffic to a attacker-controlled server that captures credentials and MFA tokens. |
| **Affected Component** | DNS Configuration, TLS Certificate Management |
| **Attack Vector** | Compromising DNS registrar account; BGP hijacking of admin IP range; DNS cache poisoning; compromising DNS hosting provider; social engineering registrar support to transfer domain |
| **Likelihood** | 2 |
| **Impact** | 5 |
| **Risk Score** | 10 (High) |
| **Mitigations** | 1. DNSSEC enabled on admin domain with verified chain of trust<br>2. Certificate Transparency monitoring for unauthorized cert issuance<br>3. Registry lock on domain (prevents unauthorized transfers/changes)<br>4. Multi-factor authentication on DNS registrar account<br>5. DNS change monitoring with real-time alerts<br>6. HPKP/Expect-CT headers for certificate pinning<br>7. Separate DNS provider from public app (isolation of compromise) |

---

### ADM-015: Supply Chain Compromise of Admin Dependencies

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-015 |
| **Category** | Tampering |
| **Description** | A malicious package is introduced into the admin control plane's dependency chain, either through compromised open-source packages, typosquatting, or dependency confusion attacks, leading to code execution or data exfiltration. |
| **Affected Component** | Build Pipeline, Runtime Dependencies |
| **Attack Vector** | Malicious npm/PyPI package with similar name to internal package; compromised maintainer account on popular package; dependency confusion between internal and public registries; compromised CI/CD build agent; malicious code injected via build tool plugin |
| **Likelihood** | 3 |
| **Impact** | 4 |
| **Risk Score** | 12 (High) |
| **Mitigations** | 1. Private npm/PyPI registry with curated allowlist (Artifactory/Nexus)<br>2. Dependency pinning with lockfiles (package-lock.json, requirements.txt hashes)<br>3. Automated SCA scanning (Snyk/Dependabot) on every PR<br>4. Dependency review for all new package additions<br>5. Namespace reservation on public registries for internal package names<br>6. Build-time integrity verification of all dependencies<br>7. Runtime application self-protection (RASP) monitoring<br>8. SBOM (Software Bill of Materials) generation for every release |

---

### ADM-016: Brute Force Against Admin Login

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-016 |
| **Category** | Denial of Service / Elevation of Privilege |
| **Description** | An attacker systematically attempts to guess admin credentials through automated login attempts, potentially locking out legitimate admins (DoS) or successfully guessing weak passwords. |
| **Affected Component** | Auth Service, Admin Login Endpoint |
| **Attack Vector** | Credential stuffing with leaked username/password pairs; dictionary attacks against known admin email addresses; password spraying with common passwords; distributed attacks from multiple IPs to evade rate limiting |
| **Likelihood** | 5 |
| **Impact** | 3 |
| **Risk Score** | 15 (High) |
| **Mitigations** | 1. Account lockout after 5 failed attempts (30-minute lockout)<br>2. Progressive delays between failed attempts (exponential backoff)<br>3. CAPTCHA after 3 failed attempts<br>4. IP-based rate limiting (10 attempts per IP per hour)<br>5. Global rate limiting across all IPs (100 attempts per hour total)<br>6. Admin login endpoint not discoverable (non-standard path)<br>7. Real-time alerting on brute force detection<br>8. Geographic restrictions on admin login (Kenya + whitelisted countries) |

---

### ADM-017: Concurrent Session Abuse

| Field | Value |
|-------|
| **Threat ID** | ADM-017 |
| **Category** | Elevation of Privilege |
| **Description** | An attacker maintains multiple concurrent sessions for a single admin account, enabling persistent access even after the legitimate admin believes they have logged out, or enabling simultaneous actions that bypass single-operator controls. |
| **Affected Component** | Session Manager |
| **Attack Vector** | Session token theft enabling parallel session; exploiting session creation race condition; using stolen credentials to create new session while legitimate session active; exploiting "remember me" functionality; browser tab isolation weakness |
| **Likelihood** | 3 |
| **Impact** | 4 |
| **Risk Score** | 12 (High) |
| **Mitigations** | 1. Maximum one active session per admin account (kill previous on new login)<br>2. Session creation triggers notification to admin's registered devices<br>3. Session list visible to admin with ability to terminate remote sessions<br>4. Device fingerprint binding prevents session transfer between devices<br>5. Absolute session timeout of 4 hours regardless of activity<br>6. Idle timeout of 15 minutes with re-authentication required<br>7. All concurrent session attempts trigger security alert |

---

### ADM-018: Time-of-Check/Time-of-Use (TOCTOU) Attacks

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-018 |
| **Category** | Tampering |
| **Description** | An attacker exploits the time gap between when an admin reviews a transaction (check) and when it is executed (use) to modify the transaction details, such as changing the withdrawal amount or destination. |
| **Affected Component** | Financial Approval Service, Withdrawal Processing |
| **Attack Vector** | Modifying transaction amount between first and second approval; changing beneficiary account after approval screen but before execution; altering transaction metadata between review and confirmation; exploiting async processing delays |
| **Likelihood** | 2 |
| **Impact** | 5 |
| **Risk Score** | 10 (High) |
| **Mitigations** | 1. Transaction details hashed and signed at creation — any modification invalidates approval<br>2. Approval locks all transaction fields (amount, destination, type)<br>3. Second approver sees exact same data as first approver (cryptographic verification)<br>4. Transaction execution validates hash matches approved version<br>5. Atomic database operations for approval + execution<br>6. Post-execution verification against pre-approval snapshot<br>7. Automated reconciliation of approved vs. executed transactions |

---

### ADM-019: Emergency Control Abuse

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-019 |
| **Category** | Denial of Service |
| **Description** | An attacker or malicious admin activates emergency controls (withdrawal freeze, platform lockdown) without legitimate cause, causing business disruption, or uses emergency controls to cover tracks during an attack (e.g., freezing withdrawals to delay detection of fraud). |
| **Affected Component** | Emergency Controls Service |
| **Attack Vector** | Unauthorized activation of withdrawal freeze; triggering platform lockdown via compromised admin; using emergency controls to mask ongoing fraud; social engineering to trick admin into activating emergency controls; exploiting emergency override to bypass normal dual approval |
| **Likelihood** | 2 |
| **Impact** | 4 |
| **Risk Score** | 8 (Medium) |
| **Mitigations** | 1. Emergency control activation requires dual super admin approval<br>2. All emergency activations logged with mandatory justification field<br>3. Automatic deactivation timer (max 4 hours) with extension requiring re-approval<br>4. Post-incident review required within 24 hours of any emergency activation<br>5. Emergency control activation triggers P0 alert to entire security team<br>6. Separate "break-glass" credentials with enhanced audit requirements<br>7. Rate limiting on emergency control activation (once per hour per admin) |

---

### ADM-020: Approval Workflow Bypass

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-020 |
| **Category** | Elevation of Privilege |
| **Description** | An attacker circumvents the dual-approval requirement for sensitive operations through technical exploitation, process manipulation, or social engineering, enabling single-person execution of critical actions. |
| **Affected Component** | Financial Approval Service, Authorization Engine |
| **Attack Vector** | Race condition between approval check and execution; API parameter manipulation to skip approval step; exploiting admin-to-admin social engineering ("please just approve this quickly"); reusing old approval tokens; exploiting emergency override for non-emergency actions; splitting transactions below dual-approval threshold |
| **Likelihood** | 3 |
| **Impact** | 5 |
| **Risk Score** | 15 (High) |
| **Mitigations** | 1. Server-side enforcement of approval count — no API can skip approval check<br>2. Approval tokens are single-use, transaction-specific, and time-limited<br>3. Minimum 5-minute delay between first and second approval (cooling period)<br>4. Approval must come from different admin account and different IP<br>5. Transaction splitting detection (cumulative amount tracking per beneficiary)<br>6. Emergency override has separate audit trail and mandatory post-review<br>7. Approval history immutable — cannot be deleted or modified |

---

### ADM-021: Admin Dashboard XSS Leading to Account Compromise

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-021 |
| **Category** | Spoofing |
| **Description** | Stored XSS in user-generated content (e.g., KYC document names, user profile fields) executes in the admin dashboard context, enabling session token theft, keystroke logging, or unauthorized API calls. |
| **Affected Component** | Admin Dashboard UI, KYC Review Interface |
| **Attack Vector** | Malicious JavaScript in user profile display name; XSS in document upload filenames; rich text content in support tickets rendered unsanitized; SVG file upload with embedded script; template injection in admin notification emails |
| **Likelihood** | 3 |
| **Impact** | 4 |
| **Risk Score** | 12 (High) |
| **Mitigations** | 1. Content Security Policy (CSP) with strict-src, no inline scripts<br>2. All user-generated content sanitized before rendering (DOMPurify)<br>3. HTTP-only cookies prevent JavaScript access to session tokens<br>4. Trusted Types API enforcement for DOM manipulation<br>5. Regular XSS scanning with automated tools (OWASP ZAP)<br>6. Input validation and output encoding on all admin-facing templates<br>7. Subresource Integrity (SRI) for all external JavaScript |

---

### ADM-022: Database Direct Access Compromise

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-022 |
| **Category** | Information Disclosure |
| **Description** | An attacker gains direct access to the admin database through compromised database credentials, network access to the database port, or exploitation of database management interfaces. |
| **Affected Component** | Admin Database, Database Network Configuration |
| **Attack Vector** | Compromised database credentials from leaked config; database port exposed to internal network with lateral movement; SQL injection in admin API enabling database access; compromised database admin tool (pgAdmin); exploiting database replication user for data access |
| **Likelihood** | 2 |
| **Impact** | 5 |
| **Risk Score** | 10 (High) |
| **Mitigations** | 1. Database in private subnet with no internet access<br>2. Database access only via authenticated connection pooling (PgBouncer)<br>3. Row-Level Security (RLS) policies on all tables<br>4. Database credentials rotated weekly via Vault<br>5. Separate credentials for admin service vs. audit service<br>6. Network-level isolation: database only accessible from admin API pods<br>7. Database query logging and anomaly detection<br>8. Encryption at rest with customer-managed KMS keys |

---

### ADM-023: Admin API Rate Limit Bypass

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-023 |
| **Category** | Denial of Service |
| **Description** | An attacker bypasses rate limiting controls on admin APIs through distributed attacks, header manipulation, or exploitation of rate limit implementation flaws, enabling brute force attacks or service degradation. |
| **Affected Component** | Admin API Gateway, Rate Limiting Service |
| **Attack Vector** | Rotating source IPs via proxy network; IP spoofing via X-Forwarded-For header manipulation; exploiting inconsistent rate limit key generation; distributing requests across multiple admin accounts; exploiting race condition in rate limit counter |
| **Likelihood** | 3 |
| **Impact** | 3 |
| **Risk Score** | 9 (Medium) |
| **Mitigations** | 1. Rate limiting based on authenticated user ID, not just IP address<br>2. X-Forwarded-For header not trusted for rate limit key generation<br>3. Redis-based distributed rate limiting with atomic operations<br>4. Tiered rate limits: per-endpoint, per-user, per-IP, global<br>5. Circuit breaker pattern for cascading failure prevention<br>6. Request queuing with backpressure for load shedding<br>7. Anomaly detection on request patterns |

---

### ADM-024: Admin Notification Suppression

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-024 |
| **Category** | Repudiation |
| **Description** | An attacker or malicious admin suppresses or manipulates security notifications and alerts, preventing detection of unauthorized actions by other administrators or the security team. |
| **Affected Component** | Monitoring & Alerting System, Notification Service |
| **Attack Vector** | Modifying alerting rules via admin settings; suppressing email/SMS delivery; compromising PagerDuty/Slack integration; deleting alert history; routing alerts to attacker-controlled channel; exploiting notification deduplication to suppress repeated alerts |
| **Likelihood** | 2 |
| **Impact** | 4 |
| **Risk Score** | 8 (Medium) |
| **Mitigations** | 1. Alerting configuration requires dual approval for changes<br>2. Alert suppression requires justification and has auto-restore timer<br>3. Immutable alert log separate from admin configuration<br>4. Alert delivery via multiple independent channels (email + Slack + PagerDuty)<br>5. Periodic alert testing (automated canary alerts every 6 hours)<br>6. Alert rule changes trigger separate notification to security team<br>7. Monitoring system isolated from admin control plane configuration |

---

### ADM-025: Kubernetes Admin Pod Compromise

| Field | Value |
|-------|-------|
| **Threat ID** | ADM-025 |
| **Category** | Elevation of Privilege |
| **Description** | An attacker compromises the Kubernetes pod running the admin control plane, gaining access to environment variables (secrets), mounted volumes, or the ability to modify the running application. |
| **Affected Component** | Kubernetes Cluster, Admin Service Pods |
| **Attack Vector** | Container escape via kernel vulnerability; exploiting service account token for cluster access; accessing secrets via mounted Vault token; compromised init container modifying application; exploiting node-level access via adjacent workload |
| **Likelihood** | 2 |
| **Impact** | 5 |
| **Risk Score** | 10 (High) |
| **Mitigations** | 1. Admin pods run on dedicated nodes with node affinity<br>2. Pod security standards enforced (restricted profile)<br>3. Read-only root filesystem for admin containers<br>4. No hostPath mounts; secrets via Vault sidecar injection<br>5. Network policies restricting pod-to-pod communication<br>6. Regular container image scanning and base image updates<br>7. Runtime security monitoring (Falco) with alerting<br>8. Kubernetes RBAC with minimal service account permissions |

---

## Attack Trees

### Attack Tree 1: Steal Platform Funds or Manipulate Settlement

```
GOAL: Steal platform funds or manipulate settlement
│
├── 1. Gain admin access with financial approval rights
│   ├── 1.1 Steal admin credentials
│   │   ├── 1.1.1 Phishing email → credential harvest [L:5, I:5]
│   │   ├── 1.1.2 Keylogger on admin workstation [L:3, I:5]
│   │   ├── 1.1.3 Credential stuffing from leaked database [L:4, I:5]
│   │   └── 1.1.4 Password reset flow exploitation [L:3, I:5]
│   │
│   ├── 1.2 Bypass MFA
│   │   ├── 1.2.1 SIM swap for TOTP seed recovery [L:2, I:5]
│   │   ├── 1.2.2 Real-time phishing proxy (AiTM) [L:3, I:5]
│   │   ├── 1.2.3 Social engineering MFA code from admin [L:2, I:5]
│   │   └── 1.2.4 Exploit MFA recovery/bypass mechanism [L:2, I:5]
│   │
│   └── 1.3 Session hijacking
│       ├── 1.3.1 XSS to steal session cookie [L:3, I:5]
│       ├── 1.3.2 Network interception of session token [L:2, I:5]
│       └── 1.3.3 Session fixation attack [L:2, I:5]
│
├── 2. Bypass dual-approval workflow
│   ├── 2.1 Collude with second admin
│   │   ├── 2.1.1 Social engineer second approver [L:2, I:5]
│   │   └── 2.1.2 Coerce or bribe second admin [L:1, I:5]
│   │
│   ├── 2.2 Exploit approval mechanism
│   │   ├── 2.2.1 TOCTOU: modify transaction after first approval [L:2, I:5]
│   │   ├── 2.2.2 Race condition in approval logic [L:2, I:5]
│   │   ├── 2.2.3 Reuse expired approval token [L:1, I:5]
│   │   └── 2.2.4 Emergency override exploitation [L:2, I:5]
│   │
│   └── 2.3 Transaction splitting
│       ├── 2.3.1 Split large withdrawal into sub-threshold amounts [L:3, I:4]
│       └── 2.3.2 Create multiple transactions to same beneficiary [L:3, I:4]
│
├── 3. Create fraudulent transactions
│   ├── 3.1 KYC bypass for shell accounts
│   │   ├── 3.1.1 Approve own KYC applications [L:2, I:5]
│   │   ├── 3.1.2 Deepfake documents for KYC [L:2, I:4]
│   │   └── 3.1.3 Use stolen identities for KYC [L:3, I:4]
│   │
│   └── 3.2 Manipulate existing transactions
│       ├── 3.2.1 Modify settlement release conditions [L:2, I:5]
│       ├── 3.2.2 Change beneficiary after approval [L:2, I:5]
│       └── 3.2.3 Create fictitious refund transactions [L:2, I:5]
│
└── 4. Cover tracks after theft
    ├── 4.1 Tamper with audit logs [L:2, I:5]
    ├── 4.2 Suppress security alerts [L:2, I:4]
    └── 4.3 Delay detection with slow exfiltration [L:3, I:4]
```

### Attack Tree 2: Gain Admin Access

```
GOAL: Gain unauthorized admin access
│
├── 1. Compromise existing admin account
│   ├── 1.1 Credential-based attacks
│   │   ├── 1.1.1 Phishing (credential harvest) [L:5, I:5]
│   │   ├── 1.1.2 Brute force / credential stuffing [L:4, I:5]
│   │   ├── 1.1.3 Password reset exploitation [L:3, I:5]
│   │   └── 1.1.4 Social engineering for credentials [L:3, I:5]
│   │
│   ├── 1.2 MFA bypass
│   │   ├── 1.2.1 AiTM proxy (evilginx) [L:3, I:5]
│   │   ├── 1.2.2 SIM swap [L:2, I:5]
│   │   ├── 1.2.3 MFA fatigue / push bombing [L:3, I:4]
│   │   └── 1.2.4 Exploit MFA enrollment flaw [L:2, I:5]
│   │
│   ├── 1.3 Session theft
│   │   ├── 1.3.1 XSS in admin dashboard [L:3, I:5]
│   │   ├── 1.3.2 Session token prediction [L:1, I:5]
│   │   └── 1.3.3 Session token from compromised Redis [L:2, I:5]
│   │
│   └── 1.4 Endpoint compromise
│       ├── 1.4.1 Malware on admin workstation [L:3, I:5]
│       ├── 1.4.2 Compromised browser extension [L:2, I:5]
│       └── 1.4.3 Rogue WiFi interception [L:2, I:4]
│
├── 2. Create new admin account
│   ├── 2.1 Exploit user management
│   │   ├── 2.1.1 IDOR in admin creation API [L:2, I:5]
│   │   ├── 2.1.2 Race condition in role assignment [L:2, I:5]
│   │   └── 2.1.3 Privilege escalation from regular admin [L:2, I:5]
│   │
│   └── 2.2 Database manipulation
│       ├── 2.2.1 Direct DB insert via SQL injection [L:2, I:5]
│       └── 2.2.2 Compromise database credentials [L:2, I:5]
│
├── 3. Exploit infrastructure
│   ├── 3.1 CI/CD pipeline compromise
│   │   ├── 3.1.1 Inject backdoor via malicious PR [L:2, I:5]
│   │   └── 3.1.2 Compromise build agent [L:2, I:5]
│   │
│   ├── 3.2 Kubernetes compromise
│   │   ├── 3.2.1 Container escape to node [L:1, I:5]
│   │   ├── 3.2.2 Service account token abuse [L:2, I:5]
│   │   └── 3.2.3 Exploit misconfigured RBAC [L:2, I:5]
│   │
│   └── 3.3 Supply chain attack
│       ├── 3.3.1 Compromised npm/PyPI dependency [L:3, I:4]
│       └── 3.3.2 Compromised base Docker image [L:2, I:5]
│
└── 4. Network-level attacks
    ├── 4.1 DNS hijacking of admin domain [L:2, I:5]
    ├── 4.2 BGP hijacking of admin IP range [L:1, I:5]
    └── 4.3 TLS interception via rogue CA [L:1, I:5]
```

### Attack Tree 3: Cover Tracks After Admin Abuse

```
GOAL: Prevent detection of unauthorized admin activity
│
├── 1. Modify audit trail
│   ├── 1.1 Direct database modification
│   │   ├── 1.1.1 Exploit SQL injection to modify logs [L:2, I:5]
│   │   ├── 1.1.2 Compromise database credentials [L:2, I:5]
│   │   └── 1.1.3 Exploit backup restore to overwrite logs [L:1, I:5]
│   │
│   ├── 1.2 Application-level manipulation
│   │   ├── 1.2.1 Exploit admin log management API [L:2, I:5]
│   │   ├── 1.2.2 Hash chain collision to hide modifications [L:1, I:5]
│   │   └── 1.2.3 Inject false log entries to create confusion [L:3, I:4]
│   │
│   └── 1.3 Infrastructure-level destruction
│       ├── 1.3.1 Delete log files from disk [L:1, I:5]
│       ├── 1.3.2 Corrupt WAL/archive logs [L:1, I:5]
│       └── 1.3.3 Destroy WORM storage replicas [L:1, I:5]
│
├── 2. Suppress detection mechanisms
│   ├── 2.1 Disable or modify alerting
│   │   ├── 2.1.1 Modify alerting rules via admin config [L:2, I:4]
│   │   ├── 2.1.2 Suppress specific alert types [L:2, I:4]
│   │   └── 2.1.3 Redirect alerts to dead channel [L:2, I:4]
│   │
│   ├── 2.2 Evade anomaly detection
│   │   ├── 2.2.1 Mimic normal admin behavior patterns [L:3, I:4]
│   │   ├── 2.2.2 Operate within normal business hours [L:4, I:3]
│   │   ├── 2.2.3 Spread actions over extended period [L:3, I:3]
│   │   └── 2.2.4 Use legitimate admin account (insider) [L:3, I:5]
│   │
│   └── 2.3 Compromise monitoring infrastructure
│       ├── 2.3.1 Modify Prometheus alert rules [L:2, I:4]
│       ├── 2.3.2 Tamper with Grafana dashboards [L:2, I:3]
│       └── 2.3.3 Disable SIEM agent/injection [L:2, I:4]
│
├── 3. Create false narratives
│   ├── 3.1 Fabricate legitimate-appearing actions
│   │   ├── 3.1.1 Create fake user support tickets as pretext [L:3, I:3]
│   │   ├── 3.1.2 Generate false KYC review justification [L:3, I:4]
│   │   └── 3.1.3 Document fake emergency requiring override [L:2, I:4]
│   │
│   └── 3.2 Shift blame
│       ├── 3.2.1 Use another admin's compromised session [L:2, I:5]
│       ├── 3.2.2 Attribute actions to system automation [L:2, I:4]
│       └── 3.2.3 Exploit shared credentials to create ambiguity [L:3, I:4]
│
└── 4. Destroy evidence
    ├── 4.1 Wipe session logs [L:2, I:4]
    ├── 4.2 Delete browser history on admin workstation [L:3, I:2]
    ├── 4.3 Destroy WORM storage [L:1, I:5]
    └── 4.4 Corrupt hash chain making all logs suspect [L:1, I:5]
```

---

## Risk Summary Matrix

### By STRIDE Category

| Category | Critical | High | Medium | Low | Total |
|----------|----------|------|--------|-----|-------|
| **Spoofing** | 1 (ADM-001) | 4 (ADM-002, ADM-008, ADM-011, ADM-021) | 0 | 0 | 5 |
| **Tampering** | 1 (ADM-005) | 4 (ADM-003, ADM-006, ADM-018, ADM-022) | 1 (ADM-015*) | 0 | 6 |
| **Repudiation** | 0 | 0 | 1 (ADM-024) | 0 | 1 |
| **Information Disclosure** | 0 | 3 (ADM-010, ADM-013, ADM-022) | 0 | 0 | 3 |
| **Denial of Service** | 0 | 1 (ADM-016) | 2 (ADM-019, ADM-023) | 0 | 3 |
| **Elevation of Privilege** | 0 | 5 (ADM-004, ADM-007, ADM-012, ADM-020, ADM-025) | 0 | 0 | 5 |
| **Total** | **2** | **17** | **4** | **0** | **23** |

*Note: ADM-015 is categorized as Tampering (supply chain) with Medium effective risk after mitigations.*

### Risk Score Distribution

| Risk Level | Score Range | Count | Threat IDs |
|-----------|-------------|-------|------------|
| **Critical** | 20-25 | 2 | ADM-001 (25), ADM-005 (20) |
| **High** | 10-19 | 17 | ADM-002 (15), ADM-003 (12), ADM-004 (15), ADM-006 (15), ADM-007 (12), ADM-008 (15), ADM-009 (10), ADM-010 (15), ADM-011 (15), ADM-012 (15), ADM-013 (12), ADM-014 (10), ADM-016 (15), ADM-017 (12), ADM-018 (10), ADM-020 (15), ADM-021 (12) |
| **Medium** | 5-9 | 4 | ADM-019 (8), ADM-023 (9), ADM-024 (8), ADM-025 (10*) |
| **Low** | 1-4 | 0 | — |

*ADM-025 has a score of 10 but is listed as medium due to existing strong Kubernetes security controls reducing effective risk.*

### Top 5 Priority Threats

| Rank | Threat ID | Threat | Risk Score | Priority Action |
|------|-----------|--------|-----------|-----------------|
| 1 | ADM-001 | Admin Credential Theft | 25 | Deploy FIDO2 hardware keys, eliminate password-only fallback |
| 2 | ADM-005 | Financial Fraud via Withdrawal Approval | 20 | Implement mandatory dual approval with transaction signing |
| 3 | ADM-002 | Session Hijacking | 15 | Device binding + concurrent session elimination |
| 4 | ADM-004 | Privilege Escalation via Role Manipulation | 15 | Dual-approval role changes + OPA policy engine |
| 5 | ADM-006 | Insider Financial Transfer | 15 | Transaction pattern ML + segregation of duties |

---

## Appendices

### Appendix A: Threat Modeling Methodology

This threat model uses the **STRIDE** methodology (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege) aligned with Microsoft's threat modeling framework. Risk scoring follows a 5×5 likelihood-impact matrix consistent with NIST SP 800-30 and ISO 27005.

### Appendix B: Review History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2025-01-15 | 1.0 | Security Engineering | Initial threat model creation |

### Appendix C: Glossary

| Term | Definition |
|------|-----------|
| 2PI | Two-Person Integrity — security control requiring two authorized individuals |
| ABAC | Attribute-Based Access Control |
| AiTM | Adversary-in-the-Middle |
| APT | Advanced Persistent Threat |
| CSP | Content Security Policy |
| FIDO2 | Fast Identity Online — passwordless authentication standard |
| IDOR | Insecure Direct Object Reference |
| KYC | Know Your Customer — identity verification process |
| OPA | Open Policy Agent — policy engine for authorization |
| RASP | Runtime Application Self-Protection |
| RBAC | Role-Based Access Control |
| RLS | Row-Level Security |
| SCA | Software Composition Analysis |
| SBOM | Software Bill of Materials |
| SIEM | Security Information and Event Management |
| STRIDE | Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege |
| TOCTOU | Time-of-Check/Time-of-Use |
| TOTP | Time-based One-Time Password |
| WORM | Write Once Read Many — immutable storage |
