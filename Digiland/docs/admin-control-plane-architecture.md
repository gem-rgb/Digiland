# Admin Control Plane Architecture

**Document Version:** 1.0  
**Classification:** Confidential — Internal Use Only  
**Last Updated:** 2025-01-15  
**Owner:** Platform Architecture Team  
**Review Cycle:** Quarterly  

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Control Plane Separation](#control-plane-separation)
3. [Access Control Architecture](#access-control-architecture)
4. [Financial Protection Architecture](#financial-protection-architecture)
5. [Session Security](#session-security)
6. [Audit Architecture](#audit-architecture)
7. [Emergency Controls](#emergency-controls)
8. [Monitoring & Alerting](#monitoring--alerting)

---

## Architecture Overview

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PUBLIC INTERNET                                │
│                                                                             │
│    ┌────────────────────┐              ┌────────────────────────┐           │
│    │   Public Users     │              │   Admin Users          │           │
│    │   (Buyers/Sellers) │              │   (Platform Staff)     │           │
│    └────────┬───────────┘              └───────────┬────────────┘           │
│             │                                      │                        │
└─────────────┼──────────────────────────────────────┼────────────────────────┘
              │                                      │
    ══════════╪══════════════════════════════════════╪══════════  NETWORK EDGE
              │                                      │
    ┌─────────┴──────────┐              ┌────────────┴───────────┐
    │  PUBLIC APP        │              │  ADMIN CONTROL PLANE  │
    │  LOAD BALANCER     │              │  LOAD BALANCER        │
    │  (ALB - Public)    │              │  (ALB - Internal)     │
    │                    │              │  + WAF + IP Allowlist  │
    └─────────┬──────────┘              └────────────┬───────────┘
              │                                      │
    ┌─────────┴──────────┐              ┌────────────┴───────────┐
    │  PUBLIC APP        │              │  ADMIN APP             │
    │  K8S NAMESPACE     │              │  K8S NAMESPACE         │
    │  ┌──────────────┐  │              │  ┌──────────────────┐  │
    │  │ Web Pods     │  │              │  │ Admin API Pods   │  │
    │  │ Celery       │  │              │  │ Admin UI Pods    │  │
    │  │ React SSR    │  │              │  │ Auth Service     │  │
    │  └──────┬───────┘  │              │  └────────┬─────────┘  │
    │         │          │              │           │            │
    │  ┌──────┴───────┐  │              │  ┌────────┴─────────┐  │
    │  │ Public DB    │  │              │  │ Admin DB         │  │
    │  │ (Schema A)   │  │              │  │ (Schema B)       │  │
    │  └──────┬───────┘  │              │  └────────┬─────────┘  │
    └─────────┼──────────┘              └───────────┼────────────┘
              │                                      │
              │     ┌─────────────────────┐          │
              └─────┤   SHARED DATA TIER  ├──────────┘
                    │                     │
                    │  ┌───────────────┐  │
                    │  │  PostgreSQL   │  │
                    │  │  (RLS + RLS)  │  │
                    │  ├───────────────┤  │
                    │  │  Redis        │  │
                    │  │  (Separated)  │  │
                    │  ├───────────────┤  │
                    │  │  S3 Buckets   │  │
                    │  │  (Encrypted)  │  │
                    │  └───────────────┘  │
                    └─────────────────────┘
```

### Network Topology

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AWS VPC: 10.0.0.0/16                       │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    PUBLIC SUBNETS (10.0.1.0/24)               │  │
│  │                                                               │  │
│  │  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐  │  │
│  │  │ Public ALB  │     │ NAT Gateway  │     │ Bastion Host │  │  │
│  │  │ (app.digi)  │     │              │     │ (admin-only) │  │  │
│  │  └──────┬──────┘     └──────────────┘     └──────────────┘  │  │
│  └─────────┼────────────────────────────────────────────────────┘  │
│            │                                                       │
│  ┌─────────┼────────────────────────────────────────────────────┐  │
│  │         │     PRIVATE APP SUBNETS (10.0.10.0/24)             │  │
│  │         │                                                    │  │
│  │  ┌──────┴──────┐    ┌───────────────┐                       │  │
│  │  │ Public EKS  │    │ Admin EKS     │                       │  │
│  │  │ Node Group  │    │ Node Group    │                       │  │
│  │  │             │    │ (DEDICATED)   │                       │  │
│  │  └─────────────┘    └───────┬───────┘                       │  │
│  └─────────────────────────────┼───────────────────────────────┘  │
│                                │                                   │
│  ┌─────────────────────────────┼───────────────────────────────┐  │
│  │                             │   DATA SUBNETS (10.0.20.0/24) │  │
│  │    ┌────────────────┐      │     ┌──────────────────┐       │  │
│  │    │ RDS PostgreSQL │◄─────┴────►│ RDS PostgreSQL   │       │  │
│  │    │ (Public Schema)│            │ (Admin Schema)   │       │  │
│  │    └────────────────┘            └──────────────────┘       │  │
│  │    ┌────────────────┐            ┌──────────────────┐       │  │
│  │    │ ElastiCache    │            │ ElastiCache      │       │  │
│  │    │ (Public Redis) │            │ (Admin Redis)    │       │  │
│  │    └────────────────┘            └──────────────────┘       │  │
│  │    ┌────────────────┐                                       │  │
│  │    │ S3 Buckets     │   ← Shared with RLS/IAM policies     │  │
│  │    │ (Encrypted)    │                                       │  │
│  │    └────────────────┘                                       │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              SECURITY SUBNETS (10.0.30.0/24)                │   │
│  │                                                              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │   │
│  │  │ Vault Cluster│  │ OPA Server   │  │ Monitoring Stack │  │   │
│  │  │ (HSM-backed) │  │ (Policy Eng) │  │ (Prometheus/     │  │   │
│  │  └──────────────┘  └──────────────┘  │  Grafana/Loki)   │  │   │
│  │                                       └──────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Authentication Flow

```
Admin Browser                    Admin API                     Auth Service              Vault/OPA
     │                              │                              │                       │
     │  1. GET /admin/login         │                              │                       │
     │─────────────────────────────>│                              │                       │
     │                              │  2. Serve login page         │                       │
     │  3. Login page               │                              │                       │
     │<─────────────────────────────│                              │                       │
     │                              │                              │                       │
     │  4. POST credentials         │                              │                       │
     │  (email + password)          │                              │                       │
     │─────────────────────────────>│  5. Validate credentials     │                       │
     │                              │─────────────────────────────>│                       │
     │                              │                              │  6. Check password     │
     │                              │                              │  (Argon2id verify)     │
     │                              │  7. Credentials valid        │                       │
     │                              │<─────────────────────────────│                       │
     │                              │                              │                       │
     │  8. MFA challenge required   │                              │                       │
     │<─────────────────────────────│                              │                       │
     │                              │                              │                       │
     │  9. POST MFA response        │                              │                       │
     │  (TOTP code / WebAuthn)      │                              │                       │
     │─────────────────────────────>│  10. Validate MFA            │                       │
     │                              │─────────────────────────────>│                       │
     │                              │                              │  11. MFA verified      │
     │                              │  12. Session created         │                       │
     │                              │<─────────────────────────────│                       │
     │                              │                              │                       │
     │  13. Set session cookie      │                              │                       │
     │  (HTTP-only, Secure,         │                              │                       │
     │   SameSite=Strict)           │                              │                       │
     │<─────────────────────────────│                              │                       │
     │                              │                              │                       │
     │  14. Subsequent request      │                              │                       │
     │  (with session cookie)       │                              │                       │
     │─────────────────────────────>│  15. Validate session        │                       │
     │                              │  16. Check authorization     │                       │
     │                              │─────────────────────────────────────────────────────>│
     │                              │                              │  17. Policy decision   │
     │                              │  18. Authorized              │<──────────────────────│
     │  19. Response                │                              │                       │
     │<─────────────────────────────│                              │                       │
```

---

## Control Plane Separation

The admin control plane is architecturally separated from the public application across multiple dimensions to prevent compromise of one from affecting the other.

### Separation Dimensions

| Dimension | Public Application | Admin Control Plane | Separation Mechanism |
|-----------|-------------------|---------------------|---------------------|
| **DNS** | `app.digiland.co.ke` | `admin.digiland.internal` | Separate domain; admin on internal DNS only |
| **TLS Certificate** | Public CA (Let's Encrypt) | Internal CA (Vault PKI) | Different CA chains; no cross-trust |
| **Load Balancer** | Public ALB (internet-facing) | Internal ALB (no public IP) | Separate AWS ALB instances |
| **Kubernetes Namespace** | `digiland-public` | `digiland-admin` | K8s namespace + NetworkPolicy |
| **K8s Node Group** | Public node group | Dedicated admin node group | Node affinity + taints/tolerations |
| **Database Schema** | `public` schema | `admin` schema | PostgreSQL schema isolation + RLS |
| **Database User** | `digiland_app` (read/write limited) | `digiland_admin` (elevated, scoped) | Separate credentials + role permissions |
| **Redis** | ElastiCache `public-redis` | ElastiCache `admin-redis` | Separate clusters, encryption in-transit |
| **S3 Buckets** | `dl-public-uploads` | `dl-admin-reports`, `dl-kyc-docs` | Separate buckets with distinct IAM policies |
| **Service Accounts** | K8s SA `public-sa` | K8s SA `admin-sa` | Separate K8s RBAC roles |
| **Secrets** | Vault path `secret/public/` | Vault path `secret/admin/` | Vault namespace + policy isolation |
| **Monitoring** | Public dashboards | Admin-specific dashboards | Separate Grafana folders + access |
| **CI/CD Pipeline** | `.github/workflows/public-*` | `.github/workflows/admin-*` | Separate pipelines with different reviewers |
| **Container Registry** | `ecr-public` repo | `ecr-admin` repo | Separate ECR repositories |

### Separate Deployment Configuration

```yaml
# admin-deployment.yaml (excerpt)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: admin-api
  namespace: digiland-admin
  labels:
    app: admin-api
    tier: control-plane
    security-level: critical
spec:
  replicas: 2
  selector:
    matchLabels:
      app: admin-api
  template:
    metadata:
      labels:
        app: admin-api
      annotations:
        vault.hashicorp.com/agent-inject: "true"
        vault.hashicorp.com/role: "admin-api"
        vault.hashicorp.com/secret-volume-path: "/vault/secrets"
    spec:
      serviceAccountName: admin-sa
      tolerations:
        - key: "dedicated"
          operator: "Equal"
          value: "admin"
          effect: "NoSchedule"
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: dedicated
                    operator: In
                    values:
                      - admin
      containers:
        - name: admin-api
          image: ECR_ADMIN_REPO/admin-api:latest
          securityContext:
            runAsNonRoot: true
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
          env:
            - name: ADMIN_MODE
              value: "true"
            - name: SESSION_TIMEOUT_IDLE
              value: "900"        # 15 minutes
            - name: SESSION_TIMEOUT_ABSOLUTE
              value: "14400"      # 4 hours
            - name: MFA_REQUIRED
              value: "true"
            - name: DUAL_APPROVAL_ENABLED
              value: "true"
```

### Separate Authentication

The admin control plane uses a completely separate authentication pipeline:

| Property | Public App | Admin Control Plane |
|----------|-----------|---------------------|
| Auth Provider | Django Allauth (email/password + social) | Custom admin auth service |
| Password Hash | Argon2id (memory: 64MB, iterations: 3) | Argon2id (memory: 128MB, iterations: 4) |
| MFA | Optional (TOTP for sellers) | Mandatory (FIDO2 + TOTP backup) |
| Session Storage | Redis (7-day TTL) | Redis (4-hour TTL, encrypted) |
| Session Cookie | `sessionid` | `admin_sessionid` (separate name) |
| Password Policy | 8+ chars | 16+ chars, no dictionary, annual rotation |
| Account Lockout | 10 failures / 1 hour | 5 failures / 30 minutes (manual unlock) |
| Login Rate Limit | 20/min/IP | 5/min/IP + 10/hour/account |
| Step-up Auth | Not implemented | Required for financial/config operations |

### Separate Monitoring

| Aspect | Public App Monitoring | Admin Monitoring |
|--------|----------------------|------------------|
| Metrics Namespace | `digiland_public_*` | `digiland_admin_*` |
| Log Stream | `/digiland/public/` | `/digiland/admin/` |
| Alert Channel | `#platform-alerts` Slack | `#admin-security-alerts` Slack + PagerDuty |
| Dashboard | "Public App Overview" | "Admin Control Plane Security" |
| Retention | 30 days hot, 1 year cold | 90 days hot, 7 years cold (compliance) |
| Access | All engineers | Security team + senior leadership only |

### Separate Secrets

All admin secrets are stored in HashiCorp Vault with distinct policies:

```hcl
# Vault policy: admin-api
path "secret/data/admin/*" {
  capabilities = ["read"]
}

path "secret/data/public/*" {
  capabilities = ["deny"]  # Admin service CANNOT read public secrets
}

path "database/creds/admin-db" {
  capabilities = ["read"]
}

path "database/creds/public-db" {
  capabilities = ["deny"]  # Admin service CANNOT read public DB creds
}
```

---

## Access Control Architecture

### Network-Level Access (Defense in Depth)

```
Layer 1: Internet Gateway
  └── Only public ALB accessible from internet
      └── Admin ALB is INTERNAL only (no public IP)

Layer 2: WAF + IP Allowlist
  └── AWS WAF rules on admin ALB
      ├── IP set allowlist: office IPs + VPN egress IPs
      ├── Geographic restriction: Kenya + approved countries
      ├── Rate limiting: 100 requests/min per IP
      └── Block known malicious IPs (threat intelligence feeds)

Layer 3: VPN / Zero Trust Network Access
  └── Cloudflare Access or AWS Client VPN
      ├── Certificate-based device authentication
      ├── User identity verification (SSO)
      └── Device posture check (OS patches, endpoint protection)

Layer 4: Application-Level Authentication
  └── Admin Auth Service
      ├── Password verification (Argon2id)
      ├── MFA verification (FIDO2/TOTP)
      ├── Device fingerprint validation
      └── Session creation with device binding

Layer 5: Authorization (RBAC + ABAC)
  └── Open Policy Agent (OPA)
      ├── Role-Based Access Control (RBAC)
      ├── Attribute-Based Access Control (ABAC)
      ├── Context-aware policy decisions
      └── Dual-approval gate for critical operations
```

### Authentication Flow (Password + MFA + Hardware Key)

```python
# Pseudocode: Admin Authentication Pipeline

def authenticate_admin(email: str, password: str, mfa_code: str = None, 
                       webauthn_response: dict = None) -> Session:
    """Multi-stage admin authentication with progressive security."""
    
    # Stage 1: Credential Validation
    admin = AdminRepository.find_by_email(email)
    if not admin or not admin.is_active:
        raise AuthenticationFailed("Invalid credentials")
    
    if not verify_argon2id(password, admin.password_hash):
        AdminAuthService.record_failed_attempt(admin.id)
        if admin.failed_attempts >= 5:
            AdminAuthService.lock_account(admin.id)
            AlertService.notify("admin_account_locked", admin_id=admin.id)
        raise AuthenticationFailed("Invalid credentials")
    
    # Stage 2: IP/Network Validation
    if not NetworkValidator.is_allowed_ip(request.remote_addr):
        raise AuthenticationFailed("Access denied from this network")
    
    # Stage 3: MFA Verification
    if not mfa_code and not webauthn_response:
        return ChallengeRequired(challenge_type="mfa")
    
    if webauthn_response:
        if not WebAuthnService.verify(webauthn_response, admin.webauthn_credentials):
            raise AuthenticationFailed("MFA verification failed")
    elif mfa_code:
        if not TOTPService.verify(mfa_code, admin.totp_secret):
            AdminAuthService.record_mfa_failure(admin.id)
            raise AuthenticationFailed("MFA verification failed")
    
    # Stage 4: Device Binding
    device_fingerprint = DeviceFingerprint.generate(request)
    if admin.registered_devices and device_fingerprint not in admin.registered_devices:
        AlertService.notify("new_device_admin_login", admin_id=admin.id)
        # Require step-up: email/SMS confirmation
    
    # Stage 5: Session Creation
    session = SessionService.create(
        admin_id=admin.id,
        device_fingerprint=device_fingerprint,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        ttl=14400,  # 4 hours absolute max
        idle_timeout=900,  # 15 minutes
    )
    
    # Stage 6: Audit Logging
    AuditLogService.log(
        event="admin_login_success",
        actor=admin.id,
        ip=request.remote_addr,
        device=device_fingerprint,
        mfa_method="webauthn" if webauthn_response else "totp",
    )
    
    # Stage 7: Notification
    NotificationService.send(admin, "Login detected from {ip} at {time}")
    
    return session
```

### Authorization Model (RBAC + ABAC)

#### Role Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                        SUPER ADMIN                              │
│  Full system access; role management; emergency controls;       │
│  Requires: FIDO2 + TOTP + hardware signing key                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐ │
│  │ FINANCE ADMIN  │  │ COMPLIANCE     │  │ SECURITY ADMIN   │ │
│  │                │  │ OFFICER        │  │                  │ │
│  │ - Approve      │  │ - Review KYC   │  │ - View audit     │ │
│  │   withdrawals  │  │ - Approve/rej  │  │   logs           │ │
│  │ - Process      │  │   KYC apps     │  │ - Manage alert   │ │
│  │   refunds      │  │ - View user    │  │   rules          │ │
│  │ - View settle- │  │   PII          │  │ - Incident       │ │
│  │   ments        │  │ - Compliance   │  │   response       │ │
│  │ - Freeze       │  │   reporting    │  │ - Session mgmt   │ │
│  │   accounts     │  │                │  │                  │ │
│  └────────────────┘  └────────────────┘  └──────────────────┘ │
│                                                                 │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐ │
│  │ SUPPORT AGENT  │  │ READ-ONLY      │  │ AUDITOR          │ │
│  │                │  │ ANALYST        │  │                  │ │
│  │ - View user    │  │ - View dash    │  │ - Read audit     │ │
│  │   profiles     │  │   boards       │  │   logs only      │ │
│  │ - View trans-  │  │ - Read-only    │  │ - Export logs    │ │
│  │   action hist  │  │   access       │  │   (no PII)       │ │
│  │ - Create       │  │                │  │ - Compliance     │ │
│  │   support      │  │                │  │   reports        │ │
│  │   tickets      │  │                │  │                  │ │
│  └────────────────┘  └────────────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

#### Permission Scoping

```rego
# OPA Policy: admin_authorization.rego

package digiland.admin.authz

# RBAC: Role-to-permission mapping
default allow = false

allow {
    some role in input.roles
    some permission in role_permissions[role]
    permission.action == input.action
    permission.resource == input.resource
}

# ABAC: Context-aware checks
allow {
    some role in input.roles
    role_permissions[role][_] == {"action": input.action, "resource": input.resource}
    
    # Time-of-day restriction for non-super-admins
    input.role != "super_admin"
    working_hours
}

# Dual approval gate for financial operations
allow {
    input.action == "approve_withdrawal"
    input.resource == "financial"
    
    # First approval
    count(input.approvals) >= 1
    input.approvals[0].role == "finance_admin"
    
    # Second approval must be different person
    count(input.approvals) >= 2
    input.approvals[1].role == "finance_admin"
    input.approvals[1].admin_id != input.approvals[0].admin_id
    
    # Different IP addresses
    input.approvals[1].ip != input.approvals[0].ip
}

working_hours {
    # EAT (East Africa Time) business hours
    time.weekday(input.time) != "Saturday"
    time.weekday(input.time) != "Sunday"
    hour := time.hour(input.time)
    hour >= 8
    hour < 18
}

role_permissions := {
    "super_admin": [
        {"action": "*", "resource": "*"},
    ],
    "finance_admin": [
        {"action": "approve_withdrawal", "resource": "financial"},
        {"action": "process_refund", "resource": "financial"},
        {"action": "view_settlement", "resource": "financial"},
        {"action": "freeze_account", "resource": "financial"},
        {"action": "view_user_financial", "resource": "user"},
    ],
    "compliance_officer": [
        {"action": "review_kyc", "resource": "kyc"},
        {"action": "approve_kyc", "resource": "kyc"},
        {"action": "reject_kyc", "resource": "kyc"},
        {"action": "view_user_pii", "resource": "user"},
        {"action": "compliance_report", "resource": "report"},
    ],
    "support_agent": [
        {"action": "view_user_profile", "resource": "user"},
        {"action": "view_transactions", "resource": "financial"},
        {"action": "create_ticket", "resource": "support"},
    ],
    "read_only_analyst": [
        {"action": "view_dashboard", "resource": "dashboard"},
        {"action": "view_reports", "resource": "report"},
    ],
    "auditor": [
        {"action": "read_audit_log", "resource": "audit"},
        {"action": "export_audit_log", "resource": "audit"},
        {"action": "compliance_report", "resource": "report"},
    ],
}
```

---

## Financial Protection Architecture

### Dual Approval Workflow

```
┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
│ Request  │      │ First    │      │ Second   │      │ Execute  │
│ Created  │─────>│ Approval │─────>│ Approval │─────>│ & Settle │
│          │      │          │      │          │      │          │
│ Amount   │      │ Verify   │      │ Verify   │      │ Hash     │
│ Dest     │      │ details  │      │ details  │      │ verify   │
│ Hash     │      │ Sign     │      │ Sign     │      │ Submit   │
│ locked   │      │ w/ HW key│      │ w/ HW key│      │ to bank  │
└──────────┘      └──────────┘      └──────────┘      └──────────┘
     │                 │                  │                  │
     ▼                 ▼                  ▼                  ▼
  Audit Log        Audit Log         Audit Log          Audit Log
  (created)        (approved-1)      (approved-2)       (executed)
     │                 │                  │                  │
     └─────────────────┴──────────────────┴──────────────────┘
                              │
                    Hash chain verification
                    at each step
```

**Transaction Signing Process:**

1. **Creation**: Admin creates withdrawal request → system generates `transaction_hash = SHA256(amount + destination + timestamp + nonce)`
2. **First Approval**: Finance admin reviews → signs with hardware key → `approval_1_sig = Sign(HW_KEY_1, transaction_hash)`
3. **Second Approval**: Different finance admin reviews → signs with hardware key → `approval_2_sig = Sign(HW_KEY_2, transaction_hash)`
4. **Execution**: System verifies both signatures match `transaction_hash` → verifies amount/destination unchanged → submits to payment provider
5. **Reconciliation**: Post-execution, compare settled amount/destination against `transaction_hash`

### Step-Up Authentication

Certain operations require re-authentication even within an active session:

| Operation | Step-Up Requirement | MFA Type |
|-----------|-------------------|----------|
| Approve withdrawal > KES 100K | Password + MFA | FIDO2 (required) |
| Approve withdrawal > KES 1M | Password + MFA + delay | FIDO2 + 30-min cooling |
| Modify admin roles | Password + MFA | FIDO2 (required) |
| Emergency freeze/unfreeze | Password + MFA | FIDO2 (required) |
| Export user data | Password + MFA | TOTP or FIDO2 |
| Modify platform configuration | Password + MFA | FIDO2 (required) |
| Impersonate user | Password + MFA + justification | FIDO2 (required) |

### Risk Scoring

Every financial transaction receives a risk score before approval:

```python
class TransactionRiskScorer:
    def score(self, transaction: Transaction, admin: Admin) -> RiskScore:
        score = 0
        
        # Amount-based risk
        if transaction.amount > 5_000_000:  # KES 5M+
            score += 30
        elif transaction.amount > 1_000_000:  # KES 1M+
            score += 20
        elif transaction.amount > 500_000:  # KES 500K+
            score += 10
        
        # Velocity risk (approvals by same admin in last hour)
        recent_approvals = self.get_recent_approvals(admin.id, hours=1)
        if recent_approvals > 5:
            score += 15
        if recent_approvals > 10:
            score += 20
        
        # Beneficiary risk
        if transaction.destination_is_new:
            score += 15
        if transaction.destination_country != "KE":
            score += 20
        
        # Time-based risk
        if not is_business_hours():
            score += 10
        if is_weekend():
            score += 5
        
        # Pattern risk (cumulative to same beneficiary today)
        daily_total = self.get_daily_total_to_beneficiary(
            transaction.destination_account
        )
        if daily_total + transaction.amount > 10_000_000:
            score += 25
        
        return RiskScore(
            value=score,
            level="critical" if score >= 60 else
                  "high" if score >= 40 else
                  "medium" if score >= 20 else
                  "low",
            requires_cooling_period=score >= 40,
            requires_triple_approval=score >= 60,
        )
```

### Transaction Signing

All financial approvals are cryptographically signed using hardware security keys:

```
Transaction Signing Protocol:
1. Admin reviews transaction details on screen
2. Admin clicks "Approve" button
3. System generates signing challenge = SHA256(tx_hash + admin_id + timestamp)
4. Browser prompts for hardware key touch (WebAuthn)
5. Hardware key signs challenge: signature = Sign(private_key, challenge)
6. Server verifies signature against admin's registered public key
7. Approval recorded with signature in audit log
8. At execution, all signatures verified before processing
```

### Withdrawal Freeze Capability

```
┌─────────────────────────────────────────────────────────┐
│                 WITHDRAWAL FREEZE FLOW                   │
│                                                          │
│  Trigger:                                                │
│  ├── Manual: Super Admin activates via Emergency Panel   │
│  ├── Automatic: Risk score threshold exceeded            │
│  └── Automatic: Anomaly detection triggers               │
│                                                          │
│  Effects:                                                │
│  ├── All pending withdrawals immediately paused          │
│  ├── New withdrawal requests rejected with message       │
│  ├── Scheduled withdrawals cancelled                     │
│  ├── In-progress withdrawals rolled back if unsettled    │
│  └── All admin users notified via Slack + PagerDuty      │
│                                                          │
│  Requirements:                                           │
│  ├── Dual super admin approval to activate               │
│  ├── Mandatory justification text field                  │
│  ├── Auto-expiry: 4 hours (extendable with re-approval) │
│  ├── Post-incident review within 24 hours                │
│  └── Full audit trail of freeze/unfreeze actions         │
└─────────────────────────────────────────────────────────┘
```

---

## Session Security

### Session Lifecycle

```
┌──────────────────────────────────────────────────────────────────────┐
│                     ADMIN SESSION LIFECYCLE                          │
│                                                                      │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌───────────────┐  │
│  │ Created │───>│ Active   │───>│ Idle     │───>│ Expired       │  │
│  │         │    │          │    │ Timeout   │    │ (auto-logout) │  │
│  │ MFA     │    │ 15-min   │    │ Warning   │    │               │  │
│  │ verified│    │ token    │    │ at 10min  │    │ Session       │  │
│  │         │    │ rotation │    │ idle      │    │ destroyed     │  │
│  └─────────┘    └────┬─────┘    └──────────┘    └───────────────┘  │
│                      │                                               │
│                      │  Step-up auth                                 │
│                      │  (for critical ops)                           │
│                      ▼                                               │
│                ┌──────────┐                                          │
│                │ Elevated │  Time-limited: 5 minutes                 │
│                │ Session  │  Re-auth required after expiry           │
│                └──────────┘                                          │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  TERMINATION TRIGGERS                                        │   │
│  │  - Idle timeout (15 minutes)                                 │   │
│  │  - Absolute timeout (4 hours)                                │   │
│  │  - Manual logout                                             │   │
│  │  - Password change (all sessions invalidated)                │   │
│  │  - Admin deactivation                                        │   │
│  │  - Global session revocation (emergency)                     │   │
│  │  - IP address change mid-session                             │   │
│  │  - Concurrent session detection (new login kills old)        │   │
│  │  - Device fingerprint mismatch                               │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### Timeout Policies

| Session Type | Idle Timeout | Absolute Timeout | Token Rotation |
|-------------|-------------|-----------------|----------------|
| Standard Admin | 15 minutes | 4 hours | Every 15 minutes |
| Elevated (step-up) | 5 minutes | 5 minutes | Every request |
| Emergency Mode | 30 minutes | 8 hours | Every 5 minutes |
| Read-Only Analyst | 30 minutes | 8 hours | Every 30 minutes |

### Device Binding

```
Device Fingerprint Composition:
├── User-Agent string (browser + OS)
├── Screen resolution
├── Timezone
├── Language preferences
├── Canvas fingerprint (non-PII rendering characteristics)
├── WebRTC local IP (within VPN)
└── Installed fonts subset hash

Binding Rules:
1. First login registers device fingerprint
2. Subsequent logins must match registered fingerprint (±10% tolerance)
3. New device triggers:
   - Alert to admin's registered email
   - Alert to security Slack channel
   - Optional step-up verification (email code)
4. Maximum 3 registered devices per admin
5. Device registration requires super admin approval
```

### Anomaly Detection

| Anomaly Type | Detection Method | Response |
|-------------|-----------------|----------|
| IP address change | Compare session IP vs. current request IP | Terminate session + alert |
| Impossible travel | Geolocation + time between logins | Terminate session + alert + lock account |
| Unusual time access | Login outside business hours | Alert + require step-up MFA |
| Concurrent sessions | Multiple active sessions for same admin | Kill oldest session + alert |
| Behavioral anomaly | ML model on admin action patterns | Alert + optional session downgrade (read-only) |
| High-velocity actions | Rate of actions exceeds baseline | Alert + progressive delays |
| New user-agent | Browser/device change mid-session | Alert + require re-authentication |

---

## Audit Architecture

### Immutable Logging

```
┌─────────────────────────────────────────────────────────────────────┐
│                     AUDIT LOG ARCHITECTURE                          │
│                                                                     │
│  ┌─────────────┐     ┌──────────────┐     ┌──────────────────┐    │
│  │ Admin API   │────>│ Audit Log    │────>│ PostgreSQL       │    │
│  │ (all events)│     │ Service      │     │ (append-only)    │    │
│  └─────────────┘     │              │     │ - INSERT only    │    │
│  ┌─────────────┐     │ - Hash chain │     │ - No UPDATE/     │    │
│  │ Auth Service │────>│ - Validation │     │   DELETE grants  │    │
│  └─────────────┘     │ - Integrity  │     │ - RLS policies   │    │
│  ┌─────────────┐     │   check      │     └────────┬─────────┘    │
│  │ Financial   │────>│              │              │               │
│  │ Service     │     └──────────────┘              │               │
│  └─────────────┘                                    │               │
│                                    ┌────────────────┘               │
│                                    ▼                                │
│                           ┌──────────────────┐                      │
│                           │ S3 WORM Storage  │                      │
│                           │ (replication)    │                      │
│                           │ - Object Lock    │                      │
│                           │ - 7-year retain  │                      │
│                           └──────────────────┘                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Hash Chain Integrity

Every audit log entry includes a cryptographic hash of the previous entry, creating an unbreakable chain:

```python
class AuditLogEntry:
    id: UUID                    # Unique entry ID
    timestamp: datetime         # UTC timestamp with microseconds
    event_type: str             # Categorized event type
    actor_id: UUID             # Admin who performed action
    actor_ip: str              # IP address of actor
    actor_device: str          # Device fingerprint
    action: str                # Specific action performed
    resource_type: str         # Type of resource affected
    resource_id: str           # ID of resource affected
    before_state: dict         # State before action (JSON)
    after_state: dict          # State after action (JSON)
    request_id: UUID           # Correlation ID for request tracing
    session_id: UUID           # Session that performed action
    mfa_verified: bool         # Whether MFA was active
    
    # Hash chain fields
    previous_hash: str         # SHA-256 hash of previous entry
    entry_hash: str            # SHA-256 hash of this entry (computed)
    
    def compute_hash(self, previous_entry_hash: str) -> str:
        """Compute hash chain for this entry."""
        self.previous_hash = previous_entry_hash
        data = f"{self.id}{self.timestamp}{self.event_type}" \
               f"{self.actor_id}{self.action}{self.resource_type}" \
               f"{self.resource_id}{json.dumps(self.after_state, sort_keys=True)}" \
               f"{self.previous_hash}"
        self.entry_hash = hashlib.sha256(data.encode()).hexdigest()
        return self.entry_hash
```

**Verification Process:**
- Automated hourly job traverses the hash chain
- Any break in the chain triggers P0 security alert
- Manual verification available on demand for investigations
- Weekly full-chain verification with signed attestation

### Retention Policies

| Log Category | Hot Storage | Warm Storage | Cold Archive | Total Retention |
|-------------|------------|-------------|-------------|----------------|
| Authentication events | 90 days | 1 year | 7 years | 7 years |
| Financial transactions | 1 year | 3 years | 7 years | 7 years |
| KYC decisions | 1 year | 3 years | 7 years | 7 years |
| Admin configuration changes | 90 days | 1 year | 7 years | 7 years |
| Session events | 30 days | 1 year | 3 years | 3 years |
| General admin actions | 90 days | 1 year | 3 years | 3 years |

### Search and Export

| Capability | Implementation |
|-----------|---------------|
| Full-text search | PostgreSQL `tsvector` on event_type, action, resource_type |
| Time-range queries | Index on timestamp; partitioned by month |
| Actor filtering | Index on actor_id |
| Event type filtering | Index on event_type + action composite |
| Export to CSV/JSON | Admin API endpoint (requires dual approval for bulk export) |
| SIEM integration | Real-time streaming via Kafka topic `admin-audit-events` |
| Forensic export | Encrypted archive with chain of custody documentation |

---

## Emergency Controls

### Withdrawal Freeze

```
Activation: Emergency Panel → "Freeze All Withdrawals"
Requires: Dual super admin approval + mandatory justification
Effect: 
  - All pending withdrawals paused immediately
  - New withdrawal requests rejected
  - In-progress withdrawals cancelled if unsettled
  - All admins notified (Slack + PagerDuty + email)
  - Auto-expiry: 4 hours (extendable with re-approval)
Deactivation: Dual super admin approval + post-incident review
```

### Session Revocation

```
Activation: Emergency Panel → "Revoke All Sessions" or per-user
Requires: Super admin + mandatory justification
Effect:
  - All active admin sessions invalidated immediately
  - All admins forced to re-authenticate
  - Compromised sessions cannot be renewed
  - Session tokens blacklisted in Redis
  - All admins notified via out-of-band channel (SMS)
```

### Account Lockdown

```
Activation: Emergency Panel → "Lockdown User Account" 
Requires: Super admin + compliance officer approval
Effect:
  - Target account frozen (no login, no transactions)
  - All active sessions for target account terminated
  - Pending settlement transactions paused
  - Regulatory notification if required
  - Compliance team alerted for review
```

### Incident Mode

```
Activation: Emergency Panel → "Activate Incident Mode"
Requires: Super admin + CISO approval
Effect:
  - Platform enters read-only mode for all admins
  - Only audit log viewing and emergency controls available
  - All financial operations suspended
  - All configuration changes blocked
  - Enhanced monitoring and logging activated
  - All actions during incident mode flagged for post-review
  - Auto-expiry: 24 hours (extendable with re-approval)
Deactivation: CISO + CTO joint approval + mandatory post-incident report
```

---

## Monitoring & Alerting

### Real-Time Admin Action Monitoring

All admin actions are streamed in real-time to the security monitoring dashboard:

```yaml
# Monitored Events (Kafka → Prometheus → Grafana → Alerting)
monitored_events:
  - admin_login_success
  - admin_login_failure
  - admin_mfa_failure
  - admin_session_created
  - admin_session_terminated
  - admin_password_change
  - admin_role_change
  - admin_permission_change
  
  # Financial events (HIGH PRIORITY)
  - withdrawal_approved
  - withdrawal_executed
  - refund_processed
  - settlement_released
  - account_frozen
  - account_unfrozen
  
  # KYC events
  - kyc_approved
  - kyc_rejected
  - kyc_document_accessed
  
  # Configuration events
  - platform_config_changed
  - alert_rule_modified
  - emergency_control_activated
  
  # Data access events
  - bulk_data_export
  - user_pii_accessed
  - kyc_document_downloaded
```

### Alert Rules and Thresholds

```yaml
# Prometheus Alerting Rules
groups:
  - name: admin_security_critical
    rules:
      - alert: AdminAccountLocked
        expr: admin_failed_logins_total >= 5
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Admin account locked due to failed logins"
          
      - alert: OffHoursAdminLogin
        expr: admin_login_total and hour() < 6 or hour() >= 20
        for: 0m
        labels:
          severity: warning
        annotations:
          summary: "Admin login outside business hours"
          
      - alert: HighValueApproval
        expr: admin_withdrawal_approved_amount > 1000000
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "High-value withdrawal approved (>KES 1M)"
          
      - alert: RapidApprovals
        expr: rate(admin_withdrawal_approved_total[5m]) > 5
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Unusual rate of withdrawal approvals"
          
      - alert: NewDeviceAdminLogin
        expr: admin_new_device_login_total > 0
        for: 0m
        labels:
          severity: warning
        annotations:
          summary: "Admin login from unrecognized device"
          
      - alert: AuditLogChainBreak
        expr: audit_hash_chain_valid == 0
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Audit log hash chain integrity violation"
          
      - alert: BulkDataExport
        expr: admin_records_accessed_total > 500
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Unusual volume of data access"
          
      - alert: EmergencyControlActivated
        expr: admin_emergency_control_activated_total > 0
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Emergency control has been activated"
```

### SIEM Integration

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Admin API    │────>│ Kafka Topic  │────>│ Logstash /   │────>│ Elasticsearch│
│ (events)     │     │ admin-events │     │ Fluentd      │     │ (SIEM)       │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                                                                      │
┌──────────────┐     ┌──────────────┐     ┌──────────────┐              │
│ Auth Service │────>│ Kafka Topic  │────>│ Enrichment   │──────────────┤
│ (auth events)│     │ auth-events  │     │ Pipeline     │              │
└──────────────┘     └──────────────┘     │ (geo, threat │              │
                                          │  intel,      │              │
┌──────────────┐     ┌──────────────┐     │  context)    │     ┌────────┴─────┐
│ Vault        │────>│ Kafka Topic  │────>│              │────>│ Kibana       │
│ (secret acc) │     │ vault-events │     └──────────────┘     │ Dashboards   │
└──────────────┘     └──────────────┘                           └──────────────┘
```

### Metrics and Dashboards

**Admin Security Dashboard (Grafana):**

| Panel | Metric | Visualization |
|-------|--------|---------------|
| Active Admin Sessions | `admin_active_sessions` | Gauge |
| Login Success Rate | `rate(admin_login_success) / rate(admin_login_total)` | Stat |
| Failed MFA Attempts (24h) | `increase(admin_mfa_failure[24h])` | Counter |
| Withdrawal Approval Volume | `sum(admin_withdrawal_approved_amount)` | Time series |
| KYC Decisions Today | `increase(kyc_decisions_total[24h])` | Bar chart |
| Anomaly Alerts (7d) | `increase(admin_anomaly_detected[7d])` | Heatmap |
| Data Access Volume | `sum(admin_records_accessed)` | Time series |
| Emergency Control Status | `admin_emergency_control_active` | Status indicator |
| Audit Chain Health | `audit_hash_chain_valid` | Status indicator |

**Financial Oversight Dashboard:**

| Panel | Metric | Visualization |
|-------|--------|---------------|
| Pending Approvals | `admin_withdrawal_pending_count` | Counter |
| Approved Today (KES) | `sum(admin_withdrawal_approved_amount[24h])` | Stat |
| Approval Velocity | `rate(admin_withdrawal_approved_total[1h])` | Time series |
| Risk Score Distribution | `histogram_quantile(admin_tx_risk_score)` | Histogram |
| Freeze Status | `admin_withdrawal_frozen` | Status indicator |
| High-Value Alerts | `increase(admin_high_value_approval[24h])` | Alert list |
