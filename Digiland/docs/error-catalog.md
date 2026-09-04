# Digiland Error Catalog

> **Phase 1 — Graceful Degradation System**
> Version: 1.0.0 | Last Updated: 2025-03-04 | Owner: Platform Engineering

## Purpose

This document defines every error code in the Digiland platform. Each error is classified by category, severity, and includes a user-safe message, recovery actions, support escalation procedures, logging configuration, and internal developer details. This catalog ensures consistent error handling across the Django backend and React frontend, and serves as the source of truth for all error-related behavior.

## Error Message Security Policy

**CRITICAL: All user-facing messages must NEVER expose:**

- Stack traces or exception class names
- SQL errors, database names, table names, or column names
- Internal service names or microservice identifiers
- Infrastructure details (server names, IP addresses, ports)
- Third-party provider names (M-Pesa, Stripe, Paystack, AWS, etc.)
- API endpoints or URL paths
- Network topology or architecture details
- Authentication mechanisms or token details
- Security controls or validation rules
- Secret values, keys, or credentials
- Error codes from external providers

**Examples of SAFE vs UNSAFE messages:**

| Unsafe (NEVER show) | Safe (ALWAYS show) |
|---------------------|---------------------|
| "PostgreSQL connection timeout on db-primary.internal:5432" | "We're having trouble loading this information right now. Please try again shortly." |
| "Stripe API returned 502 Bad Gateway" | "Your request is being processed. We'll update you as soon as it's completed." |
| "JWT token expired at 2025-03-04T10:30:00Z" | "Your session has ended. Please sign in again to continue." |
| "Elasticsearch index 'land_escrow_parcel' corrupted" | "Search results may be limited right now. You can still browse listings by category." |
| "Redis cluster at cache-01.internal:6379 unreachable" | "We're having trouble loading this information right now. Please try again shortly." |
| "M-Pesa STK push failed: DS timeout" | "Your request is being processed. We'll update you as soon as it's completed." |
| "S3 bucket digiland-uploads access denied" | "We couldn't upload your file right now. Please try again later." |

---

## Severity Definitions

| Severity | Description | Frontend Behavior | Logging Level |
|----------|-------------|-------------------|---------------|
| **critical** | System is unusable or data integrity is at risk. Immediate response required. | Full-page error with support contact | CRITICAL |
| **error** | Feature is broken but system is operational. Response within SLA. | Inline error with retry option | ERROR |
| **warning** | Feature is degraded or data may be stale. No immediate action required. | Subtle warning banner | WARNING |
| **info** | Informational; no user impact. May indicate upcoming issues. | No visible change; logged only | INFO |

---

## Category Index

| Category | Code Prefix | Description |
|----------|-------------|-------------|
| Authentication | `AUTH_` | Login, tokens, MFA, OAuth, sessions |
| Authorization | `AUTHZ_` | Permissions, roles, tenant access |
| Payments | `PAY_` | Payment processing, direct settlement, refunds |
| Withdrawals | `WD_` | Withdrawals, disbursements |
| Notifications | `NOTIF_` | SMS, email, push notifications |
| Messaging | `MSG_` | Chat, real-time messaging |
| Dashboard | `DASH_` | Dashboard aggregation, widgets |
| Analytics | `ANALYTICS_` | Reporting, data pipeline |
| Admin | `ADMIN_` | Admin control plane, dual-approval |
| File Uploads | `UPLOAD_` | File storage, virus scan, validation |
| Search | `SEARCH_` | Elasticsearch, listing search |
| User Profiles | `PROFILE_` | Profile management, KYC |
| Settings | `SETTINGS_` | User/tenant settings |
| External APIs | `EXT_` | Third-party service integrations |
| Database | `DB_` | Database connectivity, queries |
| Cache | `CACHE_` | Redis/ElastiCache operations |
| WebSocket | `WS_` | Real-time connections |
| Background Jobs | `JOB_` | Celery tasks, async processing |
| Rate Limiting | `RATE_` | API rate limiting |
| Validation | `VAL_` | Input validation errors |
| Platform | `PLAT_` | General platform errors |

---

## 1. Authentication Errors

### AUTH_INVALID_CREDENTIALS

| Field | Value |
|-------|-------|
| **Error Code** | `AUTH_INVALID_CREDENTIALS` |
| **Category** | Authentication |
| **Severity** | error |
| **User-Facing Message** | "The email or password you entered is incorrect. Please try again." |
| **Recovery Action** | User re-enters credentials; password reset flow available |
| **Support Action** | Check login attempt logs for brute-force patterns; verify account status |
| **Log Category** | `auth.login.failed` |
| **Internal Details** | Credential validation failed: either the email does not exist or the password hash does not match. Login attempt recorded in LoginAttempt model. Progressive delay applied. |

### AUTH_SESSION_EXPIRED

| Field | Value |
|-------|-------|
| **Error Code** | `AUTH_SESSION_EXPIRED` |
| **Category** | Authentication |
| **Severity** | warning |
| **User-Facing Message** | "Your session has ended. Please sign in again to continue." |
| **Recovery Action** | Redirect to login page; preserve form state via localStorage |
| **Support Action** | Check session configuration; verify token TTL settings |
| **Log Category** | `auth.session.expired` |
| **Internal Details** | Access token has expired and refresh token rotation failed or refresh token is invalid/blacklisted. May indicate token clock drift or extended inactivity. |

### AUTH_MFA_REQUIRED

| Field | Value |
|-------|-------|
| **Error Code** | `AUTH_MFA_REQUIRED` |
| **Category** | Authentication |
| **Severity** | info |
| **User-Facing Message** | "Please enter your verification code to continue signing in." |
| **Recovery Action** | Show MFA input screen; offer recovery code option |
| **Support Action** | N/A — normal flow |
| **Log Category** | `auth.mfa.required` |
| **Internal Details** | User has MFA enabled. First-factor authentication succeeded; MFA verification step is required before JWT tokens are issued. |

### AUTH_MFA_FAILED

| Field | Value |
|-------|-------|
| **Error Code** | `AUTH_MFA_FAILED` |
| **Category** | Authentication |
| **Severity** | error |
| **User-Facing Message** | "That verification code didn't work. Please try again or use a recovery code." |
| **Recovery Action** | Re-enter TOTP code; use recovery code; offer account recovery flow |
| **Support Action** | Check MFA device sync; verify TOTP time drift; check recovery code usage |
| **Log Category** | `auth.mfa.failed` |
| **Internal Details** | TOTP verification failed: code mismatch or expired. TOTP window=1 allows ±30s clock drift. Failed MFA attempts tracked per user. |

### AUTH_OAUTH_UNAVAILABLE

| Field | Value |
|-------|-------|
| **Error Code** | `AUTH_OAUTH_UNAVAILABLE` |
| **Category** | Authentication |
| **Severity** | warning |
| **User-Facing Message** | "That sign-in method isn't available right now. Please use your email and password instead." |
| **Recovery Action** | Show email/password login form; hide OAuth buttons |
| **Support Action** | Check external identity provider availability; verify OAuth configuration; check circuit breaker state |
| **Log Category** | `auth.oauth.unavailable` |
| **Internal Details** | OAuth provider endpoint unreachable or returned non-2xx response. Circuit breaker for the identity provider may be open. Fallback to email/password authentication. |

### AUTH_ACCOUNT_LOCKED

| Field | Value |
|-------|-------|
| **Error Code** | `AUTH_ACCOUNT_LOCKED` |
| **Category** | Authentication |
| **Severity** | error |
| **User-Facing Message** | "Your account has been temporarily locked for security reasons. Please try again later or contact support." |
| **Recovery Action** | Wait for lockout period; contact support; password reset |
| **Support Action** | Check LoginAttempt records; verify lockout threshold (5 attempts); assess for brute-force attack; consider IP block |
| **Log Category** | `auth.account.locked` |
| **Internal Details** | Account locked after 5 consecutive failed login attempts. Progressive delay: 1s, 2s, 4s, 8s, 16s. Admin notification triggered at 10 failed attempts from same IP. |

### AUTH_TOKEN_REFRESH_FAILED

| Field | Value |
|-------|-------|
| **Error Code** | `AUTH_TOKEN_REFRESH_FAILED` |
| **Category** | Authentication |
| **Severity** | warning |
| **User-Facing Message** | "Your session has ended. Please sign in again to continue." |
| **Recovery Action** | Redirect to login; clear token storage |
| **Support Action** | Check token blacklist; verify refresh token rotation is working; check for replay attacks |
| **Log Category** | `auth.token.refresh_failed` |
| **Internal Details** | Refresh token is invalid, blacklisted, or expired. Possible token replay attempt if refresh token was already used. Old refresh token is blacklisted immediately after rotation. |

---

## 2. Authorization Errors

### AUTHZ_PERMISSION_DENIED

| Field | Value |
|-------|-------|
| **Error Code** | `AUTHZ_PERMISSION_DENIED` |
| **Category** | Authorization |
| **Severity** | error |
| **User-Facing Message** | "You don't have permission to do this. If you think this is a mistake, please contact support." |
| **Recovery Action** | User contacts support; admin reviews role/permissions |
| **Support Action** | Verify user role and ABAC conditions; check resource ownership; review tenant boundaries |
| **Log Category** | `authz.permission.denied` |
| **Internal Details** | RBAC/ABAC evaluation denied the requested action. Denied permission logged with user_id, resource_type, action, conditions, and tenant_id. May indicate role misconfiguration or attempted privilege escalation. |

### AUTHZ_TENANT_ACCESS_DENIED

| Field | Value |
|-------|-------|
| **Error Code** | `AUTHZ_TENANT_ACCESS_DENIED` |
| **Category** | Authorization |
| **Severity** | critical |
| **User-Facing Message** | "For your security, access has been temporarily restricted. Please contact support if this persists." |
| **Recovery Action** | Redirect to support page; log security incident |
| **Support Action** | IMMEDIATE ESCALATION. Investigate possible cross-tenant data access. Check RLS policies. Review audit log for data exposure. |
| **Log Category** | `authz.tenant.denied` |
| **Internal Details** | Tenant isolation boundary violation attempted or RLS policy evaluation failed. This is a security-critical event. The user's tenant_id does not match the requested resource's tenant_id, or the tenant context could not be established. |

### AUTHZ_EVAL_TIMEOUT

| Field | Value |
|-------|-------|
| **Error Code** | `AUTHZ_EVAL_TIMEOUT` |
| **Category** | Authorization |
| **Severity** | error |
| **User-Facing Message** | "We couldn't verify your access right now. Please try again in a moment." |
| **Recovery Action** | User retries action; cached permissions used with TTL extension |
| **Support Action** | Check permission service latency; verify cache layer; check DB query performance |
| **Log Category** | `authz.eval.timeout` |
| **Internal Details** | Permission evaluation exceeded the configured timeout (500ms p99 threshold). ABAC condition evaluation involved a slow database query or cache miss. Falling back to cached permissions with extended TTL. |

---

## 3. Payment Errors

### PAY_PROCESSING_DELAYED

| Field | Value |
|-------|-------|
| **Error Code** | `PAY_PROCESSING_DELAYED` |
| **Category** | Payments |
| **Severity** | warning |
| **User-Facing Message** | "Your request is being processed. We'll update you as soon as it's completed." |
| **Recovery Action** | No user action needed; status updates via notification |
| **Support Action** | Check payment queue; verify provider circuit breaker state; monitor for settlement |
| **Log Category** | `pay.processing.delayed` |
| **Internal Details** | Payment initiation was accepted but could not be confirmed synchronously. The payment provider returned a pending status or the request was queued due to circuit breaker being in half-open state. Payment will be confirmed asynchronously via webhook callback or polling. |

### PAY_PROVIDER_UNAVAILABLE

| Field | Value |
|-------|-------|
| **Error Code** | `PAY_PROVIDER_UNAVAILABLE` |
| **Category** | Payments |
| **Severity** | critical |
| **User-Facing Message** | "Your request is being processed. We'll update you as soon as it's completed." |
| **Recovery Action** | Payment queued for retry; fallback provider attempted if available |
| **Support Action** | Check all payment provider circuit breakers; verify failover chain; monitor reconciliation queue |
| **Log Category** | `pay.provider.unavailable` |
| **Internal Details** | All configured payment providers are unavailable (circuit breakers open). Payment has been queued in the local database for retry. The failover chain (primary → secondary → tertiary) has been exhausted. Manual settlement may be required. |

### PAY_TRANSACTION_FAILED

| Field | Value |
|-------|-------|
| **Error Code** | `PAY_TRANSACTION_FAILED` |
| **Category** | Payments |
| **Severity** | critical |
| **User-Facing Message** | "We couldn't complete this transaction right now. Your money has not been deducted. Please try again." |
| **Recovery Action** | User retries; transaction is in a safe state (no funds transferred) |
| **Support Action** | Verify transaction state machine; check direct settlement provider status; ensure transaction log is consistent |
| **Log Category** | `pay.transaction.failed` |
| **Internal Details** | Direct settlement operation failed during processing. The payment was not captured by the settlement provider. Transaction is in a safe "not started" state. Compensating action may be needed if partial provider callback received. |

### PAY_SETTLEMENT_RELEASE_FAILED

| Field | Value |
|-------|-------|
| **Error Code** | `PAY_SETTLEMENT_RELEASE_FAILED` |
| **Category** | Payments |
| **Severity** | critical |
| **User-Facing Message** | "This transaction is being securely processed. We'll notify you once it's confirmed." |
| **Recovery Action** | No user action needed; release queued for retry |
| **Support Action** | IMMEDIATE ESCALATION. Direct settlement disbursement confirmation failed. Check disbursement queue; verify bank connectivity; consider manual verification with dual approval |
| **Log Category** | `pay.settlement.release_failed` |
| **Internal Details** | Direct settlement payout confirmation failed. The payout verification has been queued for retry with exponential backoff. Admin dual-approval may be required for manual verification. |

### PAY_WEBHOOK_VERIFICATION_FAILED

| Field | Value |
|-------|-------|
| **Error Code** | `PAY_WEBHOOK_VERIFICATION_FAILED` |
| **Category** | Payments |
| **Severity** | critical |
| **User-Facing Message** | "Your payment is being verified. This may take a few minutes." |
| **Recovery Action** | No user action needed; webhook stored for manual review |
| **Support Action** | IMMEDIATE ESCALATION. Verify webhook signing key configuration. Check for payload tampering. Review webhook in dead-letter queue. |
| **Log Category** | `pay.webhook.verification_failed` |
| **Internal Details** | Incoming webhook signature verification failed. Possible causes: signing key rotation, payload tampering, or configuration drift. The webhook payload has been stored in the dead-letter queue for manual review. Transaction status will be verified via polling. |

### PAY_AMOUNT_MISMATCH

| Field | Value |
|-------|-------|
| **Error Code** | `PAY_AMOUNT_MISMATCH` |
| **Category** | Payments |
| **Severity** | critical |
| **User-Facing Message** | "We couldn't complete this transaction right now. Please try again." |
| **Recovery Action** | User retries with correct amount; transaction voided |
| **Support Action** | IMMEDIATE ESCALATION. Investigate potential fraud or system error. Compare expected vs actual amounts. Review transaction audit log. |
| **Log Category** | `pay.amount.mismatch` |
| **Internal Details** | The amount confirmed by the payment provider does not match the expected settlement amount. Possible causes: currency conversion error, partial payment, or fraud. Transaction has been placed in "disputed" state pending investigation. |

---

## 4. Withdrawal Errors

### WD_DISBURSEMENT_FAILED

| Field | Value |
|-------|-------|
| **Error Code** | `WD_DISBURSEMENT_FAILED` |
| **Category** | Withdrawals |
| **Severity** | critical |
| **User-Facing Message** | "Your withdrawal is being processed. You'll receive a notification once it's complete." |
| **Recovery Action** | No user action needed; disbursement queued for retry |
| **Support Action** | Check bank disbursement queue; verify bank API circuit breaker; check settlement reconciliation |
| **Log Category** | `wd.disbursement.failed` |
| **Internal Details** | Bank disbursement API returned an error or timed out. Direct settlement disbursement has been queued for retry with exponential backoff (5m, 15m, 60m). Manual settlement may be required after 3 failed retries. |

### WD_INSUFFICIENT_BALANCE

| Field | Value |
|-------|-------|
| **Error Code** | `WD_INSUFFICIENT_BALANCE` |
| **Category** | Withdrawals |
| **Severity** | critical |
| **User-Facing Message** | "We're unable to process this withdrawal right now. Please try again later or contact support." |
| **Recovery Action** | User contacts support; withdrawal blocked |
| **Support Action** | IMMEDIATE ESCALATION. Reconcile transaction ledger. Check for double-spend or accounting errors. Verify service fee calculations. |
| **Log Category** | `wd.balance.insufficient` |
| **Internal Details** | Verified settlement balance is insufficient to cover the withdrawal amount plus fees. Possible causes: service fee deduction, concurrent withdrawals, or ledger inconsistency. This may indicate an accounting error requiring manual reconciliation. |

### WD_FRAUD_SERVICE_DOWN

| Field | Value |
|-------|-------|
| **Error Code** | `WD_FRAUD_SERVICE_DOWN` |
| **Category** | Withdrawals |
| **Severity** | warning |
| **User-Facing Message** | "Your withdrawal request has been received and is being reviewed. We'll update you shortly." |
| **Recovery Action** | Withdrawal queued for manual fraud review; no user action needed |
| **Support Action** | Check fraud detection circuit breaker; review flagged withdrawal queue; process manual reviews within 4 hours |
| **Log Category** | `wd.fraud.service_down` |
| **Internal Details** | Fraud detection service is unavailable (circuit breaker open). All withdrawals during this period are flagged for manual review. The review queue must be processed within the 4-hour SLA to prevent withdrawal delays. |

---

## 5. Notification Errors

### NOTIF_SMS_FAILED

| Field | Value |
|-------|-------|
| **Error Code** | `NOTIF_SMS_FAILED` |
| **Category** | Notifications |
| **Severity** | warning |
| **User-Facing Message** | "We're having trouble sending you a notification right now. You can check your updates in the app." |
| **Recovery Action** | No user action needed; notification viewable in-app; SMS retried |
| **Support Action** | Check SMS gateway circuit breaker; verify phone number format; check delivery reports |
| **Log Category** | `notif.sms.failed` |
| **Internal Details** | SMS delivery via Africa's Talking failed. The notification has been queued for retry (up to 10 attempts). An email fallback has been triggered as an alternate channel. The in-app notification was delivered successfully. |

### NOTIF_EMAIL_FAILED

| Field | Value |
|-------|-------|
| **Error Code** | `NOTIF_EMAIL_FAILED` |
| **Category** | Notifications |
| **Severity** | warning |
| **User-Facing Message** | "We're having trouble sending you an email right now. Please check your notifications in the app." |
| **Recovery Action** | No user action needed; notification viewable in-app; email retried |
| **Support Action** | Check email service health; verify email address; check bounce rate |
| **Log Category** | `notif.email.failed` |
| **Internal Details** | Email delivery failed. The notification has been queued for retry (up to 5 attempts). The in-app notification center serves as the primary fallback. Dead-letter queue activated after retries exhausted. |

### NOTIF_PUSH_FAILED

| Field | Value |
|-------|-------|
| **Error Code** | `NOTIF_PUSH_FAILED` |
| **Category** | Notifications |
| **Severity** | info |
| **User-Facing Message** | N/A (silent degradation; in-app notification center serves as fallback) |
| **Recovery Action** | N/A — user can view notifications in-app |
| **Support Action** | Monitor push delivery rate; check FCM/APNs configuration |
| **Log Category** | `notif.push.failed` |
| **Internal Details** | Push notification delivery via Firebase Cloud Messaging failed. This is the lowest-priority notification channel. The in-app notification center has already received the notification. Push will be retried with 5-minute backoff. |

---

## 6. Messaging Errors

### MSG_DELIVERY_FAILED

| Field | Value |
|-------|-------|
| **Error Code** | `MSG_DELIVERY_FAILED` |
| **Category** | Messaging |
| **Severity** | error |
| **User-Facing Message** | "We couldn't deliver your message. Please try sending it again." |
| **Recovery Action** | User taps "resend" button; message re-queued |
| **Support Action** | Check WebSocket connection health; verify message persistence; check for deduplication issues |
| **Log Category** | `msg.delivery.failed` |
| **Internal Details** | Real-time message delivery failed after 3 retry attempts. The WebSocket connection may have dropped, or the message persistence layer is unavailable. The message is marked as "unsent" in the UI and can be manually resent. |

### MSG_ATTACHMENT_FAILED

| Field | Value |
|-------|-------|
| **Error Code** | `MSG_ATTACHMENT_FAILED` |
| **Category** | Messaging |
| **Severity** | warning |
| **User-Facing Message** | "We couldn't attach this file right now. Your message was sent without the attachment." |
| **Recovery Action** | User can retry attachment upload from the message |
| **Support Action** | Check object storage availability; verify file size limits; check virus scan queue |
| **Log Category** | `msg.attachment.failed` |
| **Internal Details** | File attachment upload to object storage failed. The text portion of the message was delivered successfully. The attachment has been queued for background upload retry. |

---

## 7. Dashboard Errors

### DASH_DATA_STALE

| Field | Value |
|-------|-------|
| **Error Code** | `DASH_DATA_STALE` |
| **Category** | Dashboard |
| **Severity** | warning |
| **User-Facing Message** | "This information was last updated [X] minutes ago. It will refresh automatically." |
| **Recovery Action** | User can manually refresh; auto-refresh continues in background |
| **Support Action** | Check data aggregation pipeline; verify cache freshness; check for pipeline backpressure |
| **Log Category** | `dash.data.stale` |
| **Internal Details** | Dashboard data aggregation is lagging behind the configured freshness threshold. The displayed data is served from cache and may not reflect the latest transactions or listings. Background cache warming is in progress. |

### DASH_WIDGET_FAILED

| Field | Value |
|-------|-------|
| **Error Code** | `DASH_WIDGET_FAILED` |
| **Category** | Dashboard |
| **Severity** | info |
| **User-Facing Message** | "This section is temporarily unavailable. The rest of your dashboard is working normally." |
| **Recovery Action** | Widget will auto-retry on next data refresh cycle |
| **Support Action** | Check which widget component failed; verify API endpoint for that widget; check React error boundary |
| **Log Category** | `dash.widget.failed` |
| **Internal Details** | An individual dashboard widget encountered a rendering or data-fetching error. The React error boundary has isolated the failure to this widget. Other widgets continue to function normally. The widget will attempt to re-render on the next data refresh cycle. |

---

## 8. Analytics Errors

### ANALYTICS_PIPELINE_DELAYED

| Field | Value |
|-------|-------|
| **Error Code** | `ANALYTICS_PIPELINE_DELAYED` |
| **Category** | Analytics |
| **Severity** | warning |
| **User-Facing Message** | "We're having trouble loading this information right now. Please try again shortly." |
| **Recovery Action** | User can refresh; cached data displayed with freshness indicator |
| **Support Action** | Check analytics pipeline lag; verify Celery worker health; check data warehouse connectivity |
| **Log Category** | `analytics.pipeline.delayed` |
| **Internal Details** | Analytics data processing pipeline is lagging behind the expected schedule. Current lag exceeds the 30-minute threshold. Aggregated data may not include the most recent transactions. Pipeline catch-up is in progress. |

### ANALYTICS_REPORT_FAILED

| Field | Value |
|-------|-------|
| **Error Code** | `ANALYTICS_REPORT_FAILED` |
| **Category** | Analytics |
| **Severity** | error |
| **User-Facing Message** | "Your report is being generated in the background. We'll notify you when it's ready." |
| **Recovery Action** | Report queued for async generation; user notified on completion |
| **Support Action** | Check Celery task queue; verify report generation worker; check dead-letter queue |
| **Log Category** | `analytics.report.failed` |
| **Internal Details** | Synchronous report generation failed (timeout or resource limit). The report has been queued for asynchronous generation via Celery. Up to 3 retry attempts will be made. If all retries fail, the report is moved to the dead-letter queue for manual generation. |

---

## 9. Admin Control Plane Errors

### ADMIN_DUAL_APPROVAL_UNAVAILABLE

| Field | Value |
|-------|-------|
| **Error Code** | `ADMIN_DUAL_APPROVAL_UNAVAILABLE` |
| **Category** | Admin |
| **Severity** | critical |
| **User-Facing Message** | "This action requires additional approval which isn't available right now. Please try again later." |
| **Recovery Action** | Admin retries later; non-critical actions deferred |
| **Support Action** | IMMEDIATE ESCALATION. Check dual-approval service health; consider emergency single-approval mode; ensure audit logging continues |
| **Log Category** | `admin.dual_approval.unavailable` |
| **Internal Details** | The dual-approval coordination service is unavailable. Sensitive admin actions that require dual approval are blocked. Emergency single-approval mode may be activated by a Super Admin with an incident ticket. All actions are still logged to the audit trail. |

### ADMIN_AUDIT_LOG_FAILURE

| Field | Value |
|-------|-------|
| **Error Code** | `ADMIN_AUDIT_LOG_FAILURE` |
| **Category** | Admin |
| **Severity** | critical |
| **User-Facing Message** | "This action is temporarily unavailable for security reasons. Please try again shortly." |
| **Recovery Action** | Admin retries; actions blocked until audit logging restored |
| **Support Action** | IMMEDIATE ESCALATION. Verify SIEM pipeline; check log buffer capacity; ensure no audit events are lost |
| **Log Category** | `admin.audit.failure` |
| **Internal Details** | The audit logging pipeline (SIEM integration) is unavailable. Admin actions that require audit trail are blocked as a compliance safeguard. Events are being buffered in-memory (ring buffer, 10K max). Recovery must flush the buffer to the SIEM. |

### ADMIN_SECRETS_VAULT_UNREACHABLE

| Field | Value |
|-------|-------|
| **Error Code** | `ADMIN_SECRETS_VAULT_UNREACHABLE` |
| **Category** | Admin |
| **Severity** | critical |
| **User-Facing Message** | "This action is temporarily unavailable for security reasons. Please try again shortly." |
| **Recovery Action** | Admin retries; operations requiring secrets are blocked |
| **Support Action** | IMMEDIATE ESCALATION. Check vault service health; verify cached credentials; ensure mandatory secrets rotation after recovery |
| **Log Category** | `admin.secrets.unreachable` |
| **Internal Details** | The secrets management vault is unreachable. Operations requiring live secrets (API keys, encryption keys) are blocked. Cached credentials may be used for up to 5 minutes beyond their TTL. Mandatory secrets rotation is required after vault recovery. |

---

## 10. File Upload Errors

### UPLOAD_STORAGE_UNAVAILABLE

| Field | Value |
|-------|-------|
| **Error Code** | `UPLOAD_STORAGE_UNAVAILABLE` |
| **Category** | File Uploads |
| **Severity** | error |
| **User-Facing Message** | "We couldn't upload your file right now. It's been saved and will be uploaded automatically." |
| **Recovery Action** | Upload queued for retry; no user action needed |
| **Support Action** | Check object storage circuit breaker; verify upload queue depth; monitor local buffer capacity |
| **Log Category** | `upload.storage.unavailable` |
| **Internal Details** | Object storage service is unavailable. The file has been buffered locally (up to 500MB total buffer) and queued for automatic upload when storage recovers. Circuit breaker is in open state with 30s recovery timeout. |

### UPLOAD_SCAN_PENDING

| Field | Value |
|-------|-------|
| **Error Code** | `UPLOAD_SCAN_PENDING` |
| **Category** | File Uploads |
| **Severity** | warning |
| **User-Facing Message** | "Your file has been uploaded and is being checked for security. It will be available once verified." |
| **Recovery Action** | No user action needed; file available after scan completes |
| **Support Action** | Check virus scan queue depth; verify scan service health; check for false positive patterns |
| **Log Category** | `upload.scan.pending` |
| **Internal Details** | File has been uploaded but is awaiting virus/security scanning. The scan service may be experiencing high load or may be temporarily unavailable. Files are quarantined until scan completes. Download is blocked until the file passes scanning. |

### UPLOAD_VALIDATION_FAILED

| Field | Value |
|-------|-------|
| **Error Code** | `UPLOAD_VALIDATION_FAILED` |
| **Category** | File Uploads |
| **Severity** | error |
| **User-Facing Message** | "This file couldn't be uploaded. Please check the file type and size requirements and try again." |
| **Recovery Action** | User uploads a different file; checks file requirements |
| **Support Action** | Verify file type/size limits; check validation rules; review for edge cases |
| **Log Category** | `upload.validation.failed` |
| **Internal Details** | File validation failed: unsupported file type, file exceeds size limit, or file content does not match declared type. Specific validation failure details are logged internally but never exposed to the user. |

---

## 11. Search Errors

### SEARCH_UNAVAILABLE

| Field | Value |
|-------|-------|
| **Error Code** | `SEARCH_UNAVAILABLE` |
| **Category** | Search |
| **Severity** | error |
| **User-Facing Message** | "Search results may be limited right now. You can still browse listings by category." |
| **Recovery Action** | User browses by category; database fallback search available |
| **Support Action** | Check Elasticsearch cluster health; verify circuit breaker state; monitor fallback query rate |
| **Log Category** | `search.unavailable` |
| **Internal Details** | Elasticsearch cluster is unavailable. Search has fallen back to database LIKE queries with limited results (10 per page, no faceted search, no autocomplete). Circuit breaker is in open state. Background reconnection attempts are ongoing. |

### SEARCH_INDEX_STALE

| Field | Value |
|-------|-------|
| **Error Code** | `SEARCH_INDEX_STALE` |
| **Category** | Search |
| **Severity** | warning |
| **User-Facing Message** | "Search results may not include the most recent listings. We're updating them now." |
| **Recovery Action** | User can browse by category for latest listings; index updating in background |
| **Support Action** | Check indexing pipeline lag; verify Celery indexing workers; trigger manual re-index if needed |
| **Log Category** | `search.index.stale` |
| **Internal Details** | Search index lag exceeds the 15-minute threshold. New listings and updates may not appear in search results. The indexing pipeline is catching up. A manual re-index trigger is available in the admin panel. |

---

## 12. User Profile Errors

### PROFILE_UPDATE_FAILED

| Field | Value |
|-------|-------|
| **Error Code** | `PROFILE_UPDATE_FAILED` |
| **Category** | User Profiles |
| **Severity** | warning |
| **User-Facing Message** | "We couldn't save your changes right now. They've been saved locally and will be applied shortly." |
| **Recovery Action** | Changes saved locally; retry in background; user notified on success |
| **Support Action** | Check profile service health; verify database write availability; check for validation issues |
| **Log Category** | `profile.update.failed` |
| **Internal Details** | Profile update persistence failed after 3 retry attempts. Changes have been stored in the frontend's localStorage and will be applied automatically when the service recovers. A reconciliation job runs every 5 minutes to apply pending changes. |

### PROFILE_KYC_PENDING

| Field | Value |
|-------|-------|
| **Error Code** | `PROFILE_KYC_PENDING` |
| **Category** | User Profiles |
| **Severity** | info |
| **User-Facing Message** | "Your verification documents have been received and are being processed. We'll notify you of the result." |
| **Recovery Action** | No user action needed; KYC processing continues in background |
| **Support Action** | Check KYC processing queue; verify document verification service; check for queue backlog |
| **Log Category** | `profile.kyc.pending` |
| **Internal Details** | KYC verification documents have been submitted and are awaiting processing. The verification service may be experiencing delays. The 7-day verification window applies. Users with pending KYC have limited access to high-value transactions. |

---

## 13. Settings Errors

### SETTINGS_SAVE_FAILED

| Field | Value |
|-------|-------|
| **Error Code** | `SETTINGS_SAVE_FAILED` |
| **Category** | Settings |
| **Severity** | warning |
| **User-Facing Message** | "Your settings have been saved locally. They'll be applied across all your devices shortly." |
| **Recovery Action** | Settings applied to current session; sync deferred |
| **Support Action** | Check settings persistence layer; verify cross-device sync service |
| **Log Category** | `settings.save.failed` |
| **Internal Details** | Settings persistence failed. Changes have been applied to the current session and stored in localStorage. A background sync job will apply changes to the server when the persistence layer recovers. |

---

## 14. External API Errors

### EXT_AI_PREDICTION_STALE

| Field | Value |
|-------|-------|
| **Error Code** | `EXT_AI_PREDICTION_STALE` |
| **Category** | External APIs |
| **Severity** | warning |
| **User-Facing Message** | "Price estimates may not reflect the latest market data. Please verify with a local agent." |
| **Recovery Action** | User consults agent for latest pricing; cached estimate displayed |
| **Support Action** | Check price prediction model health; verify training data pipeline; check model serving latency |
| **Log Category** | `ext.ai.stale` |
| **Internal Details** | The AI price prediction model is serving cached results because the model inference service is unavailable or the circuit breaker is open. Predictions are stale and may not reflect current market conditions. The model serving endpoint is being retried. |

### EXT_MAPS_UNAVAILABLE

| Field | Value |
|-------|-------|
| **Error Code** | `EXT_MAPS_UNAVAILABLE` |
| **Category** | External APIs |
| **Severity** | warning |
| **User-Facing Message** | "Map view is temporarily unavailable. You can still browse listings and view location details." |
| **Recovery Action** | User views text-based location details; map hidden |
| **Support Action** | Check geocoding API circuit breaker; verify API key validity; check quota limits |
| **Log Category** | `ext.maps.unavailable` |
| **Internal Details** | The maps/geocoding API is unavailable. Listing pages will display text-based location information instead of embedded maps. Distance calculations are unavailable. Geocoding results are cached for up to 7 days. |

---

## 15. Database Errors

### DB_PRIMARY_UNREACHABLE

| Field | Value |
|-------|-------|
| **Error Code** | `DB_PRIMARY_UNREACHABLE` |
| **Category** | Database |
| **Severity** | critical |
| **User-Facing Message** | "We're experiencing a temporary issue. You can browse listings, but some actions may be unavailable right now." |
| **Recovery Action** | Read-only mode enabled; writes queued; HA failover in progress |
| **Support Action** | IMMEDIATE ESCALATION. Trigger HA failover; check RDS instance health; verify standby promotion; monitor write buffer |
| **Log Category** | `db.primary.unreachable` |
| **Internal Details** | Primary database instance is unreachable. HA automatic failover should occur within 30 seconds. All write operations are queued in the application buffer. Read operations are redirected to the replica. Write buffer capacity: 10,000 operations with TTL of 1 hour. |

### DB_REPLICA_LAG

| Field | Value |
|-------|-------|
| **Error Code** | `DB_REPLICA_LAG` |
| **Category** | Database |
| **Severity** | warning |
| **User-Facing Message** | "Some information may be slightly out of date. It will refresh shortly." |
| **Recovery Action** | No user action needed; data auto-refreshes when replica catches up |
| **Support Action** | Monitor replication lag; redirect critical reads to primary if lag > 30s; alert DBA if lag persists |
| **Log Category** | `db.replica.lag` |
| **Internal Details** | Read replica lag exceeds the 10-second threshold. Users may see slightly stale data for up to 60 seconds. Critical reads (payment status, settlement status) are redirected to the primary. The replica is catching up. |

### DB_POOL_EXHAUSTED

| Field | Value |
|-------|-------|
| **Error Code** | `DB_POOL_EXHAUSTED` |
| **Category** | Database |
| **Severity** | error |
| **User-Facing Message** | "We're experiencing high demand. Please try again in a moment." |
| **Recovery Action** | User retries after a short delay; connection pool recycles |
| **Support Action** | Check connection pool utilization; kill long-running queries; increase pool size; scale read replicas |
| **Log Category** | `db.pool.exhausted` |
| **Internal Details** | Database connection pool is at > 80% utilization. Non-critical requests are being rejected with 503 status. Critical operations (payments, direct settlements) are prioritized. Long-running queries (> 10s) are being terminated. Pool auto-scaling may be triggered. |

---

## 16. Cache Errors

### CACHE_UNAVAILABLE

| Field | Value |
|-------|-------|
| **Error Code** | `CACHE_UNAVAILABLE` |
| **Category** | Cache |
| **Severity** | error |
| **User-Facing Message** | "We're having trouble loading this information right now. Please try again shortly." |
| **Recovery Action** | User retries; direct database queries serve requests (slower) |
| **Support Action** | Check ElastiCache cluster health; verify circuit breaker state; monitor database load increase |
| **Log Category** | `cache.unavailable` |
| **Internal Details** | The cache cluster (ElastiCache) is unreachable. All cache reads are falling through to the database. In-process LRU cache (max 1000 entries, 60s TTL) serves as an L2 fallback. Database load will increase significantly. Rate limiting may be applied to prevent database overload. |

### CACHE_STAMPEDE

| Field | Value |
|-------|-------|
| **Error Code** | `CACHE_STAMPEDE` |
| **Category** | Cache |
| **Severity** | warning |
| **User-Facing Message** | "We're experiencing high demand. Pages may load more slowly than usual." |
| **Recovery Action** | No user action needed; stampede protection active |
| **Support Action** | Monitor cache miss rate; verify stampede protection (single-flight pattern); check for TTL mass-expiration |
| **Log Category** | `cache.stampede` |
| **Internal Details** | Cache stampede detected: cache miss rate exceeds 50%. The single-flight pattern is coalescing duplicate requests. Jittered TTLs are being applied to prevent mass-expiration. Background cache warming is in progress with priority queuing. |

---

## 17. WebSocket Errors

### WS_CONNECTION_LOST

| Field | Value |
|-------|-------|
| **Error Code** | `WS_CONNECTION_LOST` |
| **Category** | WebSocket |
| **Severity** | warning |
| **User-Facing Message** | "You've been disconnected. We're reconnecting you automatically." |
| **Recovery Action** | Auto-reconnect in progress; messages buffered |
| **Support Action** | Monitor reconnection success rate; check WebSocket server health; verify message buffer capacity |
| **Log Category** | `ws.connection.lost` |
| **Internal Details** | WebSocket connection dropped. Auto-reconnect is attempting with exponential backoff (1s, 2s, 4s, 8s, max 60s, up to 10 attempts). Missed messages are buffered server-side (last 100 messages, 5-minute window). Sequence number reconciliation occurs on reconnect. |

### WS_FALLBACK_POLLING

| Field | Value |
|-------|-------|
| **Error Code** | `WS_FALLBACK_POLLING` |
| **Category** | WebSocket |
| **Severity** | info |
| **User-Facing Message** | "Live updates are temporarily paused. You'll still receive all updates, just with a slight delay." |
| **Recovery Action** | HTTP long-polling active; 10s polling interval |
| **Support Action** | Monitor WebSocket availability; check for transport upgrade opportunities |
| **Log Category** | `ws.fallback.polling` |
| **Internal Details** | WebSocket connection could not be established. The client has fallen back to HTTP long-polling with a 10-second interval. Reduced event set (typing indicators omitted). Automatic transport upgrade will be attempted when the WebSocket endpoint becomes available. |

---

## 18. Background Job Errors

### JOB_WORKER_EXHAUSTED

| Field | Value |
|-------|-------|
| **Error Code** | `JOB_WORKER_EXHAUSTED` |
| **Category** | Background Jobs |
| **Severity** | error |
| **User-Facing Message** | "Your request is being processed. It may take longer than usual due to high demand." |
| **Recovery Action** | No user action needed; task queued; priority processing for critical tasks |
| **Support Action** | Scale Celery workers; terminate stuck tasks (> 30 min); check task queue depth; verify broker health |
| **Log Category** | `job.worker.exhausted` |
| **Internal Details** | Celery worker pool utilization exceeds 80%. Low-priority tasks (analytics, reports, CRM sync) have been paused. Critical tasks (payments, direct settlements, notifications) are processed with priority. Auto-scaling may increase worker count. Stuck tasks (> 30 min execution) are terminated. |

### JOB_TASK_DEAD_LETTERED

| Field | Value |
|-------|-------|
| **Error Code** | `JOB_TASK_DEAD_LETTERED` |
| **Category** | Background Jobs |
| **Severity** | error |
| **User-Facing Message** | "We couldn't complete this action automatically. Our team has been notified and will handle it shortly." |
| **Recovery Action** | No user action needed; admin team notified; manual retry available |
| **Support Action** | Review dead-letter queue; check task failure details; retry from admin panel; investigate root cause |
| **Log Category** | `job.task.dead_lettered` |
| **Internal Details** | A Celery task has been moved to the dead-letter queue after all retry attempts were exhausted. The task type, arguments, and original error are stored in the DLQ. Admin panel provides a retry UI. Non-idempotent tasks require manual investigation before retry. |

### JOB_BROKER_UNREACHABLE

| Field | Value |
|-------|-------|
| **Error Code** | `JOB_BROKER_UNREACHABLE` |
| **Category** | Background Jobs |
| **Severity** | critical |
| **User-Facing Message** | "Your request is being processed. It may take longer than usual." |
| **Recovery Action** | Critical tasks processed synchronously; non-critical tasks queued locally |
| **Support Action** | IMMEDIATE ESCALATION. Check broker (Redis/RabbitMQ) health; trigger HA failover; verify synchronous fallback is working |
| **Log Category** | `job.broker.unreachable` |
| **Internal Details** | The Celery message broker is unreachable. Critical tasks (payments, direct settlements) are being processed synchronously within the web request. Non-critical tasks are buffered locally. Broker HA failover should occur within 30 seconds. All task states are tracked in the database as a fallback. |

---

## 19. Rate Limiting Errors

### RATE_LIMIT_EXCEEDED

| Field | Value |
|-------|-------|
| **Error Code** | `RATE_LIMIT_EXCEEDED` |
| **Category** | Rate Limiting |
| **Severity** | warning |
| **User-Facing Message** | "You're making requests too quickly. Please wait a moment and try again." |
| **Recovery Action** | User waits and retries; `Retry-After` header provided |
| **Support Action** | Verify rate limit configuration; check for abnormal traffic patterns; adjust limits if needed |
| **Log Category** | `rate.limit.exceeded` |
| **Internal Details** | API rate limit exceeded for this user/IP. The `Retry-After` header indicates when the user may retry. Rate limits are configured per endpoint and per user tier. Sustained rate limit violations may indicate abuse or misconfigured clients. |

---

## 20. Validation Errors

### VAL_INVALID_INPUT

| Field | Value |
|-------|-------|
| **Error Code** | `VAL_INVALID_INPUT` |
| **Category** | Validation |
| **Severity** | error |
| **User-Facing Message** | "Please check the information you entered and try again." |
| **Recovery Action** | User corrects input based on field-level error messages |
| **Support Action** | Check validation rules; verify serializer configuration; review field-level error messages |
| **Log Category** | `val.invalid_input` |
| **Internal Details** | Input validation failed. Field-level errors are provided in the API response body (e.g., `{"phone": ["Enter a valid Kenyan phone number."]}`). Validation rule details are logged internally but generic messages are shown to users. Never expose internal validation patterns or regex. |

---

## 21. Platform Errors

### PLAT_MAINTENANCE_MODE

| Field | Value |
|-------|-------|
| **Error Code** | `PLAT_MAINTENANCE_MODE` |
| **Category** | Platform |
| **Severity** | warning |
| **User-Facing Message** | "We're performing scheduled maintenance. We'll be back shortly. Thank you for your patience." |
| **Recovery Action** | User waits; status page shows estimated completion |
| **Support Action** | Verify maintenance window schedule; update status page; monitor progress |
| **Log Category** | `plat.maintenance` |
| **Internal Details** | Platform has been placed in maintenance mode by an administrator. All API requests return 503 with a maintenance message. The status page reflects the current maintenance window. Estimated completion time is configurable. |

### PLAT_DEGRADED_MODE

| Field | Value |
|-------|-------|
| **Error Code** | `PLAT_DEGRADED_MODE` |
| **Category** | Platform |
| **Severity** | warning |
| **User-Facing Message** | "Some features may be temporarily limited. We're working on restoring full service." |
| **Recovery Action** | User can continue using available features; degraded features clearly indicated |
| **Support Action** | Check current degradation tier; verify affected services; monitor recovery progress |
| **Log Category** | `plat.degraded` |
| **Internal Details** | Platform is operating in a degraded tier (Tier 2 or Tier 3). The current tier level and affected domains are stored in the degradation state service. Features are progressively re-enabled as services recover. |

### PLAT_UNKNOWN_ERROR

| Field | Value |
|-------|-------|
| **Error Code** | `PLAT_UNKNOWN_ERROR` |
| **Category** | Platform |
| **Severity** | error |
| **User-Facing Message** | "Something went wrong. Please try again. If the problem continues, contact support." |
| **Recovery Action** | User retries; if persistent, contacts support |
| **Support Action** | Check error logs for unhandled exceptions; review Sentry for new error patterns; investigate root cause |
| **Log Category** | `plat.unknown` |
| **Internal Details** | An unhandled exception occurred. The error has been logged with full stack trace and context to the structured logging pipeline and Sentry. This is a catch-all error that should be investigated and mapped to a specific error code. |

---

## Error Response Format

All API errors follow a consistent JSON response format:

```json
{
  "error": {
    "code": "PAY_PROCESSING_DELAYED",
    "message": "Your request is being processed. We'll update you as soon as it's completed.",
    "severity": "warning",
    "category": "Payments",
    "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "retryable": true,
    "details": {}
  }
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `error.code` | string | Machine-readable error code from this catalog |
| `error.message` | string | User-safe message (never contains technical details) |
| `error.severity` | string | One of: `critical`, `error`, `warning`, `info` |
| `error.category` | string | Domain category from this catalog |
| `error.request_id` | string | UUID for tracing and support lookup |
| `error.retryable` | boolean | Whether the client may safely retry the request |
| `error.details` | object | Optional field-level errors or additional context (never technical) |

### HTTP Status Code Mapping

| Severity | Default HTTP Status |
|----------|-------------------|
| critical | 503 Service Unavailable |
| error | 400 Bad Request / 500 Internal Server Error |
| warning | 200 OK (with warning in response) / 202 Accepted |
| info | 200 OK |

---

## Error Handling Implementation Checklist

- [ ] All backend exceptions map to error codes from this catalog
- [ ] Frontend displays user-safe messages from `error.message` field
- [ ] Frontend never displays `error.code` directly to users (used for internal routing only)
- [ ] Sentry configured to group by error code for alerting
- [ ] Structured logging includes error code, category, severity, and request_id
- [ ] Error responses never include stack traces or internal details
- [ ] All external service errors are wrapped before API response
- [ ] Rate limiting errors include `Retry-After` header
- [ ] Frontend error boundaries catch rendering errors gracefully
- [ ] Mobile app respects the same error message format

---

*This error catalog is a living document. New error codes must be added via PR with review from Platform Engineering and Security. Next review date: 2025-06-04.*
