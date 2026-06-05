# Digiland Database Architecture

## Overview

The Digiland database is built on PostgreSQL 16 with the PostGIS spatial extension, implementing a multi-tenant architecture with row-level security (RLS) enforced at the database level. Every table carries a `tenant_id` column that identifies the owning organization, and PostgreSQL RLS policies ensure that queries can never cross tenant boundaries regardless of application code.

## Multi-Tenancy Design

### Architecture: Row-Level Tenant Isolation

Digiland uses a shared-database, shared-schema multi-tenancy model with database-enforced isolation. This approach provides the cost efficiency of a shared database while guaranteeing tenant data isolation at the lowest possible level.

**How it works**:
1. Every tenant-scoped table has a `tenant_id` UUID column
2. PostgreSQL Row-Level Security (RLS) policies compare `tenant_id` against a session variable
3. The application sets the session variable on each request via `set_config('app.current_tenant', tenant_id, false)`
4. RLS policies automatically filter all queries to the current tenant
5. Superusers (BYPASSRLS) can access all data for admin operations

### RLS Policy Template

```sql
-- Enable RLS on a table
ALTER TABLE core_landparcel ENABLE ROW LEVEL SECURITY;

-- Create policy: users can only see rows for their tenant
CREATE POLICY tenant_isolation ON core_landparcel
  USING (tenant_id::text = current_setting('app.current_tenant', true));

-- Superusers bypass RLS
ALTER ROLE digiland_admin BYPASSRLS;
```

### Tenant Resolution Flow

```
Request arrives
    │
    ▼
TenantMiddleware reads tenant_id from:
  1. JWT token claims (preferred)
  2. X-Tenant-ID header (API clients)
  3. User's default organization (fallback)
    │
    ▼
Validate organization exists and is_active
    │
    ▼
SET app.current_tenant = tenant_id
    │
    ▼
All subsequent SQL queries are filtered by RLS
    │
    ▼
On response: SET app.current_tenant = '' (clear)
```

## Schema Design

### Audit Columns

Every model includes these audit columns for traceability and soft deletes:

| Column | Type | Purpose |
|--------|------|---------|
| `tenant_id` | UUID | Organization ownership |
| `created_at` | TIMESTAMP | Record creation time |
| `updated_at` | TIMESTAMP | Last modification time |
| `deleted_at` | TIMESTAMP | Soft delete (NULL = active) |
| `created_by` | UUID FK | User who created the record |
| `updated_by` | UUID FK | User who last modified |

### Index Strategy

Indexes are designed for the actual access patterns used by the application:

**LandParcel** (most queried table):
- `(tenant_id, verification_status, county)` — Homepage filtered listings
- `(tenant_id, listed_by_id)` — Seller's parcel list
- `(tenant_id, asking_price)` — Price range searches
- `(tenant_id, land_use_type, county)` — Category/county browsing

**Transaction**:
- `(tenant_id, buyer_id, status)` — Buyer transaction history
- `(tenant_id, seller_id, status)` — Seller transaction history
- `(tenant_id, status)` — Admin status filters
- `(tenant_id, created_at)` — Chronological queries

**Ad Models** (LandPromotion, PopupAdCampaign, SponsoredAd):
- `(tenant_id, status, billing_model)` — Active campaigns by billing type
- `(tenant_id, created_by/seller)` — Seller's ad management

## Soft Deletes

Instead of physically deleting records, the `deleted_at` column is set to the current timestamp. This preserves data integrity for audit trails, regulatory compliance, and potential recovery.

```python
# Soft delete in queryset
qs.filter(deleted_at__isnull=True)

# Hard delete only via management command with explicit confirmation
```

## Backup and Recovery

### Automated Backups

| Environment | Method | Frequency | Retention |
|-------------|--------|-----------|-----------|
| Production | RDS automated snapshots | Daily | 30 days |
| Staging | RDS automated snapshots | Daily | 7 days |
| Development | Manual pg_dump | On demand | Local |

### Point-in-Time Recovery

RDS PostgreSQL supports point-in-time recovery with a recovery window of up to 35 days for production. This allows restoring the database to any second within the retention period.

### Disaster Recovery

- **RPO** (Recovery Point Objective): 5 minutes (based on WAL shipping)
- **RTO** (Recovery Time Objective): 30 minutes (automated failover)
- Production uses Multi-AZ RDS with automatic failover
- Cross-region read replica for disaster recovery (future)

## Connection Pooling

Production uses PgBouncer as a connection pooler between the application and PostgreSQL:

- **Pool Mode**: Transaction (connections returned to pool after transaction completes)
- **Max Client Connections**: 1000
- **Default Pool Size**: 50
- **Reserve Pool Size**: 10
- **Reserve Pool Timeout**: 3 seconds

## Query Performance

### Monitoring

Query performance is monitored via:
- `pg_stat_statements` extension for slow query tracking
- CloudWatch RDS Performance Insights
- Custom Django middleware logging queries > 500ms
- Prometheus metrics for database connection pool usage

### Optimization Rules

1. **N+1 Prevention**: Use `select_related()` and `prefetch_related()` in all ViewSets
2. **Index Coverage**: Every WHERE clause should be covered by an index
3. **Query Timeout**: Statements exceeding 30s are logged and terminated
4. **Vacuum Strategy**: Auto-vacuum with aggressive settings for high-update tables (ad_events, analytics_events)
