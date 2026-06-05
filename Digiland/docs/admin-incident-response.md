# Admin Control Plane Incident Response Playbook

**Document Version:** 1.0  
**Classification:** Confidential — Internal Use Only  
**Last Updated:** 2025-01-15  
**Owner:** Security Operations Center (SOC)  
**Review Cycle:** Quarterly (after each exercise or real incident)  

---

## Table of Contents

1. [Incident Classification](#incident-classification)
2. [Response Procedures](#response-procedures)
3. [Emergency Contact Template](#emergency-contact-template)
4. [Post-Incident Review Template](#post-incident-review-template)

---

## Incident Classification

### Severity Levels

| Level | Name | Definition | Response Time | Escalation | Examples |
|-------|------|-----------|---------------|------------|----------|
| **P0** | Critical | Active compromise with confirmed financial loss or data breach; immediate threat to platform integrity | < 5 minutes | CISO → CTO → CEO → Board | Admin account compromised with fraudulent withdrawals; mass data exfiltration in progress |
| **P1** | High | Confirmed security breach without confirmed loss; active attack in progress; emergency controls required | < 15 minutes | CISO → CTO | Admin session hijacking detected; unauthorized role escalation; audit log tampering |
| **P2** | Medium | Suspicious activity requiring investigation; potential breach indicators; no confirmed compromise | < 1 hour | Security Team Lead → CISO | Anomalous admin login patterns; unusual data access volumes; MFA bypass attempt |
| **P3** | Low | Security policy violation without active threat; minor misconfiguration; informational | < 4 hours | Security Team | Admin accessing from new location; password policy violation; minor alerting gap |

### Incident Types Specific to Admin Security

| Code | Incident Type | Default Severity |
|------|-------------|-----------------|
| ADM-COMP | Admin Account Compromise | P1 (escalate to P0 if financial actions detected) |
| ADM-FRAUD | Unauthorized Financial Transaction | P0 |
| ADM-AUDIT | Audit Log Tampering | P0 |
| ADM-EXFIL | Mass Data Exfiltration | P0 |
| ADM-SESS | Admin Session Hijacking | P1 |
| ADM-FREEZE | Emergency Withdrawal Freeze | P1 (may be P2 if intentional/test) |
| ADM-INSIDER | Insider Threat Detection | P0 |
| ADM-ROLE | Unauthorized Role/Permission Change | P1 |
| ADM-KYC | KYC Approval Fraud | P1 |
| ADM-CONFIG | Unauthorized Configuration Change | P1 |
| ADM-DDOS | Admin Service Denial of Service | P2 |

---

## Response Procedures

---

### Scenario 1: Suspected Admin Account Compromise

**Incident Code:** ADM-COMP  
**Default Severity:** P1 → P0 (if financial actions detected)

#### Detection Signals

- Multiple failed login attempts followed by successful login from unusual IP
- Login from geographically impossible location (impossible travel)
- Login from new device fingerprint not registered to admin
- Admin actions performed outside normal working hours
- MFA bypass or enrollment change detected
- Admin credentials found in public breach databases
- Third-party notification (law enforcement, partner, security researcher)

#### Immediate Actions (First 15 Minutes)

**T+0 to T+5 minutes: Contain**

1. **Do NOT alert the suspected compromised admin** — they may be the attacker
2. Activate emergency session revocation for the affected admin account:
   ```
   Emergency Panel → Revoke Sessions → [admin_username]
   ```
3. Disable the admin account:
   ```
   Admin Panel → User Management → [admin_username] → Suspend Account
   ```
4. If the compromised admin has super admin privileges:
   - Activate incident mode if any financial or role changes were made
   - Notify CISO and CTO immediately via PagerDuty
5. Check for concurrent sessions from different IPs on the same account

**T+5 to T+10 minutes: Assess**

1. Pull the admin's recent activity log:
   ```sql
   SELECT * FROM admin_audit_log 
   WHERE actor_id = '[admin_uuid]' 
   ORDER BY timestamp DESC 
   LIMIT 100;
   ```
2. Check for:
   - Financial approvals in last 24 hours
   - Role or permission changes
   - User data exports or bulk access
   - Configuration modifications
   - New admin accounts created
   - KYC approval/rejection anomalies
3. Identify the attack vector:
   - Review login IPs and geolocations
   - Check MFA challenge results
   - Review device fingerprints
   - Check for phishing email delivery to admin's mailbox

**T+10 to T+15 minutes: Notify**

1. Create incident ticket with severity classification
2. Notify incident response team:
   - Slack: `#incident-response` channel
   - PagerDuty: Trigger ADM-COMP incident
   - Email: `security-incident@digiland.co.ke`
3. If P0: Call CISO and CTO directly

#### Investigation Steps

1. **Timeline Reconstruction**
   - Export full audit log for the compromised account (7-day window)
   - Map all actions to timestamps, IPs, and device fingerprints
   - Identify first anomalous action (likely the initial compromise point)
   - Document all actions taken by the compromised session

2. **Blast Radius Assessment**
   - What data was accessed? (PII, financial, KYC documents)
   - Were any financial transactions approved?
   - Were any configuration changes made?
   - Were any new accounts or API keys created?
   - Were any other admin sessions observed from the same attacker IP?

3. **Lateral Movement Check**
   - Check if attacker attempted to access other admin accounts
   - Review authentication logs for all admins from attacker's IP range
   - Check for privilege escalation attempts
   - Review Vault access logs for secret retrieval by compromised credentials

4. **Forensic Evidence Collection**
   - Capture and preserve session logs (write to WORM storage)
   - Export browser/proxy logs if available
   - Screenshot admin dashboard showing unauthorized actions
   - Preserve email headers if phishing was the vector
   - Document attacker IP addresses and user agents

#### Containment Actions

1. Suspend the compromised admin account (already done in immediate actions)
2. Force password reset for the compromised account
3. Revoke and re-enroll MFA tokens for the compromised account
4. Block attacker IP addresses at WAF level
5. If super admin was compromised:
   - Rotate all secrets the admin had access to
   - Force MFA re-enrollment for all admin accounts
   - Review all role assignments made during compromise window
6. Check for persistence mechanisms:
   - New API keys generated by the compromised account
   - New admin accounts created during the compromise window
   - Modified alert rules or monitoring configuration

#### Eradication Steps

1. Delete any unauthorized admin accounts or API keys created during compromise
2. Revert any unauthorized configuration changes
3. Revoke any approval tokens generated during compromise
4. If financial transactions were approved, initiate reversal process
5. Rotate all credentials that the compromised admin had access to:
   - Database credentials
   - API keys
   - Vault tokens
   - Kubernetes service account tokens
6. Remove attacker IP addresses from any allowlists
7. Patch the attack vector:
   - If phishing: block sender domain, update email filtering rules
   - If credential stuffing: enhance rate limiting, add CAPTCHA
   - If malware: isolate and reimage admin workstation

#### Recovery Steps

1. Restore admin account with new credentials and MFA enrollment
2. Verify all system configurations are correct (compare against known-good baseline)
3. Validate audit log integrity (hash chain verification)
4. Conduct thorough review of all financial transactions approved during compromise
5. Monitor the restored account with enhanced alerting for 30 days
6. Gradually restore permissions (start with read-only, then add write access after 48 hours)

#### Post-Incident Actions

1. Conduct post-incident review within 48 hours (see template)
2. Update threat model if new attack vector discovered
3. Update detection rules based on indicators observed
4. Communicate to affected users if their data was accessed (legal requirement)
5. File regulatory notification if required (Kenya DPA 2019: 72-hour window)
6. Schedule security awareness refresher for all admins
7. Update this playbook with lessons learned

---

### Scenario 2: Unauthorized Financial Transaction

**Incident Code:** ADM-FRAUD  
**Default Severity:** P0

#### Detection Signals

- Transaction risk score exceeds critical threshold
- Transaction approved outside business hours
- Single-admin approval for dual-approval-required transaction
- Transaction to new/unknown beneficiary
- Cumulative amount to same beneficiary exceeds threshold
- Approval pattern anomaly (ML model detection)
- Reconciliation mismatch between approved and executed amounts
- Beneficiary details differ from KYC records
- Transaction splitting pattern detected (multiple sub-threshold to same destination)

#### Immediate Actions (First 15 Minutes)

**T+0 to T+5 minutes: Stop the bleeding**

1. **Activate withdrawal freeze immediately:**
   ```
   Emergency Panel → Freeze All Withdrawals
   Justification: "Unauthorized financial transaction detected — incident [ID]"
   ```
   *Note: If dual super admin not available, use emergency single-activation with post-hoc approval*

2. If transaction is in-progress but not yet settled:
   - Contact payment provider (KCB Bank) to cancel/return the transaction
   - Use payment reversal API if available:
     ```
     POST /api/v1/payments/{transaction_id}/cancel
     Authorization: Bearer {emergency_token}
     ```
3. Notify CISO and Head of Finance immediately (PagerDuty P0)

**T+5 to T+10 minutes: Identify scope**

1. Pull all transactions approved in the last 24 hours:
   ```sql
   SELECT t.*, a1.email as approver_1, a2.email as approver_2
   FROM transactions t
   LEFT JOIN admin_approvals ap1 ON t.id = ap1.transaction_id AND ap1.approval_order = 1
   LEFT JOIN admins a1 ON ap1.admin_id = a1.id
   LEFT JOIN admin_approvals ap2 ON t.id = ap2.transaction_id AND ap2.approval_order = 2
   LEFT JOIN admins a2 ON ap2.admin_id = a2.id
   WHERE t.created_at > NOW() - INTERVAL '24 hours'
   AND t.status IN ('approved', 'processing', 'completed')
   ORDER BY t.amount DESC;
   ```

2. For each suspicious transaction, verify:
   - Were both approvals from different admins?
   - Were both approvals from different IPs?
   - Was the beneficiary KYC-verified?
   - Does the beneficiary account match the KYC records?
   - Was the transaction signed with hardware keys?

3. Calculate total potential loss

**T+10 to T+15 minutes: Escalate**

1. Notify CEO if loss exceeds KES 1,000,000
2. Notify legal counsel if loss exceeds KES 5,000,000
3. Contact bank fraud department if funds may still be recoverable
4. Begin evidence preservation (chain of custody)

#### Investigation Steps

1. **Transaction Reconstruction**
   - Obtain complete audit trail for each suspicious transaction
   - Verify transaction hash integrity at each approval stage
   - Compare approved amount/destination vs. executed amount/destination
   - Check for TOCTOU: was the transaction modified between approvals?

2. **Actor Identification**
   - Determine which admin(s) approved the unauthorized transaction(s)
   - Assess whether the approving admin is compromised or complicit
   - Review the approving admin's full activity log for the past 7 days
   - Check for collusion indicators (communication between approvers)

3. **Fraud Pattern Analysis**
   - Was this a single transaction or part of a pattern?
   - Are there shell/fictitious accounts created to receive funds?
   - Is the beneficiary account linked to any admin?
   - Were KYC approval anomalies involved?
   - How long has the fraud been occurring?

4. **Financial Impact Quantification**
   - Total unauthorized amount approved
   - Total amount successfully transferred (irrecoverable)
   - Total amount frozen/cancelled (recovered)
   - Pending transactions at risk
   - Reconciliation gaps

#### Containment Actions

1. Withdrawal freeze remains active until investigation is complete
2. Suspend all admin accounts involved in unauthorized approvals
3. Freeze the beneficiary accounts on the platform
4. Contact bank to freeze receiving accounts if possible
5. Revoke all active sessions for involved admins
6. Block IPs associated with unauthorized approvals
7. If collusion suspected, suspend all involved admins simultaneously

#### Eradication Steps

1. Reverse all unauthorized transactions that haven't settled
2. File fraud reports with:
   - KCB Bank fraud department
   - Central Bank of Kenya (if required)
   - Kenya Police Cybercrime Unit
3. Recover funds through bank chargeback process where possible
4. Remove any shell/fictitious accounts created for the fraud
5. Revoke and rotate all credentials accessed by involved admins
6. Remove any unauthorized KYC approvals linked to the fraud

#### Recovery Steps

1. Lift withdrawal freeze only after:
   - All unauthorized transactions identified and actioned
   - All involved admin accounts secured
   - Dual-approval workflow verified as functioning correctly
   - CISO and Head of Finance sign-off
2. Process legitimate pending transactions in priority order
3. Conduct full platform reconciliation
4. Restore admin access for cleared admins with fresh credentials
5. Implement additional monitoring for 30 days:
   - All financial approvals require real-time security team review
   - Reduced transaction thresholds for dual approval
6. Notify affected users if their transactions were delayed

#### Post-Incident Actions

1. Mandatory post-incident review within 24 hours
2. Engage external forensic auditor if loss > KES 1,000,000
3. Report to regulators if required (CBK, Kenya DPA)
4. Update financial controls based on root cause
5. Consider legal action against involved parties
6. Update this playbook and financial control architecture
7. Board notification within 24 hours for any P0 financial incident

---

### Scenario 3: Audit Log Tampering Detected

**Incident Code:** ADM-AUDIT  
**Default Severity:** P0

#### Detection Signals

- Hash chain verification failure (automated hourly check)
- Missing sequence numbers in audit log
- Timestamp anomalies (out-of-order entries)
- Log entries with hash values that don't match computed values
- Unexpected gaps in log entries
- Log replication lag to WORM storage
- S3 Object Lock compliance alerts
- Database row count discrepancy between primary and replica

#### Immediate Actions (First 15 Minutes)

**T+0 to T+5 minutes: Preserve and isolate**

1. **Do NOT attempt to "fix" the audit logs** — preserve the tampered state as evidence
2. Take immediate snapshot of audit database:
   ```sql
   -- Create point-in-time snapshot
   SELECT pg_start_backup('audit_tampering_incident_[ID]');
   ```
3. Activate incident mode:
   ```
   Emergency Panel → Activate Incident Mode
   Justification: "Audit log integrity violation — incident [ID]"
   ```
4. Notify CISO immediately (PagerDuty P0)

**T+5 to T+10 minutes: Assess extent**

1. Identify the scope of tampering:
   ```sql
   -- Find hash chain breaks
   SELECT id, timestamp, entry_hash, previous_hash,
          LAG(entry_hash) OVER (ORDER BY timestamp) as computed_prev_hash
   FROM admin_audit_log
   WHERE timestamp > NOW() - INTERVAL '7 days'
   AND entry_hash != SHA256(CONCAT(id, timestamp, event_type, actor_id, 
       action, resource_type, resource_id, after_state, previous_hash));
   ```
2. Determine:
   - First entry that was tampered with
   - Total number of entries affected
   - Which entries were modified vs. deleted
   - Who the actor was for entries surrounding the tampered entries

3. Compare primary database against WORM replica on S3:
   ```
   aws s3api list-objects-v2 --bucket dl-audit-worm --prefix "audit-logs/"
   ```

**T+10 to T+15 minutes: Escalate**

1. This is a P0 incident — CISO and CTO must be notified immediately
2. If tampering coincides with financial transactions, also notify Head of Finance
3. Engage legal counsel — audit tampering may indicate cover-up of fraud
4. Consider engaging external forensic investigators

#### Investigation Steps

1. **Integrity Assessment**
   - Run full hash chain verification from genesis to present
   - Identify all breaks in the chain with timestamps and surrounding context
   - Compare against WORM storage copy to identify deleted entries
   - Determine if tampering was at the application level or database level

2. **Access Path Analysis**
   - Who had database write access to the audit table?
   - Were any admin API endpoints used that could modify logs?
   - Check database access logs for direct SQL connections
   - Review Vault audit logs for database credential access
   - Check for application-level vulnerabilities (SQL injection, etc.)

3. **Motivation Analysis**
   - What actions were taken in the time window around tampered entries?
   - Were any financial transactions approved in that window?
   - Were any role changes or permission modifications made?
   - Were any KYC decisions made?
   - Is the tampering consistent with covering up a specific action?

4. **Evidence Preservation**
   - Create forensic copy of the tampered database state
   - Export WORM storage copy as reference baseline
   - Document all discrepancies between primary and WORM copy
   - Preserve database connection logs and application logs
   - Chain of custody documentation for all evidence

#### Containment Actions

1. Incident mode remains active until investigation is complete
2. Revoke database write access for all non-system accounts on audit tables
3. If specific admin is suspected, suspend their account
4. If database credentials were compromised, rotate immediately
5. Block any direct database access routes that bypass the application
6. Deploy additional monitoring on all database connections

#### Eradication Steps

1. Restore audit log integrity from WORM storage backup
2. Address the vulnerability that enabled tampering:
   - Application bug: deploy fix
   - Database access: revoke grants, add RLS policies
   - Insider: remove admin access, disciplinary process
3. Implement additional integrity controls:
   - Real-time replication to WORM (reduce lag to seconds)
   - Database triggers preventing UPDATE/DELETE on audit table
   - Separate audit database credentials with minimal distribution
4. Verify hash chain integrity is restored end-to-end
5. Run full reconciliation of financial transactions against restored logs

#### Recovery Steps

1. Verify audit log integrity (full hash chain validation)
2. Restore normal operations from incident mode with CISO approval
3. Conduct complete financial reconciliation for the tampered period
4. Review all admin actions during the tampered window for unauthorized activity
5. Implement enhanced audit monitoring for 30 days
6. Validate WORM replication is functioning correctly

#### Post-Incident Actions

1. Engage external forensic auditors to validate the investigation
2. If tampering was to cover fraud, pursue legal action
3. Report to regulators (audit integrity is a compliance requirement)
4. Update audit architecture with additional safeguards
5. Update this playbook with lessons learned
6. Board notification required for audit integrity violations

---

### Scenario 4: Mass Data Exfiltration

**Incident Code:** ADM-EXFIL  
**Default Severity:** P0

#### Detection Signals

- Bulk export feature triggered for large dataset
- Admin API access volume exceeds threshold (>500 records/hour)
- KYC document download volume exceeds baseline
- Database query returning large result sets from admin queries
- Network egress anomaly (large data transfer from admin service)
- S3 GET request spike on KYC document buckets
- Admin accessing data outside their normal scope
- Data transfer to external storage detected (DLP)

#### Immediate Actions (First 15 Minutes)

**T+0 to T+5 minutes: Stop the exfiltration**

1. **Revoke the suspected admin's session immediately:**
   ```
   Emergency Panel → Revoke Sessions → [admin_username]
   ```

2. If exfiltration is still in progress (large download):
   - Terminate the active session
   - Block the admin's IP at WAF level
   - If KYC documents are being accessed, disable KYC review service temporarily

3. Activate incident mode if exfiltration volume is significant (>1000 records):
   ```
   Emergency Panel → Activate Incident Mode
   Justification: "Mass data exfiltration in progress — incident [ID]"
   ```

4. Notify CISO and DPO immediately (PagerDuty P0)

**T+5 to T+10 minutes: Assess scope**

1. Determine what data was accessed:
   ```sql
   SELECT resource_type, COUNT(*) as records_accessed,
          MIN(timestamp) as first_access, MAX(timestamp) as last_access
   FROM admin_audit_log
   WHERE actor_id = '[suspect_admin_uuid]'
   AND timestamp > NOW() - INTERVAL '24 hours'
   AND event_type IN ('data_access', 'document_view', 'export', 'search')
   GROUP BY resource_type
   ORDER BY records_accessed DESC;
   ```

2. Categorize the exfiltrated data:
   - User PII (names, emails, phone numbers, ID numbers)
   - Financial data (bank accounts, transaction history)
   - KYC documents (ID scans, selfies, proof of address)
   - Platform configuration data
   - Admin credentials or secrets

3. Estimate the number of affected users

**T+10 to T+15 minutes: Notify and prepare**

1. Notify legal counsel — data breach notification may be required
2. Prepare regulatory notification (Kenya DPA 2019: 72-hour window)
3. If > 10,000 users affected, prepare public disclosure
4. Engage external incident response firm if needed

#### Investigation Steps

1. **Exfiltration Method Analysis**
   - Which API endpoints were used for data access?
   - Was the bulk export feature used?
   - Were paginated queries systematically accessed?
   - Were KYC documents downloaded individually?
   - Was data accessed via direct database queries?

2. **Actor Analysis**
   - Was this a compromised admin account or malicious insider?
   - Review the admin's employment status and recent behavior
   - Check for signs of account compromise (impossible travel, new devices)
   - Review the admin's access patterns over the past 30 days

3. **Data Volume Assessment**
   - Total number of records accessed
   - Total number of KYC documents downloaded
   - Estimated data volume transferred
   - Whether data could have been copied to external media or cloud storage

4. **Timeline Reconstruction**
   - When did the exfiltration begin?
   - Was it a single event or gradual over time?
   - Were there any preceding reconnaissance activities?
   - Is the exfiltration ongoing from another vector?

#### Containment Actions

1. Suspend the suspected admin account
2. Revoke all API keys associated with the account
3. Block all IP addresses used during the exfiltration
4. Disable bulk export functionality until investigation is complete
5. Implement immediate rate limiting on all data access endpoints (50 records/hour max)
6. If insider threat: coordinate with HR for next steps (do not alert the individual)

#### Eradication Steps

1. Remove any unauthorized API keys or access tokens created by the attacker
2. Revoke and rotate any credentials the suspected admin had access to
3. Close any data access paths exploited during the exfiltration
4. Implement additional DLP controls on admin workstations
5. Deploy enhanced data access monitoring rules
6. Address any application vulnerabilities that enabled bulk access

#### Recovery Steps

1. Restore normal data access with enhanced rate limiting
2. Re-enable bulk export with mandatory dual approval
3. Implement data masking for non-essential fields in admin views
4. Monitor the affected admin's restored account with heightened alerting
5. Conduct a full access review for all admin accounts

#### Post-Incident Actions

1. File mandatory data breach notification:
   - Kenya Office of the Data Protection Commissioner: within 72 hours
   - Affected users: without undue delay
   - If EU users affected: GDPR Article 33/34 notifications
2. Offer credit monitoring / identity protection to affected users
3. Engage external forensic investigators
4. Update data access controls based on root cause
5. Consider legal action against the responsible party
6. Board notification required
7. Update this playbook with lessons learned

---

### Scenario 5: Admin Session Hijacking

**Incident Code:** ADM-SESS  
**Default Severity:** P1

#### Detection Signals

- IP address change during an active session
- User-agent change during an active session
- Device fingerprint change during an active session
- Concurrent session from different location for same admin
- Impossible travel (two logins from distant locations in short timeframe)
- Anomalous actions within an active session (different behavior pattern)
- Session token reuse from different browser/device
- Security alert from admin's endpoint protection

#### Immediate Actions (First 15 Minutes)

**T+0 to T+5 minutes: Terminate the hijacked session**

1. **Revoke the affected admin's session:**
   ```
   Emergency Panel → Revoke Sessions → [admin_username]
   ```

2. If the session has performed financial actions:
   - Activate withdrawal freeze immediately
   - Review all actions taken in the hijacked session

3. Force password reset for the affected admin account:
   ```
   Admin Panel → User Management → [admin_username] → Force Password Reset
   ```

4. Notify the affected admin via out-of-band channel (phone call — NOT email/Slack)

**T+5 to T+10 minutes: Determine hijack vector**

1. Review session timeline:
   - When was the session created (legitimate login)?
   - When did the hijack indicators appear?
   - What actions were taken after the hijack point?

2. Identify the likely hijack vector:
   - XSS in admin dashboard → check recent content rendered
   - Session token theft → check for malware on admin workstation
   - Network interception → check if admin was on unsecured network
   - Browser extension compromise → review installed extensions
   - Cookie theft via browser vulnerability → check browser version

3. Check if other admin sessions show similar hijack indicators

**T+10 to T+15 minutes: Contain and notify**

1. Block the hijacker's IP at WAF level
2. Check for actions taken during the hijacked session (financial, data access, config changes)
3. Notify CISO and Security Team (PagerDuty P1)
4. If financial actions were taken, escalate to P0

#### Investigation Steps

1. **Session Forensics**
   - Extract complete session log from creation to termination
   - Map all IP addresses, user agents, and device fingerprints
   - Identify the exact point of hijack (first anomalous request)
   - Document all actions taken by the legitimate admin vs. the hijacker

2. **Attack Vector Investigation**
   - If XSS suspected: review recent user-generated content rendered in admin dashboard
   - If token theft: arrange for admin workstation forensic imaging
   - If network interception: check if admin used public WiFi or VPN
   - If browser compromise: review installed extensions and browser security

3. **Lateral Movement Check**
   - Did the hijacker attempt to access other admin accounts?
   - Were any credentials or secrets accessed during the hijacked session?
   - Were any API keys generated?
   - Were any configuration changes made?

#### Containment Actions

1. Session already terminated (immediate action)
2. Password already reset (immediate action)
3. Re-enroll MFA for the affected admin account
4. If XSS was the vector: patch the vulnerability immediately
5. If workstation compromise: reimage the admin's workstation
6. Block all IPs associated with the hijacker

#### Eradication Steps

1. Patch the vulnerability that enabled the hijack
2. Remove any persistent access mechanisms (new API keys, etc.)
3. If XSS: deploy CSP headers, sanitize all rendered content
4. If workstation compromise: full malware scan and reimage
5. Update session security controls based on the attack vector
6. Deploy device binding enforcement if not already in place

#### Recovery Steps

1. Restore the affected admin's account with fresh credentials and MFA
2. Verify no persistent access remains for the attacker
3. Monitor the restored account with enhanced alerting for 14 days
4. If the hijack vector was XSS, conduct a thorough XSS scan of the admin dashboard
5. Verify session security controls are functioning correctly

#### Post-Incident Actions

1. Post-incident review within 48 hours
2. If XSS was the vector: conduct full security review of admin dashboard
3. Update session anomaly detection rules based on observed patterns
4. Consider mandatory workstation security standards for all admins
5. Update this playbook with lessons learned

---

### Scenario 6: Emergency Withdrawal Freeze Activation

**Incident Code:** ADM-FREEZE  
**Default Severity:** P1 (if legitimate activation) / P2 (if test/drill)

#### Detection Signals

- Emergency freeze control activated
- Withdrawal processing halted
- Automated alert from monitoring system
- Admin notification of freeze activation

#### Immediate Actions (First 15 Minutes)

**T+0 to T+5 minutes: Verify legitimacy**

1. **Confirm the freeze was intentional:**
   - Check who activated the freeze (which admin account)
   - Verify the justification text
   - Contact the activating admin via phone to confirm

2. If unauthorized freeze activation:
   - This is an incident (ADM-SESS or ADM-COMP)
   - Follow the appropriate scenario procedure
   - Deactivate the freeze with CISO approval

3. If legitimate activation:
   - Acknowledge the freeze in the incident tracking system
   - Notify all affected teams (Finance, Support, Communications)

**T+5 to T+10 minutes: Communicate**

1. Notify stakeholders:
   - Slack: `#incident-response` with freeze details
   - Email: `operations@digiland.co.ke` with impact assessment
   - Support team: prepare user communication about delayed withdrawals

2. Document:
   - Reason for freeze
   - Expected duration
   - Affected transaction count and total amount
   - Business impact estimate

**T+10 to T+15 minutes: Monitor**

1. Verify the freeze is working correctly (no withdrawals processing)
2. Check for any in-progress transactions that were partially settled
3. Monitor user-facing systems for error handling (proper messages)
4. Ensure support team has talking points for user inquiries

#### Investigation Steps

1. Determine the triggering event that led to the freeze
2. If related to a security incident, coordinate with that incident's investigation
3. Assess the financial impact of the freeze:
   - Number of pending withdrawals
   - Total value of frozen transactions
   - SLA implications for withdrawal processing times
   - User experience impact

#### Containment Actions

1. The freeze IS the containment action — maintain it as long as needed
2. If the freeze was activated due to a security incident, follow that incident's procedures
3. Ensure proper user communication is in place

#### Eradication Steps

1. Address the root cause that triggered the freeze
2. Verify the security issue is resolved before lifting the freeze
3. If the freeze was precautionary, confirm no actual breach occurred

#### Recovery Steps

1. **Before lifting the freeze:**
   - CISO and Head of Finance must sign off
   - All pending transactions reviewed for legitimacy
   - Dual-approval workflow verified as functioning
   - Monitoring and alerting confirmed operational

2. **Lifting the freeze:**
   ```
   Emergency Panel → Lift Withdrawal Freeze
   Requires: Dual super admin approval
   Justification: "Root cause resolved — incident [ID] closed"
   ```

3. Process pending withdrawals in priority order:
   - Oldest first
   - Lower amounts first (to reduce user impact)
   - High-value transactions require additional verification

4. Monitor withdrawal processing for anomalies for 24 hours after lift

#### Post-Incident Actions

1. Document freeze duration and business impact
2. Review freeze procedure effectiveness
3. Update withdrawal processing SLAs if needed
4. If freeze was triggered by another incident, follow that incident's post-actions
5. User communication: inform affected users of resolution

---

### Scenario 7: Insider Threat Detection

**Incident Code:** ADM-INSIDER  
**Default Severity:** P0

#### Detection Signals

- KYC approval rate anomaly (specific admin approving significantly more than peers)
- Financial approval pattern anomaly (specific admin consistently approving high-risk transactions)
- Data access outside normal job function
- Access to systems not required for role
- After-hours access without business justification
- Behavioral indicators reported by colleagues
- Whistleblower report
- Unexplained wealth or lifestyle changes
- Unusual interactions with specific users or accounts
- Small-amount systematic theft (salami attacks)
- Creating and approving transactions to accounts with personal connections

#### Immediate Actions (First 15 Minutes)

**T+0 to T+5 minutes: Covert containment**

1. **Do NOT alert the suspected insider** — premature alertation may cause evidence destruction
2. **Covertly restrict the suspect's access:**
   - Apply silent enhanced monitoring (log all actions with additional detail)
   - Do NOT suspend the account yet (may tip off the insider)
   - If the suspect has super admin access, consult CISO before any action

3. **If the insider is actively performing harmful actions:**
   - If financial theft in progress: activate withdrawal freeze (can be attributed to "system maintenance")
   - If data exfiltration in progress: implement rate limiting silently
   - If destroying evidence: this triggers immediate account suspension

4. Notify CISO and Head of HR via **encrypted, out-of-band channel** (in-person or encrypted phone)

**T+5 to T+10 minutes: Secure evidence**

1. Create forensic snapshot of the suspect's recent activity:
   ```sql
   -- Export with NO LOGGING of this query to avoid detection
   COPY (
     SELECT * FROM admin_audit_log 
     WHERE actor_id = '[suspect_uuid]'
     AND timestamp > NOW() - INTERVAL '30 days'
     ORDER BY timestamp
   ) TO '/secure/forensic/export_[incident_id].csv';
   ```

2. Preserve:
   - All session logs
   - All financial approvals
   - All KYC decisions
   - All data access records
   - Communication records (Slack, email)
   - VPN and network access logs

3. Copy evidence to secure, access-controlled location

**T+10 to T+15 minutes: Plan next steps**

1. Consult with legal counsel regarding:
   - Employment law requirements
   - Evidence preservation standards
   - Law enforcement involvement
   - Search/seizure of company devices

2. Determine if law enforcement should be notified immediately
3. Plan the timing of account suspension (ideally when insider is not at workstation)
4. Brief essential team members on need for secrecy

#### Investigation Steps

1. **Financial Analysis**
   - Review all financial approvals by the suspect
   - Check for transactions to accounts linked to the suspect
   - Analyze transaction patterns for anomalies
   - Calculate total financial exposure
   - Check for KYC approvals that enabled shell accounts

2. **Behavioral Analysis**
   - Map the suspect's access patterns over the past 90 days
   - Identify deviations from normal behavior
   - Check for gradual escalation of suspicious activity
   - Review the suspect's role and what access they legitimately have

3. **Connection Analysis**
   - Are there user accounts linked to the suspect (shared email domain, phone, address)?
   - Have any new users been registered from the suspect's IP address?
   - Are there KYC-approved accounts that match the suspect's information?
   - Have any agents or users had unusual interactions with the suspect?

4. **Covert Surveillance**
   - Enhanced logging on all suspect's actions (without their knowledge)
   - Session recording if available and legally permissible
   - Network traffic monitoring for data exfiltration
   - Email/Slack monitoring per legal counsel guidance

#### Containment Actions

1. **Coordinated suspension** (plan timing carefully):
   - Suspend account when insider is away from workstation
   - Revoke all sessions simultaneously
   - Disable VPN access
   - Revoke physical access cards (coordinate with facilities)
   - Collect company devices (coordinate with HR)

2. **Access revocation checklist:**
   - Admin dashboard account
   - VPN access
   - Email account (preserve for evidence, disable login)
   - Slack access
   - GitHub repository access
   - AWS/IAM access
   - Vault access
   - Database access
   - Kubernetes access
   - Physical office access

3. Rotate all credentials the insider had access to:
   - Database passwords
   - API keys
   - Vault tokens
   - Service account credentials

#### Eradication Steps

1. Remove any persistence mechanisms:
   - Unauthorized API keys
   - Backdoor admin accounts
   - Modified alert rules
   - Scripts or cron jobs on shared systems
2. Review and revert any unauthorized changes made by the insider
3. If fraud is confirmed, initiate financial recovery procedures
4. If KYC fraud is involved, re-review all KYC decisions made by the insider

#### Recovery Steps

1. Restore normal operations after confirming all insider access is revoked
2. Conduct thorough review of all actions taken by the insider during the threat period
3. Reconcile all financial transactions approved by the insider
4. Re-review all KYC decisions made by the insider
5. Implement additional controls to prevent similar insider threats:
   - Stricter separation of duties
   - Enhanced behavioral monitoring
   - More frequent access reviews

#### Post-Incident Actions

1. Engage external forensic auditors
2. Legal action as appropriate:
   - Civil recovery of stolen funds
   - Criminal referral to law enforcement
   - Regulatory notifications
3. Internal communication (general, without compromising investigation details)
4. Review and update insider threat detection capabilities
5. Consider employee assistance program for affected team members
6. Board notification required
7. Update this playbook with lessons learned
8. Implement enhanced monitoring for remaining admins for 60 days

---

## Emergency Contact Template

### Internal Contacts

| Role | Name | Phone (24/7) | Email | Slack | PagerDuty |
|------|------|-------------|-------|-------|-----------|
| CISO | [Name] | +254-XXX-XXX-XXX | ciso@digiland.co.ke | @ciso | ciso-oncall |
| CTO | [Name] | +254-XXX-XXX-XXX | cto@digiland.co.ke | @cto | cto-oncall |
| Head of Security Engineering | [Name] | +254-XXX-XXX-XXX | security-eng@digiland.co.ke | @security-eng | security-oncall |
| Head of Finance | [Name] | +254-XXX-XXX-XXX | finance@digiland.co.ke | @finance-head | finance-oncall |
| Head of Infrastructure | [Name] | +254-XXX-XXX-XXX | infra@digiland.co.ke | @infra-head | infra-oncall |
| Head of Platform Engineering | [Name] | +254-XXX-XXX-XXX | platform@digiland.co.ke | @platform-head | platform-oncall |
| Head of HR | [Name] | +254-XXX-XXX-XXX | hr@digiland.co.ke | @hr-head | — |
| Legal Counsel | [Name] | +254-XXX-XXX-XXX | legal@digiland.co.ke | @legal | — |
| Data Protection Officer | [Name] | +254-XXX-XXX-XXX | dpo@digiland.co.ke | @dpo | — |
| CEO | [Name] | +254-XXX-XXX-XXX | ceo@digiland.co.ke | @ceo | — |

### External Contacts

| Organization | Contact | Phone | Email | Purpose |
|-------------|---------|-------|-------|---------|
| KCB Bank — Fraud Department | [Contact Name] | +254-XXX-XXX-XXX | fraud@kcbgroup.com | Financial fraud, transaction reversal |
| Central Bank of Kenya | [Contact Name] | +254-XXX-XXX-XXX | — | Regulatory reporting |
| Kenya Police — Cybercrime Unit | [Contact Name] | +254-XXX-XXX-XXX | — | Criminal investigation |
| Office of the Data Protection Commissioner | [Contact Name] | +254-XXX-XXX-XXX | complaints@odpc.go.ke | Data breach notification |
| External Forensic Firm | [Firm Name] | +254-XXX-XXX-XXX | incident@[firm].com | Forensic investigation |
| External Legal (Cyber) | [Firm Name] | +254-XXX-XXX-XXX | cyber@[firm].com | Legal counsel on cyber incidents |
| Cloudflare (if using) | Support | — | support@cloudflare.com | DDoS, WAF, Access issues |
| AWS Support | Enterprise Support | — | — | Infrastructure incidents |

### Escalation Matrix

```
Time since detection    P0                     P1                     P2                     P3
───────────────────────────────────────────────────────────────────────────────────────────────
0-5 minutes            SOC + CISO + CTO       SOC + Security Lead    SOC                    SOC
5-15 minutes           + CEO + Legal          + CISO                 + Security Lead        
15-30 minutes          + Board                + Head of Finance      + CISO                 
30-60 minutes          + External Forensics   + CTO                  + Relevant team lead   
1-4 hours              + Law Enforcement      + Head of Infra                              
4-24 hours             + Regulators           + CEO (if escalated)                          
24+ hours              + Public Disclosure    + Legal (if needed)                           
```

---

## Post-Incident Review Template

### Incident Summary

| Field | Value |
|-------|-------|
| Incident ID | INC-[YYYY]-[NNN] |
| Date/Time Detected | |
| Date/Time Resolved | |
| Total Duration | |
| Severity | P0 / P1 / P2 / P3 |
| Incident Type | ADM-[CODE] |
| Incident Commander | |
| Affected Systems | |
| Affected Users | |
| Financial Impact | |
| Data Impact | |

### Timeline

| Time (UTC) | Event | Action Taken | By Whom |
|-----------|-------|-------------|---------|
| | | | |

### Root Cause Analysis

**What happened:**

**Why it happened:**

**Why it wasn't detected sooner:**

**What could have prevented it:**

### Five Whys Analysis

1. **Why did the incident occur?**
   → _Answer_

2. **Why did [answer to #1] happen?**
   → _Answer_

3. **Why did [answer to #2] happen?**
   → _Answer_

4. **Why did [answer to #3] happen?**
   → _Answer_

5. **Why did [answer to #4] happen?**
   → _Answer_

### Impact Assessment

| Category | Impact | Details |
|----------|--------|---------|
| Financial | | |
| Data/Privacy | | |
| Operational | | |
| Reputational | | |
| Regulatory | | |

### What Went Well

1. 
2. 
3. 

### What Needs Improvement

1. 
2. 
3. 

### Action Items

| # | Action Item | Owner | Priority | Due Date | Status |
|---|-----------|-------|----------|----------|--------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

### Lessons Learned

_Fill in after action items are completed and verified_

### Sign-Off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Incident Commander | | | |
| CISO | | | |
| CTO | | | |
| Head of Finance (if financial impact) | | | |
