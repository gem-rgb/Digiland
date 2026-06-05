"""
Background job monitoring and status tracking.

Tracks background jobs through their lifecycle:
QUEUED → PROCESSING → COMPLETED / FAILED / RETRYING

Uses Redis for status tracking. Includes Celery task signals integration.

Jobs are tracked with:
- Current state
- Job type
- Progress percentage
- Error information (if failed)
- User-facing status (safe, no internal details)
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class JobState:
    """Valid job states."""
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"


# Redis key prefix for job status
JOB_KEY_PREFIX = "digiland:job:"
JOB_TTL = 86400 * 7  # 7 days


class BackgroundJobMonitor:
    """Track background jobs through their lifecycle.

    Usage::

        monitor = BackgroundJobMonitor()

        # When queuing a job
        monitor.mark_queued(job_id, "payment_verification", metadata={"txn_id": "abc"})

        # When processing starts
        monitor.mark_processing(job_id, progress=10)

        # On completion
        monitor.mark_completed(job_id, result={"status": "verified"})

        # On failure
        monitor.mark_failed(job_id, "PAYMENT_PROVIDER_UNAVAILABLE", "Payment could not be verified", is_retryable=True)

        # Get user-safe status
        status = monitor.get_user_facing_status(job_id)
    """

    def mark_queued(
        self,
        job_id: str,
        job_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mark a job as queued.

        Args:
            job_id: Unique job identifier.
            job_type: Type of job (e.g. "payment_verification").
            metadata: Optional additional metadata.
        """
        status = {
            "state": JobState.QUEUED,
            "job_type": job_type,
            "progress": 0,
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            status["metadata"] = metadata

        self._set_job_status(job_id, status)

        logger.info(
            "Job queued: id=%s type=%s",
            job_id,
            job_type,
            extra={
                "job_id": job_id,
                "job_type": job_type,
                "job_state": JobState.QUEUED,
            },
        )

    def mark_processing(
        self,
        job_id: str,
        progress: Optional[int] = None,
    ) -> None:
        """Mark a job as processing, with optional progress %.

        Args:
            job_id: Unique job identifier.
            progress: Progress percentage (0-100).
        """
        status = self._get_job_status(job_id)
        if status is None:
            logger.warning("mark_processing called for unknown job: %s", job_id)
            status = {"job_type": "unknown"}

        status["state"] = JobState.PROCESSING
        status["processing_at"] = datetime.now(timezone.utc).isoformat()
        status["updated_at"] = datetime.now(timezone.utc).isoformat()
        if progress is not None:
            status["progress"] = max(0, min(100, progress))

        self._set_job_status(job_id, status)

        logger.info(
            "Job processing: id=%s progress=%s",
            job_id,
            progress,
            extra={
                "job_id": job_id,
                "job_state": JobState.PROCESSING,
                "progress": progress,
            },
        )

    def mark_completed(
        self,
        job_id: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mark a job as completed.

        Args:
            job_id: Unique job identifier.
            result: Optional result data.
        """
        status = self._get_job_status(job_id)
        if status is None:
            logger.warning("mark_completed called for unknown job: %s", job_id)
            status = {"job_type": "unknown"}

        status["state"] = JobState.COMPLETED
        status["progress"] = 100
        status["completed_at"] = datetime.now(timezone.utc).isoformat()
        status["updated_at"] = datetime.now(timezone.utc).isoformat()
        if result:
            status["result"] = result

        self._set_job_status(job_id, status)

        logger.info(
            "Job completed: id=%s type=%s",
            job_id,
            status.get("job_type", "unknown"),
            extra={
                "job_id": job_id,
                "job_type": status.get("job_type", "unknown"),
                "job_state": JobState.COMPLETED,
            },
        )

    def mark_failed(
        self,
        job_id: str,
        error_code: str,
        user_message: str,
        is_retryable: bool = True,
    ) -> None:
        """Mark a job as failed.

        Args:
            job_id: Unique job identifier.
            error_code: Error code from the taxonomy.
            user_message: Safe user-facing message.
            is_retryable: Whether the job can be retried.
        """
        status = self._get_job_status(job_id)
        if status is None:
            logger.warning("mark_failed called for unknown job: %s", job_id)
            status = {"job_type": "unknown"}

        status["state"] = JobState.FAILED
        status["failed_at"] = datetime.now(timezone.utc).isoformat()
        status["updated_at"] = datetime.now(timezone.utc).isoformat()
        status["error_code"] = error_code
        status["user_message"] = user_message
        status["is_retryable"] = is_retryable

        self._set_job_status(job_id, status)

        log_level = logging.ERROR if not is_retryable else logging.WARNING
        logger.log(
            log_level,
            "Job failed: id=%s type=%s code=%s retryable=%s",
            job_id,
            status.get("job_type", "unknown"),
            error_code,
            is_retryable,
            extra={
                "job_id": job_id,
                "job_type": status.get("job_type", "unknown"),
                "job_state": JobState.FAILED,
                "error_code": error_code,
                "is_retryable": is_retryable,
            },
        )

    def mark_retrying(
        self,
        job_id: str,
        attempt_number: int,
        next_retry_at: Optional[str] = None,
    ) -> None:
        """Mark a job as being retried.

        Args:
            job_id: Unique job identifier.
            attempt_number: The current attempt number (1-based).
            next_retry_at: ISO timestamp of the next retry.
        """
        status = self._get_job_status(job_id)
        if status is None:
            logger.warning("mark_retrying called for unknown job: %s", job_id)
            status = {"job_type": "unknown"}

        status["state"] = JobState.RETRYING
        status["attempt_number"] = attempt_number
        status["next_retry_at"] = next_retry_at
        status["retrying_at"] = datetime.now(timezone.utc).isoformat()
        status["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._set_job_status(job_id, status)

        logger.info(
            "Job retrying: id=%s attempt=%s",
            job_id,
            attempt_number,
            extra={
                "job_id": job_id,
                "job_state": JobState.RETRYING,
                "attempt_number": attempt_number,
                "next_retry_at": next_retry_at,
            },
        )

    def get_status(self, job_id: str) -> Dict[str, Any]:
        """Get the current status of a job.

        Returns the full internal status including error codes,
        metadata, and other details.

        Args:
            job_id: Unique job identifier.

        Returns:
            Dict with job status, or {"state": "UNKNOWN"} if not found.
        """
        status = self._get_job_status(job_id)
        if status is None:
            return {"state": "UNKNOWN", "job_id": job_id}
        return status

    def get_user_facing_status(self, job_id: str) -> Dict[str, Any]:
        """Get a user-safe status (no internal details).

        Removes all internal information like error codes, metadata,
        and exception details. Only provides user-safe information.

        Args:
            job_id: Unique job identifier.

        Returns:
            Dict with user-safe status.
        """
        status = self._get_job_status(job_id)
        if status is None:
            return {
                "job_id": job_id,
                "state": "UNKNOWN",
                "message": "Job status not found.",
            }

        state = status.get("state", "UNKNOWN")

        # Build user-safe response
        safe_status: Dict[str, Any] = {
            "job_id": job_id,
            "state": state,
        }

        # Add progress if available
        if "progress" in status:
            safe_status["progress"] = status["progress"]

        # State-specific user messages
        if state == JobState.QUEUED:
            safe_status["message"] = "Your request has been received and is waiting to be processed."
        elif state == JobState.PROCESSING:
            safe_status["message"] = "Your request is being processed."
        elif state == JobState.COMPLETED:
            safe_status["message"] = "Your request has been completed successfully."
        elif state == JobState.FAILED:
            safe_status["message"] = status.get("user_message", "Your request could not be completed.")
            safe_status["is_retryable"] = status.get("is_retryable", False)
        elif state == JobState.RETRYING:
            safe_status["message"] = "Your request is being retried. We'll notify you of the result."
            safe_status["attempt"] = status.get("attempt_number", 1)

        # Include timestamps
        for ts_key in ("queued_at", "completed_at", "failed_at"):
            if ts_key in status:
                safe_status[ts_key] = status[ts_key]

        return safe_status

    # ------------------------------------------------------------------
    # Redis/Cache helpers
    # ------------------------------------------------------------------

    def _get_cache_key(self, job_id: str) -> str:
        """Get the cache key for a job."""
        return f"{JOB_KEY_PREFIX}{job_id}"

    def _get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve job status from cache."""
        try:
            key = self._get_cache_key(job_id)
            data = cache.get(key)
            if data is None:
                return None
            if isinstance(data, str):
                return json.loads(data)
            return data
        except Exception:
            logger.warning("Failed to get job status: id=%s", job_id)
            return None

    def _set_job_status(self, job_id: str, status: Dict[str, Any]) -> None:
        """Store job status in cache."""
        try:
            key = self._get_cache_key(job_id)
            cache.set(key, json.dumps(status), timeout=JOB_TTL)
        except Exception:
            logger.warning("Failed to set job status: id=%s", job_id)


# ======================================================================
# Celery Signal Integration
# ======================================================================


def setup_celery_signals() -> None:
    """Connect Celery task signals to the BackgroundJobMonitor.

    Call this from AppConfig.ready() to enable automatic job tracking.
    """
    try:
        from celery.signals import (
            task_prerun,
            task_postrun,
            task_failure,
            task_retry,
            task_revoked,
        )

        monitor = BackgroundJobMonitor()

        @task_prerun.connect
        def on_task_prerun(sender=None, task_id=None, task=None, **kwargs):
            """Mark task as processing when it starts."""
            if task_id:
                monitor.mark_processing(task_id, progress=0)

        @task_postrun.connect
        def on_task_postrun(sender=None, task_id=None, task=None, state=None, **kwargs):
            """Mark task as completed when it finishes successfully."""
            if task_id and state == "SUCCESS":
                monitor.mark_completed(task_id)

        @task_failure.connect
        def on_task_failure(sender=None, task_id=None, exception=None, **kwargs):
            """Mark task as failed when it raises an exception."""
            if task_id and exception:
                from .error_taxonomy import map_exception_to_error_code
                error_code = map_exception_to_error_code(exception)
                monitor.mark_failed(
                    task_id,
                    error_code=error_code,
                    user_message="The background task could not be completed.",
                    is_retryable=True,
                )

        @task_retry.connect
        def on_task_retry(sender=None, task_id=None, reason=None, **kwargs):
            """Mark task as retrying when it's being retried."""
            if task_id:
                status = monitor.get_status(task_id)
                attempt = status.get("attempt_number", 1) + 1
                monitor.mark_retrying(task_id, attempt_number=attempt)

        @task_revoked.connect
        def on_task_revoked(sender=None, task_id=None, **kwargs):
            """Mark task as failed when it's revoked."""
            if task_id:
                monitor.mark_failed(
                    task_id,
                    error_code="SYSTEM_UNKNOWN_ERROR",
                    user_message="The task was cancelled.",
                    is_retryable=False,
                )

        logger.info("Celery signals connected to BackgroundJobMonitor")

    except ImportError:
        logger.warning("Celery not available — background job monitoring signals not connected")
    except Exception as exc:
        logger.warning("Failed to connect Celery signals: %s", exc)
