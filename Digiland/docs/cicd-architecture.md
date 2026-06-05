# Digiland CI/CD Architecture

## Overview

The Digiland platform uses a modern, enterprise-grade CI/CD pipeline built on GitHub Actions, Docker, Kubernetes, and Helm. The pipeline supports three environments: Development, Staging, and Production, with automated testing, security scanning, and deployment validation at every stage.

## Pipeline Architecture

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Source     │───▶│  Continuous   │───▶│   Build &    │───▶│  Continuous  │
│   Control    │    │  Integration  │    │   Package    │    │  Deployment  │
│   (GitHub)   │    │   (CI)       │    │  (Docker)    │    │   (CD)       │
└─────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                          │                     │                    │
                    ┌─────┴─────┐        ┌──────┴──────┐     ┌──────┴──────┐
                    │ Lint      │        │ Docker Build│     │ Dev: Auto   │
                    │ Type Check│        │ Image Sign  │     │ Stage: Auto │
                    │ Unit Test │        │ SBOM Gen    │     │ Prod: Manual│
                    │ Security  │        │ Push to GHCR│     │ Blue-Green  │
                    └───────────┘        └─────────────┘     └─────────────┘
```

## Branch Strategy

| Branch | Environment | Deployment | Trigger |
|--------|------------|------------|---------|
| `feature/*` | N/A | CI only | Pull Request |
| `develop` | Staging | Automatic | Push to develop |
| `main` | Production (canary) | Manual approval | Release published |
| `hotfix/*` | Production | Emergency | Manual approval |

## CI Pipeline Stages

### Stage 1: Lint and Static Analysis

The linting stage runs in parallel with the frontend lint stage to minimize pipeline duration. Python code is checked with flake8 for style violations, isort for import ordering, black for formatting consistency, and mypy for type checking. The frontend code is checked with ESLint, Prettier, and TypeScript compiler.

### Stage 2: Unit and Integration Tests

Tests run against a real PostgreSQL+PostGIS database and Redis instance using GitHub Actions service containers. Django's test runner executes all unit and integration tests with coverage reporting. The coverage threshold is set at 70% and will fail the build if not met. Coverage reports are uploaded to Codecov for tracking over time.

### Stage 3: Security Scanning

Security scanning runs in parallel with tests (after lint passes). Bandit performs SAST analysis on Python code, Safety checks for known vulnerabilities in dependencies, and detect-secrets scans for accidentally committed secrets. Container scanning with Trivy runs on the built Docker image.

### Stage 4: Build and Package

The Docker image is built using multi-stage builds with layer caching via GitHub Actions cache. Images are tagged with both the commit SHA and branch name for traceability. An SBOM (Software Bill of Materials) is generated using Syft for supply chain transparency.

## Deployment Strategies

### Development Environment

Developers use `docker-compose.dev.yml` for local development with hot reload, exposed database ports, pgAdmin, and Celery Flower for task monitoring. No CI/CD deployment is needed for development.

### Staging Environment

Staging deploys automatically on every push to `develop`. The deployment uses Helm to upgrade the release in the `digiland-staging` namespace. Smoke tests verify the health endpoint and API availability after deployment.

### Production Environment

Production uses a blue-green deployment strategy triggered by GitHub Releases. The process involves:

1. **Build**: Docker image built and pushed with release tag
2. **Deploy Green**: New version deployed alongside the current (blue) version
3. **Health Check**: Green deployment is validated with health checks
4. **Traffic Switch**: Service selector updated to route traffic to green
5. **Validation**: Production URL checked for 200 OK responses
6. **Cleanup**: Old blue deployment removed on success
7. **Rollback**: Automatic rollback to blue if validation fails

## Artifact Management

All Docker images are stored in GitHub Container Registry (ghcr.io). Images are tagged with:
- `sha-<commit>`: Exact commit reference
- `staging`/`production`: Environment-specific latest
- `<version>`: Semantic version from release tags

Images are signed using cosign for supply chain verification. SBOMs are generated and stored as build artifacts for every release.

## Quality Gates

The following conditions must be met for a build to proceed to deployment:

| Gate | Threshold | Action on Failure |
|------|-----------|-------------------|
| Test Coverage | >= 70% | Block deployment |
| Lint Errors | 0 | Block deployment |
| Type Errors | 0 | Block deployment |
| Critical Vulnerabilities | 0 | Block deployment |
| High Vulnerabilities | 0 | Block deployment |
| Health Check | HTTP 200 | Auto-rollback |
| Error Rate | < 5% | Auto-rollback |
| P95 Latency | < 5s | Alert |

## Secrets Management

Secrets are managed through a combination of:
- **GitHub Secrets**: CI/CD pipeline secrets (KUBE_CONFIG, registry credentials)
- **AWS Secrets Manager**: Application runtime secrets (database URL, API keys)
- **Kubernetes Secrets**: Mounted via Helm chart with external-secrets-operator
- **Terraform State**: Encrypted S3 backend with DynamoDB locking
