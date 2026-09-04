# Admin Control Plane Risk Register

**Document Version:** 1.0  
**Classification:** Confidential — Internal Use Only  
**Last Updated:** 2025-01-15  
**Owner:** Chief Information Security Officer (CISO)  
**Review Cycle:** Monthly (operational risks), Quarterly (strategic risks)  

---

## Table of Contents

1. [Risk Assessment Methodology](#risk-assessment-methodology)
2. [Risk Register Table](#risk-register-table)
3. [Risk Heat Map](#risk-heat-map)
4. [Risk Treatment Summary](#risk-treatment-summary)
5. [Appendices](#appendices)

---

## Risk Assessment Methodology

### Scoring System

Risks are assessed using a **5×5 likelihood-impact matrix** aligned with ISO 31000 and NIST SP 800-30 frameworks.

#### Likelihood Scale

| Score | Level | Description | Frequency Approximation |
|-------|-------|-------------|------------------------|
| 1 | Rare | May occur only in exceptional circumstances | < 1 per 5 years |
| 2 | Unlikely | Could occur at some time but not expected | 1 per 2-5 years |
| 3 | Possible | Might occur at some time | 1 per 1-2 years |
| 4 | Likely | Will probably occur in most circumstances | 1-6 per year |
| 5 | Almost Certain | Expected to occur frequently | > 6 per year |

#### Impact Scale

| Score | Level | Financial Impact | Operational Impact | Reputational Impact |
|-------|-------|-----------------|-------------------|---------------------|
| 1 | Negligible | < KES 100,000 | Minor disruption, no SLA breach | No media attention |
| 2 | Minor | KES 100,000 – 1M | Brief service degradation, < 1hr | Local media mention |
| 3 | Moderate | KES 1M – 10M | Service disruption 1-4 hrs, SLA breach | National media coverage |
| 4 | Major | KES 10M – 50M | Extended outage 4-24 hrs, regulatory scrutiny | International media, user exodus |
| 5 | Severe | > KES 50M | Platform-wide outage > 24 hrs, regulatory action | Existential reputational damage |

#### Risk Score Calculation

**Risk Score = Likelihood × Impact**

| Risk Score | Risk Level | Color Code | Action Required |
|-----------|------------|------------|-----------------|
| 1-4 | Low | 🟢 Green | Accept and monitor; review annually |
| 5-9 | Medium | 🟡 Yellow | Mitigate within 90 days; review quarterly |
| 10-15 | High | 🟠 Orange | Priority mitigation within 30 days; review monthly |
| 16-25 | Critical | 🔴 Red | Immediate mitigation within 7 days; review weekly |

### Acceptance Criteria

- **Low risk:** May be accepted by Security Team Lead with documented justification
- **Medium risk:** May be accepted by CISO with documented justification and compensating controls
- **High risk:** Requires CISO + CTO joint acceptance with board notification
- **Critical risk:** Cannot be accepted; must be mitigated to High or below. Board notification required within 24 hours

### Risk Categories

| Category | Code | Description |
|----------|------|-------------|
| Security | SEC | Risks related to confidentiality, integrity, availability of systems and data |
| Operational | OPS | Risks related to business processes, procedures, and operational continuity |
| Compliance | CMP | Risks related to regulatory, legal, and contractual obligations |
| Financial | FIN | Risks related to monetary loss, fraud, or financial misstatement |

---

## Risk Register Table

### RSK-ADM-001: Public Internet Exposure of Admin Panel

| Field | Value |
|-------|-------|
| **Risk ID** | RSK-ADM-001 |
| **Risk Title** | Public Internet Exposure of Admin Panel |
| **Category** | Security |
| **Description** | The admin control plane is accessible from the public internet without network-level access restrictions, significantly increasing the attack surface for credential theft, brute force, and exploitation attacks. Any internet user can reach the admin login page and attempt to authenticate. |
| **Likelihood** | 5 |
| **Impact** | 5 |
| **Risk Score** | 25 (Critical) |
| **Risk Level** | Critical |
| **Current Controls** | WAF with basic rule set; HTTPS enforced; rate limiting on login endpoint |
| **Residual Risk** | 20 (Critical) — Admin panel still reachable from any IP; WAF rules can be bypassed |
| **Treatment Plan** | 1. Deploy admin panel behind VPN with IP allowlist (only office/static IPs)<br>2. Implement network-level authentication (mutual TLS) before reaching application<br>3. Admin subdomain on separate, non-public DNS zone<br>4. Deploy Cloudflare Access or similar zero-trust gateway<br>5. Geographic IP restriction (Kenya + approved countries only) |
| **Owner** | Head of Infrastructure |
| **Status** | Open |
| **Target Date** | 2025-02-15 |

---

### RSK-ADM-002: Single-Factor Admin Authentication

| Field | Value |
|-------|-------|
| **Risk ID** | RSK-ADM-002 |
| **Risk Title** | Single-Factor Admin Authentication |
| **Category** | Security |
| **Description** | Admin accounts authenticate using only a password, without multi-factor authentication. A single compromised password grants full access to the admin control plane, enabling financial fraud, data theft, and platform manipulation. |
| **Likelihood** | 4 |
| **Impact** | 5 |
| **Risk Score** | 20 (Critical) |
| **Risk Level** | Critical |
| **Current Controls** | Password complexity policy (8+ characters); account lockout after 5 failures |
| **Residual Risk** | 20 (Critical) — Password-only auth remains highly vulnerable to credential theft |
| **Treatment Plan** | 1. Deploy TOTP-based MFA for all admin accounts (immediate)<br>2. Migrate to FIDO2/WebAuthn hardware keys (within 60 days)<br>3. Disable password-only login for all admin accounts<br>4. Implement step-up MFA for high-risk operations<br>5. Quarterly MFA enrollment verification |
| **Owner** | CISO |
| **Status** | Open |
| **Target Date** | 2025-02-28 |

---

### RSK-ADM-003: Single-Admin Financial Approval

| Field | Value |
|-------|-------|
| **Risk ID** | RSK-ADM-003 |
| **Risk Title** | Single-Admin Financial Approval |
| **Category** | Financial |
| **Description** | Financial transactions (withdrawals, refunds, settlement verifications) can be approved by a single administrator without requiring a second approver. This enables a single compromised or malicious admin to authorize fraudulent transactions resulting in direct financial loss. |
| **Likelihood** | 4 |
| **Impact** | 5 |
| **Risk Score** | 20 (Critical) |
| **Risk Level** | Critical |
| **Current Controls** | Transaction amount logging; email notification on approval |
| **Residual Risk** | 20 (Critical) — Single approval remains the primary financial risk |
| **Treatment Plan** | 1. Implement mandatory dual approval for ALL financial transactions<br>2. Two-person integrity (2PI) with approvers from different teams<br>3. Transaction signing with hardware tokens for approval<br>4. Cooling-off period for transactions > KES 500,000<br>5. Automated anomaly detection on approval patterns<br>6. Real-time Slack/PagerDuty alerts on every financial approval |
| **Owner** | Head of Finance + CTO |
| **Status** | Open |
| **Target Date** | 2025-02-15 |

---

### RSK-ADM-004: Mutable Audit Logs

| Field | Value |
|-------|-------|
| **Risk ID** | RSK-ADM-004 |
| **Risk Title** | Mutable Audit Logs |
| **Category** | Security |
| **Description** | Audit logs can be modified or deleted by administrators or through application vulnerabilities. This allows malicious actors to cover their tracks after unauthorized actions, undermines forensic investigations, and creates compliance violations. |
| **Likelihood** | 3 |
| **Impact** | 5 |
| **Risk Score** | 15 (High) |
| **Risk Level** | High |
| **Current Controls** | Standard database permissions; basic logging of admin actions |
| **Residual Risk** | 15 (High) — Logs can still be modified at database level |
| **Treatment Plan** | 1. Implement append-only database with no UPDATE/DELETE grants<br>2. Add hash chain integrity to log entries (each entry hashes previous)<br>3. Replicate audit logs to WORM storage (S3 Object Lock)<br>4. Separate audit database credentials from admin service credentials<br>5. Automated hourly hash chain verification<br>6. Tampering detection triggers P0 security alert |
| **Owner** | Head of Platform Engineering |
| **Status** | Open |
| **Target Date** | 2025-03-01 |

---

### RSK-ADM-005: Shared Admin Credentials

| Field | Value |
|-------|-------|
| **Risk ID** | RSK-ADM-005 |
| **Risk Title** | Shared Admin Credentials |
| **Category** | Security |
| **Description** | Multiple administrators share the same login credentials for the admin control plane, making it impossible to attribute actions to specific individuals. This violates the principle of individual accountability and prevents effective audit and investigation. |
| **Likelihood** | 4 |
| **Impact** | 4 |
| **Risk Score** | 16 (Critical) |
| **Risk Level** | Critical |
| **Current Controls** | Verbal agreement not to share credentials; basic action logging |
| **Residual Risk** | 16 (Critical) — Shared credentials remain in use; no technical enforcement |
| **Treatment Plan** | 1. Immediately assign individual admin accounts to all administrators<br>2. Enforce unique credentials policy with technical controls (no shared passwords)<br>3. Implement individual MFA tokens per account<br>4. Detect and alert on concurrent sessions from same account<br>5. Quarterly access review with individual account certification<br>6. Disable shared/generic accounts within 14 days |
| **Owner** | CISO + HR |
| **Status** | Open |
| **Target Date** | 2025-02-01 |

---

### RSK-ADM-006: No IP Restrictions on Admin Access

| Field | Value |
|-------|-------|
| **Risk ID** | RSK-ADM-006 |
| **Risk Title** | No IP Restrictions on Admin Access |
| **Category** | Security |
| **Description** | The admin control plane accepts connections from any IP address globally. There are no geographic or network-level restrictions, allowing attackers from any location to attempt authentication and increasing exposure to credential-based attacks. |
| **Likelihood** | 4 |
| **Impact** | 4 |
| **Risk Score** | 16 (Critical) |
| **Risk Level** | Critical |
| **Current Controls** | WAF with basic geo-blocking for known attack countries |
| **Residual Risk** | 12 (High) — WAF geo-blocking is easily bypassed via VPN/proxy |
| **Treatment Plan** | 1. Implement IP allowlist at load balancer level (office IPs, VPN egress IPs)<br>2. Deploy zero-trust network access (ZTNA) solution<br>3. Geographic restriction: Kenya + explicitly whitelisted countries only<br>4. Alert on admin access from new/unrecognized IP addresses<br>5. Block Tor exit nodes and known VPN/proxy IP ranges<br>6. Require VPN connection for all admin access within 30 days |
| **Owner** | Head of Infrastructure |
| **Status** | Open |
| **Target Date** | 2025-02-28 |

---

### RSK-ADM-007: Long-Lived Admin Sessions

| Field | Value |
|-------|-------|
| **Risk ID** | RSK-ADM-007 |
| **Risk Title** | Long-Lived Admin Sessions |
| **Category** | Security |
| **Description** | Admin sessions remain active for extended periods (24+ hours) without re-authentication requirements. This increases the window of opportunity for session hijacking and unauthorized access if an admin workstation is left unattended or compromised. |
| **Likelihood** | 4 |
| **Impact** | 4 |
| **Risk Score** | 16 (Critical) |
| **Risk Level** | Critical |
| **Current Controls** | Browser session persistence; no explicit timeout configuration |
| **Residual Risk** | 16 (Critical) — No session timeout enforced |
| **Treatment Plan** | 1. Implement 15-minute idle session timeout with re-authentication<br>2. Enforce 4-hour absolute session maximum (regardless of activity)<br>3. Session token rotation every 15 minutes<br>4. Mandatory re-authentication for all financial operations (step-up auth)<br>5. Visual session timer warning at 5-minute and 2-minute marks<br>6. Auto-logout with session cleanup on timeout |
| **Owner** | Head of Platform Engineering |
| **Status** | Open |
| **Target Date** | 2025-02-15 |

---

### RSK-ADM-008: No Session Anomaly Detection

| Field | Value |
|-------|-------|
| **Risk ID** | RSK-ADM-008 |
| **Risk Title** | No Session Anomaly Detection |
| **Category** | Security |
| **Description** | The system does not detect or respond to anomalous session behavior such as IP address changes mid-session, impossible travel (login from distant locations in short timeframes), unusual access patterns, or concurrent sessions. This allows attackers to maintain compromised sessions without detection. |
| **Likelihood** | 3 |
| **Impact** | 4 |
| **Risk Score** | 12 (High) |
| **Risk Level** | High |
| **Current Controls** | Basic session logging |
| **Residual Risk** | 12 (High) — No anomaly detection or automated response |
| **Treatment Plan** | 1. Implement IP consistency check during session (flag changes)<br>2. Impossible travel detection (login from two distant locations)<br>3. Behavioral anomaly detection using ML on admin access patterns<br>4. Automated session termination on high-confidence anomalies<br>5. Real-time alerting on all session anomalies<br>6. Device fingerprinting for session validation<br>7. Concurrent session detection and prevention |
| **Owner** | Head of Security Engineering |
| **Status** | Open |
| **Target Date** | 2025-03-15 |

---

### RSK-ADM-009: Broad Admin Permissions

| Field | Value |
|-------|-------|
| **Risk ID** | RSK-ADM-009 |
| **Risk Title** | Broad Admin Permissions |
| **Category** | Security |
| **Description** | Admin roles have overly broad permissions that exceed the minimum required for their job functions. For example, KYC reviewers can access financial data, or finance admins can modify system configurations. This violates the principle of least privilege and increases the blast radius of any account compromise. |
| **Likelihood** | 4 |
| **Impact** | 4 |
| **Risk Score** | 16 (Critical) |
| **Risk Level** | Critical |
| **Current Controls** | Basic role assignment (admin/super-admin); manual permission review |
| **Residual Risk** | 12 (High) — Two-tier role model provides insufficient granularity |
| **Treatment Plan** | 1. Design and implement granular RBAC with role hierarchy:<br>   - KYC Reviewer, Finance Officer, Support Agent, Compliance Officer, Super Admin<br>2. Implement ABAC for context-aware authorization<br>3. Map each role to minimum required permissions (principle of least privilege)<br>4. Implement permission scoping: financial admins cannot access KYC docs and vice versa<br>5. Deploy Open Policy Agent (OPA) for centralized policy management<br>6. Quarterly access reviews with automated permission audit<br>7. Just-in-time (JIT) access for elevated privileges |
| **Owner** | CTO + CISO |
| **Status** | Open |
| **Target Date** | 2025-03-31 |

---

### RSK-ADM-010: No Emergency Controls

| Field | Value |
|-------|-------|
| **Risk ID** | RSK-ADM-010 |
| **Risk Title** | No Emergency Controls |
| **Category** | Operational |
| **Description** | The platform lacks emergency controls such as withdrawal freeze, platform lockdown, or session revocation capabilities. In the event of a security incident, there is no rapid-response mechanism to stop ongoing financial loss or prevent further unauthorized access. |
| **Likelihood** | 3 |
| **Impact** | 5 |
| **Risk Score** | 15 (High) |
| **Risk Level** | High |
| **Current Controls** | Manual database intervention (slow, error-prone) |
| **Residual Risk** | 15 (High) — No automated emergency response capability |
| **Treatment Plan** | 1. Implement "kill switch" for withdrawal processing (immediate freeze)<br>2. Global session revocation capability (invalidate all admin sessions)<br>3. Account lockdown mode (prevent all financial transactions)<br>4. Platform-wide incident mode (restrict to read-only operations)<br>5. Emergency control activation requires dual super admin approval<br>6. Auto-expiry on emergency controls (max 4 hours, then requires re-approval)<br>7. Emergency control playbook with step-by-step procedures<br>8. Monthly emergency control testing (fire drill) |
| **Owner** | CTO |
| **Status** | Open |
| **Target Date** | 2025-03-01 |

---

### RSK-ADM-011: Unencrypted KYC Documents at Rest

| Field | Value |
|-------|-------|
| **Risk ID** | RSK-ADM-011 |
| **Risk Title** | Unencrypted KYC Documents at Rest |
| **Category** | Compliance |
| **Description** | KYC documents (national ID scans, passport photos, selfie verifications) are stored without encryption at rest. If an attacker gains access to the storage layer (S3 bucket, EBS volume), they can directly read sensitive personal identification documents, violating data protection regulations (Kenya DPA 2019, GDPR). |
| **Likelihood** | 3 |
| **Impact** | 5 |
| **Risk Score** | 15 (High) |
| **Risk Level** | High |
| **Current Controls** | S3 bucket policies restricting access; server-side request logging |
| **Residual Risk** | 10 (High) — Documents still unencrypted at storage layer |
| **Treatment Plan** | 1. Enable S3 SSE-KMS encryption with customer-managed CMK for all KYC buckets<br>2. Implement envelope encryption for document access (decrypt on read only)<br>3. Separate KMS keys per document type with access auditing<br>4. S3 bucket policy: deny unencrypted uploads (aws:SecureTransport)<br>5. Key rotation policy: annual CMK rotation<br>6. Document access logging with CloudTrail + S3 access logs<br>7. Automated compliance check: alert if unencrypted documents detected |
| **Owner** | Head of Platform Engineering + DPO |
| **Status** | Open |
| **Target Date** | 2025-02-28 |

---

### RSK-ADM-012: API Keys in Source Code

| Field | Value |
|-------|-------|
| **Risk ID** | RSK-ADM-012 |
| **Risk Title** | API Keys in Source Code |
| **Category** | Security |
| **Description** | API keys, database credentials, and other secrets are hardcoded in source code or configuration files within the repository. This exposes secrets to anyone with read access to the codebase, including contractors, former employees, and anyone who gains access to the repository (public or private). |
| **Likelihood** | 4 |
| **Impact** | 4 |
| **Risk Score** | 16 (Critical) |
| **Risk Level** | Critical |
| **Current Controls** | Private GitHub repositories; code review process (manual) |
| **Residual Risk** | 12 (High) — Secrets still present in codebase; manual review misses some |
| **Treatment Plan** | 1. Migrate all secrets to HashiCorp Vault immediately<br>2. Remove all secrets from source code (git history rewriting if needed)<br>3. Implement pre-commit hooks (gitleaks) to prevent future secret commits<br>4. Enable GitHub secret scanning on all repositories<br>5. Runtime secret injection via Vault sidecar (no env vars in CI/CD)<br>6. Automated secret rotation every 30 days<br>7. Developer training on secret management best practices<br>8. BFG Repo-Cleaner to purge leaked secrets from git history |
| **Owner** | Head of DevOps |
| **Status** | Open |
| **Target Date** | 2025-02-15 |

---

### RSK-ADM-013: No Admin Action Alerting

| Field | Value |
|-------|-------|
| **Risk ID** | RSK-ADM-013 |
| **Risk Title** | No Admin Action Alerting |
| **Category** | Operational |
| **Description** | There is no real-time alerting system for admin actions. Critical operations such as financial approvals, KYC decisions, role changes, and configuration modifications are not monitored in real-time, allowing unauthorized or suspicious actions to go unnoticed for extended periods. |
| **Likelihood** | 4 |
| **Impact** | 4 |
| **Risk Score** | 16 (Critical) |
| **Risk Level** | Critical |
| **Current Controls** | Daily log review (manual); weekly admin action report |
| **Residual Risk** | 16 (Critical) — Manual review cannot detect real-time threats |
| **Treatment Plan** | 1. Implement real-time Slack notifications for all admin actions<br>2. PagerDuty alerts for critical operations (financial approvals, role changes)<br>3. Anomaly-based alerting on admin behavior patterns<br>4. Threshold alerts (e.g., > 5 approvals/hour, > KES 1M approved in a day)<br>5. Off-hours alerting (any admin action outside 8am-6pm EAT)<br>6. New IP/device alerting for admin login<br>7. Alerting on failed admin actions (potential reconnaissance)<br>8. SIEM integration with correlation rules |
| **Owner** | Head of Security Engineering |
| **Status** | Open |
| **Target Date** | 2025-02-28 |

---

### RSK-ADM-014: Missing Dual Approval for High-Value Operations

| Field | Value |
|-------|-------|
| **Risk ID** | RSK-ADM-014 |
| **Risk Title** | Missing Dual Approval for High-Value Operations |
| **Category** | Financial |
| **Description** | High-value operations (withdrawals > KES 500,000, bulk user operations, system configuration changes) do not require dual approval. A single admin can execute these operations without oversight, creating risk of fraud, errors, or unauthorized changes. |
| **Likelihood** | 3 |
| **Impact** | 5 |
| **Risk Score** | 15 (High) |
| **Risk Level** | High |
| **Current Controls** | Manual email confirmation for high-value transactions |
| **Residual Risk** | 12 (High) — Email confirmation is easily forged or ignored |
| **Treatment Plan** | 1. Dual approval required for ALL withdrawals regardless of amount<br>2. Triple approval for transactions > KES 5,000,000<br>3. Dual approval for system configuration changes<br>4. Dual approval for bulk user operations (> 10 users)<br>5. Dual approval for admin role assignment changes<br>6. Cooling-off period of 30 minutes for high-value approvals<br>7. Transaction signing with hardware tokens for second approver<br>8. Cumulative threshold tracking (multiple sub-threshold transactions to same beneficiary) |
| **Owner** | Head of Finance + CISO |
| **Status** | Open |
| **Target Date** | 2025-03-15 |

---

### RSK-ADM-015: No Incident Response Playbook

| Field | Value |
|-------|-------|
| **Risk ID** | RSK-ADM-015 |
| **Risk Title** | No Incident Response Playbook |
| **Category** | Operational |
| **Description** | There is no documented, tested incident response playbook specific to admin control plane security incidents. In the event of an admin account compromise or financial fraud, the response will be ad hoc, leading to delayed containment, evidence destruction, and increased financial and reputational damage. |
| **Likelihood** | 3 |
| **Impact** | 4 |
| **Risk Score** | 12 (High) |
| **Risk Level** | High |
| **Current Controls** | General incident response procedure (not admin-specific); on-call rotation |
| **Residual Risk** | 12 (High) — Generic IR process inadequate for admin-specific scenarios |
| **Treatment Plan** | 1. Develop admin-specific incident response playbook (7 scenario-based procedures)<br>2. Define severity classification for admin security incidents<br>3. Establish emergency contact list and escalation paths<br>4. Conduct tabletop exercise quarterly (admin compromise scenario)<br>5. Integrate playbook with PagerDuty/Slack for guided response<br>6. Post-incident review template with mandatory documentation<br>7. Annual full-scale incident simulation exercise<br>8. Train all admins on incident response procedures |
| **Owner** | CISO |
| **Status** | Open |
| **Target Date** | 2025-03-31 |

---

### RSK-ADM-016: Inadequate Admin Offboarding Process

| Field | Value |
|-------|-------|
| **Risk ID** | RSK-ADM-016 |
| **Risk Title** | Inadequate Admin Offboarding Process |
| **Category** | Operational |
| **Description** | When administrators leave the organization or change roles, their access is not consistently or promptly revoked. Former employees may retain access to the admin control plane, enabling unauthorized actions, data theft, or sabotage. |
| **Likelihood** | 3 |
| **Impact** | 4 |
| **Risk Score** | 12 (High) |
| **Risk Level** | High |
| **Current Controls** | Manual HR notification to IT for account deactivation; 24-hour target |
| **Residual Risk** | 9 (Medium) — Manual process with inconsistent execution; delays of days reported |
| **Treatment Plan** | 1. Automated account deactivation triggered by HR system (Workday integration)<br>2. Admin offboarding checklist with security sign-off<br>3. Immediate session termination on account deactivation<br>4. Revocation of all API keys and tokens associated with departing admin<br>5. Removal from all approval workflows and distribution lists<br>6. Return and verification of hardware security keys<br>7. Post-offboarding audit: verify no active sessions or credentials after 4 hours<br>8. Access revocation SLA: 1 hour for involuntary departure, 4 hours for voluntary |
| **Owner** | Head of HR + CISO |
| **Status** | Open |
| **Target Date** | 2025-03-15 |

---

### RSK-ADM-017: No Admin Activity Forensic Capability

| Field | Value |
|-------|-------|
| **Risk ID** | RSK-ADM-017 |
| **Risk Title** | No Admin Activity Forensic Capability |
| **Category** | Compliance |
| **Description** | The platform lacks the ability to perform forensic analysis on admin activity. There is no session recording, no detailed request logging, and no ability to reconstruct the sequence of admin actions for investigation. This hampers incident response and regulatory compliance. |
| **Likelihood** | 3 |
| **Impact** | 4 |
| **Risk Score** | 12 (High) |
| **Risk Level** | High |
| **Current Controls** | Basic admin action logging (action type, timestamp, user); no request body logging |
| **Residual Risk** | 12 (High) — Insufficient detail for forensic reconstruction |
| **Treatment Plan** | 1. Implement detailed request logging (full API request/response for admin actions)<br>2. Session recording for admin dashboard (screen recording with consent)<br>3. Structured audit log format with full context (IP, device, action, before/after state)<br>4. Long-term log retention (1 year hot, 7 years cold archive)<br>5. Log export capability for forensic tools (STIX format)<br>6. Automated anomaly timeline generation for investigations<br>7. Evidence preservation procedures (chain of custody) |
| **Owner** | Head of Security Engineering + DPO |
| **Status** | Open |
| **Target Date** | 2025-04-30 |

---

### RSK-ADM-018: Insufficient Dependency Security Monitoring

| Field | Value |
|-------|-------|
| **Risk ID** | RSK-ADM-018 |
| **Risk Title** | Insufficient Dependency Security Monitoring |
| **Category** | Security |
| **Description** | The admin control plane's dependencies (npm packages, Python libraries, Docker base images) are not continuously monitored for known vulnerabilities or supply chain attacks. Vulnerable or compromised dependencies may introduce security flaws or backdoors into the admin application. |
| **Likelihood** | 3 |
| **Impact** | 4 |
| **Risk Score** | 12 (High) |
| **Risk Level** | High |
| **Current Controls** | Manual dependency updates; ad-hoc vulnerability scanning |
| **Residual Risk** | 9 (Medium) — Manual process leaves gaps; no continuous monitoring |
| **Treatment Plan** | 1. Deploy Snyk/Dependabot for automated dependency scanning<br>2. Enable GitHub Dependabot alerts and auto-PRs for critical vulnerabilities<br>3. Implement private npm/PyPI registry with allowlist (Artifactory)<br>4. Dependency pinning with integrity hashes (lockfiles)<br>5. SBOM generation for every release<br>6. Container image scanning (Trivy) in CI/CD pipeline<br>7. Block deployment if critical vulnerabilities detected<br>8. Weekly dependency review meeting for admin service |
| **Owner** | Head of DevOps + Security Engineering |
| **Status** | Open |
| **Target Date** | 2025-03-15 |

---

### RSK-ADM-019: No Regular Penetration Testing

| Field | Value |
|-------|-------|
| **Risk ID** | RSK-ADM-019 |
| **Risk Title** | No Regular Penetration Testing |
| **Category** | Compliance |
| **Description** | The admin control plane has not undergone formal penetration testing. Unknown vulnerabilities in the application, infrastructure, or business logic may exist and could be exploited by attackers before they are discovered and patched. |
| **Likelihood** | 3 |
| **Impact** | 4 |
| **Risk Score** | 12 (High) |
| **Risk Level** | High |
| **Current Controls** | Automated vulnerability scanning (OWASP ZAP) in CI/CD; code review |
| **Residual Risk** | 9 (Medium) — Automated scanning misses business logic and complex vulnerabilities |
| **Treatment Plan** | 1. Engage third-party penetration testing firm for annual comprehensive test<br>2. Scope must include: admin authentication, authorization, financial workflows, KYC review process<br>3. Quarterly internal red team exercises focused on admin control plane<br>4. Bug bounty program with admin-specific scope<br>5. Remediation SLA: Critical findings patched within 7 days, High within 30 days<br>6. Re-testing after remediation to verify fixes<br>7. Findings tracked in risk register and reported to board |
| **Owner** | CISO |
| **Status** | Open |
| **Target Date** | 2025-04-30 |

---

### RSK-ADM-020: Inadequate Key Management

| Field | Value |
|-------|-------|
| **Risk ID** | RSK-ADM-020 |
| **Risk Title** | Inadequate Key Management |
| **Category** | Security |
| **Description** | Encryption keys used for admin data protection (database encryption, document encryption, JWT signing) are not properly managed. Keys may be stored insecurely, lack rotation policies, or be accessible to too many individuals, increasing the risk of key compromise. |
| **Likelihood** | 3 |
| **Impact** | 4 |
| **Risk Score** | 12 (High) |
| **Risk Level** | High |
| **Current Controls** | AWS KMS for some encryption keys; manual key rotation |
| **Residual Risk** | 8 (Medium) — Some keys still managed manually; inconsistent rotation |
| **Treatment Plan** | 1. Migrate all encryption keys to HashiCorp Vault with auto-unsealing<br>2. Implement automated key rotation policies (90 days for data keys, annually for master keys)<br>3. Separate keys per environment (dev/staging/production)<br>4. Key access auditing with alerting on unauthorized access attempts<br>5. Hardware Security Module (HSM) for master key protection<br>6. Cryptographic key backup with split knowledge (dual control for key recovery)<br>7. Emergency key rotation procedure documented and tested |
| **Owner** | Head of Infrastructure |
| **Status** | Open |
| **Target Date** | 2025-03-31 |

---

## Risk Heat Map

```
IMPACT →
         1           2           3           4           5
       Negligible    Minor      Moderate     Major       Severe
    ┌───────────┬───────────┬───────────┬───────────┬───────────┐
 5  │           │           │           │ RSK-004   │ RSK-001   │
    │           │           │           │ RSK-010   │ RSK-002   │
    │           │           │           │ RSK-011   │ RSK-003   │
    │           │           │           │ RSK-014   │           │
    ├───────────┼───────────┼───────────┼───────────┼───────────┤
 4  │           │           │           │ RSK-005   │           │
    │           │           │           │ RSK-006   │           │
    │           │           │           │ RSK-007   │           │
L   │           │           │           │ RSK-009   │           │
I   │           │           │           │ RSK-012   │           │
K   │           │           │           │ RSK-013   │           │
E   │           │           │           │ RSK-015   │           │
L   │           │           │           │ RSK-016   │           │
I   │           │           │           │ RSK-017   │           │
H   │           │           │           │ RSK-018   │           │
O   │           │           │           │ RSK-019   │           │
O   │           │           │           │ RSK-020   │           │
D   ├───────────┼───────────┼───────────┼───────────┼───────────┤
 ↓  │           │           │           │ RSK-008   │           │
 3  │           │           │           │           │           │
    ├───────────┼───────────┼───────────┼───────────┼───────────┤
 2  │           │           │           │           │           │
    ├───────────┼───────────┼───────────┼───────────┼───────────┤
 1  │           │           │           │           │           │
    └───────────┴───────────┴───────────┴───────────┴───────────┘

    Legend:
    ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐
    │ 1-4       │ │ 5-9       │ │ 10-15     │ │ 16-25     │
    │   Low     │ │  Medium   │ │   High    │ │ Critical  │
    │   🟢      │ │   🟡      │ │   🟠      │ │   🔴      │
    └───────────┘ └───────────┘ └───────────┘ └───────────┘
```

### Risk Distribution Summary

| Risk Level | Count | Percentage | Risk IDs |
|-----------|-------|-----------|----------|
| **Critical** (16-25) | 7 | 35% | RSK-001, RSK-002, RSK-003, RSK-005, RSK-006, RSK-007, RSK-009, RSK-012, RSK-013 |
| **High** (10-15) | 11 | 55% | RSK-004, RSK-008, RSK-010, RSK-011, RSK-014, RSK-015, RSK-016, RSK-017, RSK-018, RSK-019, RSK-020 |
| **Medium** (5-9) | 0 | 0% | — |
| **Low** (1-4) | 0 | 0% | — |

### Category Distribution

| Category | Count | Critical | High | Medium | Low |
|----------|-------|----------|------|--------|-----|
| **Security** | 9 | 5 | 4 | 0 | 0 |
| **Operational** | 4 | 1 | 3 | 0 | 0 |
| **Compliance** | 3 | 0 | 3 | 0 | 0 |
| **Financial** | 2 | 1 | 1 | 0 | 0 |
| **Total** | 18 | 7 | 11 | 0 | 0 |

---

## Risk Treatment Summary

### Priority Treatment Plan (Critical Risks — 30-Day Target)

| Priority | Risk ID | Treatment | Estimated Effort | Owner |
|----------|---------|-----------|-----------------|-------|
| P0 | RSK-001 | Deploy VPN + IP allowlist for admin access | 2 weeks | Infra |
| P0 | RSK-002 | Deploy MFA for all admin accounts (TOTP → FIDO2) | 3 weeks | Security |
| P0 | RSK-003 | Implement dual approval for financial transactions | 4 weeks | Platform |
| P0 | RSK-005 | Eliminate shared admin credentials | 1 week | Security + HR |
| P0 | RSK-012 | Migrate secrets to Vault; remove from codebase | 2 weeks | DevOps |
| P1 | RSK-006 | Deploy ZTNA / IP restrictions | 3 weeks | Infra |
| P1 | RSK-007 | Implement session timeouts | 1 week | Platform |
| P1 | RSK-009 | Implement granular RBAC | 6 weeks | Platform + Security |
| P1 | RSK-013 | Implement real-time admin action alerting | 3 weeks | Security |

### Treatment Strategy Distribution

| Strategy | Count | Risk IDs |
|----------|-------|----------|
| **Mitigate** | 18 | All (RSK-001 through RSK-020) |
| **Accept** | 0 | — |
| **Transfer** | 0 | — |
| **Avoid** | 0 | — |

---

## Appendices

### Appendix A: Risk Register Review History

| Date | Reviewer | Changes |
|------|----------|---------|
| 2025-01-15 | Security Engineering Team | Initial risk register creation |

### Appendix B: Risk Ownership Matrix

| Owner | Risk IDs |
|-------|----------|
| CISO | RSK-002, RSK-005, RSK-013, RSK-015 |
| CTO | RSK-003, RSK-010 |
| Head of Infrastructure | RSK-001, RSK-006, RSK-020 |
| Head of Platform Engineering | RSK-004, RSK-007, RSK-011 |
| Head of Security Engineering | RSK-008, RSK-017 |
| Head of Finance + CISO | RSK-014 |
| Head of DevOps | RSK-012, RSK-018 |
| Head of HR + CISO | RSK-016 |
| CISO | RSK-019 |

### Appendix C: Regulatory Mapping

| Risk ID | Kenya DPA 2019 | CBK Guidelines | GDPR (if applicable) |
|--------|---------------|---------------|----------------------|
| RSK-001 | Art. 25 (Security of Processing) | — | Art. 32 |
| RSK-004 | Art. 25, 29 | — | Art. 5(2), 32 |
| RSK-011 | Art. 25, 26 | — | Art. 32 |
| RSK-015 | Art. 25 | — | Art. 33, 34 |
| RSK-017 | Art. 25, 29 | — | Art. 5(2), 30 |
