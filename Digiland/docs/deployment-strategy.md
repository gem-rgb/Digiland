# Digiland Deployment Strategy

## Overview

Digiland uses a multi-environment deployment strategy with progressive delivery, automated rollbacks, and zero-downtime guarantees. The deployment infrastructure is managed as code using Terraform for cloud resources and Helm for Kubernetes application deployments.

## Environments

### Development (Local)

**Purpose**: Rapid iteration and feature development  
**Infrastructure**: Docker Compose on developer machines  
**Database**: PostgreSQL+PostGIS in Docker container  
**Deployment**: Manual (`docker compose up`)  
**URL**: http://localhost:8000

### Staging

**Purpose**: Pre-production validation, integration testing, UAT  
**Infrastructure**: AWS ECS Fargate (small instances)  
**Database**: RDS db.t3.medium with PostGIS  
**Deployment**: Automatic on push to `develop` branch  
**URL**: https://staging.digiland.co.ke

### Production

**Purpose**: Live production traffic  
**Infrastructure**: AWS ECS Fargate (multi-AZ, auto-scaled)  
**Database**: RDS db.r6g.large with PostGIS, Multi-AZ, read replicas  
**Deployment**: Manual approval + blue-green on release  
**URL**: https://digiland.co.ke

## Deployment Strategies

### Rolling Deployment (Staging)

Staging uses standard rolling updates via Helm upgrade. New pods are gradually created while old pods are terminated. The PodDisruptionBudget ensures at least one pod is always available during the update.

```bash
helm upgrade --install digiland ./helm/digiland \
  --namespace digiland-staging \
  --values ./helm/digiland/values-staging.yaml \
  --set image.tag=sha-abc123 \
  --wait --timeout=300s
```

### Blue-Green Deployment (Production)

Production uses a blue-green strategy to achieve zero-downtime deployments. The process maintains two identical environments (blue = current, green = new) and switches traffic atomically.

**Steps**:
1. Deploy new version as "green" alongside current "blue"
2. Wait for green pods to pass health checks
3. Switch service selector from blue to green
4. Validate production traffic on green
5. On failure: immediately switch back to blue
6. On success: scale down blue deployment

### Canary Deployment (Future)

For high-risk changes, a canary deployment routes a small percentage of traffic to the new version before full rollout. This requires Istio or a similar service mesh for traffic splitting.

## Health Checks

Every deployment is validated using multiple health check mechanisms:

| Check | Endpoint | Expected | Timeout |
|-------|----------|----------|---------|
| Liveness | GET /admin/ | HTTP 200/301/302 | 10s |
| Readiness | GET /admin/ | HTTP 200/301/302 | 5s |
| API Health | GET /api/v1/ | HTTP 200/401 | 10s |
| Database | Internal | Connection OK | 5s |
| Redis | Internal | PING → PONG | 3s |

## Automatic Rollback

Rollbacks are triggered automatically when:
- Health check fails after deployment
- Error rate exceeds 5% within 10 minutes
- P95 latency exceeds 5 seconds for 10 minutes
- Pod crash loop detected

**Rollback Procedure**:
```bash
# Kubernetes automatic rollback
kubectl rollout undo deployment/digiland -n digiland-production

# Helm rollback to previous release
helm rollback digiland -n digiland-production
```

## Database Migrations

Database migrations are run as an init container before the main application starts. This ensures migrations complete before traffic is routed to the new version.

**Migration Strategy**:
1. Backward-compatible migrations first (add columns, add tables)
2. Deploy new application code that uses new schema
3. Remove deprecated columns in next release cycle
4. Zero-downtime: migrations run before pods become ready

## Rollback Procedures

See [runbook-rollback.md](./runbook-rollback.md) for detailed rollback procedures.
