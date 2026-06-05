# Digiland Rollback Runbook

## Overview

This runbook describes procedures for rolling back Digiland deployments when issues are detected in staging or production environments.

## When to Rollback

Rollback should be initiated when:
- Health check endpoints return non-200 status codes
- Error rate exceeds 5% of total requests
- P95 latency exceeds 5 seconds for more than 10 minutes
- Critical functionality is broken (login, payments, listings)
- Data integrity issues are detected
- Security vulnerability is discovered in deployed version

## Automatic Rollback

The CI/CD pipeline includes automatic rollback triggers:

- **Health check failure**: Service selector reverts to blue deployment
- **Smoke test failure**: Deployment is marked as failed, Helm rollback initiated
- **Error rate spike**: Kubernetes HPA + custom alert triggers investigation

## Manual Rollback Procedures

### Helm Rollback

```bash
# List release history
helm history digiland -n digiland-production

# Rollback to previous revision
helm rollback digiland -n digiland-production

# Rollback to specific revision
helm rollback digiland -n digiland-production [REVISION_NUMBER]

# Verify rollback
helm status digiland -n digiland-production
kubectl get pods -n digiland-production
```

### Blue-Green Rollback

```bash
# Switch service back to blue (previous version)
kubectl patch service digiland-production -n digiland-production \
  -p '{"spec":{"selector":{"app":"digiland-blue"}}}'

# Verify traffic is flowing to blue
kubectl describe svc digiland-production -n digiland-production | grep Selector

# Scale down green deployment
kubectl scale deployment digiland-green -n digiland-production --replicas=0
```

### Database Migration Rollback

If a deployment included database migrations that need to be reversed:

```bash
# Run reverse migration
kubectl exec -it deployment/digiland -n digiland-production -- \
  python manage.py migrate core [PREVIOUS_MIGRATION_NUMBER]

# For critical reversions, use a SQL backup
# Restore from RDS snapshot (AWS Console → RDS → Snapshots → Restore)
```

### Emergency: Full Environment Reset

In extreme cases, restore the entire environment from backup:

```bash
# 1. Scale down application
kubectl scale deployment --all --replicas=0 -n digiland-production

# 2. Restore database from RDS snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier digiland-production-restored \
  --db-snapshot-identifier digiland-production-snapshot-[TIMESTAMP]

# 3. Wait for database to be available
aws rds wait db-instance-available --db-instance-identifier digiland-production-restored

# 4. Update application secrets with new database endpoint
kubectl patch secret digiland-secrets -n digiland-production \
  -p '{"data":{"DATABASE_URL":"[NEW_BASE64_ENCODED_URL]"}}'

# 5. Scale up application
kubectl scale deployment digiland -n digiland-production --replicas=4
```

## Post-Rollback Checklist

- [ ] Verify health endpoints return 200
- [ ] Verify login flow works
- [ ] Verify payment flow works (test transaction)
- [ ] Check error rates in Grafana (< 1%)
- [ ] Check latency in Grafana (P95 < 2s)
- [ ] Notify stakeholders of rollback
- [ ] Create incident ticket for root cause analysis
- [ ] Schedule fix and re-deployment
