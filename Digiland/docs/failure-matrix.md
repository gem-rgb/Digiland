# Digiland Failure Matrix

> **Phase 1 — Graceful Degradation System**
> Version: 1.0.0 | Last Updated: 2025-03-04 | Owner: Platform Engineering

## Purpose

This document maps every foreseeable failure scenario across all Digiland platform domains. For each failure, it defines the impact level, fallback behavior, recovery strategy, user-safe messaging, and monitoring approach. This matrix drives the implementation of circuit breakers, fallback UI states, and operational runbooks.

## Impact Severity Definitions

| Level | Definition | SLA Target | Example |
|-------|-----------|------------|---------|
| **Critical** | Revenue loss, data corruption, or safety risk; platform unusable for core flows | < 5 min detection, < 30 min resolution | Payment processing down, escrow lockout |
| **High** | Major feature unavailable; users cannot complete key workflows | < 15 min detection, < 2 hr resolution | Search down, notifications failed |
| **Medium** | Degraded experience; workarounds exist | < 30 min detection, < 8 hr resolution | Analytics delayed, ads not loading |
| **Low** | Minor inconvenience; cosmetic or non-essential feature | < 1 hr detection, < 24 hr resolution | Price prediction stale, avatar upload slow |

## User Message Guidelines

All user-facing messages in this matrix follow these principles:

1. **No technical details** — never expose stack traces, SQL errors, DB/table names, internal service names, infrastructure details, provider names, API endpoints, network topology, auth mechanisms, or security controls
2. **Action-oriented** — tell the user what they can do, not what went wrong
3. **Empathetic tone** — acknowledge the inconvenience
4. **Consistent format** — "We're having trouble [action]. [Guidance]."

---

## 1. Authentication

| Attribute | Failure 1 | Failure 2 | Failure 3 |
|-----------|-----------|-----------|-----------|
| **Failure Type** | Session/token expiry | OAuth provider unreachable | MFA service unavailable |
| **Impact** | Medium | High | High |
| **Fallback Behavior** | Redirect to login page; preserve form state via localStorage | Fall back to email/password login; hide OAuth buttons | Allow login with recovery codes; queue MFA setup for later |
| **Recovery Strategy** | Auto-refresh via refresh token; if refresh fails, force re-login with rotation | Circuit breaker with 30s recovery; retry OAuth on next login attempt | Circuit breaker with 60s recovery; generate temporary bypass token for admin users only |
| **User Message** | "Your session has ended. Please sign in again to continue." | "That sign-in method isn't available right now. Please use your email and password instead." | "We couldn't complete the extra verification step. Please use one of your recovery codes to sign in." |
| **Monitoring Strategy** | Track token refresh failure rate; alert on > 5% refresh failure; Grafana panel `auth_token_refresh_failures` | Track OAuth provider response time and error rate; PagerDuty alert on circuit open; Grafana panel `auth_oauth_circuit_state` | Track MFA verification success rate; alert on > 10% MFA failure; Grafana panel `auth_mfa_availability` |

## 2. Authorization

| Attribute | Failure 1 | Failure 2 | Failure 3 |
|-----------|-----------|-----------|-----------|
| **Failure Type** | Permission check timeout | Role/permission cache miss | Tenant isolation failure |
| **Impact** | High | Medium | Critical |
| **Fallback Behavior** | Deny by default; show "insufficient permissions" rather than granting access | Re-evaluate from source; allow read access with cached role during recompute | Block all access; redirect to support page; log security incident |
| **Recovery Strategy** | Retry permission check once; if timeout persists, fall back to cached permissions with TTL extension | Background cache warming; serve stale permissions for up to 5 min | Immediate page lockout; trigger security audit; require admin re-authentication |
| **User Message** | "We couldn't verify your access right now. Please try again in a moment." | "Some features may be temporarily limited. Please refresh the page if something seems off." | "For your security, access has been temporarily restricted. Please contact support if this persists." |
| **Monitoring Strategy** | Track permission evaluation latency (p99); alert on > 500ms; Grafana panel `authz_eval_latency` | Track cache hit ratio; alert on < 80% hit rate; Grafana panel `authz_cache_hit_rate` | Track tenant boundary violations; immediate PagerDuty on any cross-tenant data access; Grafana panel `authz_tenant_violations` |

## 3. Payments

| Attribute | Failure 1 | Failure 2 | Failure 3 | Failure 4 |
|-----------|-----------|-----------|-----------|-----------|
| **Failure Type** | M-Pesa STK push timeout | Stripe API unreachable | Paystack webhook delivery failure | Escrow hold/release failure |
| **Impact** | Critical | Critical | Critical | Critical |
| **Fallback Behavior** | Queue payment for async processing; show "processing" status; send SMS confirmation when complete | Fall back to Paystack as alternate provider; if both down, queue and notify | Store webhook events in local buffer; replay on recovery; mark transactions as "pending verification" | Lock escrow state; prevent double-spend; queue release for retry; manual admin override with dual approval |
| **Recovery Strategy** | Circuit breaker (failure_threshold=3, recovery_timeout=30s); poll M-Pesa callback endpoint for up to 10 min; mark failed after 3 async retries | Circuit breaker per provider; automatic failover to alternate provider; manual reconciliation queue | Dead-letter queue for failed webhooks; hourly retry batch; manual reconciliation dashboard for finance team | Database-level transaction lock; compensating transaction pattern; admin dual-approval for manual override |
| **User Message** | "Your request is being processed. We'll update you as soon as it's completed." | "Your request is being processed. We'll update you as soon as it's completed." | "Your payment is being verified. This may take a few minutes." | "This transaction is being securely processed. We'll notify you once it's confirmed." |
| **Monitoring Strategy** | Track STK push success rate; alert on < 95% within 30s; track callback latency; Grafana panel `payments_mpesa_stk_success` | Track per-provider circuit state and error rates; PagerDuty on circuit open; Grafana panel `payments_provider_circuits` | Track webhook delivery success rate; alert on > 5% delivery failure; Grafana panel `payments_webhook_health` | Track escrow state machine violations; immediate PagerDuty on anomaly; Grafana panel `payments_escrow_integrity` |

## 4. Withdrawals

| Attribute | Failure 1 | Failure 2 | Failure 3 |
|-----------|-----------|-----------|-----------|
| **Failure Type** | Bank disbursement timeout | Insufficient escrow balance for withdrawal | Fraud detection service down during withdrawal |
| **Impact** | Critical | Critical | High |
| **Fallback Behavior** | Queue withdrawal for retry; hold funds in escrow; send "pending" notification | Block withdrawal; show clear balance discrepancy message; alert finance team | Allow withdrawal with manual fraud review flag; queue for post-hoc screening |
| **Recovery Strategy** | Circuit breaker (failure_threshold=3, recovery_timeout=60s); retry up to 3 times with exponential backoff (5m, 15m, 60m); manual settlement queue | Reconcile escrow ledger; admin dual-approval override; automated balance check before release | Circuit breaker with 120s recovery; flag all withdrawals during outage for manual review within 4 hours |
| **User Message** | "Your withdrawal is being processed. You'll receive a notification once it's complete." | "We're unable to process this withdrawal right now. Please try again later or contact support." | "Your withdrawal request has been received and is being reviewed. We'll update you shortly." |
| **Monitoring Strategy** | Track disbursement success rate and latency; alert on > 2% failure; Grafana panel `withdrawals_disbursement_health` | Track escrow balance discrepancies; alert on any negative balance; Grafana panel `withdrawals_escrow_balance` | Track fraud service availability; alert on circuit open; track flagged review queue depth; Grafana panel `withdrawals_fraud_service` |

## 5. Notifications

| Attribute | Failure 1 | Failure 2 | Failure 3 |
|-----------|-----------|-----------|-----------|
| **Failure Type** | SMS gateway (Africa's Talking) down | Email service unavailable | Push notification service failure |
| **Impact** | Medium | Medium | Low |
| **Fallback Behavior** | Queue SMS in database; attempt email as alternate channel; retry batch every 5 min | Queue emails in database; attempt in-app notification as alternate; retry batch every 10 min | Queue push notifications; rely on in-app notification center as fallback |
| **Recovery Strategy** | Circuit breaker (failure_threshold=5, recovery_timeout=30s); dead-letter queue after 10 retries; fall back to email channel | Circuit breaker (failure_threshold=5, recovery_timeout=60s); dead-letter queue after 5 retries; fall back to in-app | Circuit breaker (failure_threshold=10, recovery_timeout=60s); auto-retry with 5-min backoff |
| **User Message** | "We're having trouble sending you a notification right now. You can check your updates in the app." | "We're having trouble sending you an email right now. Please check your notifications in the app." | N/A (silent degradation; in-app notification center serves as fallback) |
| **Monitoring Strategy** | Track SMS delivery rate; alert on < 90% delivery within 5 min; Grafana panel `notif_sms_delivery` | Track email delivery rate; alert on < 95% delivery within 10 min; Grafana panel `notif_email_delivery` | Track push delivery rate; alert on < 85% delivery within 2 min; Grafana panel `notif_push_delivery` |

## 6. Messaging

| Attribute | Failure 1 | Failure 2 | Failure 3 |
|-----------|-----------|-----------|-----------|
| **Failure Type** | Real-time message delivery failure | Message persistence failure | Attachment upload failure in chat |
| **Impact** | Medium | High | Medium |
| **Fallback Behavior** | Show "sending" indicator; queue message locally; deliver on reconnect; show "delivered" on confirmation | Show "message saved" optimistic UI; retry persistence in background; notify user if permanently failed | Allow text-only message; queue attachment for background upload; show attachment placeholder |
| **Recovery Strategy** | Automatic reconnect with exponential backoff (1s, 2s, 4s, 8s, max 60s); message deduplication on delivery | Retry persistence 3 times with backoff; mark message as "unsent" on permanent failure; allow manual resend | Circuit breaker for storage service; retry upload 3 times; allow retry from message UI |
| **User Message** | "Your message is being sent. It will arrive once the connection is restored." | "We couldn't deliver your message. Please try sending it again." | "We couldn't attach this file right now. Your message was sent without the attachment." |
| **Monitoring Strategy** | Track WebSocket connection stability and message delivery latency; alert on > 5% undelivered within 30s; Grafana panel `msg_delivery_rate` | Track message persistence success rate; alert on any data loss; Grafana panel `msg_persistence_health` | Track attachment upload success rate; alert on < 95% success; Grafana panel `msg_attachment_uploads` |

## 7. Dashboard

| Attribute | Failure 1 | Failure 2 | Failure 3 |
|-----------|-----------|-----------|-----------|
| **Failure Type** | Dashboard data aggregation timeout | Real-time dashboard stats stale | Widget rendering failure |
| **Impact** | Medium | Low | Low |
| **Fallback Behavior** | Show cached dashboard from last successful load; display "Data as of [timestamp]" banner; allow manual refresh | Show last known values with "Updated [X] min ago" label; auto-refresh every 60s | Hide failed widget; show remaining widgets; display "This section is temporarily unavailable" |
| **Recovery Strategy** | Circuit breaker on aggregation service (failure_threshold=5, recovery_timeout=30s); serve cached version for up to 10 min; background refresh | Cache warming every 60s; fall back to direct DB query for critical metrics; graceful cache expiration | Component-level error boundary in React; isolate widget failures; auto-retry render on next data refresh |
| **User Message** | "We're having trouble loading this information right now. Please try again shortly." | "This information was last updated [X] minutes ago. It will refresh automatically." | "This section is temporarily unavailable. The rest of your dashboard is working normally." |
| **Monitoring Strategy** | Track dashboard load time (p95); alert on > 5s; Grafana panel `dashboard_load_latency` | Track data freshness; alert on > 10 min stale; Grafana panel `dashboard_data_freshness` | Track widget error rate per component; alert on > 10% widget failures; Grafana panel `dashboard_widget_errors` |

## 8. Analytics

| Attribute | Failure 1 | Failure 2 | Failure 3 |
|-----------|-----------|-----------|-----------|
| **Failure Type** | Analytics pipeline processing delay | Report generation timeout | Historical data query failure |
| **Impact** | Medium | Medium | Low |
| **Fallback Behavior** | Show cached analytics; display "Data as of [timestamp]" banner; reduce granularity (daily instead of hourly) | Queue report for background generation; email when ready; show estimated completion time | Show cached historical data; reduce date range; suggest smaller query scope |
| **Recovery Strategy** | Circuit breaker (failure_threshold=5, recovery_timeout=60s); auto-reduce granularity; background pipeline catch-up | Async report generation with Celery; 3 retry attempts; dead-letter after exhaustion; manual generation link | Circuit breaker on analytics DB; fall back to summary tables; cache frequently queried ranges |
| **User Message** | "We're having trouble loading this information right now. Please try again shortly." | "Your report is being generated and will be ready soon. We'll send you a notification when it's done." | "We couldn't load the full history. Try selecting a shorter date range for better results." |
| **Monitoring Strategy** | Track pipeline lag; alert on > 30 min delay; Grafana panel `analytics_pipeline_lag` | Track report generation success rate and time; alert on > 10% failure; Grafana panel `analytics_report_gen` | Track query latency and failure rate; alert on > 20% failure; Grafana panel `analytics_query_health` |

## 9. Admin Control Plane

| Attribute | Failure 1 | Failure 2 | Failure 3 |
|-----------|-----------|-----------|-----------|
| **Failure Type** | Dual-approval service unavailable | SIEM/logging pipeline down | Secrets vault unreachable |
| **Impact** | Critical | Critical | Critical |
| **Fallback Behavior** | Block sensitive admin actions requiring approval; allow read-only admin access; queue approval requests | Buffer audit events locally (in-memory ring buffer, 10K events max); continue operations with local logging | Block operations requiring secrets; use cached secrets with extended TTL; alert security team |
| **Recovery Strategy** | Circuit breaker (failure_threshold=2, recovery_timeout=30s); emergency single-approval mode with Super Admin only (requires incident ticket) | Local buffer flush on recovery; no event loss guarantee for < 10K events; PagerDuty immediate escalation | Circuit breaker (failure_threshold=2, recovery_timeout=15s); cached credentials valid for 5 min beyond TTL; mandatory secrets rotation after recovery |
| **User Message** | "This action requires additional approval which isn't available right now. Please try again later." | N/A (admin-only; no external user impact) | "This action is temporarily unavailable for security reasons. Please try again shortly." |
| **Monitoring Strategy** | Track dual-approval service latency and availability; immediate PagerDuty on circuit open; Grafana panel `admin_dual_approval_health` | Track log pipeline throughput; alert on > 10s lag; track buffer utilization; Grafana panel `admin_siem_pipeline` | Track vault access latency; immediate PagerDuty on vault unreachable; track secret TTL expirations; Grafana panel `admin_vault_health` |

## 10. File Uploads

| Attribute | Failure 1 | Failure 2 | Failure 3 |
|-----------|-----------|-----------|-----------|
| **Failure Type** | Object storage (S3) unavailable | File validation service timeout | Virus scan service failure |
| **Impact** | High | Medium | High |
| **Fallback Behavior** | Queue uploads locally; retry with exponential backoff; show upload progress with "pending" status | Allow upload with "pending verification" status; process validation asynchronously | Quarantine files; allow upload with "pending scan" status; block download until scan completes |
| **Recovery Strategy** | Circuit breaker (failure_threshold=5, recovery_timeout=30s); local buffer up to 500MB total; auto-upload on recovery | Process validation in Celery worker; retry 3 times; mark invalid files for admin review after 24h | Circuit breaker (failure_threshold=5, recovery_timeout=60s); mandatory scan before download; admin override for known-safe files |
| **User Message** | "We're having trouble uploading your file. It's been saved and will be uploaded automatically." | "Your file has been uploaded and is being verified. We'll let you know once it's ready." | "Your file has been uploaded and is being checked for security. It will be available once verified." |
| **Monitoring Strategy** | Track upload success rate; alert on < 98% success; track queue depth; Grafana panel `uploads_storage_health` | Track validation queue depth and processing time; alert on > 1000 pending; Grafana panel `uploads_validation_queue` | Track scan completion rate; alert on > 100 unscanned files; Grafana panel `uploads_scan_health` |

## 11. Search

| Attribute | Failure 1 | Failure 2 | Failure 3 |
|-----------|-----------|-----------|-----------|
| **Failure Type** | Search engine (Elasticsearch) unavailable | Search index stale/out of sync | Search query timeout |
| **Impact** | High | Medium | Medium |
| **Fallback Behavior** | Fall back to database LIKE queries with limited results; show banner "Limited search results"; reduce result count to 10 | Show results with "Last indexed [X] min ago" banner; accept that newest listings may not appear; continue indexing in background | Return partial results; suggest filters to narrow search; show cached results if available |
| **Recovery Strategy** | Circuit breaker (failure_threshold=5, recovery_timeout=30s); database fallback with pagination; background reconnection attempts | Continuous indexing pipeline; catch-up indexing on recovery; manual re-index trigger in admin | Query timeout reduction (5s → 2s); circuit breaker per-shard; fall back to cached popular queries |
| **User Message** | "Search results may be limited right now. You can still browse listings by category." | "Search results may not include the most recent listings. We're updating them now." | "We're having trouble finding results right now. Try narrowing your search or check back shortly." |
| **Monitoring Strategy** | Track search availability; alert on circuit open; track fallback query rate; Grafana panel `search_availability` | Track index lag; alert on > 15 min stale; track indexing error rate; Grafana panel `search_index_freshness` | Track query latency (p95); alert on > 3s; track timeout rate; Grafana panel `search_query_latency` |

## 12. User Profiles

| Attribute | Failure 1 | Failure 2 | Failure 3 |
|-----------|-----------|-----------|-----------|
| **Failure Type** | Profile update failure | KYC verification service down | Avatar/profile image upload failure |
| **Impact** | Medium | High | Low |
| **Fallback Behavior** | Show last saved profile; queue update for retry; display "Changes not yet saved" indicator | Queue KYC submissions; allow platform use with "verification pending" status; limit high-risk operations | Show placeholder avatar; queue image upload; show "Updating" status on profile |
| **Recovery Strategy** | Retry update 3 times with backoff; fall back to cached profile; notify user on permanent failure | Circuit breaker (failure_threshold=5, recovery_timeout=60s); process queue on recovery; 7-day verification window | Same as File Uploads domain; retry with exponential backoff |
| **User Message** | "We couldn't save your changes right now. They've been saved locally and will be applied shortly." | "Your verification documents have been received and are being processed. We'll notify you of the result." | "Your profile picture is being updated. It may take a moment to appear." |
| **Monitoring Strategy** | Track profile update success rate; alert on < 95% success; Grafana panel `profiles_update_health` | Track KYC processing queue depth and age; alert on > 500 pending or > 24h oldest; Grafana panel `profiles_kyc_queue` | Track image upload success rate; alert on < 95% success; Grafana panel `profiles_image_uploads` |

## 13. Settings

| Attribute | Failure 1 | Failure 2 | Failure 3 |
|-----------|-----------|-----------|-----------|
| **Failure Type** | Settings persistence failure | Notification preferences sync failure | Multi-tenancy settings propagation delay |
| **Impact** | Medium | Low | Medium |
| **Fallback Behavior** | Apply settings locally (in-memory); show "unsaved changes" warning; retry in background | Apply preference changes to local state; queue sync; show "Preferences saved locally" | Apply settings to current session; queue propagation to all tenant services; show "Applying..." status |
| **Recovery Strategy** | Retry persistence 3 times; fall back to localStorage on frontend; reconcile on recovery | Circuit breaker (failure_threshold=5, recovery_timeout=30s); batch sync on recovery; manual refresh trigger | Async propagation with Celery; retry up to 5 times; manual "apply everywhere" button in admin |
| **User Message** | "Your settings have been saved locally. They'll be applied across all your devices shortly." | "Your notification preferences have been updated. It may take a few minutes to take full effect." | "Your settings have been saved. They're being applied across the platform and may take a moment." |
| **Monitoring Strategy** | Track settings write success rate; alert on < 99% success; Grafana panel `settings_persistence_health` | Track preferences sync latency; alert on > 5 min delay; Grafana panel `settings_prefs_sync` | Track tenant settings propagation time; alert on > 10 min delay; Grafana panel `settings_tenant_propagation` |

## 14. Reporting

| Attribute | Failure 1 | Failure 2 | Failure 3 |
|-----------|-----------|-----------|-----------|
| **Failure Type** | Report generation engine failure | Scheduled report delivery failure | Data export timeout |
| **Impact** | Medium | Medium | Low |
| **Fallback Behavior** | Queue report for async generation; show estimated time; offer email delivery | Queue for retry; show "pending" in report history; attempt alternate delivery channel | Reduce export scope; offer paginated download; suggest smaller date range |
| **Recovery Strategy** | Celery task retry (3 attempts, exponential backoff); dead-letter after exhaustion; manual generation fallback | Retry delivery 3 times (email → in-app → SMS link); dead-letter after exhaustion; admin report dashboard | Circuit breaker on export endpoint; chunked export for large datasets; background processing with download link |
| **User Message** | "Your report is being generated in the background. We'll notify you when it's ready." | "Your scheduled report couldn't be delivered. You can download it from your report history." | "This export is taking longer than expected. We'll prepare it and send you a download link." |
| **Monitoring Strategy** | Track report generation success rate and time; alert on > 10% failure or > 10 min generation; Grafana panel `reporting_gen_health` | Track scheduled report delivery success; alert on > 5% delivery failure; Grafana panel `reporting_delivery_health` | Track export timeout rate; alert on > 10% timeout; Grafana panel `reporting_export_health` |

## 15. External APIs

| Attribute | Failure 1 | Failure 2 | Failure 3 | Failure 4 |
|-----------|-----------|-----------|-----------|-----------|
| **Failure Type** | Maps/ geocoding service down | AI price prediction model failure | CRM integration failure | ERP/accounting sync failure |
| **Impact** | Medium | Medium | Low | Medium |
| **Fallback Behavior** | Show listings without map view; hide distance calculations; allow text-based location search | Show last cached price estimates; display "Estimate as of [date]" banner; hide prediction confidence | Queue CRM events; batch sync on recovery; no user-facing impact | Queue accounting entries; batch sync on recovery; allow platform use with "sync pending" status |
| **Recovery Strategy** | Circuit breaker (failure_threshold=5, recovery_timeout=30s); cache geocoding results for 7 days; fall back to centroid-based display | Circuit breaker (failure_threshold=3, recovery_timeout=120s); serve stale model predictions; flag for manual re-estimation on recovery | Circuit breaker (failure_threshold=5, recovery_timeout=60s); dead-letter queue; reconciliation job on recovery | Circuit breaker (failure_threshold=5, recovery_timeout=120s); idempotent sync on recovery; reconciliation dashboard for finance |
| **User Message** | "Map view is temporarily unavailable. You can still browse listings and view location details." | "Price estimates may not reflect the latest market data. Please verify with a local agent." | N/A (no direct user impact) | "Some financial records may be temporarily out of sync. They will be updated shortly." |
| **Monitoring Strategy** | Track geocoding success rate; alert on circuit open; cache hit ratio monitoring; Grafana panel `extapi_maps_health` | Track model inference latency and error rate; alert on circuit open; track stale prediction count; Grafana panel `extapi_ai_prediction` | Track CRM sync queue depth and error rate; alert on > 1000 queued; Grafana panel `extapi_crm_sync` | Track ERP sync latency and error rate; alert on > 1hr lag; Grafana panel `extapi_erp_sync` |

## 16. Database Access

| Attribute | Failure 1 | Failure 2 | Failure 3 |
|-----------|-----------|-----------|-----------|
| **Failure Type** | Primary database unreachable | Read replica lag/stale reads | Connection pool exhaustion |
| **Impact** | Critical | Medium | High |
| **Fallback Behavior** | Switch to read replica for read operations; block all writes; show "read-only mode" banner; queue writes in application buffer | Serve slightly stale data with "Data as of [timestamp]" banner; redirect critical reads to primary; alert on significant lag | Queue requests; apply connection throttle; reject non-critical requests with 503; prioritize payment and escrow operations |
| **Recovery Strategy** | HA failover to standby (automatic within 30s); application-level reconnection; write replay from buffer; manual promotion if auto-failover fails | Monitor replication lag; redirect reads to primary if lag > 30s; catch-up replication; alert DBA for manual intervention | Increase pool size dynamically; kill long-running queries; restart connection pool; scale read replicas |
| **User Message** | "We're experiencing a temporary issue. You can browse listings, but some actions may be unavailable right now." | "Some information may be slightly out of date. It will refresh shortly." | "We're experiencing high demand. Please try again in a moment." |
| **Monitoring Strategy** | Track DB connection health; alert on primary unreachable > 10s; track failover events; Grafana panel `db_primary_health` | Track replication lag in seconds; alert on > 10s lag; Grafana panel `db_replication_lag` | Track connection pool utilization; alert on > 80% pool usage; track query queue depth; Grafana panel `db_pool_utilization` |

## 17. Cache Access

| Attribute | Failure 1 | Failure 2 | Failure 3 |
|-----------|-----------|-----------|-----------|
| **Failure Type** | Cache cluster (ElastiCache) unreachable | Cache stampede/thundering herd | Cache corruption/inconsistency |
| **Impact** | High | High | Medium |
| **Fallback Behavior** | Fall back to database queries directly; apply rate limiting; show "Loading..." with longer wait times; cache locally in process memory | Apply request coalescing (single-flight pattern); queue duplicate requests; serve first result to all waiters | Invalidate affected cache keys; rebuild from source; serve from database during rebuild |
| **Recovery Strategy** | Circuit breaker (failure_threshold=5, recovery_timeout=15s); in-process LRU cache as L2 fallback; background reconnection attempts; cache warming on recovery | Mutex/lock per cache key; jittered TTL; gradual cache warming; stampede protection in cache client | Selective cache invalidation; background rebuild; versioned cache keys; cache warming priority queue |
| **User Message** | "We're having trouble loading this information right now. Please try again shortly." | "We're experiencing high demand. Pages may load more slowly than usual." | "We're having trouble loading this information right now. Please try again shortly." |
| **Monitoring Strategy** | Track cache availability; alert on circuit open; track cache miss rate spike; Grafana panel `cache_availability` | Track cache miss rate and request concurrency; alert on miss rate > 50%; Grafana panel `cache_stampede_detection` | Track cache consistency checks; alert on invalidation failures; Grafana panel `cache_consistency` |

## 18. WebSockets

| Attribute | Failure 1 | Failure 2 | Failure 3 |
|-----------|-----------|-----------|-----------|
| **Failure Type** | WebSocket server unreachable | Connection drop mid-session | Message ordering violation |
| **Impact** | Medium | Medium | High |
| **Fallback Behavior** | Fall back to HTTP long-polling; show "real-time updates paused" banner; poll for updates every 10s | Auto-reconnect with exponential backoff; replay missed messages from server-side buffer (last 100); show "reconnecting..." indicator | Ignore out-of-order messages; request gap fill from server; show warning if gap cannot be filled |
| **Recovery Strategy** | Circuit breaker on WS endpoint; automatic transport upgrade to long-polling; server-side reconnection within 30s | Client-side auto-reconnect (max 10 attempts); server message buffer (5 min); sequence number reconciliation on reconnect | Server-side sequence tracking; client-side gap detection; reconciliation request on reconnect; manual page refresh as last resort |
| **User Message** | "Live updates are temporarily paused. You'll still receive all updates, just with a slight delay." | "You've been disconnected. We're reconnecting you automatically." | N/A (handled transparently; user refreshes if visual inconsistency) |
| **Monitoring Strategy** | Track WebSocket connection success rate; alert on < 95% success; track fallback to long-polling; Grafana panel `ws_connection_health` | Track reconnection rate and success; alert on > 10% reconnection rate; Grafana panel `ws_reconnection_rate` | Track message sequence gaps; alert on any gaps; track reconciliation requests; Grafana panel `ws_message_ordering` |

## 19. Background Jobs

| Attribute | Failure 1 | Failure 2 | Failure 3 |
|-----------|-----------|-----------|-----------|
| **Failure Type** | Celery worker pool exhausted | Task execution failure (retries exhausted) | Celery broker (Redis/RabbitMQ) unreachable |
| **Impact** | High | Medium | Critical |
| **Fallback Behavior** | Queue tasks with priority; drop low-priority tasks (analytics, reports); process critical tasks first (payments, escrow); show "processing" for queued user actions | Move to dead-letter queue; notify admin dashboard; allow manual retry from admin panel; log detailed failure context | Fall back to synchronous processing for critical tasks (payments, escrow); queue non-critical tasks locally; show "processing" banners |
| **Recovery Strategy** | Auto-scale workers; terminate stuck tasks (> 30 min); priority queue rebalancing; alert ops team for manual intervention | Dead-letter queue with admin retry UI; automated retry after 24h for idempotent tasks; manual intervention for non-idempotent tasks | Broker HA failover; application-level task buffering; reconnect with exponential backoff; broker health check every 10s |
| **User Message** | "Your request is being processed. It may take longer than usual due to high demand." | "We couldn't complete this action automatically. Our team has been notified and will handle it shortly." | "Your request is being processed. It may take longer than usual." |
| **Monitoring Strategy** | Track worker utilization and task queue depth; alert on > 80% utilization or > 1000 queued tasks; Grafana panel `jobs_worker_pool` | Track task failure rate by type; alert on > 5% failure; track DLQ depth; Grafana panel `jobs_task_failures` | Track broker availability; immediate PagerDuty on broker unreachable; track broker latency; Grafana panel `jobs_broker_health` |

---

## Cross-Domain Failure Chains

The following failure chains represent cascading failures where one domain's failure triggers failures in dependent domains:

| Chain | Trigger | Cascade | Mitigation |
|-------|---------|---------|------------|
| **Database → Cache → Search** | Primary DB fails → Cache invalidation fails → Search index out of sync | Serve stale data across all domains; prevent writes; read-only mode | Independent cache invalidation pipeline; search index checkpoint/restore |
| **External APIs → Payments → Notifications** | Payment provider down → Payment queue grows → Notification backlog | Payment delays; users not notified of payment status changes | Decouple notification from payment confirmation; async notification delivery |
| **Database → Background Jobs → Reporting** | DB connection pool exhaustion → Celery tasks fail → Reports not generated | Stale reports; scheduled reports missed | Dedicated DB connection pool for workers; report generation isolation |
| **Cache → Dashboard → Analytics** | Cache cluster down → Dashboard aggregation slow → Analytics pipeline backpressure | User-facing dashboards timing out; analytics processing delayed | Direct DB queries as fallback for dashboard; separate analytics pipeline |
| **External APIs → KYC → Payments** | Identity verification service down → KYC queue grows → New users can't make payments | New users blocked from transacting | Allow limited transactions for verified users; grace period for pending KYC |

---

## Failure Frequency & Historical Context

Based on Kenyan infrastructure patterns and Digiland's operational history:

| Domain | Expected Failure Frequency | Typical Duration | Notes |
|--------|--------------------------|------------------|-------|
| M-Pesa | Weekly (intermittent) | 5-30 min | Safaricom maintenance windows; STK push reliability varies |
| Database | Monthly | 1-5 min | HA failover typically resolves within 30s |
| Cache | Quarterly | 1-10 min | ElastiCache node replacement |
| Search | Monthly | 5-15 min | Index corruption; cluster rebalancing |
| SMS Gateway | Weekly | 5-60 min | Africa's Talking rate limits; carrier issues |
| WebSockets | Daily (individual drops) | < 30s per reconnect | Mobile network instability in Kenya |
| Background Jobs | Weekly | Variable | Worker scaling lag during peak |
| File Storage | Rare | 5-15 min | S3 multi-AZ resilience |

---

## Kenya-Specific Infrastructure Considerations

Digiland operates within the Kenyan technology ecosystem, which introduces specific failure patterns that differ from typical US/EU deployments:

### Mobile Network Instability

- **Safaricom dominance**: ~65% market share means most users are on a single carrier; Safaricom outages affect the majority of users
- **M-Pesa dependency**: M-Pesa is the primary payment method; STK push reliability varies significantly during peak hours (end-of-month salary payments, 25th-5th)
- **Data costs**: Users frequently switch between WiFi and mobile data, causing WebSocket disconnections
- **Feature phone users**: Some agents still use USSD-based flows; M-Pesa callback delays are common on feature phones

### M-Pesa Operational Windows

| Window | Time (EAT) | Risk Level | Notes |
|--------|-----------|------------|-------|
| Morning peak | 07:00 - 09:00 | Medium | Salary processing, rent payments |
| Midday | 12:00 - 14:00 | Low | Normal operations |
| Evening peak | 17:00 - 20:00 | High | Bill payments, transactions |
| End-of-month | 25th - 5th | Critical | Salary processing; M-Pesa congestion |
| Maintenance windows | Sunday 00:00 - 06:00 | Medium | Scheduled Safaricom maintenance |
| Public holidays | Variable | High | Increased transaction volume; reduced support |

### Payment Provider Priority Matrix

Given the Kenyan market, payment provider failover follows this priority order:

1. **M-Pesa** (primary — ~80% of transactions)
2. **Paystack** (secondary — card payments, bank transfers)
3. **Stripe** (tertiary — international cards, USD/EUR transactions)
4. **KCB Bank** (direct bank integration for large escrow transactions)
5. **Manual queue** (last resort — admin processes with dual approval)

### Compliance & Regulatory Failure Handling

| Regulation | Failure Scenario | Impact | Required Action |
|-----------|-----------------|--------|-----------------|
| **CBK (Central Bank of Kenya)** | Escrow reporting system down | Critical | Queue reports; manual submission within 24 hours |
| **KRA (Kenya Revenue Authority)** | Tax computation service failure | High | Queue tax calculations; ensure reconciliation before any payouts |
| **Data Protection Act 2019** | Audit logging pipeline failure | Critical | Block all operations requiring audit trail; buffer events locally |
| **Anti-Money Laundering** | Fraud detection service unavailable | Critical | Block all transactions > KES 100,000; flag for manual review |
| **Land Registration Act** | Document verification service down | High | Queue document processing; allow viewing but not transfer |

---

## Failure Simulation & Testing Protocol

### Monthly Failure Drill Schedule

| Week | Domain Under Test | Failure Type | Expected Tier Change |
|------|------------------|--------------|---------------------|
| Week 1 | Payments | M-Pesa circuit breaker open | Tier 1 → Tier 2 (payment failover) |
| Week 2 | Database | Primary DB failover | Tier 1 → Tier 3 → Tier 2 → Tier 1 |
| Week 3 | Cache | ElastiCache node replacement | Tier 1 → Tier 2 (cache fallback) |
| Week 4 | External APIs | AI prediction model outage | Tier 1 (no change — Low impact) |

### Failure Drill Checklist

For each monthly failure drill, the on-call team must verify:

1. **Detection** — Was the failure detected within the SLA target?
2. **Alerting** — Did the correct PagerDuty alert fire with the right severity?
3. **Degradation** — Did the system transition to the expected tier?
4. **User Messaging** — Were user-safe messages displayed correctly?
5. **Fallback** — Did the fallback behavior work as documented?
6. **Recovery** — Did the system recover within the SLA target?
7. **Data Integrity** — Was there any data loss or inconsistency?
8. **Post-Drill** — Update this matrix if behavior differs from documentation

### Chaos Engineering Integration

Digiland integrates with Gremlin/Litmus for automated failure injection:

- **Network**: Latency injection (500ms, 2s, 5s) on external service calls
- **Process**: Kill Celery workers, gunicorn processes
- **Resource**: CPU/memory pressure on application servers
- **Dependency**: Block outbound connections to specific providers

All chaos experiments are run during business hours (10:00-16:00 EAT) on Tuesdays and Thursdays in the staging environment. Production experiments require VP Engineering approval.

---

## Failure Response Escalation Matrix

| Impact | Detection → Acknowledge | Acknowledge → Mitigated | Mitigated → Resolved | Escalation Path |
|--------|------------------------|------------------------|---------------------|-----------------|
| Critical | < 5 min | < 15 min | < 30 min | On-call → Engineering Lead → VP Engineering → CTO |
| High | < 15 min | < 1 hr | < 2 hr | On-call → Engineering Lead → VP Engineering |
| Medium | < 30 min | < 4 hr | < 8 hr | On-call → Engineering Lead |
| Low | < 1 hr | < 12 hr | < 24 hr | On-call |

### Escalation Communication Templates

**Critical Impact (Slack #incidents-critical):**
```
🚨 CRITICAL: [Domain] - [Failure Type]
Tier: [Current Tier]
Impact: [User-facing impact]
Started: [Timestamp EAT]
On-call: [@engineer]
Status: Investigating
Next update: [+15 min]
```

**High Impact (Slack #incidents):**
```
⚠️ HIGH: [Domain] - [Failure Type]
Tier: [Current Tier]
Impact: [User-facing impact]
Started: [Timestamp EAT]
On-call: [@engineer]
Status: [Investigating/Mitigating]
```

---

## Dependency Map

The following diagram shows critical service dependencies that drive failure cascading:

```
                    ┌──────────────────┐
                    │   Load Balancer   │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
        ┌─────┴─────┐ ┌────┴─────┐ ┌──────┴──────┐
        │ Django API │ │  ASGI    │ │  Celery     │
        │ (Gunicorn) │ │(Daphne)  │ │  Workers    │
        └─────┬─────┘ └────┬─────┘ └──────┬──────┘
              │             │              │
    ┌─────────┼─────────────┼──────────────┼──────────┐
    │         │             │              │          │
    ▼         ▼             ▼              ▼          ▼
┌───────┐ ┌───────┐  ┌──────────┐  ┌──────────┐ ┌───────┐
│  RDS  │ │Redis  │  │WebSocket │  │  Broker  │ │  S3   │
│Primary│ │Cache  │  │  State   │  │ (Redis)  │ │Storage│
│  +Rep │ │       │  │          │  │          │ │       │
└───┬───┘ └───┬───┘  └────┬─────┘  └────┬─────┘ └───┬───┘
    │         │           │              │          │
    │    ┌────┴────┐      │              │          │
    │    │Elastic  │      │              │          │
    │    │ Search  │      │              │          │
    │    └─────────┘      │              │          │
    │                     │              │          │
    └──────────┬──────────┴──────────────┴──────────┘
               │
    ┌──────────┼──────────────────────────┐
    │          │          │               │
    ▼          ▼          ▼               ▼
┌───────┐ ┌───────┐ ┌───────────┐ ┌──────────┐
│M-Pesa │ │Paystack│ │  Stripe   │ │AI Models │
│       │ │       │ │           │ │          │
└───────┘ └───────┘ └───────────┘ └──────────┘
```

---

*This failure matrix is a living document. All teams must update it when introducing new service dependencies or external integrations. Next review date: 2025-06-04.*
