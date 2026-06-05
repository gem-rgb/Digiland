# Digiland Backup & Recovery

## Backup Strategy

### Database Backups

| Component | Method | Frequency | Retention | Location |
|-----------|--------|-----------|-----------|----------|
| PostgreSQL (Production) | RDS Automated Snapshot | Daily at 03:00 UTC | 30 days | AWS Region |
| PostgreSQL (Staging) | RDS Automated Snapshot | Daily at 03:00 UTC | 7 days | AWS Region |
| PostgreSQL (Manual) | pg_dump | Before migrations | 90 days | S3 bucket |
| Redis | ElastiCache Snapshot | Daily | 7 days | AWS Region |

### Application Data

| Component | Method | Versioning | Location |
|-----------|--------|------------|----------|
| Media Files (S3) | S3 Versioning | Enabled | Same region |
| Static Files (S3/CloudFront) | S3 Versioning | Enabled | Same region |
| Docker Images | GHCR | All tags | ghcr.io |
| Helm Charts | Git | All versions | GitHub |

### Infrastructure State

| Component | Method | Location |
|-----------|--------|----------|
| Terraform State | S3 + DynamoDB lock | Encrypted S3 bucket |
| Kubernetes Manifests | Git | GitHub |
| Secrets | AWS Secrets Manager | Encrypted at rest |

## Recovery Procedures

### Point-in-Time Database Recovery

```bash
# 1. Identify recovery point (timestamp)
RECOVERY_TIME="2024-01-15T14:30:00Z"

# 2. Restore RDS to point in time
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier digiland-production \
  --target-db-instance-identifier digiland-production-restored \
  --restore-time "$RECOVERY_TIME"

# 3. Wait for restoration
aws rds wait db-instance-available --db-instance-identifier digiland-production-restored

# 4. Update application to point to restored database
# Update Kubernetes secret with new endpoint

# 5. Verify data integrity
# Run Django management command to check critical data
```

### S3 Media Recovery

```bash
# List object versions
aws s3api list-object-versions --bucket digiland-production-media --prefix path/to/file

# Restore specific version
aws s3api copy-object \
  --bucket digiland-production-media \
  --copy-source digiland-production-media/path/to/file?versionId=VERSION_ID \
  --key path/to/file
```

## Disaster Recovery

### RPO and RTO Targets

| Scenario | RPO | RTO | Strategy |
|----------|-----|-----|----------|
| Single AZ failure | 0 | 5 min | Multi-AZ auto failover |
| Region failure | 5 min | 30 min | Cross-region read replica |
| Data corruption | 1 hour | 1 hour | Point-in-time recovery |
| Ransomware | 1 day | 4 hours | Offline backup restoration |

### DR Testing

Disaster recovery procedures must be tested quarterly:
1. Restore database from snapshot to test environment
2. Verify application functionality against restored data
3. Document recovery time and any issues
4. Update runbook if procedures need adjustment
