"""
Logging filters and middleware for request correlation and PII scrubbing.

Production readiness requirements:
- Request ID in every log entry for cross-service tracing
- PII scrubbing to comply with Kenya Data Protection Act
"""

import uuid
import re
import logging
import threading

# Thread-local storage for request ID
_request_id = threading.local()


def get_request_id():
    """Get the current request ID from thread-local storage."""
    return getattr(_request_id, 'value', '-')


def set_request_id(request_id):
    """Set the request ID in thread-local storage."""
    _request_id.value = request_id


class RequestIDMiddleware:
    """
    Middleware that generates a unique request ID for every incoming request
    and stores it in thread-local storage for access by logging filters.

    Also sets the X-Request-ID response header for client-side correlation.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Use the X-Request-ID header from nginx if available, else generate
        request_id = request.META.get('HTTP_X_REQUEST_ID') or str(uuid.uuid4())
        set_request_id(request_id)
        request.request_id = request_id

        response = self.get_response(request)
        response['X-Request-ID'] = request_id
        return response


class RequestIDFilter(logging.Filter):
    """
    Logging filter that injects the current request ID into log records.

    Usage in settings.py:
        'filters': {
            'request_id': {
                '()': 'core.log_filters.RequestIDFilter',
            },
        },
    """

    def filter(self, record):
        record.request_id = get_request_id()
        return True


class PIIScrubberFilter(logging.Filter):
    """
    Logging filter that redacts personally identifiable information (PII)
    from log messages to comply with data protection regulations.

    Redacts:
    - Email addresses
    - Phone numbers (+254XXXXXXXXX)
    - KRA PINs (A123456789B format)
    - IP addresses (configurable)
    - National ID numbers (7-9 digit sequences)
    """

    # Patterns to redact
    PATTERNS = [
        # Email addresses
        (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL_REDACTED]'),
        # Kenya phone numbers
        (re.compile(r'\+254\d{9}\b'), '[PHONE_REDACTED]'),
        (re.compile(r'\b0\d{9}\b'), '[PHONE_REDACTED]'),
        # KRA PINs (Letter + 9 digits + Letter)
        (re.compile(r'\b[A-Z]\d{9}[A-Z]\b'), '[KRA_PIN_REDACTED]'),
        # IP addresses
        (re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'), '[IP_REDACTED]'),
        # National ID numbers (7-9 consecutive digits in context)
        (re.compile(r'\bid[_\s:]*(\d{7,9})\b', re.IGNORECASE), 'id=[ID_REDACTED]'),
    ]

    def filter(self, record):
        if isinstance(record.msg, str):
            for pattern, replacement in self.PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        if hasattr(record, 'args') and record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: pattern.sub(replacement, str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                    for pattern, replacement in self.PATTERNS
                }
            elif isinstance(record.args, (tuple, list)):
                record.args = tuple(
                    pattern.sub(replacement, str(v)) if isinstance(v, str) else v
                    for v in record.args
                    for pattern, replacement in self.PATTERNS
                )
        return True
