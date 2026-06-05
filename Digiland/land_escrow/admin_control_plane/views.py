"""API views for the Enterprise Admin Control Plane.

Every view enforces the following invariants:
1. ``IsAuthenticated`` — caller must hold a valid JWT.
2. Admin role check — ``request.user.role == 'Admin'``.
3. Admin session validity — an active ``AdminSession`` must be presented
   via the ``X-Admin-Session-Token`` header.
4. Immutable audit logging — all mutations are recorded through
   ``ImmutableAuditService``.
5. Step-up auth for sensitive operations — TOTP verification via
   ``StepUpAuthService``.
6. Dual approval for financial actions — amounts above the threshold
   require a second admin's approval.

Headers
-------
``X-Admin-Session-Token`` : Required on all endpoints.
``X-Step-Up-Code``        : Required on endpoints marked as sensitive.
"""

import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from core.auth_mfa import MFAService, StepUpAuthService

from .models import (
    AdminActionLog,
    AdminSession,
    DualApprovalRequest,
    EmergencyControl,
)
from .services import (
    AdminSessionService,
    DualApprovalService,
    FinancialProtectionService,
    EmergencyControlService,
    ImmutableAuditService,
)
from .serializers import (
    AdminSessionSerializer,
    AdminActionLogSerializer,
    DualApprovalRequestSerializer,
    DualApprovalActionSerializer,
    EmergencyControlSerializer,
    FinancialActionSerializer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_admin(user):
    """Raise PermissionDenied if the user is not an admin."""
    if user.role != 'Admin':
        raise PermissionDenied('Admin role required.')


def _get_admin_session(request):
    """Extract and validate the admin session from the request header.

    Returns the validated ``AdminSession`` or raises a ValueError.
    """
    token = request.META.get('HTTP_X_ADMIN_SESSION_TOKEN', '')
    if not token:
        raise ValueError('X-Admin-Session-Token header is required.')
    return AdminSessionService.validate_session(token)


def _get_client_ip(request):
    """Best-effort extraction of the client IP address."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _get_user_agent(request):
    """Return the User-Agent header or empty string."""
    return request.META.get('HTTP_USER_AGENT', '')


def _verify_step_up(request, operation: str):
    """Verify step-up authentication for the given operation.

    Reads the TOTP code from ``X-Step-Up-Code`` header or the
    ``totp_code`` field in the request body.

    Raises ``PermissionDenied`` if step-up verification fails.
    """
    totp_code = (
        request.META.get('HTTP_X_STEP_UP_CODE', '')
        or request.data.get('totp_code', '')
    )
    if not totp_code:
        raise PermissionDenied(
            f'Step-up authentication required for operation: {operation}. '
            'Provide X-Step-Up-Code header or totp_code in body.'
        )

    if not MFAService.verify_mfa(request.user, totp_code):
        raise PermissionDenied('Step-up authentication failed: invalid TOTP code.')


def _admin_context(request):
    """Return a dict of common audit context values."""
    return {
        'ip_address': _get_client_ip(request),
        'user_agent': _get_user_agent(request),
    }


# ===========================================================================
# ADMIN SESSION MANAGEMENT
# ===========================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_session_create(request):
    """Create a new admin session.

    **Requires MFA verification.**

    Request Body
    ------------
    - ``mfa_code`` (str, required): 6-digit TOTP code.

    Returns
    -------
    201 : AdminSession data including session token.
    """
    _require_admin(request.user)

    mfa_code = request.data.get('mfa_code', '')
    if not mfa_code:
        return Response(
            {'detail': 'mfa_code is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        session = AdminSessionService.create_session(
            user=request.user,
            mfa_code=mfa_code,
            ip_address=_get_client_ip(request),
            user_agent=_get_user_agent(request),
        )
    except ValueError as exc:
        return Response(
            {'detail': str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except PermissionDenied as exc:
        return Response(
            {'detail': str(exc)},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = AdminSessionSerializer(session)
    data = serializer.data
    # Include the session token only on creation so the client can use it
    data['session_token'] = session.session_token
    return Response(data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_session_validate(request):
    """Validate the current admin session.

    Returns
    -------
    200 : Session data if valid.
    400 : If the session is invalid or expired.
    """
    _require_admin(request.user)

    try:
        session = _get_admin_session(request)
    except ValueError as exc:
        return Response(
            {'detail': str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Ensure the session belongs to the requesting user
    if session.user_id != request.user.id:
        return Response(
            {'detail': 'Session does not belong to the authenticated user.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = AdminSessionSerializer(session)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_session_terminate(request, pk):
    """Terminate a specific admin session.

    Path Parameters
    ---------------
    - ``pk`` (UUID): AdminSession ID to terminate.

    Returns
    -------
    200 : Confirmation of termination.
    """
    _require_admin(request.user)

    try:
        AdminSessionService.terminate_session(
            session_id=pk,
            terminated_by=request.user,
        )
    except ValueError as exc:
        return Response(
            {'detail': str(exc)},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response({'detail': 'Session terminated.'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_session_terminate_all(request):
    """Terminate all active admin sessions for the authenticated user.

    Returns
    -------
    200 : Count of terminated sessions.
    """
    _require_admin(request.user)

    count = AdminSessionService.terminate_all_sessions(
        user=request.user,
        terminated_by=request.user,
    )

    return Response(
        {'detail': f'{count} session(s) terminated.', 'count': count},
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_session_list(request):
    """List active admin sessions for the authenticated user.

    Query Parameters
    ----------------
    - ``user_id`` (UUID, optional): Filter by user (admin-only).

    Returns
    -------
    200 : List of active admin sessions.
    """
    _require_admin(request.user)

    # Allow admins to view their own sessions; superadmins can view all
    user_id = request.query_params.get('user_id')
    target_user = None
    if user_id and user_id != str(request.user.id):
        # Only allow viewing other users' sessions if explicitly admin
        from core.models import User
        try:
            target_user = User.objects.get(id=user_id, role='Admin')
        except User.DoesNotExist:
            return Response(
                {'detail': 'User not found or not an admin.'},
                status=status.HTTP_404_NOT_FOUND,
            )
    else:
        target_user = request.user

    sessions = AdminSessionService.list_active_sessions(user=target_user)
    serializer = AdminSessionSerializer(sessions, many=True)
    return Response(serializer.data)


# ===========================================================================
# DUAL APPROVAL WORKFLOW
# ===========================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dual_approval_request(request):
    """Submit a request requiring dual approval.

    Request Body
    ------------
    - ``action_type`` (str): One of DualApprovalRequest.REQUEST_TYPE_CHOICES.
    - ``description`` (str): Human-readable description.
    - ``payload`` (dict): Structured data for executing the action.

    Returns
    -------
    201 : The created DualApprovalRequest.
    """
    _require_admin(request.user)

    action_type = request.data.get('action_type', '')
    description = request.data.get('description', '')
    payload = request.data.get('payload', {})

    if not action_type or not description:
        return Response(
            {'detail': 'action_type and description are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    valid_actions = [choice[0] for choice in DualApprovalRequest.REQUEST_TYPE_CHOICES]
    if action_type not in valid_actions:
        return Response(
            {'detail': f'Invalid action_type. Valid: {", ".join(valid_actions)}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    ctx = _admin_context(request)

    try:
        approval_request = DualApprovalService.submit_request(
            requested_by=request.user,
            action_type=action_type,
            description=description,
            payload=payload,
            **ctx,
        )
    except PermissionDenied as exc:
        return Response(
            {'detail': str(exc)},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = DualApprovalRequestSerializer(approval_request)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dual_approval_list_pending(request):
    """List all pending dual-approval requests.

    Returns
    -------
    200 : List of pending DualApprovalRequests.
    """
    _require_admin(request.user)

    pending = DualApprovalService.list_pending()
    serializer = DualApprovalRequestSerializer(pending, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dual_approval_approve(request, pk):
    """Approve a dual-approval request.

    **Requires step-up authentication.**

    The approving admin must be different from the requesting admin.

    Path Parameters
    ---------------
    - ``pk`` (UUID): DualApprovalRequest ID.

    Request Body
    ------------
    - ``review_notes`` (str, optional): Notes from the reviewer.
    - ``totp_code`` (str): 6-digit TOTP for step-up auth.

    Returns
    -------
    200 : Updated DualApprovalRequest.
    """
    _require_admin(request.user)
    _verify_step_up(request, 'dual_approval_approve')

    review_notes = request.data.get('review_notes', '')
    ctx = _admin_context(request)

    try:
        approval_request = DualApprovalService.approve_request(
            request_id=pk,
            approved_by=request.user,
            review_notes=review_notes,
            **ctx,
        )
    except ValueError as exc:
        return Response(
            {'detail': str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except PermissionDenied as exc:
        return Response(
            {'detail': str(exc)},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = DualApprovalRequestSerializer(approval_request)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dual_approval_reject(request, pk):
    """Reject a dual-approval request.

    Path Parameters
    ---------------
    - ``pk`` (UUID): DualApprovalRequest ID.

    Request Body
    ------------
    - ``review_notes`` (str, required): Reason for rejection.

    Returns
    -------
    200 : Updated DualApprovalRequest.
    """
    _require_admin(request.user)

    review_notes = request.data.get('review_notes', '')
    if not review_notes:
        return Response(
            {'detail': 'review_notes are required when rejecting a request.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    ctx = _admin_context(request)

    try:
        approval_request = DualApprovalService.reject_request(
            request_id=pk,
            rejected_by=request.user,
            review_notes=review_notes,
            **ctx,
        )
    except ValueError as exc:
        return Response(
            {'detail': str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = DualApprovalRequestSerializer(approval_request)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dual_approval_detail(request, pk):
    """Get details of a specific dual-approval request.

    Path Parameters
    ---------------
    - ``pk`` (UUID): DualApprovalRequest ID.

    Returns
    -------
    200 : DualApprovalRequest details.
    """
    _require_admin(request.user)

    approval_request = get_object_or_404(DualApprovalRequest, id=pk)
    serializer = DualApprovalRequestSerializer(approval_request)
    return Response(serializer.data)


# ===========================================================================
# FINANCIAL OPERATIONS
# ===========================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def financial_initiate_withdrawal(request):
    """Initiate a withdrawal approval.

    If the amount exceeds the dual-approval threshold, a
    ``DualApprovalRequest`` is automatically created.

    **Requires step-up authentication.**

    Request Body
    ------------
    - ``amount`` (Decimal): Withdrawal amount in KES.
    - ``recipient_id`` (UUID): Recipient user ID.
    - ``reference`` (str, optional): Payment reference.
    - ``totp_code`` (str): 6-digit TOTP for step-up auth.

    Returns
    -------
    201 : Withdrawal initiation result.
    """
    _require_admin(request.user)
    _verify_step_up(request, 'escrow_withdrawal')

    serializer = FinancialActionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    ctx = _admin_context(request)

    try:
        result = FinancialProtectionService.initiate_withdrawal(
            initiated_by=request.user,
            amount=data['amount'],
            recipient_id=str(data['recipient_id']),
            reference=data.get('reference', ''),
            **ctx,
        )
    except ValueError as exc:
        return Response(
            {'detail': str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    response_data = {
        'requires_dual_approval': result['requires_dual_approval'],
    }
    if result['approval_request']:
        response_data['approval_request'] = DualApprovalRequestSerializer(
            result['approval_request']
        ).data

    return Response(response_data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def financial_approve_withdrawal(request, pk):
    """Approve and execute a withdrawal.

    **Requires step-up authentication.**

    The corresponding ``DualApprovalRequest`` must be in APPROVED status
    (approved by a different admin) before this endpoint can execute it.

    Path Parameters
    ---------------
    - ``pk`` (UUID): DualApprovalRequest ID.

    Request Body
    ------------
    - ``totp_code`` (str): 6-digit TOTP for step-up auth.

    Returns
    -------
    200 : Executed withdrawal details.
    """
    _require_admin(request.user)
    _verify_step_up(request, 'escrow_withdrawal')

    ctx = _admin_context(request)

    try:
        result = FinancialProtectionService.approve_withdrawal(
            approval_request_id=pk,
            approved_by=request.user,
            **ctx,
        )
    except ValueError as exc:
        return Response(
            {'detail': str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(DualApprovalRequestSerializer(result).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def financial_balance_adjustment(request):
    """Request a balance adjustment (dual-approval required).

    **Requires step-up authentication.**

    Request Body
    ------------
    - ``amount`` (Decimal): Adjustment amount in KES.
    - ``recipient_id`` (UUID): User whose balance is adjusted.
    - ``reason`` (str, required): Reason for the adjustment.
    - ``totp_code`` (str): 6-digit TOTP for step-up auth.

    Returns
    -------
    201 : Created DualApprovalRequest.
    """
    _require_admin(request.user)
    _verify_step_up(request, 'payment_release')

    serializer = FinancialActionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    if not data.get('reason'):
        return Response(
            {'detail': 'reason is required for balance adjustments.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    ctx = _admin_context(request)

    try:
        approval_request = FinancialProtectionService.balance_adjustment(
            initiated_by=request.user,
            user_id=str(data['recipient_id']),
            amount=data['amount'],
            reason=data['reason'],
            **ctx,
        )
    except PermissionDenied as exc:
        return Response(
            {'detail': str(exc)},
            status=status.HTTP_403_FORBIDDEN,
        )

    return Response(
        DualApprovalRequestSerializer(approval_request).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def financial_payout_approve(request, pk):
    """Approve and execute a payout.

    **Requires step-up authentication.**

    Path Parameters
    ---------------
    - ``pk`` (UUID): DualApprovalRequest ID.

    Request Body
    ------------
    - ``totp_code`` (str): 6-digit TOTP for step-up auth.

    Returns
    -------
    200 : Executed payout details.
    """
    _require_admin(request.user)
    _verify_step_up(request, 'payment_release')

    ctx = _admin_context(request)

    try:
        result = FinancialProtectionService.approve_payout(
            approval_request_id=pk,
            approved_by=request.user,
            **ctx,
        )
    except ValueError as exc:
        return Response(
            {'detail': str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(DualApprovalRequestSerializer(result).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def financial_freeze_status(request):
    """Check if withdrawals are currently frozen.

    Returns
    -------
    200 : Freeze status details.
    """
    _require_admin(request.user)

    freeze_status = FinancialProtectionService.get_freeze_status()
    return Response(freeze_status)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def financial_transaction_history(request):
    """View financial audit log history.

    Query Parameters
    ----------------
    - ``action`` (str): Filter by action code.
    - ``since`` (ISO-8601): Filter entries after this timestamp.
    - ``until`` (ISO-8601): Filter entries before this timestamp.

    Returns
    -------
    200 : Paginated list of financial audit log entries.
    """
    _require_admin(request.user)

    # Filter for financial-related actions
    financial_actions = [
        'WITHDRAWAL_INITIATED', 'WITHDRAWAL_EXECUTED',
        'PAYOUT_EXECUTED', 'BALANCE_ADJUSTMENT',
        'WITHDRAWAL_FREEZE_ACTIVATED', 'WITHDRAWAL_FREEZE_DEACTIVATED',
    ]

    qs = AdminActionLog.objects.filter(
        action__in=financial_actions,
    ).order_by('-timestamp')

    # Additional filters
    action = request.query_params.get('action')
    if action:
        qs = qs.filter(action=action)

    since = request.query_params.get('since')
    if since:
        qs = qs.filter(timestamp__gte=since)

    until = request.query_params.get('until')
    if until:
        qs = qs.filter(timestamp__lte=until)

    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(qs, request)
    serializer = AdminActionLogSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


# ===========================================================================
# EMERGENCY CONTROLS
# ===========================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def emergency_withdrawal_freeze(request):
    """Activate or deactivate the withdrawal freeze.

    **Requires step-up authentication.**

    Request Body
    ------------
    - ``activate`` (bool): True to activate, False to deactivate.
    - ``totp_code`` (str): 6-digit TOTP for step-up auth.

    Returns
    -------
    200 : Updated emergency control status.
    """
    _require_admin(request.user)
    _verify_step_up(request, 'organization_settings_change')

    activate = request.data.get('activate', True)
    ctx = _admin_context(request)

    try:
        control = EmergencyControlService.set_withdrawal_freeze(
            activated_by=request.user,
            activate=bool(activate),
            **ctx,
        )
    except PermissionDenied as exc:
        return Response(
            {'detail': str(exc)},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = EmergencyControlSerializer(control)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def emergency_session_revocation(request):
    """Revoke all active admin sessions across the platform.

    **Requires step-up authentication.** This is a critical emergency
    operation that terminates every active admin session.

    Request Body
    ------------
    - ``totp_code`` (str): 6-digit TOTP for step-up auth.

    Returns
    -------
    200 : Count of revoked sessions.
    """
    _require_admin(request.user)
    _verify_step_up(request, 'admin_user_delete')

    ctx = _admin_context(request)

    count = EmergencyControlService.revoke_all_sessions(
        revoked_by=request.user,
        **ctx,
    )

    return Response(
        {'detail': f'{count} admin session(s) revoked.', 'count': count},
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def emergency_incident_mode(request):
    """Activate or deactivate incident mode.

    **Requires step-up authentication.**

    Request Body
    ------------
    - ``activate`` (bool): True to activate, False to deactivate.
    - ``description`` (str, required when activating): Incident description.
    - ``totp_code`` (str): 6-digit TOTP for step-up auth.

    Returns
    -------
    200 : Updated emergency control status.
    """
    _require_admin(request.user)
    _verify_step_up(request, 'organization_settings_change')

    activate = request.data.get('activate', True)
    description = request.data.get('description', '')

    if activate and not description:
        return Response(
            {'detail': 'description is required when activating incident mode.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    ctx = _admin_context(request)

    try:
        control = EmergencyControlService.set_incident_mode(
            activated_by=request.user,
            activate=bool(activate),
            description=description,
            **ctx,
        )
    except PermissionDenied as exc:
        return Response(
            {'detail': str(exc)},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = EmergencyControlSerializer(control)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def emergency_account_lock(request, pk):
    """Lock an admin account.

    **Requires step-up authentication.** Deactivates the user and
    terminates all their admin sessions.

    Path Parameters
    ---------------
    - ``pk`` (UUID): User ID of the admin account to lock.

    Request Body
    ------------
    - ``totp_code`` (str): 6-digit TOTP for step-up auth.

    Returns
    -------
    200 : Lock confirmation.
    """
    _require_admin(request.user)
    _verify_step_up(request, 'admin_user_delete')

    from core.models import User
    user_to_lock = get_object_or_404(User, id=pk)

    if user_to_lock.role != 'Admin':
        return Response(
            {'detail': 'Can only lock admin accounts.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if user_to_lock.id == request.user.id:
        return Response(
            {'detail': 'Cannot lock your own account through emergency controls.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    ctx = _admin_context(request)

    try:
        result = EmergencyControlService.lock_admin_account(
            locked_by=request.user,
            user_to_lock=user_to_lock,
            **ctx,
        )
    except ValueError as exc:
        return Response(
            {'detail': str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(result, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def emergency_status(request):
    """Get the current emergency control status.

    Returns
    -------
    200 : Emergency control status summary.
    """
    _require_admin(request.user)

    status_data = EmergencyControlService.get_status()

    # Add active session count
    active_sessions = AdminSession.objects.filter(
        is_active=True,
        expires_at__gt=timezone.now(),
    ).count()
    status_data['active_admin_sessions'] = active_sessions

    return Response(status_data)


# ===========================================================================
# ADMIN AUDIT
# ===========================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_log_list(request):
    """List admin action logs (paginated, filterable).

    Query Parameters
    ----------------
    - ``action`` (str): Filter by action code.
    - ``actor_id`` (UUID): Filter by actor.
    - ``resource_type`` (str): Filter by resource type.
    - ``since`` (ISO-8601): Filter entries after this timestamp.
    - ``until`` (ISO-8601): Filter entries before this timestamp.

    Returns
    -------
    200 : Paginated list of AdminActionLog entries.
    """
    _require_admin(request.user)

    qs = AdminActionLog.objects.order_by('-timestamp')

    # Filters
    action = request.query_params.get('action')
    if action:
        qs = qs.filter(action=action)

    actor_id = request.query_params.get('actor_id')
    if actor_id:
        qs = qs.filter(actor_id=actor_id)

    resource_type = request.query_params.get('resource_type')
    if resource_type:
        qs = qs.filter(resource_type=resource_type)

    since = request.query_params.get('since')
    if since:
        qs = qs.filter(timestamp__gte=since)

    until = request.query_params.get('until')
    if until:
        qs = qs.filter(timestamp__lte=until)

    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(qs, request)
    serializer = AdminActionLogSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_log_detail(request, pk):
    """Get a specific audit log entry.

    Path Parameters
    ---------------
    - ``pk`` (UUID): AdminActionLog ID.

    Returns
    -------
    200 : AdminActionLog details.
    """
    _require_admin(request.user)

    log_entry = get_object_or_404(AdminActionLog, id=pk)
    serializer = AdminActionLogSerializer(log_entry)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def audit_integrity_verify(request):
    """Verify the hash-chain integrity of the audit log.

    **Requires step-up authentication.** This is a computationally
    expensive operation on large log tables.

    Returns
    -------
    200 : Integrity verification result.
    """
    _require_admin(request.user)

    result = ImmutableAuditService.verify_integrity()

    ImmutableAuditService.log(
        actor=request.user,
        action_type='AUDIT_INTEGRITY_VERIFY',
        resource_type='AdminActionLog',
        metadata={
            'valid': result['valid'],
            'total_entries': result['total_entries'],
            'errors_count': len(result['errors']),
        },
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
    )

    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_export(request):
    """Export audit logs for compliance.

    Query Parameters
    ----------------
    - ``since`` (ISO-8601): Filter entries after this timestamp.
    - ``until`` (ISO-8601): Filter entries before this timestamp.
    - ``actor_id`` (UUID): Filter by actor.
    - ``action`` (str): Filter by action code.
    - ``resource_type`` (str): Filter by resource type.

    Returns
    -------
    200 : Paginated list of audit log entries for export.
    """
    _require_admin(request.user)

    since = request.query_params.get('since')
    until = request.query_params.get('until')
    actor_id = request.query_params.get('actor_id')
    action = request.query_params.get('action')
    resource_type = request.query_params.get('resource_type')

    qs = ImmutableAuditService.export_logs(
        since=since,
        until=until,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
    )

    paginator = PageNumberPagination()
    paginator.page_size = 100  # Larger page for export
    page = paginator.paginate_queryset(qs, request)
    serializer = AdminActionLogSerializer(page, many=True)

    ImmutableAuditService.log(
        actor=request.user,
        action_type='AUDIT_EXPORT',
        resource_type='AdminActionLog',
        metadata={
            'filters': {
                'since': since,
                'until': until,
                'actor_id': actor_id,
                'action': action,
                'resource_type': resource_type,
            },
        },
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
    )

    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_actor_history(request):
    """Get actions performed by a specific admin.

    Query Parameters
    ----------------
    - ``actor_id`` (UUID, required): The admin to look up.
    - ``limit`` (int, optional): Max entries to return (default 100).

    Returns
    -------
    200 : List of AdminActionLog entries.
    """
    _require_admin(request.user)

    actor_id = request.query_params.get('actor_id')
    if not actor_id:
        return Response(
            {'detail': 'actor_id query parameter is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    limit = int(request.query_params.get('limit', 100))
    limit = min(limit, 500)  # Cap at 500

    from core.models import User
    actor = get_object_or_404(User, id=actor_id)

    logs = ImmutableAuditService.get_actor_history(actor, limit=limit)
    serializer = AdminActionLogSerializer(logs, many=True)
    return Response(serializer.data)


# ===========================================================================
# KYC & VERIFICATION OPERATIONS
# ===========================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_kyc_approve(request, pk):
    """Approve a KYC application.

    **Requires step-up authentication.**

    Path Parameters
    ---------------
    - ``pk`` (UUID): AgentKYCApplication ID.

    Request Body
    ------------
    - ``notes`` (str, optional): Admin notes.
    - ``totp_code`` (str): 6-digit TOTP for step-up auth.

    Returns
    -------
    200 : Approval confirmation.
    """
    _require_admin(request.user)
    _verify_step_up(request, 'admin_role_change')

    from core.models import AgentKYCApplication

    application = get_object_or_404(AgentKYCApplication, id=pk)
    notes = request.data.get('notes', '')

    if application.status != 'Pending':
        return Response(
            {'detail': f'KYC application is in status {application.status}, cannot approve.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    application.status = 'Approved'
    application.reviewed_at = timezone.now()
    application.save()

    # Mark the agent as identity verified
    application.agent.is_identity_verified = True
    application.agent.save(update_fields=['is_identity_verified'])

    ImmutableAuditService.log(
        actor=request.user,
        action_type='KYC_APPLICATION_APPROVED',
        resource_type='AgentKYCApplication',
        resource_id=str(application.id),
        metadata={'agent_email': application.agent.email, 'notes': notes[:500]},
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
    )

    return Response({
        'detail': 'KYC application approved.',
        'application_id': str(application.id),
        'agent_email': application.agent.email,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_kyc_reject(request, pk):
    """Reject a KYC application.

    **Requires step-up authentication.**

    Path Parameters
    ---------------
    - ``pk`` (UUID): AgentKYCApplication ID.

    Request Body
    ------------
    - ``reason`` (str, required): Reason for rejection.
    - ``totp_code`` (str): 6-digit TOTP for step-up auth.

    Returns
    -------
    200 : Rejection confirmation.
    """
    _require_admin(request.user)
    _verify_step_up(request, 'admin_role_change')

    from core.models import AgentKYCApplication

    application = get_object_or_404(AgentKYCApplication, id=pk)
    reason = request.data.get('reason', '')

    if not reason:
        return Response(
            {'detail': 'reason is required when rejecting a KYC application.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if application.status != 'Pending':
        return Response(
            {'detail': f'KYC application is in status {application.status}, cannot reject.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    application.status = 'Rejected'
    application.reviewed_at = timezone.now()
    application.save()

    ImmutableAuditService.log(
        actor=request.user,
        action_type='KYC_APPLICATION_REJECTED',
        resource_type='AgentKYCApplication',
        resource_id=str(application.id),
        metadata={
            'agent_email': application.agent.email,
            'reason': reason[:500],
        },
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
    )

    return Response({
        'detail': 'KYC application rejected.',
        'application_id': str(application.id),
        'agent_email': application.agent.email,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_user_verify(request, pk):
    """Verify a user's identity.

    **Requires step-up authentication.**

    Path Parameters
    ---------------
    - ``pk`` (UUID): User ID.

    Request Body
    ------------
    - ``verification_notes`` (str, optional): Notes on the verification.
    - ``totp_code`` (str): 6-digit TOTP for step-up auth.

    Returns
    -------
    200 : Verification confirmation.
    """
    _require_admin(request.user)
    _verify_step_up(request, 'admin_role_change')

    from core.models import User
    user = get_object_or_404(User, id=pk)
    notes = request.data.get('verification_notes', '')

    user.is_identity_verified = True
    user.save(update_fields=['is_identity_verified'])

    ImmutableAuditService.log(
        actor=request.user,
        action_type='USER_IDENTITY_VERIFIED',
        resource_type='User',
        resource_id=str(user.id),
        metadata={
            'user_email': user.email,
            'verification_notes': notes[:500],
        },
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
    )

    return Response({
        'detail': 'User identity verified.',
        'user_id': str(user.id),
        'user_email': user.email,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_user_suspend(request, pk):
    """Suspend a user account.

    **Requires step-up authentication.**

    Path Parameters
    ---------------
    - ``pk`` (UUID): User ID.

    Request Body
    ------------
    - ``reason`` (str, required): Reason for suspension.
    - ``totp_code`` (str): 6-digit TOTP for step-up auth.

    Returns
    -------
    200 : Suspension confirmation.
    """
    _require_admin(request.user)
    _verify_step_up(request, 'admin_user_delete')

    from core.models import User
    user = get_object_or_404(User, id=pk)
    reason = request.data.get('reason', '')

    if not reason:
        return Response(
            {'detail': 'reason is required when suspending a user.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if user.id == request.user.id:
        return Response(
            {'detail': 'Cannot suspend your own account.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.is_active = False
    user.save(update_fields=['is_active'])

    # Terminate all sessions for the suspended user
    from .models import AdminSession
    AdminSession.objects.filter(user=user, is_active=True).update(
        is_active=False, terminated_at=timezone.now()
    )

    ImmutableAuditService.log(
        actor=request.user,
        action_type='USER_SUSPENDED',
        resource_type='User',
        resource_id=str(user.id),
        metadata={
            'user_email': user.email,
            'reason': reason[:500],
        },
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
    )

    return Response({
        'detail': 'User account suspended.',
        'user_id': str(user.id),
        'user_email': user.email,
    })


# ===========================================================================
# PERMISSION & ROLE MANAGEMENT
# ===========================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_role_change(request, pk):
    """Change a user's role (dual-approval required).

    Creates a ``DualApprovalRequest`` for the role change.  The change
    is not applied until a second admin approves it.

    Path Parameters
    ---------------
    - ``pk`` (UUID): User ID whose role is being changed.

    Request Body
    ------------
    - ``new_role`` (str): The target role.
    - ``reason`` (str, required): Justification for the role change.
    - ``totp_code`` (str): 6-digit TOTP for step-up auth.

    Returns
    -------
    201 : Created DualApprovalRequest.
    """
    _require_admin(request.user)
    _verify_step_up(request, 'admin_role_change')

    from core.models import User
    user = get_object_or_404(User, id=pk)

    new_role = request.data.get('new_role', '')
    reason = request.data.get('reason', '')

    if not new_role:
        return Response(
            {'detail': 'new_role is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    valid_roles = [choice[0] for choice in User.ROLE_CHOICES]
    if new_role not in valid_roles:
        return Response(
            {'detail': f'Invalid role. Valid: {", ".join(valid_roles)}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not reason:
        return Response(
            {'detail': 'reason is required for role changes.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if user.id == request.user.id:
        return Response(
            {'detail': 'Cannot change your own role.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    ctx = _admin_context(request)

    approval_request = DualApprovalService.submit_request(
        requested_by=request.user,
        action_type='ROLE_CHANGE',
        description=f'Role change for {user.email}: {user.role} -> {new_role}. Reason: {reason}',
        payload={
            'user_id': str(user.id),
            'user_email': user.email,
            'current_role': user.role,
            'new_role': new_role,
            'reason': reason,
        },
        **ctx,
    )

    ImmutableAuditService.log(
        actor=request.user,
        action_type='ROLE_CHANGE_REQUESTED',
        resource_type='User',
        resource_id=str(user.id),
        metadata={
            'current_role': user.role,
            'new_role': new_role,
            'reason': reason[:500],
            'approval_request_id': str(approval_request.id),
        },
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
    )

    return Response(
        DualApprovalRequestSerializer(approval_request).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_permission_assign(request, pk):
    """Assign specific permissions to a user (dual-approval required).

    Path Parameters
    ---------------
    - ``pk`` (UUID): User ID.

    Request Body
    ------------
    - ``permission_codenames`` (list[str]): Permissions to assign.
    - ``reason`` (str, required): Justification.
    - ``totp_code`` (str): 6-digit TOTP for step-up auth.

    Returns
    -------
    201 : Created DualApprovalRequest.
    """
    _require_admin(request.user)
    _verify_step_up(request, 'admin_role_change')

    from core.models import User
    user = get_object_or_404(User, id=pk)

    codenames = request.data.get('permission_codenames', [])
    reason = request.data.get('reason', '')

    if not codenames:
        return Response(
            {'detail': 'permission_codenames is required and must be a non-empty list.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not reason:
        return Response(
            {'detail': 'reason is required for permission assignments.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    ctx = _admin_context(request)

    approval_request = DualApprovalService.submit_request(
        requested_by=request.user,
        action_type='PERMISSION_ASSIGN',
        description=(
            f'Assign permissions to {user.email}: '
            f'{", ".join(codenames)}. Reason: {reason}'
        ),
        payload={
            'user_id': str(user.id),
            'user_email': user.email,
            'permission_codenames': codenames,
            'reason': reason,
        },
        **ctx,
    )

    ImmutableAuditService.log(
        actor=request.user,
        action_type='PERMISSION_ASSIGN_REQUESTED',
        resource_type='User',
        resource_id=str(user.id),
        metadata={
            'permission_codenames': codenames,
            'reason': reason[:500],
            'approval_request_id': str(approval_request.id),
        },
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
    )

    return Response(
        DualApprovalRequestSerializer(approval_request).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_permission_remove(request, pk):
    """Remove permissions from a user (dual-approval required).

    Path Parameters
    ---------------
    - ``pk`` (UUID): User ID.

    Request Body
    ------------
    - ``permission_codenames`` (list[str]): Permissions to remove.
    - ``reason`` (str, required): Justification.
    - ``totp_code`` (str): 6-digit TOTP for step-up auth.

    Returns
    -------
    201 : Created DualApprovalRequest.
    """
    _require_admin(request.user)
    _verify_step_up(request, 'admin_role_change')

    from core.models import User
    user = get_object_or_404(User, id=pk)

    codenames = request.data.get('permission_codenames', [])
    reason = request.data.get('reason', '')

    if not codenames:
        return Response(
            {'detail': 'permission_codenames is required and must be a non-empty list.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not reason:
        return Response(
            {'detail': 'reason is required for permission removals.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    ctx = _admin_context(request)

    approval_request = DualApprovalService.submit_request(
        requested_by=request.user,
        action_type='PERMISSION_REMOVE',
        description=(
            f'Remove permissions from {user.email}: '
            f'{", ".join(codenames)}. Reason: {reason}'
        ),
        payload={
            'user_id': str(user.id),
            'user_email': user.email,
            'permission_codenames': codenames,
            'reason': reason,
        },
        **ctx,
    )

    ImmutableAuditService.log(
        actor=request.user,
        action_type='PERMISSION_REMOVE_REQUESTED',
        resource_type='User',
        resource_id=str(user.id),
        metadata={
            'permission_codenames': codenames,
            'reason': reason[:500],
            'approval_request_id': str(approval_request.id),
        },
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
    )

    return Response(
        DualApprovalRequestSerializer(approval_request).data,
        status=status.HTTP_201_CREATED,
    )
