"""
Specialized error handler for admin control plane operations.

Principles:
- Provide operational context (what was being done)
- Confirm the state of affected resources
- Never expose stack traces, SQL, internal service names
- Provide actionable recovery information

Admin error messages should be MORE informative than user-facing messages,
but still MUST NOT expose:
- Stack traces
- SQL queries
- Database/table names
- Provider names (Stripe, M-Pesa, etc.)
- Internal API endpoints
- Infrastructure details
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from django.http import HttpRequest

from .error_taxonomy import get_error_definition, map_exception_to_error_code

logger = logging.getLogger(__name__)


class AdminErrorHandler:
    """Error handler for admin operations.

    Usage::

        handler = AdminErrorHandler()
        try:
            approval.approve(requesting_admin)
        except Exception as exc:
            response = handler.handle_approval_failure(
                "withdrawal", withdrawal.id, exc, request
            )
    """

    # Map resource types to user-safe labels
    RESOURCE_LABELS = {
        "withdrawal": "withdrawal request",
        "verification": "verification request",
        "kyc_application": "KYC application",
        "transaction": "transaction",
        "refund": "refund request",
        "parcel": "land parcel",
        "user": "user account",
        "agent": "agent account",
        "promotion": "promotion",
        "payout": "payout",
    }

    def handle_verification_failure(
        self,
        resource_type: str,
        resource_id: Any,
        error: Exception,
        request: Optional[HttpRequest] = None,
    ) -> Dict[str, Any]:
        """Handle a verification service failure.

        Example message: "Verification service unavailable. Pending
        reviews remain safe and will be processed when the service recovers."

        Args:
            resource_type: Type of resource being verified.
            resource_id: ID of the resource.
            error: The exception.
            request: The HTTP request.

        Returns:
            Dict with error response data.
        """
        reference_id = str(uuid.uuid4())
        error_code = map_exception_to_error_code(error)
        resource_label = self.RESOURCE_LABELS.get(resource_type, resource_type)

        logger.error(
            "Admin verification failure: resource=%s/%s ref=%s code=%s exc=%s",
            resource_type,
            resource_id,
            reference_id,
            error_code,
            type(error).__name__,
            extra={
                "reference_id": reference_id,
                "resource_type": resource_type,
                "resource_id": str(resource_id),
                "error_code": error_code,
                "exception_type": type(error).__name__,
                "exception_message": str(error)[:500],
            },
        )

        self._create_admin_audit_log(
            event="VERIFICATION_FAILURE",
            resource_type=resource_type,
            resource_id=resource_id,
            reference_id=reference_id,
            error=error,
            request=request,
        )

        return {
            "success": False,
            "error_code": error_code,
            "user_message": (
                f"Verification service is currently unavailable. "
                f"The {resource_label} remains safe and unchanged. "
                f"Pending reviews will be processed when the service recovers. "
                f"Reference: {reference_id}"
            ),
            "reference_id": reference_id,
            "resource_state": "unchanged",
            "action_required": "No immediate action needed. Try again later.",
        }

    def handle_approval_failure(
        self,
        resource_type: str,
        resource_id: Any,
        error: Exception,
        request: Optional[HttpRequest] = None,
    ) -> Dict[str, Any]:
        """Handle an approval service failure.

        Example message: "Withdrawal approval service unavailable. No
        funds have been moved."

        Args:
            resource_type: Type of resource being approved.
            resource_id: ID of the resource.
            error: The exception.
            request: The HTTP request.

        Returns:
            Dict with error response data.
        """
        reference_id = str(uuid.uuid4())
        error_code = map_exception_to_error_code(error)
        resource_label = self.RESOURCE_LABELS.get(resource_type, resource_type)

        logger.error(
            "Admin approval failure: resource=%s/%s ref=%s code=%s exc=%s",
            resource_type,
            resource_id,
            reference_id,
            error_code,
            type(error).__name__,
            extra={
                "reference_id": reference_id,
                "resource_type": resource_type,
                "resource_id": str(resource_id),
                "error_code": error_code,
                "exception_type": type(error).__name__,
                "exception_message": str(error)[:500],
            },
        )

        # For financial approvals, explicitly confirm no funds were moved
        funds_message = ""
        if resource_type in ("withdrawal", "payout", "refund", "transaction"):
            funds_message = " No funds have been moved."

        self._create_admin_audit_log(
            event="APPROVAL_FAILURE",
            resource_type=resource_type,
            resource_id=resource_id,
            reference_id=reference_id,
            error=error,
            request=request,
        )

        return {
            "success": False,
            "error_code": error_code,
            "user_message": (
                f"The approval service is currently unavailable. "
                f"The {resource_label} has not been modified.{funds_message} "
                f"Reference: {reference_id}"
            ),
            "reference_id": reference_id,
            "resource_state": "unchanged",
            "action_required": "Try the approval again later.",
        }

    def handle_dual_approval_error(
        self,
        approval_request: Any,
        error: Exception,
        request: Optional[HttpRequest] = None,
    ) -> Dict[str, Any]:
        """Handle errors in the dual-approval workflow.

        Dual approval requires two separate admins to approve a critical
        operation. Errors here must confirm that the approval request
        remains in its previous state.

        Args:
            approval_request: The dual-approval request object.
            error: The exception.
            request: The HTTP request.

        Returns:
            Dict with error response data.
        """
        reference_id = str(uuid.uuid4())
        error_code = map_exception_to_error_code(error)
        approval_id = str(getattr(approval_request, "id", "unknown"))

        # Determine the approval state
        current_state = "unknown"
        if hasattr(approval_request, "status"):
            current_state = getattr(approval_request, "status", "unknown")

        logger.error(
            "Dual approval error: approval=%s state=%s ref=%s code=%s exc=%s",
            approval_id,
            current_state,
            reference_id,
            error_code,
            type(error).__name__,
            extra={
                "reference_id": reference_id,
                "approval_id": approval_id,
                "current_state": current_state,
                "error_code": error_code,
                "exception_type": type(error).__name__,
                "exception_message": str(error)[:500],
            },
        )

        self._create_admin_audit_log(
            event="DUAL_APPROVAL_ERROR",
            resource_type="dual_approval",
            resource_id=approval_id,
            reference_id=reference_id,
            error=error,
            request=request,
            extra_details={
                "approval_state": current_state,
            },
        )

        return {
            "success": False,
            "error_code": error_code,
            "user_message": (
                f"The dual-approval operation could not be completed. "
                f"The approval request remains in its current state "
                f"({current_state}). No critical action has been executed. "
                f"Reference: {reference_id}"
            ),
            "reference_id": reference_id,
            "approval_id": approval_id,
            "approval_state": current_state,
            "resource_state": "unchanged",
            "action_required": (
                "Verify the approval request state and try again. "
                "If the state is unexpected, contact the system administrator."
            ),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_admin_audit_log(
        self,
        event: str,
        resource_type: str,
        resource_id: Any,
        reference_id: str,
        error: Exception,
        request: Optional[HttpRequest] = None,
        extra_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Create an audit log entry for an admin error event."""
        try:
            from core.models import AuditLog

            user = None
            if request and hasattr(request, "user"):
                user = request.user if getattr(request.user, "is_authenticated", False) else None

            metadata = {
                "event": event,
                "resource_type": resource_type,
                "resource_id": str(resource_id),
                "reference_id": reference_id,
                "exception_type": type(error).__name__,
            }
            if extra_details:
                metadata.update(extra_details)

            AuditLog.objects.create(
                user=user,
                action=f"ADMIN_ERROR: {event} {resource_type}={resource_id} ref={reference_id}",
                ip_address=self._get_client_ip(request) if request else None,
                metadata=metadata,
            )
        except Exception:
            logger.warning(
                "Failed to create admin audit log: ref=%s event=%s",
                reference_id,
                event,
            )

    @staticmethod
    def _get_client_ip(request: Optional[HttpRequest]) -> Optional[str]:
        """Extract client IP from request."""
        if not request:
            return None
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
