"""URL configuration for the Enterprise Admin Control Plane.

All URLs are mounted under ``/api/v1/admin/control-plane/`` via the
main project URL configuration.

URL Structure
-------------
- ``sessions/``          : Admin session management
- ``approvals/``         : Dual-approval workflow
- ``financial/``         : Financial operations
- ``emergency/``         : Emergency controls
- ``audit/``             : Audit log access
- ``kyc/``               : KYC verification operations
- ``users/``             : User management operations
- ``roles/``             : Role management
- ``permissions/``       : Permission management
"""

from django.urls import path
from . import views

urlpatterns = [
    # ===================================================================
    # SESSION MANAGEMENT
    # ===================================================================
    path(
        'sessions/create',
        views.admin_session_create,
        name='admin-session-create',
    ),
    path(
        'sessions/validate',
        views.admin_session_validate,
        name='admin-session-validate',
    ),
    path(
        'sessions/<uuid:pk>/terminate',
        views.admin_session_terminate,
        name='admin-session-terminate',
    ),
    path(
        'sessions/terminate-all',
        views.admin_session_terminate_all,
        name='admin-session-terminate-all',
    ),
    path(
        'sessions/',
        views.admin_session_list,
        name='admin-session-list',
    ),

    # ===================================================================
    # DUAL APPROVAL
    # ===================================================================
    path(
        'approvals/request',
        views.dual_approval_request,
        name='dual-approval-request',
    ),
    path(
        'approvals/pending',
        views.dual_approval_list_pending,
        name='dual-approval-pending',
    ),
    path(
        'approvals/<uuid:pk>/approve',
        views.dual_approval_approve,
        name='dual-approval-approve',
    ),
    path(
        'approvals/<uuid:pk>/reject',
        views.dual_approval_reject,
        name='dual-approval-reject',
    ),
    path(
        'approvals/<uuid:pk>',
        views.dual_approval_detail,
        name='dual-approval-detail',
    ),

    # ===================================================================
    # FINANCIAL OPERATIONS
    # ===================================================================
    path(
        'financial/withdrawal/initiate',
        views.financial_initiate_withdrawal,
        name='financial-withdrawal-initiate',
    ),
    path(
        'financial/withdrawal/<uuid:pk>/approve',
        views.financial_approve_withdrawal,
        name='financial-withdrawal-approve',
    ),
    path(
        'financial/balance-adjustment',
        views.financial_balance_adjustment,
        name='financial-balance-adjustment',
    ),
    path(
        'financial/payout/<uuid:pk>/approve',
        views.financial_payout_approve,
        name='financial-payout-approve',
    ),
    path(
        'financial/freeze-status',
        views.financial_freeze_status,
        name='financial-freeze-status',
    ),
    path(
        'financial/history',
        views.financial_transaction_history,
        name='financial-transaction-history',
    ),

    # ===================================================================
    # EMERGENCY CONTROLS
    # ===================================================================
    path(
        'emergency/withdrawal-freeze',
        views.emergency_withdrawal_freeze,
        name='emergency-withdrawal-freeze',
    ),
    path(
        'emergency/session-revocation',
        views.emergency_session_revocation,
        name='emergency-session-revocation',
    ),
    path(
        'emergency/incident-mode',
        views.emergency_incident_mode,
        name='emergency-incident-mode',
    ),
    path(
        'emergency/account-lock/<uuid:pk>',
        views.emergency_account_lock,
        name='emergency-account-lock',
    ),
    path(
        'emergency/status',
        views.emergency_status,
        name='emergency-status',
    ),

    # ===================================================================
    # AUDIT
    # ===================================================================
    path(
        'audit/logs',
        views.audit_log_list,
        name='audit-log-list',
    ),
    path(
        'audit/logs/<uuid:pk>',
        views.audit_log_detail,
        name='audit-log-detail',
    ),
    path(
        'audit/integrity-verify',
        views.audit_integrity_verify,
        name='audit-integrity-verify',
    ),
    path(
        'audit/export',
        views.audit_export,
        name='audit-export',
    ),
    path(
        'audit/actor-history',
        views.audit_actor_history,
        name='audit-actor-history',
    ),

    # ===================================================================
    # KYC & VERIFICATION
    # ===================================================================
    path(
        'kyc/<uuid:pk>/approve',
        views.admin_kyc_approve,
        name='admin-kyc-approve',
    ),
    path(
        'kyc/<uuid:pk>/reject',
        views.admin_kyc_reject,
        name='admin-kyc-reject',
    ),
    path(
        'users/<uuid:pk>/verify',
        views.admin_user_verify,
        name='admin-user-verify',
    ),
    path(
        'users/<uuid:pk>/suspend',
        views.admin_user_suspend,
        name='admin-user-suspend',
    ),

    # ===================================================================
    # ROLE & PERMISSION MANAGEMENT
    # ===================================================================
    path(
        'roles/<uuid:pk>/change',
        views.admin_role_change,
        name='admin-role-change',
    ),
    path(
        'permissions/<uuid:pk>/assign',
        views.admin_permission_assign,
        name='admin-permission-assign',
    ),
    path(
        'permissions/<uuid:pk>/remove',
        views.admin_permission_remove,
        name='admin-permission-remove',
    ),
]
