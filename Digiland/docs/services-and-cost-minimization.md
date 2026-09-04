# Digiland Production Services & Cost Minimization Blueprint

> **Objective**: Comprehensive inventory of all third-party services, cloud infrastructure, APIs, and operational overhead in Digiland, accompanied by an actionable guide to reduce maintenance and production costs by 90–95%.
>
> **Architecture Principle (Non-Custodial / Zero Escrow)**: Digiland operates strictly on a **non-custodial direct settlement model**. Digiland never holds, pools, or custodies land purchase funds, and does not operate an escrow wallet or escrow ledger. Land purchase payments settle directly between buyer and seller accounts via verified banking/mobile rails (M-Pesa STK push, Bank PesaLink, or RTGS). Digiland charges only transparent transaction coordination and verification fees, collected separately into its own operational accounts. (Note: `land_escrow/` refers solely to the historical backend repository folder name on disk).

---

## 1. Executive Summary: Two Production Paths

When deploying Digiland, there is an enormous financial difference between a "Naive Enterprise" deployment and a "Lean High-Efficiency" deployment:

| Category | Naive Cloud Setup (Default AWS Terraform) | Lean High-Efficiency Setup (Docker / Lean Cloud) | Monthly Savings |
| :--- | :--- | :--- | :--- |
| **Compute & Workers** | AWS ECS Fargate (8 tasks: 4 Web + 4 Celery) | 1–2 Dedicated VPS (Hetzner / DigitalOcean) | **~$220/mo** |
| **Database** | AWS RDS `db.r6g.large` Multi-AZ + 200GB SSD | Managed Postgres (Neon / Supabase) or Docker PostGIS | **~$380/mo** |
| **Caching & Broker** | AWS ElastiCache `cache.r6g.large` (3 nodes) | Self-hosted Redis 7 on VPS or Upstash Serverless | **~$480/mo** |
| **Networking & CDN** | AWS ALB + 2x NAT Gateways + CloudFront | Cloudflare Free Tier + Caddy / Nginx Reverse Proxy | **~$120/mo** |
| **Search Engine** | Dedicated AWS OpenSearch / Elasticsearch | PostgreSQL 16 Trigram + Full-Text Search | **~$60/mo** |
| **AI Vision & LLM** | Uncached GPT-4o calls on all document uploads | Local Tesseract OCR + `gpt-4o-mini` with prompt caching | **~$80/mo** |
| **Communications & Maps**| Unrestricted SMS & Google Maps API queries | WhatsApp / Email first, Redis-cached Geo queries | **~$100/mo** |
| **TOTAL MONTHLY BURN** | **~$1,450 – $2,000 / month** *(KES 190,000 – 260,000)* | **~$24.50 – $55 / month** *(KES 3,200 – 7,100)* | **> 95% Cut** |

---

## 2. Complete Inventory of Digiland Services & Cost Minimization

### Category 1: Cloud & Server Infrastructure

#### 1. Web Application & Background Workers (`web`, `celery-worker`, `celery-beat`)
* **Role in Digiland**: Executes Django WSGI/Gunicorn, Celery asynchronous task queues (for KYC document processing, email notifications, payment reconciliation), and Celery Beat periodic scheduler.
* **Relevant Files**: `docker-compose.yml`, `config/Dockerfile`, `terraform/ecs.tf`, `terraform/environments/production.tfvars`
* **Cost Drivers**: CPU/RAM allocations, number of running container replicas.
* **Optimization Strategies**:
  1. **Do not use AWS ECS Fargate initially**: Default Terraform specifies 8 Fargate tasks (4 web + 4 celery), each with 1 vCPU and 2GB RAM, running continuously (~$220–$280/mo).
  2. **Deploy on a single high-performance VPS**: Run `docker compose up -d` on a single VPS (such as a Hetzner CPX31 with 4 vCPUs, 8GB RAM, 160GB NVMe at ~$16/month, or a DigitalOcean 8GB Droplet at $24/month).
  3. **Tune Worker Concurrency**: In `.env`, keep `CELERY_WORKER_CONCURRENCY=2` (default was 4). Two worker processes are more than enough to process KYC and webhook tasks for low-to-medium traffic without eating system RAM.

#### 2. PostgreSQL 16 + PostGIS Database (`db`)
* **Role in Digiland**: Relational store for users, land parcels, title deed records, direct settlement payment evidence, geospatial land boundaries, audit logs, and dual-approval records.
* **Relevant Files**: `docker-compose.yml`, `terraform/rds.tf`, `land_escrow/land_escrow/settings.py`
* **Cost Drivers**: Instance sizing, Multi-AZ replication, provisioned IOPS, automated snapshot storage.
* **Optimization Strategies**:
  1. **Self-hosted Dockerized PostGIS (Lowest Cost)**: The `postgis/postgis:16-3.4` container in `docker-compose.yml` runs locally on the VPS with zero extra licensing or cloud fees. Set up a simple cron script to run `pg_dump` daily and sync encrypted backups to Cloudflare R2 (costs ~$0.50/mo).
  2. **Managed Postgres Alternative**: If you prefer managed hosting without server management, use **Neon.tech** or **Supabase** (free tier includes 500MB database, scaling up to ~$19–$25/mo only when traffic expands).

#### 3. Redis Cache & Celery Broker (`redis`)
* **Role in Digiland**: Cache layer, session storage, rate limiting, and Celery task broker.
* **Relevant Files**: `docker-compose.yml`, `terraform/elasticache.tf`
* **Cost Drivers**: Multi-node cluster nodes, memory overhead.
* **Optimization Strategies**:
  1. **Disable ElastiCache**: Terraform `production.tfvars` provisions a 3-node `cache.r6g.large` cluster (~$480/mo). This is extreme overkill for an early-stage or growing platform.
  2. **Run Redis in Alpine Container**: The `redis:7-alpine` container configured in `docker-compose.yml` is limited to `256mb` (`--maxmemory 256mb --maxmemory-policy allkeys-lru`). It consumes negligible VPS resources and costs $0 extra.
  3. **Serverless Alternative**: Use **Upstash Redis** (free tier gives 10,000 commands/day).

#### 4. Object & Media Storage (Property Photos, Title Deeds, KYC Selfies)
* **Role in Digiland**: File uploads, identity card photos, spousal consent affidavits, surveyor beacon diagrams.
* **Relevant Files**: `external_services/adapters/storage/`, `land_escrow/settings.py` (`CLOUDINARY_*`, `AWS_STORAGE_BUCKET_NAME`)
* **Cost Drivers**: Stored data volume and **outbound egress bandwidth** (users viewing images).
* **Optimization Strategies**:
  1. **Switch to Cloudflare R2 (`R2Adapter`)**: AWS S3 charges $0.09 per GB of outbound bandwidth. Cloudflare R2 has **$0 egress fees** and provides 10GB free monthly storage.
  2. **Cloudinary Free Tier Guardrails**: If using Cloudinary for image transformations, keep usage within the 25 free monthly credits. Set image max-upload limits (`FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024` is already enforced in `settings.py`).
  3. **Compress client uploads**: Images should be compressed to WebP/JPEG before upload to reduce storage size by 70%.

#### 5. Search Engine (Elasticsearch)
* **Role in Digiland**: Full-text searching of land listings.
* **Relevant Files**: `docker-compose.yml`, `land_escrow/settings.py`
* **Optimization Strategies**:
  1. **Keep `ELASTICSEARCH_ENABLED=False`**: Elasticsearch requires at least 1–2GB of dedicated JVM heap RAM.
  2. **Use Postgres Trigram Search**: Digiland's database already has PostGIS and PostgreSQL full-text capabilities. Searching parcel titles, locations, and descriptions using PostgreSQL `ilike` or `tsvector` handles tens of thousands of listings with sub-millisecond response times at zero cost.

#### 6. Networking, Load Balancing & CDN
* **Role in Digiland**: SSL/TLS termination, static asset delivery (`styles.css`, `main.js`), reverse proxy.
* **Optimization Strategies**:
  1. **Cloudflare Free Tier**: Connect your domain names (`digiland.co.ke`, `app.digiland.co.ke`, `staff.digiland.co.ke`, `admin.digiland.co.ke`) through Cloudflare Free. Cloudflare provides enterprise-grade DDoS mitigation, free Edge SSL, and CDN caching of all static media.
  2. **Replace AWS ALB**: Using Nginx (already configured in `nginx/nginx.conf`) with Let's Encrypt certificates saves the $25/mo AWS Application Load Balancer fee and the $75/mo NAT Gateway fees.

---

### Category 2: Payment Gateways & Banking APIs

#### 1. Safaricom Daraja API (M-Pesa C2B & B2C)
* **Role in Digiland**:
  * **C2B (STK Push)**: Direct buyer earnest money settlements to seller paybill/till, survey fees, and platform coordination fees.
  * **B2C (Disbursements)**: Automated payout releases of collected platform service fees to verified advocates and licensed field surveyors upon milestone completion.
* **Relevant Files**: `core/services/payment.py`, `external_services/adapters/payment/`
* **Cost Drivers**: Safaricom charges transaction tariffs per transaction.
* **Optimization Strategies**:
  1. **Fee Pass-Through**: Digiland's `ServiceFeeService` (`core/services/service_fee.py`) includes transparent transaction coordination and verification fees. Ensure payment processing and provider verification fees are passed through to transaction participants so Digiland incurs zero out-of-pocket processing expense.
  2. **Batch Disbursements**: Rather than multiple micro-payouts, aggregate staff/agent compensation payouts at milestone completions to reduce per-transfer B2C tariffs.

#### 2. KCB Bank BFRG API (Corporate Operational Settlement)
* **Role in Digiland**: Corporate operational fee collection and direct B2C facilitator payout account (`KCB_PLATFORM_ACCOUNT=DIGILAND-OPS-001`). Digiland does NOT hold customer land purchase funds; land purchase funds are settled directly between buyer and seller accounts via PesaLink/RTGS.
* **Relevant Files**: `core/services/kcb.py`, `core/services/payment_reconciliation.py`
* **Cost Drivers**: Corporate banking fees, RTGS / Pesalink transfer tariffs for operational fee reconciliation.
* **Optimization Strategies**:
  1. **Negotiate Corporate Operating Tier**: Partner with KCB for corporate operational banking to minimize tariffs on fee settlements and disbursements.
  2. **Route by Rail**: Encourage direct buyer-to-seller bank PesaLink/RTGS for land purchase transactions, using M-Pesa for platform coordination fees and professional survey disbursements under KES 250,000.

#### 3. Paystack & Stripe
* **Role in Digiland**: Credit and debit card processing.
* **Cost Drivers**: Paystack charges 1.5% (local) / 2.9% (international). Stripe charges 2.9% + $0.30.
* **Optimization Strategies**:
  1. **Restrict High-Value Card Payments**: On a KES 5,000,000 land purchase, credit card processing fees would be KES 75,000 to KES 145,000! Restrict card checkout strictly to platform services (listing fees, title deed verification fees, and boost packages). Land purchase payments are executed via direct bank transfer (RTGS/PesaLink) or direct M-Pesa between buyer and seller with zero platform payment card processing overhead.

---

### Category 3: Government Identity & Verification APIs

#### 1. GavaConnect (Kenya Revenue Authority APIs)
* **Role in Digiland**:
  * PIN Checker by ID
  * PIN Checker by PIN
  * Tax Compliance Certificate (TCC) Checker
* **Relevant Files**: `core/services/identity.py`
* **Optimization Strategies**:
  1. **Use Format Validation in Development/Staging**:
     Line 720 of `settings.py`:
     ```python
     KRA_DB_VALIDATION_ENABLED = config('KRA_DB_VALIDATION_ENABLED', default=False, cast=bool)
     ```
     Keep this `False` during testing and early operations. Format validation checks the strict KRA format regex (`[A-Z]\d{9}[A-Z]`) at **zero cost** and prevents signups from blocking when KRA servers experience downtime.
  2. **Cache Verification State**: Once a user is verified (`is_identity_verified = True`), store the `gavakonect_verification_id` permanently in the database. Never call GavaConnect twice for the same user.

#### 2. Ardhisasa / Ministry of Lands Official Search
* **Role in Digiland**: Title registry searches (Section 54 Land Registration Act).
* **Cost Drivers**: Official land search fees (~KES 500 – 1,000 per search).
* **Optimization Strategies**:
  1. **Do not absorb search fees**: Digiland's `ServiceFeeService` models explicitly allocate `due_diligence` and `verification` fees as payable by the buyer/seller. The platform should never pay government registry fees out-of-pocket.

---

### Category 4: AI, Machine Learning & Document Verification

#### 1. OpenAI / Anthropic APIs
* **Role in Digiland**: Document authenticity verification (`AIDocumentAuthenticityVerifier`), smart ad generation, title deed completeness.
* **Relevant Files**: `external_services/adapters/ai/`, `core/services/ai_doc_authenticity.py`
* **Cost Drivers**: Vision and LLM tokens per document page uploaded.
* **Optimization Strategies**:
  1. **Local-First Verification**: Digiland already includes a built-in OpenCV, Laplacian blur detection, and Tesseract OCR engine in `core/ai_kyc.py`. Run this local engine first on the server CPU. Only fall back to external LLMs if local confidence is low.
  2. **Use `gpt-4o-mini`**: In `external_services/adapters/ai/__init__.py`, `gpt-4o-mini` costs $0.00015 per 1K input tokens (over 15x cheaper than `gpt-4o` or `gpt-4-turbo`).
  3. **Disable Unnecessary AI Flags**:
     ```python
     ENABLE_AI_PRICE_PREDICTION = False  # Keep disabled or use local scikit-learn
     ```
     Digiland's land valuation pipeline (`core/services/price_prediction.py`) runs on `scikit-learn` locally on your server CPU without any external API fees.

---

### Category 5: Communications (SMS, Email, Push)

#### 1. Africa's Talking (SMS & OTP Gateway)
* **Role in Digiland**: OTP verification, critical conveyancing and milestone updates.
* **Relevant Files**: `external_services/adapters/sms/`
* **Cost Drivers**: ~KES 0.80 – 1.00 per SMS message.
* **Optimization Strategies**:
  1. **Email-First OTP**: Default to sending verification codes to user email addresses; only send SMS for phone verification or critical conveyancing and title transfer milestone alerts.
  2. **Push Notifications (Firebase FCM)**: Web and mobile push notifications (`FirebaseAdapter` in `external_services/adapters/push/`) are **100% free** from Google.
  3. **TOTP MFA Authenticator**: Digiland already supports Google/Microsoft Authenticator apps (`core/auth_mfa.py`). Authenticator apps have zero recurring cost compared to SMS OTPs.

#### 2. Transactional Email (Resend / SendGrid / Amazon SES)
* **Role in Digiland**: Account verification, dispute notifications, formal closing statements.
* **Relevant Files**: `land_escrow/settings.py` (`RESEND_API_KEY`, `EMAIL_HOST`)
* **Optimization Strategies**:
  1. **Resend Free Tier**: Resend provides **3,000 free emails per month** with high deliverability.
  2. **Amazon SES Fallback**: If you exceed 3,000 emails, Amazon SES charges only **$0.10 per 1,000 emails** (KES 13 per 1,000). Never purchase expensive marketing email plans for transactional notifications.

---

### Category 6: Maps & Geolocation

#### 1. Google Maps Platform
* **Role in Digiland**: Geocoding parcel coordinates, calculating distance to roads/power/water (`GoogleMapsAdapter`).
* **Relevant Files**: `external_services/adapters/maps/`
* **Cost Drivers**: Google Geocoding API ($5/1,000 calls), Distance Matrix API ($5–$10/1,000 calls).
* **Optimization Strategies**:
  1. **Leverage Google's $200 Monthly Free Credit**: Provides ~28,000 free geocoding requests every month.
  2. **Permanent Redis & Database Caching**: Land parcels and towns do not move. When geocoding coordinates for a parcel or town, cache the latitude and longitude indefinitely in PostgreSQL. Never query Google Maps twice for the same location.
  3. **Client-side OpenStreetMap**: Use Leaflet / OpenStreetMap for displaying maps on the frontend at zero cost.

---

### Category 7: Monitoring & Observability

#### 1. Sentry (`sentry-sdk`)
* **Role in Digiland**: Exception tracking and performance monitoring.
* **Optimization Strategies**:
  1. **Sentry Developer Plan (Free)**: 5,000 error events/month.
  2. **Tune Traces Sample Rate**: In `settings.py`:
     ```python
     SENTRY_TRACES_SAMPLE_RATE = 0.05  # 5% sampling instead of 100%
     ```
     This keeps you comfortably inside the free tier indefinitely.

#### 2. Prometheus & Grafana (`monitoring/`)
* **Role in Digiland**: System resource monitoring and alerts.
* **Cost**: **100% Free open-source software**. Run them inside Docker on your server.

---

## 3. Recommended Production Stack ($25 - $30 / Month Blueprint)

This lean deployment architecture supports up to 100,000 monthly pageviews and hundreds of active land purchase transactions:

```
┌────────────────────────────────────────────────────────────────────────┐
│                    LEAN DIGILAND MONTHLY PRODUCTION BUDGET             │
├──────────────────────────────────────┬────────────────┬────────────────┤
│ Service                              │ Provider       │ Monthly Cost   │
├──────────────────────────────────────┼────────────────┼────────────────┤
│ Production VPS (4 vCPU, 8GB RAM)     │ Hetzner Cloud  │ $16.00         │
│ Database Backups Storage (10GB)      │ Cloudflare R2  │ $0.00 (Free)   │
│ CDN, Edge Caching, SSL & DDoS        │ Cloudflare     │ $0.00 (Free)   │
│ Transactional Email (3,000/mo)       │ Resend         │ $0.00 (Free)   │
│ Web & Mobile Push Notifications      │ Firebase FCM   │ $0.00 (Free)   │
│ Error & Crash Monitoring             │ Sentry (Dev)   │ $0.00 (Free)   │
│ Product Analytics (1M events/mo)     │ PostHog Cloud  │ $0.00 (Free)   │
│ Domain Registration (.co.ke)         │ KeNIC Host     │ $1.00 ($12/yr) │
│ SMS & OTP Gateway Buffer             │ Africa's Talk. │ $4.00 (KES 520)│
│ AI Vision / OCR Fallback Buffer      │ OpenAI mini    │ $3.00          │
├──────────────────────────────────────┴────────────────┼────────────────┤
│ TOTAL ESTIMATED MONTHLY OPERATING COST                │ ~$24.00 / mo   │
│                                                       │ (KES 3,120/mo) │
└───────────────────────────────────────────────────────┴────────────────┘
```

---

## 4. Production Settings Checklist (`.env`)

Add or verify these cost-saving parameters in your production `.env` file:

```bash
# 1. Disable Elasticsearch (Use PostgreSQL Full-Text Search)
ELASTICSEARCH_ENABLED=False

# 2. Keep KRA verification format-based until live deal clearance
KRA_DB_VALIDATION_ENABLED=False

# 3. AI Scoping (Use local scikit-learn & Tesseract OCR)
ENABLE_AI_PRICE_PREDICTION=False
ENABLE_AI_DOC_VERIFICATION=True
OPENAI_MODEL=gpt-4o-mini

# 4. Email & Notifications (Leverage free tiers)
NOTIFICATION_EMAIL_PROVIDER=resend
RESEND_API_KEY=re_your_api_key_here
DEFAULT_FROM_EMAIL=noreply@digiland.co.ke

# 5. Sentry Sampling (Stay inside 5,000 free events/mo)
SENTRY_TRACES_SAMPLE_RATE=0.05

# 6. Celery Concurrency (Prevent memory thrashing on VPS)
CELERY_WORKER_CONCURRENCY=2
```

---

## 5. Summary of Golden Rules for Digiland Cost Efficiency

1. **Pass-through all verification costs**: Surveyors, lawyers, and government search fees are paid by transaction participants; Digiland collects its 2%–4% facilitation fee net of these costs.
2. **Never query static data twice**: Cache geocoding, KRA identities, and title deed OCR results permanently in PostgreSQL and Redis.
3. **Prefer Open Source on-server compute**: Use Digiland's built-in Tesseract, OpenCV, and scikit-learn models before making paid API calls to OpenAI.
4. **Scale cloud hardware strictly with revenue**: Do not provision multi-node AWS ElastiCache and multi-AZ RDS until transaction volume and platform fee revenues easily justify the infrastructure.
