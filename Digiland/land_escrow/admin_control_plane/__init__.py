"""
Enterprise Admin Control Plane
================================

A separate security domain for all administrative operations.

Architecture Principle: The admin control plane is logically isolated from
the customer-facing application. Compromise of the public application does
NOT automatically lead to compromise of administrative systems.

Security Layers:
1. Network Isolation (VPN/Zero Trust/Private Network)
2. Phishing-Resistant Authentication (Hardware Keys/WebAuthn)
3. Mandatory MFA (TOTP + Hardware Key)
4. Fine-Grained Authorization (RBAC + ABAC)
5. Financial Action Protection (Dual Approval)
6. Immutable Audit Trail
7. Emergency Controls
"""
__version__ = '1.0.0'

default_app_config = 'admin_control_plane.apps.AdminControlPlaneConfig'
