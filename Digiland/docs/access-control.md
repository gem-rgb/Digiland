# Access Control Model

## Overview

The Digiland platform implements a hybrid Role-Based Access Control (RBAC) and Attribute-Based Access Control (ABAC) model. This approach provides coarse-grained access control through roles while enabling fine-grained permissions through attribute-based rules.

## User Roles

### Role Hierarchy

```
Admin (Superuser)
  └── Staff
       └── Agent
            └── Buyer
                 └── Anonymous
```

### Role Definitions

| Role | Description | Capabilities |
|------|-------------|-------------|
| **Admin** | Platform superuser with full system access | All system operations, user management, platform configuration, financial oversight |
| **Staff** | Internal team members with administrative privileges | Dashboard access, approval workflows, content management, user support |
| **Agent** | Verified real estate agents | Parcel management, buyer assistance, KYC verification, commission tracking |
| **Buyer** | Registered platform users | Parcel browsing, direct settlement transactions, joint purchases, messaging |
| **Anonymous** | Unauthenticated visitors | Public parcel browsing, registration, password reset |

## Permission Matrix

### Parcel Management

| Action | Admin | Staff | Agent | Buyer | Anonymous |
|--------|-------|-------|-------|-------|-----------|
| View public parcels | ✓ | ✓ | ✓ | ✓ | ✓ |
| View parcel details | ✓ | ✓ | ✓ | ✓ | ✓ |
| Create parcel listing | ✓ | ✓ | ✓ | ✗ | ✗ |
| Edit own parcels | ✓ | ✓ | ✓ | ✗ | ✗ |
| Edit any parcel | ✓ | ✓ | ✗ | ✗ | ✗ |
| Delete parcel | ✓ | ✓ | ✗ | ✗ | ✗ |
| Verify parcel | ✓ | ✓ | ✗ | ✗ | ✗ |
| Assign agent | ✓ | ✓ | ✗ | ✗ | ✗ |

### Transaction / Settlement

| Action | Admin | Staff | Agent | Buyer | Anonymous |
|--------|-------|-------|-------|-------|-----------|
| Initiate transaction | ✓ | ✗ | ✗ | ✓ | ✗ |
| View own transactions | ✓ | ✓ | ✓ | ✓ | ✗ |
| View all transactions | ✓ | ✓ | ✗ | ✗ | ✗ |
| Approve transaction | ✓ | ✓ | ✗ | ✓ | ✗ |
| Process payment | ✓ | ✗ | ✗ | ✓ | ✗ |
| Confirm settlement release | ✓ | ✓ | ✗ | ✗ | ✗ |
| Cancel transaction | ✓ | ✓ | ✗ | ✓ | ✗ |
| View financial reports | ✓ | ✓ | ✗ | ✗ | ✗ |

### User Management

| Action | Admin | Staff | Agent | Buyer | Anonymous |
|--------|-------|-------|-------|-------|-----------|
| View own profile | ✓ | ✓ | ✓ | ✓ | ✗ |
| Edit own profile | ✓ | ✓ | ✓ | ✓ | ✗ |
| View other profiles | ✓ | ✓ | ✓* | ✗ | ✗ |
| Create users | ✓ | ✓ | ✗ | ✗ | ✗ |
| Deactivate users | ✓ | ✓ | ✗ | ✗ | ✗ |
| Change user roles | ✓ | ✗ | ✗ | ✗ | ✗ |
| Manage MFA | ✓ | ✓ | ✓ | ✓ | ✗ |

*Agents can view profiles of buyers they are assisting

### Agent-Specific Actions

| Action | Admin | Staff | Agent | Buyer |
|--------|-------|-------|-------|-------|
| Apply as agent | ✗ | ✗ | ✓ | ✓ |
| Complete KYC | ✓ | ✓ | ✓ | ✗ |
| View agent dashboard | ✓ | ✓ | ✓ | ✗ |
| Approve agent applications | ✓ | ✓ | ✗ | ✗ |
| Rate agent | ✓ | ✗ | ✗ | ✓ |
| View agent ratings | ✓ | ✓ | ✓ | ✓ |
| Manage assigned parcels | ✓ | ✓ | ✓ | ✗ |

### Joint Purchase Groups

| Action | Admin | Staff | Agent | Buyer |
|--------|-------|-------|-------|-------|
| Create group | ✗ | ✗ | ✗ | ✓ |
| Invite members | ✗ | ✗ | ✗ | ✓ |
| Accept invitation | ✗ | ✗ | ✗ | ✓ |
| Remove member | ✓ | ✗ | ✗ | ✓ |
| Dissolve group | ✓ | ✓ | ✗ | ✓ |
| View group details | ✓ | ✓ | ✓* | ✓ |

*Agents can view groups for parcels they manage

## Attribute-Based Access Control (ABAC)

Beyond role-based permissions, the system enforces attribute-based rules:

### Ownership Rules

- Users can only edit resources they own (parcels, transactions, groups)
- Agent ownership extends to parcels assigned to them
- Admin and Staff bypass ownership checks

### Status-Based Rules

- Parcels in "Pending Verification" status cannot be purchased
- Transactions in "Completed" status cannot be modified
- Agent applications in "Rejected" status require re-application
- Users with "Suspended" status cannot perform any actions

### Time-Based Rules

- Verification deadlines: Agents must complete verification within 48 hours
- Payment windows: Buyers must complete payment within 24 hours of initiation
- Session timeouts: 30 minutes of inactivity terminates the session

### Location-Based Rules

- Certain features are restricted to Kenyan IP addresses (payment processing)
- International users can browse but cannot complete transactions
- PostGIS-based proximity rules for agent assignment

## Implementation

### Django Permission System

```python
# Custom permission classes
class IsOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role in ['Admin', 'Staff']:
            return True
        return obj.owner == request.user

class IsAgentOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['Admin', 'Staff', 'Agent']

class IsBuyerOrAbove(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['Admin', 'Staff', 'Agent', 'Buyer']
```

### DRF ViewSet Permissions

```python
class ParcelViewSet(viewsets.ModelViewSet):
    permission_classes = {
        'list': [AllowAny],
        'retrieve': [AllowAny],
        'create': [IsAuthenticated, IsAgentOrAdmin],
        'update': [IsAuthenticated, IsOwnerOrAdmin],
        'destroy': [IsAuthenticated, IsAdminUser],
        'verify': [IsAuthenticated, IsAdminOrStaff],
    }
```

### Frontend Route Guards

```typescript
// Route-based access control
const routes = [
  { path: '/admin/*', component: AdminDashboard, roles: ['Admin', 'Staff'] },
  { path: '/agent/*', component: AgentDashboard, roles: ['Agent', 'Admin', 'Staff'] },
  { path: '/dashboard/*', component: BuyerDashboard, roles: ['Buyer', 'Agent', 'Admin', 'Staff'] },
  { path: '/*', component: PublicPages, roles: ['*'] },
];
```

## Audit Logging

All access control decisions are logged:

- **Granted Access**: User, resource, action, timestamp
- **Denied Access**: User, resource, action, reason, timestamp
- **Role Changes**: Who changed, target user, old role, new role, timestamp
- **Permission Escalation**: Any attempt to access above role level

## Security Considerations

1. **Principle of Least Privilege**: Users are assigned the minimum role necessary
2. **Separation of Duties**: No single user can both create and approve critical operations
3. **Defense in Depth**: Both frontend route guards and backend permission checks
4. **No Role Self-Elevation**: Users cannot change their own role
5. **Session Invalidation**: Role changes invalidate all active sessions
