# Digiland Degradation Strategy

> **Phase 1 — Graceful Degradation System**
> Version: 1.0.0 | Last Updated: 2025-03-04 | Owner: Platform Engineering

## Purpose

This document defines Digiland's multi-tier degradation strategy, specifying how the platform progressively reduces functionality under stress or failure conditions. It establishes tier definitions, per-domain degradation paths, data freshness requirements, and circuit breaker policies for all external services.

---

## Tier Definitions

### Tier 1 — Full Functionality

All platform features operate normally. This is the default state.

**Characteristics:**
- All read and write operations available
- Real-time updates via WebSocket
- Full search capabilities with Elasticsearch
- Payment processing via all providers (M-Pesa, Stripe, Paystack)
- All notifications channels active (SMS, email, push)
- AI-powered features available (price prediction, recommendations)
- File uploads and document verification operational
- Admin control plane fully operational

**Entry Condition:** All critical and high-impact services healthy.

**Exit Triggers:**
- Any Critical-impact service failure → degrade to Tier 2
- Multiple High-impact services failing simultaneously → degrade to Tier 2
- System-wide latency p99 > 5s for > 2 minutes → degrade to Tier 2

---

### Tier 2 — Reduced Functionality

Core workflows remain available but non-essential features are disabled or simplified. Performance may be slower than normal.

**Characteristics:**
- Read operations fully available
- Write operations available for critical flows (payments, escrow, messaging)
- Search falls back to database queries with limited results
- Real-time updates switch to polling (10s intervals)
- Non-critical background jobs paused (reports, analytics pipelines, CRM sync)
- AI features show cached/stale results
- File uploads queued for background processing
- Notifications may use alternate channels (email fallback for SMS)
- Ads and sponsored content may not display
- Admin control plane in reduced mode (dual-approval deferred for non-critical actions)

**Entry Condition:** One or more Critical/High services degraded but core read/write paths functional.

**Exit Triggers:**
- All services recovered → upgrade to Tier 1
- Primary database write capability lost → degrade to Tier 3
- Multiple Critical services down simultaneously → degrade to Tier 3

---

### Tier 3 — Read-Only Mode

Users can browse and view data but cannot make changes. All write operations are blocked or queued.

**Characteristics:**
- All read operations available (may serve slightly stale data)
- All write operations blocked with clear user messaging
- Payments queued but not processed
- Search uses cached results only
- No real-time updates; static snapshots displayed
- No file uploads
- No notification sending (queued for later)
- Dashboard shows cached data with "as of" timestamps
- Admin control plane read-only (no configuration changes)

**Entry Condition:** Primary database write capability lost, or multiple Critical services down.

**Exit Triggers:**
- Write capability restored → upgrade to Tier 2
- All services recovered → upgrade to Tier 1
- Complete infrastructure failure → degrade to Tier 4

---

### Tier 4 — Static / Offline Mode

The platform serves a static version with minimal functionality. Users see a landing page with status information and can access cached data from their browser.

**Characteristics:**
- Static HTML landing page served from CDN
- Status page showing current platform status
- No API functionality
- Service Worker provides limited offline access to previously viewed data
- Contact information and support channels displayed
- "We'll be back soon" messaging with estimated recovery time

**Entry Condition:** Complete infrastructure failure or planned maintenance.

**Exit Triggers:**
- API servers reachable → upgrade to Tier 3
- Database read capability restored → upgrade to Tier 2

---

## Degradation Tier Decision Matrix

```
┌──────────────────────────────────────────────────────────────────┐
│                    TIER TRANSITION ENGINE                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Current Tier    │  Condition                        │  Target   │
│  ───────────────┼──────────────────────────────────┼────────── │
│  Tier 1          │  Any Critical service down         │  Tier 2   │
│  Tier 1          │  ≥2 High services down             │  Tier 2   │
│  Tier 1          │  p99 latency >5s for >2min         │  Tier 2   │
│  Tier 1          │  DB writes unavailable              │  Tier 3   │
│  ───────────────┼──────────────────────────────────┼────────── │
│  Tier 2          │  All services healthy for 5min      │  Tier 1   │
│  Tier 2          │  DB writes unavailable              │  Tier 3   │
│  Tier 2          │  ≥2 Critical services down          │  Tier 3   │
│  Tier 2          │  Complete infra failure             │  Tier 4   │
│  ───────────────┼──────────────────────────────────┼────────── │
│  Tier 3          │  All services healthy for 5min      │  Tier 1   │
│  Tier 3          │  Writes restored, some deps down    │  Tier 2   │
│  Tier 3          │  Complete infra failure             │  Tier 4   │
│  ───────────────┼──────────────────────────────────┼────────── │
│  Tier 4          │  API servers reachable              │  Tier 3   │
│  Tier 4          │  DB reads restored                  │  Tier 2   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Hysteresis Rules

To prevent tier oscillation (flapping between tiers):

1. **Upgrade delay:** A tier upgrade only occurs after the target tier's conditions have been continuously met for **5 minutes** (configurable per environment).
2. **Downgrade immediacy:** A tier downgrade occurs **immediately** when the trigger condition is met.
3. **Cooldown period:** After a tier change, the system waits **2 minutes** before considering another change (except for Critical-triggered downgrades).

---

## Per-Domain Degradation Paths

### Authentication

| From Tier → To Tier | Behavioral Change |
|---------------------|-------------------|
| Tier 1 → Tier 2 | OAuth buttons hidden; email/password only; MFA uses recovery codes if TOTP service unavailable |
| Tier 2 → Tier 3 | Login still available (required for read access); no new registrations; no password changes |
| Tier 3 → Tier 4 | Static login page only; no authentication processing; cached session tokens honored if valid |

### Authorization

| From Tier → To Tier | Behavioral Change |
|---------------------|-------------------|
| Tier 1 → Tier 2 | Cached permissions used with extended TTL; ABAC conditions simplified to RBAC-only |
| Tier 2 → Tier 3 | Read-only permissions enforced; all write permissions denied regardless of role |
| Tier 3 → Tier 4 | No authorization processing; static pages have no dynamic access control |

### Payments

| From Tier → To Tier | Behavioral Change |
|---------------------|-------------------|
| Tier 1 → Tier 2 | Primary provider failover (M-Pesa → Paystack → Stripe); async processing with status polling; receipt generation delayed |
| Tier 2 → Tier 3 | All payment initiation blocked; existing payments continue processing; escrow holds maintained |
| Tier 3 → Tier 4 | No payment functionality; static page shows "Payments will resume shortly" |

### Withdrawals

| From Tier → To Tier | Behavioral Change |
|---------------------|-------------------|
| Tier 1 → Tier 2 | Manual fraud review for all withdrawals; processing delays (up to 4 hours); bank disbursement queued |
| Tier 2 → Tier 3 | Withdrawal requests blocked; existing withdrawals continue processing; escrow funds locked |
| Tier 3 → Tier 4 | No withdrawal functionality; static status page |

### Notifications

| From Tier → To Tier | Behavioral Change |
|---------------------|-------------------|
| Tier 1 → Tier 2 | Channel fallback (SMS → email → in-app); batch delivery instead of real-time; non-critical notifications suppressed |
| Tier 2 → Tier 3 | All notifications queued; no delivery attempts; notification center shows cached items only |
| Tier 3 → Tier 4 | No notification processing; queued notifications delivered on recovery |

### Messaging

| From Tier → To Tier | Behavioral Change |
|---------------------|-------------------|
| Tier 1 → Tier 2 | WebSocket → HTTP long-polling; attachment uploads queued; message delivery confirmation delayed |
| Tier 2 → Tier 3 | Read-only message viewing; no new messages; chat shows "messaging paused" banner |
| Tier 3 → Tier 4 | No messaging; static "We'll be back" page |

### Dashboard

| From Tier → To Tier | Behavioral Change |
|---------------------|-------------------|
| Tier 1 → Tier 2 | Cached data with freshness indicators; reduced widget set; manual refresh required |
| Tier 2 → Tier 3 | Static dashboard snapshot; no real-time data; "Data as of [time]" prominently displayed |
| Tier 3 → Tier 4 | No dashboard; static status page |

### Analytics

| From Tier → To Tier | Behavioral Change |
|---------------------|-------------------|
| Tier 1 → Tier 2 | Reduced granularity (daily vs hourly); cached reports; no ad-hoc queries; scheduled reports delayed |
| Tier 2 → Tier 3 | Analytics dashboard hidden; existing reports viewable but not exportable |
| Tier 3 → Tier 4 | No analytics; static status page |

### Admin Control Plane

| From Tier → To Tier | Behavioral Change |
|---------------------|-------------------|
| Tier 1 → Tier 2 | Dual-approval deferred for non-critical actions; emergency single-approval for Critical ops; audit logging buffered locally |
| Tier 2 → Tier 3 | Admin panel read-only; no configuration changes; no user management; audit events queued |
| Tier 3 → Tier 4 | No admin access; all operations frozen; incident bridge activated |

### File Uploads

| From Tier → To Tier | Behavioral Change |
|---------------------|-------------------|
| Tier 1 → Tier 2 | Uploads queued for background processing; virus scan results delayed; larger file size limits reduced |
| Tier 2 → Tier 3 | All uploads blocked; existing files still downloadable (if scanned) |
| Tier 3 → Tier 4 | No file access; static status page |

### Search

| From Tier → To Tier | Behavioral Change |
|---------------------|-------------------|
| Tier 1 → Tier 2 | Database fallback with limited results (10 per page); no faceted search; no autocomplete; category browsing available |
| Tier 2 → Tier 3 | Cached popular searches only; no dynamic search; category links for navigation |
| Tier 3 → Tier 4 | No search; static listing categories only |

### User Profiles

| From Tier → To Tier | Behavioral Change |
|---------------------|-------------------|
| Tier 1 → Tier 2 | Profile edits queued; KYC processing delayed; avatar uploads queued |
| Tier 2 → Tier 3 | Profiles viewable but not editable; KYC submissions blocked |
| Tier 3 → Tier 4 | No profile access; static status page |

### Settings

| From Tier → To Tier | Behavioral Change |
|---------------------|-------------------|
| Tier 1 → Tier 2 | Settings applied locally first; sync deferred; notification preferences may be delayed |
| Tier 2 → Tier 3 | Settings viewable but not changeable |
| Tier 3 → Tier 4 | No settings access |

### Reporting

| From Tier → To Tier | Behavioral Change |
|---------------------|-------------------|
| Tier 1 → Tier 2 | Report generation queued; scheduled reports delayed; export limited to CSV only |
| Tier 2 → Tier 3 | Existing reports viewable; no new report generation; no exports |
| Tier 3 → Tier 4 | No reporting; static status page |

### External APIs

| From Tier → To Tier | Behavioral Change |
|---------------------|-------------------|
| Tier 1 → Tier 2 | AI predictions show cached estimates; maps unavailable (text-based locations); CRM/ERP sync deferred |
| Tier 2 → Tier 3 | All external API calls suspended; cached results only where available |
| Tier 3 → Tier 4 | No external integrations; static page |

### Database Access

| From Tier → To Tier | Behavioral Change |
|---------------------|-------------------|
| Tier 1 → Tier 2 | Read replicas preferred; connection pooling tightened; slow queries killed after 10s |
| Tier 2 → Tier 3 | Read-only mode; all writes blocked and queued; stale reads accepted up to 60s lag |
| Tier 3 → Tier 4 | No database access; CDN-served static content only |

### Cache Access

| From Tier → To Tier | Behavioral Change |
|---------------------|-------------------|
| Tier 1 → Tier 2 | In-process LRU cache as L2 fallback; stampede protection active; longer cache TTLs |
| Tier 2 → Tier 3 | Direct database queries for all reads; connection pooling critical; rate limiting applied |
| Tier 3 → Tier 4 | No caching; no dynamic content |

### WebSockets

| From Tier → To Tier | Behavioral Change |
|---------------------|-------------------|
| Tier 1 → Tier 2 | HTTP long-polling fallback; 10s polling interval; reduced event set (no typing indicators) |
| Tier 2 → Tier 3 | No real-time updates; periodic page refresh required |
| Tier 3 → Tier 4 | No live connections; static content only |

### Background Jobs

| From Tier → To Tier | Behavioral Change |
|---------------------|-------------------|
| Tier 1 → Tier 2 | Low-priority jobs paused (analytics, reports, CRM sync); critical jobs prioritized (payments, escrow, notifications) |
| Tier 2 → Tier 3 | All background jobs paused; critical operations processed synchronously if possible |
| Tier 3 → Tier 4 | No background processing; all operations frozen |

---

## Data Freshness Requirements Per Tier

### Definition of Freshness Levels

| Level | Label | Max Acceptable Age | Use Case |
|-------|-------|--------------------|----------|
| **Real-time** | "Live" | < 5 seconds | Chat messages, payment status, WebSocket events |
| **Near Real-time** | "Updated just now" | < 60 seconds | Dashboard stats, notification counts, search index |
| **Recent** | "Updated recently" | < 5 minutes | Listing details, user profiles, escrow balances |
| **Cached** | "As of [time]" | < 30 minutes | Analytics, reports, price predictions, recommendations |
| **Stale** | "May not reflect recent changes" | < 24 hours | Historical data, archived reports, AI model outputs |

### Per-Domain Freshness by Tier

| Domain | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|--------|--------|--------|--------|--------|
| **Payments** | Real-time | Real-time (with delay) | Stale (last known state) | N/A |
| **Escrow** | Real-time | Near Real-time | Stale (last known state) | N/A |
| **Search** | Near Real-time | Recent (< 15 min) | Cached (< 30 min) | N/A |
| **Dashboard** | Near Real-time | Recent (< 5 min) | Cached (< 30 min) | N/A |
| **Analytics** | Recent | Cached (< 30 min) | Stale (< 24 hr) | N/A |
| **User Profiles** | Recent | Recent (< 5 min) | Cached (< 30 min) | N/A |
| **Messaging** | Real-time | Near Real-time | Stale (read-only) | N/A |
| **Notifications** | Real-time | Near Real-time | Cached (queued) | N/A |
| **Admin CP** | Real-time | Near Real-time | Recent (read-only) | N/A |
| **Price Prediction** | Cached (< 30 min) | Stale (< 24 hr) | Stale (< 24 hr) | N/A |
| **Reporting** | Recent | Cached (< 30 min) | Stale (view-only) | N/A |
| **File Uploads** | Real-time | Recent (< 5 min) | Blocked | N/A |
| **KYC/Verification** | Near Real-time | Recent (< 15 min) | Blocked | N/A |

### Freshness Enforcement

1. **Client-side:** React components display a freshness banner when data age exceeds the tier's threshold. The banner includes the data's timestamp and a refresh action.
2. **API-level:** Every API response includes an `X-Data-Freshness` header with the data's age in seconds and the current tier level.
3. **Frontend cache:** Service Worker cache respects freshness TTLs per domain. Stale data is served only if within the tier's acceptable age.
4. **User notification:** When data freshness drops below the tier's threshold, a toast notification appears: "Some information may not be up to date. [Refresh]"

---

## Circuit Breaker Policies Per External Service

### Policy Configuration Template

Each circuit breaker is configured with:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `failure_threshold` | Consecutive failures before opening | 5 |
| `recovery_timeout` | Seconds before transitioning OPEN → HALF_OPEN | 60s |
| `half_open_max_calls` | Successful probes needed to close | 3 |
| `expected_exceptions` | Exception types that count as failures | `(Exception,)` |
| `timeout_seconds` | Per-request timeout | 30s |
| `max_retries` | Max retry attempts before circuit considers it a failure | 1 |

### Payment Services

| Service | failure_threshold | recovery_timeout | half_open_max_calls | timeout_seconds | Priority |
|---------|------------------|-----------------|--------------------|-----------------|----------|
| **M-Pesa (STK Push)** | 3 | 30s | 2 | 45s | Critical |
| **M-Pesa (C2B)** | 3 | 30s | 2 | 30s | Critical |
| **M-Pesa (B2C)** | 3 | 60s | 2 | 60s | Critical |
| **Stripe** | 5 | 60s | 3 | 30s | High |
| **Paystack** | 5 | 60s | 3 | 30s | High |
| **KCB Bank** | 3 | 90s | 2 | 60s | High |

**Failover chain:** M-Pesa → Paystack → Stripe → Manual queue

### Identity & Verification Services

| Service | failure_threshold | recovery_timeout | half_open_max_calls | timeout_seconds | Priority |
|---------|------------------|-----------------|--------------------|-----------------|----------|
| **KYC Verification** | 5 | 120s | 3 | 60s | High |
| **Document Verification** | 5 | 120s | 3 | 60s | High |
| **AI KYC** | 3 | 90s | 2 | 45s | Medium |

### Communication Services

| Service | failure_threshold | recovery_timeout | half_open_max_calls | timeout_seconds | Priority |
|---------|------------------|-----------------|--------------------|-----------------|----------|
| **Africa's Talking (SMS)** | 5 | 30s | 3 | 15s | Medium |
| **Email (SES/SMTP)** | 5 | 60s | 3 | 30s | Medium |
| **Push (Firebase)** | 10 | 60s | 3 | 10s | Low |

### Infrastructure Services

| Service | failure_threshold | recovery_timeout | half_open_max_calls | timeout_seconds | Priority |
|---------|------------------|-----------------|--------------------|-----------------|----------|
| **Elasticsearch** | 5 | 30s | 3 | 10s | High |
| **Redis/ElastiCache** | 5 | 15s | 3 | 5s | Critical |
| **S3 (Storage)** | 5 | 30s | 3 | 30s | High |
| **RDS Primary** | 3 | 10s | 2 | 10s | Critical |
| **RDS Replica** | 5 | 15s | 3 | 10s | High |

### AI & Analytics Services

| Service | failure_threshold | recovery_timeout | half_open_max_calls | timeout_seconds | Priority |
|---------|------------------|-----------------|--------------------|-----------------|----------|
| **Price Prediction Model** | 3 | 120s | 2 | 30s | Low |
| **Recommendation Engine** | 5 | 90s | 3 | 15s | Low |
| **Fraud Detection** | 3 | 60s | 2 | 15s | High |

### Maps & Geocoding

| Service | failure_threshold | recovery_timeout | half_open_max_calls | timeout_seconds | Priority |
|---------|------------------|-----------------|--------------------|-----------------|----------|
| **Google Maps API** | 5 | 30s | 3 | 10s | Medium |
| **Geocoding Service** | 5 | 60s | 3 | 15s | Medium |

### CRM & ERP Integrations

| Service | failure_threshold | recovery_timeout | half_open_max_calls | timeout_seconds | Priority |
|---------|------------------|-----------------|--------------------|-----------------|----------|
| **CRM (HubSpot)** | 5 | 120s | 3 | 30s | Low |
| **Accounting (QuickBooks)** | 5 | 120s | 3 | 30s | Low |

### Circuit Breaker State Monitoring

All circuit breaker state transitions are:

1. **Logged** to the structured logging pipeline with full context (service type, provider, old state, new state, reason, timestamp)
2. **Emitted as metrics** to Prometheus via the `CircuitBreakerRegistry.get_all_stats()` method
3. **Visible in Grafana** on the "Circuit Breaker Dashboard" with real-time state indicators
4. **Alerting rules** fire when any Critical or High priority circuit opens

### Circuit Breaker Event Callbacks

The circuit breaker framework supports state-change callbacks for integration with:

```python
# Example: Slack notification on payment circuit open
def on_payment_circuit_open(event: StateTransitionEvent):
    if event.new_state == "open" and event.breaker_name.startswith("payment:"):
        send_slack_alert(
            channel="#incidents-payments",
            message=f"Payment circuit OPEN: {event.breaker_name} — {event.reason}"
        )

# Register callback
registry = CircuitBreakerRegistry.get_global()
for breaker in registry.get_all().values():
    breaker.on_state_change(on_payment_circuit_open)
```

---

## Tier Announcement & User Communication

### Tier Transition Notifications

| Transition | User Communication | Channel | Timing |
|-----------|-------------------|---------|--------|
| Tier 1 → Tier 2 | Persistent banner: "Some features may be temporarily limited." | In-app banner | Immediately |
| Tier 2 → Tier 3 | Full-width banner: "You can browse listings, but some actions are temporarily unavailable." | In-app banner + email to active users | Immediately |
| Tier 3 → Tier 4 | Status page + "We'll be back soon" page | Status page + social media | Immediately |
| Tier 4 → Tier 3 | Banner: "Services are coming back online. Some features may still be limited." | In-app banner | After 2 min stable |
| Tier 3 → Tier 2 | Banner: "Most features are now available. Some may still be loading slowly." | In-app banner | After 5 min stable |
| Tier 2 → Tier 1 | Toast: "All services have been fully restored. Thank you for your patience." | In-app toast | After 5 min stable |

### Status Page Integration

Digiland's status page (hosted externally at status.digiland.co.ke) reflects the current tier:

| Tier | Status Page Display |
|------|-------------------|
| Tier 1 | "All Systems Operational" (green) |
| Tier 2 | "Partial Service Degradation" (yellow) — with affected services listed |
| Tier 3 | "Major Service Disruption" (orange) — with affected services and workarounds |
| Tier 4 | "Service Outage" (red) — with estimated recovery time |

---

## Implementation Priorities

### Phase 1 (Current) — Documentation & Foundation
- [x] Failure matrix documentation
- [x] Degradation strategy documentation
- [x] Error catalog documentation
- [ ] Tier detection middleware implementation
- [ ] Circuit breaker configuration deployment
- [ ] Frontend tier-aware UI components

### Phase 2 — Core Implementation
- [ ] Tier state management service (Redis-backed)
- [ ] Per-domain fallback implementations
- [ ] Frontend degradation banners and state awareness
- [ ] Data freshness enforcement in API responses
- [ ] Circuit breaker state monitoring dashboard

### Phase 3 — Advanced Features
- [ ] Automated tier transitions based on health checks
- [ ] Service Worker offline mode (Tier 4)
- [ ] Automated recovery validation tests
- [ ] Chaos engineering integration (Gremlin/Litmus)
- [ ] Incident runbook integration with tier system

---

## Operational Procedures

### Manual Tier Override

Operators can manually set the degradation tier via the admin control plane:

```
POST /api/v1/admin/degradation/tier
{
    "tier": 2,
    "reason": "Planned M-Pesa maintenance window",
    "duration_minutes": 60,
    "requested_by": "ops-engineer@digiland.co.ke"
}
```

This requires dual approval from a Super Admin when setting Tier 3 or Tier 4.

### Tier Transition Checklist

For each tier downgrade, the on-call engineer must:

1. **Verify the trigger condition** — confirm the failure via monitoring dashboards
2. **Assess blast radius** — determine which domains are affected
3. **Communicate** — post to #incidents Slack channel and update status page
4. **Activate runbook** — follow the domain-specific recovery runbook
5. **Monitor recovery** — watch for tier upgrade conditions
6. **Post-incident review** — document the incident and update this strategy if needed

---

*This degradation strategy is a living document. It must be reviewed after every Tier 2+ incident. Next review date: 2025-06-04.*
