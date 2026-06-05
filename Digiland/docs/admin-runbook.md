# Admin Security Operational Runbooks

**Document Version:** 1.0  
**Classification:** Internal — Authorized Personnel Only  
**Last Updated:** 2025-01-15  
**Owner:** Security Operations Team  
**Review Cycle:** Monthly (operational), Quarterly (procedures)  

---

## Table of Contents

1. [Admin Onboarding — Security Setup Checklist](#1-admin-onboarding--security-setup-checklist)
2. [Admin Offboarding — Access Revocation Checklist](#2-admin-offboarding--access-revocation-checklist)
3. [Daily Admin Security Review](#3-daily-admin-security-review)
4. [Weekly Admin Audit Review](#4-weekly-admin-audit-review)
5. [Monthly Security Assessment](#5-monthly-security-assessment)
6. [Emergency Withdrawal Freeze Procedure](#6-emergency-withdrawal-freeze-procedure)
7. [Session Revocation Procedure](#7-session-revocation-procedure)
8. [Incident Mode Activation Procedure](#8-incident-mode-activation-procedure)

---

## 1. Admin Onboarding — Security Setup Checklist

**Purpose:** Ensure every new administrator is provisioned with secure access following the principle of least privilege.  
**Owner:** Security Team + HR  
**Estimated Time:** 2-4 hours  
**Approval Required:** Super Admin + CISO sign-off

### Prerequisites

- [ ] HR has completed background check and received clearance
- [ ] Manager has submitted admin access request with role justification
- [ ] CISO has approved the access request
- [ ] New admin has signed the Admin Access Agreement and NDA
- [ ] New admin has completed security awareness training

### Step-by-Step Procedure

#### Phase 1: Identity Verification (30 minutes)

| # | Task | Details | Verified |
|---|------|---------|----------|
| 1.1 | Verify identity in person | Government-issued ID verification at office | ☐ |
| 1.2 | Collect official email | Corporate email on `@digiland.co.ke` domain | ☐ |
| 1.3 | Collect phone number | For MFA and emergency contact | ☐ |
| 1.4 | Record device information | Workstation OS, browser, hardware key serial number | ☐ |
| 1.5 | Photograph for admin record | Stored in HR system, not in admin platform | ☐ |

#### Phase 2: Account Creation (30 minutes)

| # | Task | Details | Verified |
|---|------|---------|----------|
| 2.1 | Create admin account | Super Admin creates account with temporary password | ☐ |
| 2.2 | Assign minimal role | Start with read-only; escalate after probation period | ☐ |
| 2.3 | Set role scope | Limit to specific organizational unit / function | ☐ |
| 2.4 | Configure session policies | 15-min idle timeout, 4-hour absolute timeout | ☐ |
| 2.5 | Register device fingerprint | First login from designated workstation only | ☐ |
| 2.6 | Record account in admin registry | Document account ID, role, creation date, approver | ☐ |

#### Phase 3: MFA Enrollment (30 minutes)

| # | Task | Details | Verified |
|---|------|---------|----------|
| 3.1 | Issue hardware security key | YubiKey 5 NFC or equivalent; record serial number | ☐ |
| 3.2 | Register FIDO2/WebAuthn credential | On designated admin workstation | ☐ |
| 3.3 | Enroll TOTP backup | Scan QR code in authenticator app on admin phone | ☐ |
| 3.4 | Store recovery procedure | Recovery requires CISO approval; no backup codes | ☐ |
| 3.5 | Verify MFA works | Test both FIDO2 and TOTP login | ☐ |
| 3.6 | Document MFA method | Record which MFA method(s) enrolled | ☐ |

#### Phase 4: Network Access (20 minutes)

| # | Task | Details | Verified |
|---|------|---------|----------|
| 4.1 | Provision VPN access | Issue VPN client certificate; register device | ☐ |
| 4.2 | Add IP to allowlist | Office IP or static VPN IP for admin access | ☐ |
| 4.3 | Verify VPN connectivity | Test connection to admin control plane via VPN | ☐ |
| 4.4 | Configure DNS resolution | Admin subdomain resolvable from VPN only | ☐ |

#### Phase 5: Workstation Security (20 minutes)

| # | Task | Details | Verified |
|---|------|---------|----------|
| 5.1 | Verify endpoint protection | CrowdStrike / SentinelOne installed and active | ☐ |
| 5.2 | Verify OS patches | All critical patches applied, auto-update enabled | ☐ |
| 5.3 | Verify browser version | Chrome/Firefox latest stable; no unsupported versions | ☐ |
| 5.4 | Install browser extensions | Password manager only; no other extensions allowed | ☐ |
| 5.5 | Configure screen lock | Auto-lock after 5 minutes of inactivity | ☐ |
| 5.6 | Verify full-disk encryption | FileVault / BitLocker enabled and active | ☐ |

#### Phase 6: Authorization Configuration (20 minutes)

| # | Task | Details | Verified |
|---|------|---------|----------|
| 6.1 | Assign RBAC role | Per approved access request; verify least privilege | ☐ |
| 6.2 | Configure ABAC attributes | Organizational unit, job function, approval limits | ☐ |
| 6.3 | Set financial approval limits | Per role: max amount, requires dual/triple approval | ☐ |
| 6.4 | Configure approval workflow | Add to appropriate approval queues | ☐ |
| 6.5 | Verify OPA policy | Confirm authorization policy applies correctly | ☐ |

#### Phase 7: Verification & Documentation (30 minutes)

| # | Task | Details | Verified |
|---|------|---------|----------|
| 7.1 | Test full login flow | Password → MFA → dashboard access | ☐ |
| 7.2 | Test authorized actions | Verify can perform role-appropriate actions | ☐ |
| 7.3 | Test unauthorized actions | Verify cannot perform actions outside role scope | ☐ |
| 7.4 | Verify audit logging | Perform actions and confirm they appear in audit log | ☐ |
| 7.5 | Verify alert generation | Login from new device should trigger alert | ☐ |
| 7.6 | Document in admin registry | Complete all fields in admin account registry | ☐ |
| 7.7 | Set probation review | Schedule 30-day review for role escalation decision | ☐ |

### Sign-Off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| New Admin | | | |
| Super Admin (provisioner) | | | |
| CISO (approver) | | | |
| HR Representative | | | |

---

## 2. Admin Offboarding — Access Revocation Checklist

**Purpose:** Ensure complete and timely revocation of all admin access when an administrator leaves the organization or changes roles.  
**Owner:** HR + Security Team  
**SLA:** 1 hour (involuntary departure) / 4 hours (voluntary departure)  
**Approval Required:** HR notification triggers the process

### Immediate Actions (Involuntary Departure — Within 1 Hour)

| # | Task | Details | Completed |
|---|------|---------|-----------|
| 1.1 | Suspend admin account | `Admin Panel → User Management → [admin] → Suspend` | ☐ |
| 1.2 | Revoke all active sessions | `Emergency Panel → Revoke Sessions → [admin]` | ☐ |
| 1.3 | Disable VPN access | Revoke VPN client certificate | ☐ |
| 1.4 | Remove IP from allowlist | Remove admin's IP from admin access allowlist | ☐ |
| 1.5 | Disable email account | Prevent login; preserve mailbox for evidence | ☐ |
| 1.6 | Revoke Slack access | Deactivate from all channels including admin channels | ☐ |
| 1.7 | Disable SSO access | Remove from identity provider | ☐ |

### Extended Revocation (Within 4 Hours)

| # | Task | Details | Completed |
|---|------|---------|-----------|
| 2.1 | Revoke database access | Remove admin DB user; rotate shared credentials if accessed | ☐ |
| 2.2 | Revoke Vault access | Remove Vault policy; revoke all leases and tokens | ☐ |
| 2.3 | Revoke Kubernetes access | Remove K8s RBAC bindings; revoke service account tokens | ☐ |
| 2.4 | Revoke AWS IAM access | Remove IAM user/role; delete access keys | ☐ |
| 2.5 | Revoke GitHub access | Remove from organization and all repositories | ☐ |
| 2.6 | Revoke monitoring access | Remove from Grafana, Prometheus, PagerDuty | ☐ |
| 2.7 | Remove from approval workflows | Remove from all dual-approval queues | ☐ |
| 2.8 | Revoke API keys | Delete all API keys associated with the admin | ☐ |
| 2.9 | Revoke Cloudflare Access | Remove from zero-trust access policies | ☐ |

### Physical Access Revocation

| # | Task | Details | Completed |
|---|------|---------|-----------|
| 3.1 | Collect hardware security key | Record serial number; deactivate in system | ☐ |
| 3.2 | Collect company laptop | Forensic image if needed; wipe and reassign | ☐ |
| 3.3 | Collect physical access card | Deactivate in building access system | ☐ |
| 3.4 | Collect any printed materials | Secure documents with admin credentials or procedures | ☐ |
| 3.5 | Change lock codes | If admin had access to server room or secure areas | ☐ |

### Credential Rotation

| # | Task | Details | Completed |
|---|------|---------|-----------|
| 4.1 | Rotate shared database credentials | If admin had access to shared DB credentials | ☐ |
| 4.2 | Rotate API keys | Any API keys the admin had access to | ☐ |
| 4.3 | Rotate Vault shared secrets | If admin had read access to shared secret paths | ☐ |
| 4.4 | Rotate Kubernetes secrets | If admin had access to K8s secret namespaces | ☐ |
| 4.5 | Verify no persistent access | Attempt login with old credentials — should fail | ☐ |

### Audit & Validation

| # | Task | Details | Completed |
|---|------|---------|-----------|
| 5.1 | Review recent activity | Audit last 30 days of admin actions for anomalies | ☐ |
| 5.2 | Review financial approvals | Check for unusual approvals in last 30 days | ☐ |
| 5.3 | Review data access | Check for bulk data access or exports | ☐ |
| 5.4 | Verify no backdoor accounts | Check for admin accounts created by departing admin | ☐ |
| 5.5 | Verify no unauthorized API keys | Check for API keys generated by departing admin | ☐ |
| 5.6 | Update admin registry | Mark account as deactivated with date and reason | ☐ |
| 5.7 | Archive audit trail | Preserve departing admin's audit logs per retention policy | ☐ |

### Post-Offboarding Verification (4 Hours After)

| # | Task | Details | Completed |
|---|------|---------|-----------|
| 6.1 | Verify no active sessions | `SELECT * FROM admin_sessions WHERE admin_id = '[id]'` returns 0 | ☐ |
| 6.2 | Verify login fails | Attempt login with old credentials — should be rejected | ☐ |
| 6.3 | Verify VPN access denied | VPN connection attempt should fail | ☐ |
| 6.4 | Verify no database access | Database connection with old credentials should fail | ☐ |
| 6.5 | Verify no Vault access | Vault token should be revoked | ☐ |
| 6.6 | Confirm with all system owners | Email checklist to all system owners for confirmation | ☐ |

### Sign-Off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| HR Representative | | | |
| Security Team Lead | | | |
| System Administrator | | | |
| Manager (of departing admin) | | | |

---

## 3. Daily Admin Security Review

**Purpose:** Daily operational security review of the admin control plane to detect anomalies and ensure controls are functioning.  
**Owner:** Security Operations (SOC)  
**Estimated Time:** 30-45 minutes  
**Schedule:** Daily, 08:00-09:00 EAT  

### Automated Pre-Check (System-Generated)

Before the manual review, verify these automated checks have completed:

| # | Check | Source | Expected | Action if Failed |
|---|-------|--------|----------|-----------------|
| 1 | Hash chain verification | Automated hourly job | "PASS" | P0 incident |
| 2 | WORM replication lag | S3 monitoring | < 60 seconds | P2 incident |
| 3 | Certificate expiry check | SSL monitoring | > 30 days remaining | Renew if < 30 days |
| 4 | Vulnerability scan results | Snyk/Trivy | No critical findings | Remediate within 7 days |
| 5 | Backup completion | Backup monitoring | All backups successful | Investigate and re-run |

### Manual Review Checklist

#### Authentication Review (10 minutes)

| # | Item | Query / Source | Threshold | Action if Exceeded |
|---|------|---------------|-----------|-------------------|
| 1 | Failed login attempts (24h) | `SELECT COUNT(*) FROM admin_auth_log WHERE success=false AND timestamp > NOW() - INTERVAL '24 hours'` | > 10 per account | Investigate; lock if > 5 per account |
| 2 | MFA failure rate (24h) | Admin dashboard → Security Metrics | > 3% of attempts | Investigate for MFA bypass attempts |
| 3 | Logins from new IPs (24h) | `SELECT DISTINCT ip_address FROM admin_auth_log WHERE event='login_success' AND ip_address NOT IN (SELECT DISTINCT ip_address FROM admin_ip_allowlist)` | Any | Verify with admin; flag if suspicious |
| 4 | Logins outside business hours (24h) | `SELECT * FROM admin_auth_log WHERE event='login_success' AND EXTRACT(HOUR FROM timestamp) NOT BETWEEN 7 AND 19` | Any | Verify with admin; document justification |
| 5 | Account lockouts (24h) | Admin dashboard → Security Metrics | Any | Review; determine if brute force or user error |
| 6 | New device registrations (24h) | Device registration log | Any | Verify with admin; check for device theft |

#### Financial Review (10 minutes)

| # | Item | Query / Source | Threshold | Action if Exceeded |
|---|------|---------------|-----------|-------------------|
| 7 | Total withdrawal amount approved (24h) | `SELECT SUM(amount) FROM transactions WHERE status='approved' AND created_at > NOW() - INTERVAL '24 hours'` | Compare to 7-day average ± 50% | Investigate if anomalous |
| 8 | High-value approvals (24h) | `SELECT * FROM admin_approvals WHERE amount > 1000000 AND created_at > NOW() - INTERVAL '24 hours'` | Any | Verify dual approval compliance |
| 9 | Single-approver transactions (24h) | `SELECT * FROM transactions WHERE approval_count < 2 AND created_at > NOW() - INTERVAL '24 hours'` | 0 | P0 incident — investigate immediately |
| 10 | Risk score distribution | Transaction risk scoring dashboard | No critical-scored without enhanced review | Investigate |
| 11 | Approval velocity per admin (24h) | `SELECT actor_id, COUNT(*) FROM admin_approvals WHERE timestamp > NOW() - INTERVAL '24 hours' GROUP BY actor_id` | > 20 per admin | Investigate for automation or compromise |
| 12 | Cumulative amounts to same beneficiary | Transaction analytics | > KES 5M/day to single destination | Investigate for splitting or fraud |

#### Data Access Review (5 minutes)

| # | Item | Query / Source | Threshold | Action if Exceeded |
|---|------|---------------|-----------|-------------------|
| 13 | KYC document access volume (24h) | `SELECT actor_id, COUNT(*) FROM admin_audit_log WHERE resource_type='kyc_document' AND timestamp > NOW() - INTERVAL '24 hours' GROUP BY actor_id` | > 100 per admin | Investigate |
| 14 | Bulk data exports (24h) | `SELECT * FROM admin_audit_log WHERE event_type='bulk_export' AND timestamp > NOW() - INTERVAL '24 hours'` | Any | Verify justification |
| 15 | PII access outside role scope (24h) | ABAC violation log | 0 | Investigate authorization failure |
| 16 | User profile view volume (24h) | Audit log analytics | > 200 per admin | Investigate for reconnaissance |

#### System Health (5 minutes)

| # | Item | Source | Expected | Action if Anomaly |
|---|------|--------|----------|-------------------|
| 17 | Admin service uptime | Grafana dashboard | 99.9% | Investigate downtime |
| 18 | Session count trend | `SELECT COUNT(DISTINCT admin_id) FROM admin_sessions WHERE last_activity > NOW() - INTERVAL '1 hour'` | Within normal range | Investigate spike/drop |
| 19 | Alert rule status | Prometheus alerting | All rules active and firing | Re-enable disabled rules |
| 20 | Emergency control status | Admin dashboard | All controls in normal state | Investigate any active freeze/lockdown |

#### Documentation

| # | Task | Details | Completed |
|---|------|---------|-----------|
| 21 | Record review in log | Date, reviewer, findings, actions taken | ☐ |
| 22 | File any incident tickets | For any items exceeding thresholds | ☐ |
| 23 | Escalate critical findings | Notify CISO for any P0/P1 indicators | ☐ |
| 24 | Update trending data | Add daily metrics to weekly/monthly trend analysis | ☐ |

---

## 4. Weekly Admin Audit Review

**Purpose:** Comprehensive weekly review of admin control plane audit logs to identify patterns, anomalies, and compliance gaps.  
**Owner:** Security Team Lead + Compliance Officer  
**Estimated Time:** 2-3 hours  
**Schedule:** Every Monday, 09:00-12:00 EAT  

### Audit Log Integrity Verification (30 minutes)

| # | Task | Method | Expected Result | Action if Failed |
|---|------|--------|-----------------|-----------------|
| 1 | Full hash chain verification | Run `verify_audit_chain.py --full` from last verification | "Chain intact — 0 breaks" | P0 incident; follow ADM-AUDIT procedure |
| 2 | WORM replica reconciliation | Compare row counts between primary and S3 WORM | Counts match exactly | Investigate missing/extra entries |
| 3 | Entry volume consistency | Compare daily entry counts to 30-day average | Within ±30% of average | Investigate anomalies |
| 4 | Timestamp ordering check | `SELECT * FROM admin_audit_log WHERE timestamp < LAG(timestamp) OVER (ORDER BY id)` | 0 results | Investigate out-of-order entries |

### Financial Transaction Audit (45 minutes)

| # | Task | Method | Threshold | Action if Exceeded |
|---|------|--------|-----------|-------------------|
| 5 | Dual-approval compliance rate | `SELECT COUNT(CASE WHEN approval_count >= 2 THEN 1 END)::float / COUNT(*) * 100 FROM transactions WHERE created_at > NOW() - INTERVAL '7 days'` | 100% | P0 for any non-compliant transaction |
| 6 | Approval from same IP | `SELECT t.* FROM transactions t JOIN admin_approvals a1 ON t.id = a1.transaction_id JOIN admin_approvals a2 ON t.id = a2.transaction_id WHERE a1.ip_address = a2.ip_address AND a1.admin_id != a2.admin_id` | 0 | Investigate for proxy/VPN sharing |
| 7 | Self-approval detection | `SELECT * FROM transactions WHERE creator_admin_id IN (SELECT admin_id FROM admin_approvals WHERE transaction_id = transactions.id)` | 0 | P1 incident |
| 8 | Off-hours financial approvals | `SELECT * FROM admin_approvals WHERE EXTRACT(HOUR FROM timestamp) NOT BETWEEN 7 AND 19 OR EXTRACT(DOW FROM timestamp) IN (0, 6)` | Review all | Verify justification |
| 9 | Transaction amount vs. approval limit | `SELECT * FROM transactions t JOIN admin_approvals a ON t.id = a1.transaction_id JOIN admins ad ON a.admin_id = ad.id WHERE t.amount > ad.approval_limit` | 0 | Policy violation |
| 10 | Cumulative withdrawal analysis | Group by beneficiary, sum amounts for week | > KES 10M/week per beneficiary | Investigate for transaction splitting |
| 11 | Reconciliation with bank statements | Compare platform transactions with bank records | 100% match | Investigate discrepancies |

### KYC Decision Audit (30 minutes)

| # | Task | Method | Threshold | Action if Exceeded |
|---|------|--------|-----------|-------------------|
| 12 | Approval rate per reviewer | `SELECT actor_id, COUNT(CASE WHEN action='approve' THEN 1 END)::float / COUNT(*) * 100 as approval_rate FROM admin_audit_log WHERE event_type='kyc_decision' GROUP BY actor_id` | Within ±15% of team average | Investigate outlier |
| 13 | Rapid-fire KYC decisions | `SELECT actor_id, COUNT(*) FROM admin_audit_log WHERE event_type='kyc_decision' AND timestamp > NOW() - INTERVAL '7 days' GROUP BY actor_id, DATE_TRUNC('hour', timestamp) HAVING COUNT(*) > 30` | None | Investigate for rubber-stamping |
| 14 | KYC reversal rate | KYC decisions reversed within 7 days | < 5% | Investigate quality of initial review |
| 15 | Self-referential KYC | Admin approving KYC for accounts linked to themselves | 0 | P1 incident |

### Access & Authorization Audit (30 minutes)

| # | Task | Method | Threshold | Action if Exceeded |
|---|------|--------|-----------|-------------------|
| 16 | Role change review | `SELECT * FROM admin_audit_log WHERE event_type='role_change' AND timestamp > NOW() - INTERVAL '7 days'` | All changes approved | Investigate unauthorized changes |
| 17 | Permission escalation attempts | `SELECT * FROM admin_audit_log WHERE event_type='authorization_failure' AND timestamp > NOW() - INTERVAL '7 days'` | Review all | Investigate for reconnaissance |
| 18 | Dormant admin accounts | `SELECT * FROM admins WHERE last_login < NOW() - INTERVAL '30 days' AND is_active = true` | Review and deactivate | Deactivate if no longer needed |
| 19 | Super admin activity review | Full activity log for all super admins | All actions justified | Investigate anomalies |
| 20 | API key usage review | `SELECT * FROM api_keys WHERE last_used < NOW() - INTERVAL '30 days' AND is_active = true` | Revoke unused keys | Revoke and document |

### Data Access Audit (15 minutes)

| # | Task | Method | Threshold | Action if Exceeded |
|---|------|--------|-----------|-------------------|
| 21 | Bulk data access review | `SELECT actor_id, COUNT(*) FROM admin_audit_log WHERE resource_type IN ('user_pii', 'kyc_document', 'financial_data') AND timestamp > NOW() - INTERVAL '7 days' GROUP BY actor_id ORDER BY COUNT(*) DESC` | Compare to role norm | Investigate outliers |
| 22 | Data export audit | Review all bulk export events | All have dual approval | Investigate unauthorized exports |
| 23 | Cross-scope access | Admin accessing data outside their role scope | 0 | Investigate authorization failure |

### Documentation & Reporting

| # | Task | Details | Completed |
|---|------|---------|-----------|
| 24 | Compile weekly audit report | Summarize findings, metrics, anomalies | ☐ |
| 25 | File incident tickets | For any items exceeding thresholds | ☐ |
| 26 | Update risk register | Add any newly identified risks | ☐ |
| 27 | Distribute report | Send to CISO, CTO, Head of Finance, Compliance | ☐ |
| 28 | Archive review evidence | Store in compliance folder for regulatory audit | ☐ |

---

## 5. Monthly Security Assessment

**Purpose:** Comprehensive monthly security assessment of the admin control plane including penetration testing coordination, access review, and control validation.  
**Owner:** CISO + Security Engineering  
**Estimated Time:** 4-8 hours (spread over the month)  
**Schedule:** First week of each month  

### Access Review (2 hours)

| # | Task | Method | Action |
|---|------|--------|--------|
| 1 | Full admin account inventory | List all active admin accounts with roles | Verify each account is still needed |
| 2 | Role-permission mapping review | Export current RBAC configuration | Verify least privilege compliance |
| 3 | Privileged access certification | Each manager certifies their team's access | Revoke uncertified access |
| 4 | Service account review | List all service accounts with permissions | Verify still needed; rotate credentials |
| 5 | API key inventory | List all active API keys with scope | Revoke unused; verify scope |
| 6 | Dormant account cleanup | Disable accounts with no login in 30+ days | Re-enable only with CISO approval |
| 7 | Shared credential check | Audit for any shared or generic accounts | Eliminate; create individual accounts |

### Control Validation (2 hours)

| # | Task | Method | Expected Result | Action if Failed |
|---|------|--------|-----------------|-----------------|
| 8 | MFA enforcement test | Attempt login without MFA for each admin | All accounts require MFA | Fix immediately |
| 9 | Session timeout test | Open session and wait; verify auto-logout | Timeout at 15 min idle, 4 hr absolute | Fix session configuration |
| 10 | IP allowlist test | Attempt admin access from non-allowlisted IP | Connection refused | Fix network ACL |
| 11 | Dual approval test | Submit withdrawal for single approval | Rejected; requires second approval | Fix authorization policy |
| 12 | Rate limiting test | Send 100 requests/minute to admin API | Rate limited after threshold | Fix rate limit configuration |
| 13 | Audit log immutability test | Attempt UPDATE on audit log entry | Permission denied | Fix database grants |
| 14 | Emergency control test | Activate withdrawal freeze in staging | Freeze works correctly | Fix emergency control service |
| 15 | VPN enforcement test | Attempt admin access without VPN | Connection refused | Fix network configuration |

### Vulnerability Assessment (1-2 hours)

| # | Task | Method | Frequency | Action |
|---|------|--------|-----------|--------|
| 16 | Dependency scan | Snyk / npm audit / pip audit | Monthly + on every PR | Patch critical within 7 days |
| 17 | Container image scan | Trivy scan of admin Docker images | Monthly | Patch critical before deployment |
| 18 | Infrastructure scan | AWS Inspector on admin instances | Monthly | Remediate findings within 14 days |
| 19 | SAST review | Review CodeQL/Semgrep findings | Monthly | Address new high/critical findings |
| 20 | Secret scan | GitLeaks + GitHub secret scanning | Continuous | Rotate and remove immediately |

### Security Metrics Review (1 hour)

| # | Metric | Target | Actual | Trend |
|---|--------|--------|--------|-------|
| 21 | Mean time to detect (MTTD) | < 15 minutes | | |
| 22 | Mean time to respond (MTTR) | < 30 minutes | | |
| 23 | Failed login attempts / week | < 50 | | |
| 24 | MFA bypass attempts / week | 0 | | |
| 25 | Unauthorized access attempts / week | 0 | | |
| 26 | Audit log integrity checks | 100% pass | | |
| 27 | Dual-approval compliance | 100% | | |
| 28 | Vulnerability remediation SLA | Critical: 7 days, High: 30 days | | |
| 29 | Admin account certification | 100% certified monthly | | |
| 30 | Penetration test findings closure | 95% within SLA | | |

### Documentation & Reporting

| # | Task | Details | Completed |
|---|------|---------|-----------|
| 31 | Compile monthly security report | Metrics, findings, remediation status | ☐ |
| 32 | Update risk register | Add new risks, close mitigated risks | ☐ |
| 33 | Review and update playbooks | Incorporate lessons learned | ☐ |
| 34 | Board security briefing | Prepare summary for board review | ☐ |
| 35 | Compliance attestation | Sign off on monthly compliance status | ☐ |

---

## 6. Emergency Withdrawal Freeze Procedure

**Purpose:** Immediately halt all withdrawal processing to prevent financial loss during a security incident.  
**Owner:** CISO / Super Admin  
**Estimated Time:** 5 minutes to activate  
**Approval:** Dual super admin (or emergency single activation with post-hoc approval)

### Pre-Conditions

- Security incident detected involving financial transactions, OR
- Suspicious withdrawal pattern detected, OR
- Admin account compromise with financial approval privileges, OR
- CISO or CTO direct instruction

### Activation Procedure

#### Step 1: Verify the Emergency (1 minute)

1. Confirm the situation warrants a withdrawal freeze:
   - Is there an active financial fraud incident?
   - Is an admin account with financial access compromised?
   - Is there suspicious withdrawal activity?
   - Has CISO/CTO authorized the freeze?

2. If uncertain, err on the side of caution — you can always lift the freeze

#### Step 2: Activate the Freeze (2 minutes)

**Via Admin Dashboard:**
```
1. Navigate to: Emergency Panel → Financial Controls
2. Click: "Activate Withdrawal Freeze"
3. Enter justification: "[Incident ID] - [Brief description]"
4. First Super Admin: Click "Approve" + hardware key tap
5. Second Super Admin: Click "Approve" + hardware key tap
6. Freeze is activated immediately
```

**Via API (if dashboard unavailable):**
```bash
curl -X POST https://admin.digiland.internal/api/v1/emergency/freeze \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "X-Admin-Signature: $(sign_with_hw_key 'freeze')" \
  -d '{"action": "freeze_withdrawals", "justification": "[Incident ID] - [Brief description]"}'
```

**Via CLI (if API unavailable):**
```bash
# Emergency database-level freeze
psql -h admin-db.internal -U emergency_admin -d digiland_admin -c \
  "INSERT INTO emergency_controls (control_type, status, activated_by, justification, auto_expiry) 
   VALUES ('withdrawal_freeze', 'active', '${ADMIN_ID}', '${JUSTIFICATION}', NOW() + INTERVAL '4 hours');"
```

#### Step 3: Verify Activation (1 minute)

1. Check withdrawal freeze status:
   ```
   Emergency Panel → Financial Controls → Status: "WITHDRAWAL FROZEN"
   ```

2. Verify no withdrawals are processing:
   ```sql
   SELECT COUNT(*) FROM transactions 
   WHERE status = 'processing' 
   AND type = 'withdrawal';
   -- Should return 0
   ```

3. Test that new withdrawal attempts are rejected:
   - Submit a test withdrawal (in staging if available)
   - Verify the request is rejected with "Withdrawals currently frozen" message

#### Step 4: Notify Stakeholders (1 minute)

1. Automated notifications are sent to:
   - Slack: `#incident-response` and `#finance`
   - PagerDuty: P1 alert to on-call
   - Email: `security-incident@digiland.co.ke`

2. Manual notifications:
   - Call CISO (if not already aware)
   - Call Head of Finance
   - Brief support team on user-facing messaging

#### Step 5: Document

1. Create incident ticket if not already created
2. Record in the emergency control log:
   - Date/time of activation
   - Activating admins
   - Justification
   - Expected duration
   - Incident ticket reference

### Monitoring During Freeze

| # | Check | Frequency | Action |
|---|-------|-----------|--------|
| 1 | Verify freeze is still active | Every 30 minutes | Re-activate if auto-expired |
| 2 | Count of pending withdrawals | Every hour | Report to incident commander |
| 3 | User support tickets about withdrawals | Every hour | Provide status updates |
| 4 | Auto-expiry timer | Check at 3.5 hours | Extend if needed (requires re-approval) |

### Lifting the Freeze

#### Pre-Conditions for Lifting

- [ ] Root cause of the freeze is resolved
- [ ] All unauthorized transactions identified and actioned
- [ ] CISO and Head of Finance sign-off
- [ ] Dual-approval workflow verified as functional
- [ ] Monitoring and alerting confirmed operational

#### Lifting Procedure

```
1. Navigate to: Emergency Panel → Financial Controls
2. Click: "Lift Withdrawal Freeze"
3. Enter justification: "Root cause resolved — incident [ID] closed"
4. First Super Admin: Click "Approve" + hardware key tap
5. Second Super Admin: Click "Approve" + hardware key tap
6. Freeze is lifted
```

#### Post-Freeze Actions

1. Process pending withdrawals in priority order (oldest first)
2. Monitor withdrawal processing for 24 hours
3. Conduct post-incident review within 24 hours
4. Update this procedure with lessons learned

---

## 7. Session Revocation Procedure

**Purpose:** Immediately terminate one or all admin sessions to prevent unauthorized access.  
**Owner:** Security Team / Super Admin  
**Estimated Time:** 2-5 minutes  
**Approval:** Super Admin (single admin) or CISO (all sessions)

### Scope Options

| Scope | When to Use | Approval Required |
|-------|-----------|-------------------|
| Single admin session | Suspected session hijack for specific admin | Super Admin |
| All sessions for one admin | Admin account compromise | Super Admin |
| All admin sessions (global) | Platform-wide security incident | CISO + Super Admin |
| Sessions from specific IP | Attacker IP identified | Super Admin |

### Procedure: Revoke Single Admin Sessions

#### Step 1: Identify the Target (1 minute)

1. Determine the admin account whose sessions need revocation
2. Verify the admin account identity (confirm with HR or manager if needed)
3. Check active sessions for the admin:
   ```sql
   SELECT session_id, ip_address, device_fingerprint, 
          created_at, last_activity, user_agent
   FROM admin_sessions 
   WHERE admin_id = '[target_admin_uuid]' 
   AND is_active = true;
   ```

#### Step 2: Revoke Sessions (1 minute)

**Via Admin Dashboard:**
```
1. Navigate to: Emergency Panel → Session Management
2. Search for admin: [username or email]
3. Click: "Revoke All Sessions"
4. Confirm: "Yes, revoke all sessions for [admin]"
5. Enter justification: "[Reason for revocation]"
6. Sessions are terminated immediately
```

**Via API:**
```bash
curl -X POST https://admin.digiland.internal/api/v1/sessions/revoke \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -d '{"admin_id": "[target_admin_uuid]", "scope": "all", "justification": "[reason]"}'
```

#### Step 3: Verify Revocation (1 minute)

1. Confirm no active sessions remain:
   ```sql
   SELECT COUNT(*) FROM admin_sessions 
   WHERE admin_id = '[target_admin_uuid]' 
   AND is_active = true;
   -- Should return 0
   ```

2. Verify the admin cannot access the dashboard:
   - Attempt to load admin dashboard with old session token
   - Should redirect to login page

3. Confirm session tokens are blacklisted in Redis:
   ```bash
   redis-cli -h admin-redis.internal SMEMBERS "revoked_sessions"
   ```

#### Step 4: Notify (1 minute)

1. Notify the affected admin via out-of-band channel (phone call):
   - Inform them their sessions were terminated
   - Ask them to re-authenticate
   - If compromise suspected, do NOT notify via the compromised channel

2. Log the revocation in the incident tracking system

### Procedure: Global Session Revocation

**Use only for platform-wide security incidents.**

#### Step 1: Authorization (2 minutes)

1. Obtain CISO verbal or written authorization
2. Obtain Super Admin approval
3. Document the reason and expected impact

#### Step 2: Execute Global Revocation (1 minute)

**Via Admin Dashboard:**
```
1. Navigate to: Emergency Panel → Session Management
2. Click: "Revoke ALL Admin Sessions (Global)"
3. Read the warning: "This will terminate all active admin sessions. All admins will need to re-authenticate."
4. Type confirmation: "REVOKE ALL SESSIONS"
5. CISO/Super Admin: Click "Authorize" + hardware key tap
6. Second Super Admin: Click "Confirm" + hardware key tap
7. All sessions are terminated
```

**Via API:**
```bash
curl -X POST https://admin.digiland.internal/api/v1/sessions/revoke-global \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "X-Admin-Signature: $(sign_with_hw_key 'revoke-global')" \
  -d '{"justification": "[Platform-wide security incident — INC-XXXX]", "authorized_by": "${CISO_ID}"}'
```

#### Step 3: Verify and Notify (2 minutes)

1. Verify all sessions are terminated:
   ```sql
   SELECT COUNT(*) FROM admin_sessions WHERE is_active = true;
   -- Should return 0
   ```

2. Send notification to all admins:
   - SMS: "Digiland admin sessions have been terminated due to a security incident. Please re-authenticate at admin.digiland.internal. Contact security@digiland.co.ke with questions."
   - Slack: Post to `#admin-announcements`

3. Log the global revocation in the incident tracking system

---

## 8. Incident Mode Activation Procedure

**Purpose:** Place the admin control plane into incident mode, restricting operations to read-only and emergency controls only. This is the most restrictive emergency state.  
**Owner:** CISO / CTO  
**Estimated Time:** 5 minutes to activate  
**Approval:** CISO + CTO joint approval (or CISO alone for initial activation with CTO confirmation within 1 hour)

### When to Activate Incident Mode

- Confirmed admin account compromise with unknown blast radius
- Active financial fraud with multiple compromised accounts suspected
- Audit log tampering detected
- Supply chain compromise affecting admin dependencies
- Any P0 incident where the risk of continued operations outweighs the cost of disruption

### Incident Mode Effects

When incident mode is active, the following restrictions are enforced:

| Capability | Normal Mode | Incident Mode |
|-----------|-------------|---------------|
| View audit logs | ✅ | ✅ |
| View dashboards | ✅ | ✅ (read-only) |
| Approve withdrawals | ✅ (with dual approval) | ❌ Blocked |
| Process refunds | ✅ (with dual approval) | ❌ Blocked |
| Review/approve KYC | ✅ | ❌ Blocked |
| Modify platform config | ✅ (super admin) | ❌ Blocked |
| Create/modify admin accounts | ✅ (super admin) | ❌ Blocked |
| Export data | ✅ (with approval) | ❌ Blocked |
| Emergency controls | ✅ | ✅ |
| Session revocation | ✅ | ✅ |
| Withdrawal freeze | ✅ | ✅ |
| Account lockdown | ✅ | ✅ |
| Impersonate user | ✅ (with approval) | ❌ Blocked |

### Activation Procedure

#### Step 1: Authorize (2 minutes)

1. Contact CISO and CTO (phone call — do not use potentially compromised channels)
2. Provide briefing:
   - Nature of the incident
   - Why incident mode is needed
   - Expected duration
   - Business impact
3. Obtain verbal approval from both CISO and CTO
4. Document approval:
   - CISO name and approval time
   - CTO name and approval time

#### Step 2: Activate (2 minutes)

**Via Admin Dashboard:**
```
1. Navigate to: Emergency Panel → Incident Mode
2. Review the confirmation: "Activating Incident Mode will restrict all admin operations to read-only and emergency controls only."
3. Click: "Activate Incident Mode"
4. Enter incident details:
   - Incident ID: INC-[YYYY]-[NNN]
   - Justification: "[Brief description]"
   - Expected duration: [hours]
5. CISO: Click "Authorize" + hardware key tap
6. CTO/Super Admin: Click "Confirm" + hardware key tap
7. Incident mode is activated
```

**Via API (if dashboard unavailable):**
```bash
curl -X POST https://admin.digiland.internal/api/v1/emergency/incident-mode \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "X-Admin-Signature: $(sign_with_hw_key 'incident-mode')" \
  -d '{
    "action": "activate",
    "incident_id": "INC-[YYYY]-[NNN]",
    "justification": "[Brief description]",
    "expected_duration_hours": 4,
    "authorized_by": {
      "ciso_id": "${CISO_ID}",
      "cto_id": "${CTO_ID}"
    }
  }'
```

#### Step 3: Verify Activation (1 minute)

1. Check incident mode status:
   ```
   Emergency Panel → Incident Mode → Status: "ACTIVE"
   ```

2. Verify restrictions are in place:
   - Attempt a non-emergency action (e.g., view user profile) — should work (read-only)
   - Attempt a write action (e.g., approve a transaction) — should be blocked
   - Verify emergency controls are still accessible

3. Confirm the banner is displayed on all admin pages:
   ```
   ⚠️ INCIDENT MODE ACTIVE — Operations restricted to read-only and emergency controls
   Incident: INC-[YYYY]-[NNN] | Activated: [timestamp] | Contact: security@digiland.co.ke
   ```

#### Step 4: Notify (1 minute)

1. Automated notifications:
   - Slack: `#incident-response` — "🚨 INCIDENT MODE ACTIVATED — [Incident ID]"
   - PagerDuty: P0 alert to all on-call
   - Email: `security-incident@digiland.co.ke` and `operations@digiland.co.ke`

2. Manual notifications:
   - Call Head of Finance: inform that all financial operations are suspended
   - Call Head of Support: provide user-facing messaging about delays
   - Email all admins: "Incident mode has been activated. All admin operations are restricted to read-only and emergency controls. Do not attempt to bypass restrictions. Contact security@digiland.co.ke with questions."

### Monitoring During Incident Mode

| # | Check | Frequency | Action |
|---|-------|-----------|--------|
| 1 | Incident mode status | Every 15 minutes | Verify still active |
| 2 | Auto-expiry timer | Check at 3.5 hours | Extend if needed (requires re-approval) |
| 3 | Emergency control usage | Real-time | All emergency actions require enhanced logging |
| 4 | Unauthorized bypass attempts | Real-time | Alert on any attempt to bypass restrictions |
| 5 | User impact | Every 30 minutes | Update support team on expected resolution |

### Deactivation Procedure

#### Pre-Conditions for Deactivation

- [ ] Root cause of the incident is resolved
- [ ] All compromised accounts are secured
- [ ] All unauthorized changes are reverted
- [ ] Financial reconciliation is complete
- [ ] Audit log integrity verified
- [ ] CISO and CTO sign-off on deactivation
- [ ] Post-incident review scheduled (within 24 hours)

#### Deactivation Steps

```
1. Navigate to: Emergency Panel → Incident Mode
2. Click: "Deactivate Incident Mode"
3. Enter deactivation justification:
   - "Root cause resolved — incident [ID]"
   - List of verification checks completed
4. CISO: Click "Authorize Deactivation" + hardware key tap
5. CTO: Click "Confirm Deactivation" + hardware key tap
6. Incident mode is deactivated
7. All admins are notified via Slack and email
```

#### Post-Incident Mode Actions

1. Process any pending operations that were queued during incident mode
2. Conduct full financial reconciliation
3. Verify all system configurations are correct
4. Monitor all admin activity with enhanced alerting for 72 hours
5. Schedule and conduct post-incident review within 24 hours
6. Update this procedure with lessons learned
7. Prepare board notification

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-15 | Security Operations Team | Initial runbook creation |

---

## Quick Reference: Emergency Procedures

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    EMERGENCY QUICK REFERENCE CARD                        │
│                                                                          │
│  WITHDRAWAL FREEZE:                                                      │
│  Emergency Panel → Financial Controls → Activate Freeze                  │
│  Requires: 2 Super Admin approvals + justification                       │
│  Auto-expires: 4 hours                                                   │
│                                                                          │
│  SESSION REVOCATION (single):                                            │
│  Emergency Panel → Session Management → [Admin] → Revoke All            │
│  Requires: 1 Super Admin + justification                                 │
│                                                                          │
│  SESSION REVOCATION (global):                                            │
│  Emergency Panel → Session Management → Revoke ALL Sessions              │
│  Requires: CISO + Super Admin                                            │
│                                                                          │
│  INCIDENT MODE:                                                          │
│  Emergency Panel → Incident Mode → Activate                              │
│  Requires: CISO + CTO approvals                                          │
│  Auto-expires: 24 hours                                                  │
│  Effect: Read-only + emergency controls only                             │
│                                                                          │
│  ESCALATION:                                                             │
│  P0 (Critical): CISO → CTO → CEO → Board                                │
│  P1 (High):     CISO → CTO                                              │
│  P2 (Medium):   Security Team Lead → CISO                               │
│  P3 (Low):      Security Team                                           │
│                                                                          │
│  CONTACTS:                                                               │
│  Security Slack: #incident-response                                      │
│  Security Email: security-incident@digiland.co.ke                        │
│  PagerDuty: security-oncall                                              │
└──────────────────────────────────────────────────────────────────────────┘
```
