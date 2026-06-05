"""
Specialized handler for financial operations.

Principles:
- Never tell a user a payment failed if it might have succeeded
- Always provide a transaction ID for tracking
- Always provide a support reference ID
- Queue failed operations for automatic retry
- Send confirmation notifications when outcome is known

This is the MOST CRITICAL error handler in the system. Financial errors
must be handled with extreme care because:
1. Telling a user "payment failed" when it might have succeeded causes
   them to retry, resulting in double charges
2. Telling a user "payment succeeded" when it might have failed causes
   them to expect goods/services they haven't paid for
3. The safe default for UNCERTAIN outcomes is: tell the user the status
   is being verified and NOT to retry
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from django.conf import settings
from django.http import HttpRequest

from .error_taxonomy import get_error_definition, map_exception_to_error_code
from .error_responses import create_financial_error_response

logger = logging.getLogger(__name__)


class FinancialErrorHandler:
    """Handles errors in financial operations with the highest care.

    Usage::

        handler = FinancialErrorHandler()
        try:
            result = provider.charge(...)
        except TimeoutError as exc:
            response = handler.handle_payment_uncertain(transaction, exc, request)
    """

    def handle_payment_failure(
        self,
        transaction: Any,
        error: Exception,
        request: Optional[HttpRequest] = None,
    ) -> Dict[str, Any]:
        """Handle a payment that definitively failed.

        This should ONLY be called when we are 100% certain that the
        payment did NOT succeed — e.g., the provider returned an
        explicit error code, or the payment was rejected due to
        insufficient funds.

        Args:
            transaction: The transaction object (must have .id, .status).
            error: The exception that occurred.
            request: The HTTP request, if available.

        Returns:
            Dict with the error response data.
        """
        reference_id = str(uuid.uuid4())
        transaction_id = str(getattr(transaction, "id", "unknown"))

        error_code = map_exception_to_error_code(error)
        # Override for definitive payment failures
        if error_code in ("EXTERNAL_SERVICE_TIMEOUT", "NETWORK_TIMEOUT"):
            # This should NOT happen — timeout means UNCERTAIN, not failed
            logger.critical(
                "FINANCIAL SAFETY: handle_payment_failure called with a timeout "
                "error (should use handle_payment_uncertain). ref=%s txn=%s",
                reference_id,
                transaction_id,
            )
            # Delegate to uncertain handler for safety
            return self.handle_payment_uncertain(transaction, error, request)

        logger.error(
            "Payment failure: txn=%s ref=%s code=%s exc=%s",
            transaction_id,
            reference_id,
            error_code,
            type(error).__name__,
            extra={
                "reference_id": reference_id,
                "transaction_id": transaction_id,
                "error_code": error_code,
                "funds_moved": False,
                "exception_type": type(error).__name__,
                "exception_message": str(error)[:500],
            },
        )

        # Queue for internal tracking
        self._create_financial_audit_log(
            transaction=transaction,
            event="PAYMENT_FAILED",
            reference_id=reference_id,
            details={
                "error_code": error_code,
                "exception_type": type(error).__name__,
                "funds_moved": False,
            },
        )

        definition = get_error_definition(error_code)
        user_message = None
        if definition:
            user_message = definition.user_message

        return {
            "success": False,
            "error_code": error_code,
            "user_message": user_message,
            "reference_id": reference_id,
            "transaction_id": transaction_id,
            "funds_moved": False,
        }

    def handle_payment_uncertain(
        self,
        transaction: Any,
        error: Exception,
        request: Optional[HttpRequest] = None,
    ) -> Dict[str, Any]:
        """Handle a payment where the outcome is unknown (timeout, network error).

        CRITICAL: This is the safest handler for uncertain outcomes.
        It tells the user:
        - The status is being verified
        - Do NOT retry the same payment
        - A confirmation will be sent

        Args:
            transaction: The transaction object.
            error: The exception that caused the uncertainty.
            request: The HTTP request, if available.

        Returns:
            Dict with the error response data.
        """
        reference_id = str(uuid.uuid4())
        transaction_id = str(getattr(transaction, "id", "unknown"))

        logger.critical(
            "Payment UNCERTAIN: txn=%s ref=%s exc=%s — DO NOT tell user payment failed",
            transaction_id,
            reference_id,
            type(error).__name__,
            extra={
                "reference_id": reference_id,
                "transaction_id": transaction_id,
                "error_code": "PAYMENT_PROVIDER_UNAVAILABLE",
                "funds_moved": "UNKNOWN",
                "exception_type": type(error).__name__,
                "exception_message": str(error)[:500],
                "handler": "handle_payment_uncertain",
            },
        )

        # Queue for status verification
        self._queue_status_verification(transaction, reference_id)

        # Queue for automatic retry of the verification check
        self._queue_verification_notification(transaction, reference_id)

        # Create audit log
        self._create_financial_audit_log(
            transaction=transaction,
            event="PAYMENT_UNCERTAIN",
            reference_id=reference_id,
            details={
                "exception_type": type(error).__name__,
                "funds_moved": "UNKNOWN",
                "verification_queued": True,
            },
        )

        return {
            "success": False,
            "error_code": "PAYMENT_PROVIDER_UNAVAILABLE",
            "user_message": (
                "We couldn't confirm your payment status. Your money may or may not "
                "have been debited. Please DO NOT attempt the same payment again. "
                "We are verifying the status and will send you a confirmation. "
                f"Reference: {reference_id}"
            ),
            "reference_id": reference_id,
            "transaction_id": transaction_id,
            "funds_moved": None,  # Unknown
            "verification_pending": True,
        }

    def handle_withdrawal_failure(
        self,
        withdrawal: Any,
        error: Exception,
        request: Optional[HttpRequest] = None,
    ) -> Dict[str, Any]:
        """Handle a withdrawal that definitively failed.

        The user's funds remain in their account.

        Args:
            withdrawal: The withdrawal object.
            error: The exception.
            request: The HTTP request.

        Returns:
            Dict with the error response data.
        """
        reference_id = str(uuid.uuid4())
        withdrawal_id = str(getattr(withdrawal, "id", "unknown"))

        error_code = map_exception_to_error_code(error)
        # Same safety check as payment
        if error_code in ("EXTERNAL_SERVICE_TIMEOUT", "NETWORK_TIMEOUT"):
            return self.handle_withdrawal_uncertain(withdrawal, error, request)

        logger.error(
            "Withdrawal failure: wdl=%s ref=%s code=%s exc=%s",
            withdrawal_id,
            reference_id,
            error_code,
            type(error).__name__,
            extra={
                "reference_id": reference_id,
                "withdrawal_id": withdrawal_id,
                "error_code": error_code,
                "funds_moved": False,
                "exception_type": type(error).__name__,
            },
        )

        self._create_financial_audit_log(
            transaction=withdrawal,
            event="WITHDRAWAL_FAILED",
            reference_id=reference_id,
            details={
                "error_code": error_code,
                "exception_type": type(error).__name__,
                "funds_moved": False,
            },
        )

        definition = get_error_definition(error_code)
        user_message = definition.user_message if definition else None

        return {
            "success": False,
            "error_code": error_code,
            "user_message": user_message,
            "reference_id": reference_id,
            "withdrawal_id": withdrawal_id,
            "funds_moved": False,
        }

    def handle_withdrawal_uncertain(
        self,
        withdrawal: Any,
        error: Exception,
        request: Optional[HttpRequest] = None,
    ) -> Dict[str, Any]:
        """Handle a withdrawal where the outcome is uncertain.

        The funds may or may not have been disbursed.

        Args:
            withdrawal: The withdrawal object.
            error: The exception.
            request: The HTTP request.

        Returns:
            Dict with the error response data.
        """
        reference_id = str(uuid.uuid4())
        withdrawal_id = str(getattr(withdrawal, "id", "unknown"))

        logger.critical(
            "Withdrawal UNCERTAIN: wdl=%s ref=%s exc=%s",
            withdrawal_id,
            reference_id,
            type(error).__name__,
            extra={
                "reference_id": reference_id,
                "withdrawal_id": withdrawal_id,
                "error_code": "WITHDRAWAL_PENDING_RETRY",
                "funds_moved": "UNKNOWN",
                "exception_type": type(error).__name__,
                "handler": "handle_withdrawal_uncertain",
            },
        )

        # Queue status verification
        self._queue_status_verification(withdrawal, reference_id)
        self._queue_verification_notification(withdrawal, reference_id)

        self._create_financial_audit_log(
            transaction=withdrawal,
            event="WITHDRAWAL_UNCERTAIN",
            reference_id=reference_id,
            details={
                "exception_type": type(error).__name__,
                "funds_moved": "UNKNOWN",
                "verification_queued": True,
            },
        )

        return {
            "success": False,
            "error_code": "WITHDRAWAL_PENDING_RETRY",
            "user_message": (
                "We couldn't confirm the status of your withdrawal. "
                "We are verifying and will notify you of the result. "
                "Please do not attempt the same withdrawal again. "
                f"Reference: {reference_id}"
            ),
            "reference_id": reference_id,
            "withdrawal_id": withdrawal_id,
            "funds_moved": None,
            "verification_pending": True,
        }

    def handle_escrow_error(
        self,
        transaction: Any,
        error: Exception,
        request: Optional[HttpRequest] = None,
    ) -> Dict[str, Any]:
        """Handle an escrow operation error.

        Escrow errors are critical — funds are held in escrow and must
        not be lost or double-counted.

        Args:
            transaction: The transaction object.
            error: The exception.
            request: The HTTP request.

        Returns:
            Dict with the error response data.
        """
        reference_id = str(uuid.uuid4())
        transaction_id = str(getattr(transaction, "id", "unknown"))
        error_code = map_exception_to_error_code(error)

        # Default to ESCROW_ERROR for unmapped exceptions
        if error_code in ("SYSTEM_UNKNOWN_ERROR", "EXTERNAL_SERVICE_UNAVAILABLE"):
            error_code = "ESCROW_ERROR"

        logger.critical(
            "Escrow error: txn=%s ref=%s code=%s exc=%s",
            transaction_id,
            reference_id,
            error_code,
            type(error).__name__,
            extra={
                "reference_id": reference_id,
                "transaction_id": transaction_id,
                "error_code": error_code,
                "exception_type": type(error).__name__,
                "exception_message": str(error)[:500],
                "handler": "handle_escrow_error",
            },
        )

        self._create_financial_audit_log(
            transaction=transaction,
            event="ESCROW_ERROR",
            reference_id=reference_id,
            details={
                "error_code": error_code,
                "exception_type": type(error).__name__,
            },
        )

        definition = get_error_definition(error_code)
        user_message = definition.user_message if definition else (
            "We couldn't complete the escrow operation. Your funds are safe. "
            f"Reference: {reference_id}"
        )

        return {
            "success": False,
            "error_code": error_code,
            "user_message": user_message,
            "reference_id": reference_id,
            "transaction_id": transaction_id,
            "funds_moved": False,
        }

    def handle_refund_pending(
        self,
        transaction: Any,
        request: Optional[HttpRequest] = None,
    ) -> Dict[str, Any]:
        """Handle a refund that is pending.

        The refund has been initiated but not yet confirmed by the provider.

        Args:
            transaction: The transaction object.
            request: The HTTP request.

        Returns:
            Dict with the error response data.
        """
        reference_id = str(uuid.uuid4())
        transaction_id = str(getattr(transaction, "id", "unknown"))

        logger.info(
            "Refund pending: txn=%s ref=%s",
            transaction_id,
            reference_id,
            extra={
                "reference_id": reference_id,
                "transaction_id": transaction_id,
                "error_code": "REFUND_PENDING",
            },
        )

        self._create_financial_audit_log(
            transaction=transaction,
            event="REFUND_PENDING",
            reference_id=reference_id,
            details={
                "refund_status": "pending_provider_confirmation",
            },
        )

        # Queue for refund status verification
        self._queue_status_verification(transaction, reference_id)
        self._queue_verification_notification(transaction, reference_id)

        return {
            "success": True,
            "error_code": "REFUND_PENDING",
            "user_message": (
                "Your refund has been initiated and is being processed. "
                "You will receive a notification once it's complete. "
                f"Reference: {reference_id}"
            ),
            "reference_id": reference_id,
            "transaction_id": transaction_id,
            "refund_status": "pending",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_financial_audit_log(
        self,
        transaction: Any,
        event: str,
        reference_id: str,
        details: Dict[str, Any],
    ) -> None:
        """Create an audit log entry for a financial event.

        This is a best-effort operation — failures should not break
        the main error handling flow.
        """
        try:
            from core.models import AuditLog
            from django.contrib.auth import get_user_model

            transaction_id = str(getattr(transaction, "id", "unknown"))

            # Try to get user from transaction
            user = None
            for attr in ("buyer", "user", "seller"):
                if hasattr(transaction, attr):
                    user = getattr(transaction, attr)
                    break

            AuditLog.objects.create(
                user=user,
                action=f"FINANCIAL: {event} transaction={transaction_id} ref={reference_id}",
                metadata={
                    "event": event,
                    "transaction_id": transaction_id,
                    "reference_id": reference_id,
                    **details,
                },
            )
        except Exception:
            logger.warning(
                "Failed to create financial audit log: ref=%s event=%s",
                reference_id,
                event,
            )

    def _queue_status_verification(
        self, transaction: Any, reference_id: str
    ) -> None:
        """Queue a task to verify the transaction status with the provider."""
        try:
            from core.tasks import retry_failed_operation

            transaction_id = str(getattr(transaction, "id", "unknown"))
            retry_failed_operation.delay(
                function_path="core.services.payment.verify_transaction_status",
                args=[transaction_id],
                kwargs={"reference_id": reference_id},
                reference_id=reference_id,
            )
        except Exception:
            logger.warning(
                "Failed to queue status verification: ref=%s", reference_id
            )

    def _queue_verification_notification(
        self, transaction: Any, reference_id: str
    ) -> None:
        """Queue a notification to be sent once the outcome is known."""
        try:
            from core.tasks import retry_failed_operation

            transaction_id = str(getattr(transaction, "id", "unknown"))
            retry_failed_operation.delay(
                function_path="core.services.payment.send_payment_confirmation",
                args=[transaction_id],
                kwargs={"reference_id": reference_id},
                reference_id=reference_id,
            )
        except Exception:
            logger.warning(
                "Failed to queue verification notification: ref=%s", reference_id
            )
