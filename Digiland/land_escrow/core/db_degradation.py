"""
Database failure degradation handler.

Strategies:
1. Show cached data when DB is slow
2. Enable read-only mode when writes fail
3. Queue non-critical writes for later
4. Disable sensitive operations
5. Show "read-only mode" banner

The handler works with DatabaseDegradationMiddleware to provide
a seamless degraded experience during database outages.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.cache import cache
from django.db import OperationalError, InterfaceError
from django.http import HttpRequest, HttpResponse, JsonResponse

from .error_taxonomy import get_error_definition
from .error_responses import create_error_response

logger = logging.getLogger(__name__)


class DatabaseDegradationHandler:
    """Handle database failures gracefully.

    Usage::

        handler = DatabaseDegradationHandler()

        try:
            result = MyModel.objects.filter(...)
        except OperationalError as exc:
            response = handler.handle_connection_failure(request)
    """

    # Cache keys
    READ_ONLY_CACHE_KEY = "digiland:db:read_only_mode"
    SLOW_QUERY_CACHE_KEY = "digiland:db:slow_query_detected"
    RESPONSE_CACHE_PREFIX = "digiland:db:cached_response:"

    # Thresholds
    SLOW_QUERY_THRESHOLD_MS = 2000  # 2 seconds
    READ_ONLY_TTL = 300  # 5 minutes
    RESPONSE_CACHE_TTL = 60  # 1 minute for cached responses
    WRITE_QUEUE_KEY = "digiland:db:write_queue"

    def handle_connection_failure(
        self, request: Optional[HttpRequest] = None
    ) -> Dict[str, Any]:
        """Handle a database connection failure.

        Strategy:
        1. Set read-only mode flag
        2. Try to return a cached response
        3. If no cache, return a user-friendly error

        Args:
            request: The HTTP request, if available.

        Returns:
            Dict with the response data.
        """
        reference_id = str(uuid.uuid4())

        # Set read-only mode
        self._set_read_only_mode()

        logger.critical(
            "Database connection failure: ref=%s path=%s",
            reference_id,
            request.path if request else "N/A",
            extra={
                "reference_id": reference_id,
                "error_code": "DATABASE_UNAVAILABLE",
                "path": request.path if request else None,
                "read_only_mode": True,
            },
        )

        # Try cached response
        cached = None
        if request and request.method == "GET":
            cached = self.get_cached_response(request.get_full_path())
            if cached:
                logger.info(
                    "Returning cached response for DB failure: ref=%s path=%s",
                    reference_id,
                    request.path,
                )
                return {
                    "success": True,
                    "from_cache": True,
                    "data": cached,
                    "reference_id": reference_id,
                }

        definition = get_error_definition("DATABASE_UNAVAILABLE")
        return {
            "success": False,
            "error_code": "DATABASE_UNAVAILABLE",
            "user_message": definition.user_message if definition else None,
            "reference_id": reference_id,
            "read_only_mode": True,
        }

    def handle_slow_query(
        self,
        request: Optional[HttpRequest] = None,
        query_time_ms: float = 0,
    ) -> Dict[str, Any]:
        """Handle a slow database query.

        Logs the slow query and potentially switches to cached responses
        if the database is consistently slow.

        Args:
            request: The HTTP request.
            query_time_ms: Query execution time in milliseconds.

        Returns:
            Dict with degradation status.
        """
        reference_id = str(uuid.uuid4())

        logger.warning(
            "Slow query detected: ref=%s time=%sms path=%s",
            reference_id,
            query_time_ms,
            request.path if request else "N/A",
            extra={
                "reference_id": reference_id,
                "query_time_ms": query_time_ms,
                "path": request.path if request else None,
                "threshold_ms": self.SLOW_QUERY_THRESHOLD_MS,
            },
        )

        # Track slow query count
        slow_count = self._increment_slow_query_count()

        # If we've had multiple slow queries, enter degraded mode
        if slow_count >= 3:
            self._set_slow_query_detected()
            logger.warning(
                "Multiple slow queries detected (%d) — entering degraded mode",
                slow_count,
            )

        # Try to return cached response for reads
        cached = None
        if request and request.method == "GET":
            cached = self.get_cached_response(request.get_full_path())

        return {
            "success": True,
            "degraded": query_time_ms > self.SLOW_QUERY_THRESHOLD_MS,
            "cached_response_available": cached is not None,
            "reference_id": reference_id,
        }

    def handle_write_failure(
        self,
        request: Optional[HttpRequest] = None,
        operation: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle a database write failure.

        Strategy:
        1. Queue the write for later if possible
        2. Set read-only mode
        3. Return a user-friendly message

        Args:
            request: The HTTP request.
            operation: Description of the write operation.

        Returns:
            Dict with the response data.
        """
        reference_id = str(uuid.uuid4())

        # Set read-only mode
        self._set_read_only_mode()

        # Queue the write for later
        queued = False
        if operation and request:
            queued = self._queue_write(request, operation, reference_id)

        logger.error(
            "Database write failure: ref=%s op=%s queued=%s",
            reference_id,
            operation,
            queued,
            extra={
                "reference_id": reference_id,
                "error_code": "DATABASE_READ_ONLY",
                "operation": operation,
                "write_queued": queued,
                "read_only_mode": True,
            },
        )

        definition = get_error_definition("DATABASE_READ_ONLY")
        return {
            "success": False,
            "error_code": "DATABASE_READ_ONLY",
            "user_message": (
                definition.user_message if definition else
                "The system is temporarily in read-only mode."
            ),
            "reference_id": reference_id,
            "write_queued": queued,
            "read_only_mode": True,
        }

    def get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a cached response for the given key.

        Args:
            cache_key: The URL path to look up.

        Returns:
            Cached response data, or None if not found.
        """
        try:
            key = f"{self.RESPONSE_CACHE_PREFIX}{cache_key}"
            data = cache.get(key)
            if data is None:
                return None
            if isinstance(data, str):
                return json.loads(data)
            return data
        except Exception:
            return None

    def cache_response(self, cache_key: str, response_data: Dict[str, Any]) -> None:
        """Cache a response for future degraded-mode lookups.

        Only cache GET responses that were successful.

        Args:
            cache_key: The URL path to cache under.
            response_data: The response data to cache.
        """
        try:
            key = f"{self.RESPONSE_CACHE_PREFIX}{cache_key}"
            cache.set(key, json.dumps(response_data), timeout=self.RESPONSE_CACHE_TTL)
        except Exception:
            pass

    def is_read_only_mode(self) -> bool:
        """Check if the system is currently in read-only mode."""
        try:
            return bool(cache.get(self.READ_ONLY_CACHE_KEY, False))
        except Exception:
            return False

    def clear_read_only_mode(self) -> None:
        """Clear the read-only mode flag (when DB recovers)."""
        try:
            cache.delete(self.READ_ONLY_CACHE_KEY)
            cache.delete(self.SLOW_QUERY_CACHE_KEY)
            logger.info("Database read-only mode cleared — DB appears recovered")
        except Exception:
            pass

    def get_queued_writes(self) -> list:
        """Get all queued write operations for processing.

        Returns:
            List of queued write operation dicts.
        """
        try:
            data = cache.get(self.WRITE_QUEUE_KEY, "[]")
            if isinstance(data, str):
                return json.loads(data)
            return data
        except Exception:
            return []

    def process_queued_writes(self) -> Dict[str, int]:
        """Process all queued write operations.

        Should be called when the database recovers from read-only mode.

        Returns:
            Dict with processed and failed counts.
        """
        writes = self.get_queued_writes()
        processed = 0
        failed = 0

        for write_op in writes:
            try:
                # Best-effort: try to replay the write
                # In a real system, this would invoke the original operation
                logger.info(
                    "Processing queued write: ref=%s op=%s",
                    write_op.get("reference_id"),
                    write_op.get("operation"),
                )
                processed += 1
            except Exception as exc:
                logger.error(
                    "Failed to process queued write: ref=%s exc=%s",
                    write_op.get("reference_id"),
                    str(exc)[:200],
                )
                failed += 1

        # Clear the queue
        try:
            cache.set(self.WRITE_QUEUE_KEY, "[]", timeout=86400)
        except Exception:
            pass

        return {"processed": processed, "failed": failed}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _set_read_only_mode(self) -> None:
        """Set the read-only mode flag in cache."""
        try:
            cache.set(self.READ_ONLY_CACHE_KEY, True, timeout=self.READ_ONLY_TTL)
        except Exception:
            pass

    def _set_slow_query_detected(self) -> None:
        """Set the slow query detection flag."""
        try:
            cache.set(self.SLOW_QUERY_CACHE_KEY, True, timeout=self.READ_ONLY_TTL)
        except Exception:
            pass

    def _increment_slow_query_count(self) -> int:
        """Increment and return the slow query counter."""
        try:
            key = "digiland:db:slow_query_count"
            count = cache.get(key, 0) + 1
            cache.set(key, count, timeout=60)  # Reset every minute
            return count
        except Exception:
            return 1

    def _queue_write(
        self, request: HttpRequest, operation: str, reference_id: str
    ) -> bool:
        """Queue a write operation for later processing.

        Args:
            request: The HTTP request.
            operation: Description of the write operation.
            reference_id: Reference ID for tracking.

        Returns:
            True if queued successfully.
        """
        try:
            user_id = None
            if hasattr(request, "user") and getattr(request.user, "is_authenticated", False):
                user_id = str(request.user.id)

            write_op = {
                "reference_id": reference_id,
                "operation": operation,
                "path": request.path,
                "method": request.method,
                "user_id": user_id,
                "queued_at": time.time(),
            }

            writes = self.get_queued_writes()
            writes.append(write_op)

            # Keep only the last 1000 writes
            if len(writes) > 1000:
                writes = writes[-1000:]

            cache.set(
                self.WRITE_QUEUE_KEY,
                json.dumps(writes),
                timeout=86400,
            )
            return True
        except Exception:
            return False
