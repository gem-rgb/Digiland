# Digiland Release Process

## Overview

This document describes the release management process for the Digiland platform, including versioning, branching, changelog generation, and deployment procedures.

## Versioning

Digiland follows Semantic Versioning (SemVer) with the format `MAJOR.MINOR.PATCH`:

- **MAJOR**: Breaking API changes, major feature additions
- **MINOR**: New features, backward-compatible changes
- **PATCH**: Bug fixes, security patches

### Pre-release Versions

- `alpha`: Internal testing (`1.0.0-alpha.1`)
- `beta`: External testing/UAT (`1.0.0-beta.1`)
- `rc`: Release candidate (`1.0.0-rc.1`)

## Release Workflow

### 1. Feature Development

```bash
git checkout develop
git checkout -b feature/PROJ-123-description
# ... develop and test ...
git push origin feature/PROJ-123-description
# Create PR to develop
```

### 2. Staging Validation

After PR merge to `develop`:
- Automatic CI pipeline runs
- Automatic deployment to staging
- QA team validates on staging environment
- UAT sign-off obtained

### 3. Release Preparation

```bash
git checkout main
git merge develop
# Update version in settings.py, package.json
# Update CHANGELOG.md
git tag -a v1.0.0 -m "Release v1.0.0: Description"
git push origin main --tags
```

### 4. Production Deployment

Create a GitHub Release from the tag:
- CI pipeline builds Docker image with version tag
- Manual approval required for production environment
- Blue-green deployment executed
- Health checks validated
- Monitoring confirms stability

### 5. Post-Release

- Verify all features in production
- Update documentation
- Notify stakeholders
- Archive release branch

## Hotfix Process

For critical production fixes:

```bash
git checkout main
git checkout -b hotfix/PROJ-456-description
# ... fix and test ...
git push origin hotfix/PROJ-456-description
# Create PR to main AND develop
# Emergency production deployment
```

## Rollback

If a release causes issues in production:

1. **Automatic Rollback**: Triggered by health check failures or error rate spikes
2. **Manual Rollback**: See [runbook-rollback.md](./runbook-rollback.md)

```bash
# Helm rollback to previous release
helm rollback digiland -n digiland-production [REVISION]

# Or revert service selector for blue-green
kubectl patch service digiland-production -n digiland-production \
  -p '{"spec":{"selector":{"app":"digiland-blue"}}}'
```
