"""
Security module for the External Services Layer.

Enforces TLS, request signing, payload validation, IP allowlists,
and audit logging for all interactions with external providers.

Usage::

    from external_services.security import security

    # Sign an outbound request
    signer = security.get_request_signer('paystack')
    signature = signer.sign(payload)

    # Verify an inbound webhook signature
    is_valid = security.validate_inbound_webhook('paystack', payload, signature)

    # Validate outbound request (enforces HTTPS in production)
    security.validate_outbound_request('payment', 'paystack', url, payload, headers)

    # Check IP allowlist
    if security.ip_allowlist.is_allowed(client_ip):
        ...
"""

import hashlib
import hmac
import time
import ipaddress
import logging
from typing import Optional, List, Dict, Union

from django.conf import settings
from django.core.exceptions import PermissionDenied

logger = logging.getLogger('external_services.security')


class RequestSigner:
    """HMAC-SHA256 request signing with timestamp nonce for replay protection.

    Each signature embeds a Unix timestamp so that recipients can detect
    and reject replayed requests after a configurable tolerance window.

    The signature format is::

        t=<timestamp>,v1=<hmac-sha256>

    This mirrors the scheme used by Stripe webhooks and similar APIs.

    Args:
        secret_key: The shared secret used for HMAC computation.
        algorithm: Hash algorithm name (default: ``sha256``).
    """

    def __init__(
        self,
        secret_key: Union[str, bytes],
        algorithm: str = 'sha256',
    ) -> None:
        self.secret_key = (
            secret_key.encode() if isinstance(secret_key, str) else secret_key
        )
        self.algorithm = algorithm

    def sign(self, payload: str, timestamp: Optional[float] = None) -> str:
        """Generate a signed header for the given payload.

        Args:
            payload: The request body to sign.
            timestamp: Unix timestamp.  Defaults to the current time.

        Returns:
            A signature header string in the format ``t=<ts>,v1=<sig>``.
        """
        ts = str(timestamp or time.time())
        message = f"{ts}.{payload}"
        signature = hmac.new(
            self.secret_key, message.encode(), hashlib.sha256,
        ).hexdigest()
        return f"t={ts},v1={signature}"

    def verify(
        self,
        payload: str,
        signature_header: str,
        tolerance_seconds: int = 300,
    ) -> bool:
        """Verify a signature header against the given payload.

        The method checks both the HMAC digest **and** that the timestamp
        is within the tolerance window to mitigate replay attacks.

        Args:
            payload: The raw request body.
            signature_header: The ``t=...,v1=...`` header value.
            tolerance_seconds: Maximum age of the signature in seconds.

        Returns:
            ``True`` if the signature is valid and recent, ``False``
            otherwise.
        """
        parts: Dict[str, str] = {}
        for item in signature_header.split(','):
            key, _, value = item.partition('=')
            parts[key.strip()] = value.strip()

        timestamp = parts.get('t', '')
        expected_sig = parts.get('v1', '')

        # Validate timestamp freshness
        try:
            if abs(time.time() - float(timestamp)) > tolerance_seconds:
                logger.warning(
                    "RequestSigner: Signature timestamp expired (tolerance=%ds)",
                    tolerance_seconds,
                )
                return False
        except (ValueError, TypeError):
            logger.warning("RequestSigner: Invalid timestamp in signature header")
            return False

        # Compute and compare HMAC
        message = f"{timestamp}.{payload}"
        computed = hmac.new(
            self.secret_key, message.encode(), hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(computed, expected_sig):
            logger.warning("RequestSigner: HMAC mismatch")
            return False

        return True


class IPAllowlist:
    """IP-based access control for external service endpoints.

    Supports both individual IP addresses and CIDR ranges.  If no
    networks are configured, all IPs are allowed (useful for
    development).

    Args:
        allowed_ips: List of IP addresses or CIDR ranges.
    """

    def __init__(self, allowed_ips: Optional[List[str]] = None) -> None:
        self._networks: List[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        if allowed_ips:
            for ip in allowed_ips:
                try:
                    self._networks.append(ipaddress.ip_network(ip, strict=False))
                except ValueError:
                    logger.warning("IPAllowlist: Invalid IP/network '%s' skipped", ip)

    def is_allowed(self, ip_address: str) -> bool:
        """Check whether an IP address is in the allowlist.

        Args:
            ip_address: The client IP address to check.

        Returns:
            ``True`` if the IP is allowed (or if no allowlist is
            configured), ``False`` otherwise.
        """
        if not self._networks:
            return True
        try:
            addr = ipaddress.ip_address(ip_address)
            return any(addr in net for net in self._networks)
        except ValueError:
            logger.warning("IPAllowlist: Invalid IP address '%s'", ip_address)
            return False


class SecurityManager:
    """Central security manager for the External Services Layer.

    Provides:
    * Per-provider request signing with automatic key management.
    * IP allowlist enforcement.
    * Outbound request validation (HTTPS enforcement in production).
    * Inbound webhook signature verification.

    Configuration is driven by Django settings:

    * ``ESL_IP_ALLOWLIST`` — list of allowed IPs/CIDRs.
    * ``ESL_<PROVIDER>_SIGNING_SECRET`` — per-provider HMAC secrets.
    * ``ESL_ENFORCE_HTTPS`` — block non-HTTPS outbound (default: not DEBUG).
    """

    def __init__(self) -> None:
        self.ip_allowlist = IPAllowlist(
            getattr(settings, 'ESL_IP_ALLOWLIST', []),
        )
        self._request_signers: Dict[str, RequestSigner] = {}

        # Whether to enforce HTTPS for outbound requests
        self._enforce_https = getattr(
            settings, 'ESL_ENFORCE_HTTPS', not getattr(settings, 'DEBUG', True),
        )

    def get_request_signer(self, provider_name: str) -> RequestSigner:
        """Get or create a :class:`RequestSigner` for the given provider.

        Signing secrets are resolved from Django settings using the
        pattern ``ESL_<PROVIDER>_SIGNING_SECRET``, falling back to
        ``settings.SECRET_KEY``.

        Args:
            provider_name: Provider identifier (e.g. ``paystack``).

        Returns:
            A :class:`RequestSigner` instance for the provider.
        """
        if provider_name not in self._request_signers:
            secret = getattr(
                settings,
                f'ESL_{provider_name.upper()}_SIGNING_SECRET',
                settings.SECRET_KEY,
            )
            self._request_signers[provider_name] = RequestSigner(secret)
        return self._request_signers[provider_name]

    def validate_outbound_request(
        self,
        service_type: str,
        provider_name: str,
        url: str,
        payload: str,
        headers: Dict[str, str],
    ) -> bool:
        """Validate an outbound request before it is sent.

        Checks that the URL uses HTTPS when the platform is running
        in production mode.  Raises :class:`PermissionDenied` if the
        check fails.

        Args:
            service_type: Category of service.
            provider_name: Provider identifier.
            url: Target URL.
            payload: Request body.
            headers: Outgoing headers.

        Returns:
            ``True`` if the request passes all validations.

        Raises:
            PermissionDenied: If the request violates security policy.
        """
        # Enforce HTTPS in production
        if self._enforce_https and not url.startswith('https://'):
            raise PermissionDenied(
                f"Non-HTTPS request to {url} blocked in production"
            )

        logger.debug(
            "Outbound request validated: %s/%s → %s",
            service_type,
            provider_name,
            url[:80],
        )
        return True

    def validate_inbound_webhook(
        self,
        provider_name: str,
        payload: str,
        signature: str,
        tolerance: int = 300,
    ) -> bool:
        """Verify the signature of an inbound webhook request.

        Args:
            provider_name: Provider that sent the webhook.
            payload: Raw request body.
            signature: Signature header from the webhook request.
            tolerance: Maximum age of the signature in seconds.

        Returns:
            ``True`` if the signature is valid.
        """
        signer = self.get_request_signer(provider_name)
        return signer.verify(payload, signature, tolerance)

    def validate_payload_size(
        self,
        payload: Union[str, bytes],
        max_size_bytes: int = 10 * 1024 * 1024,
    ) -> bool:
        """Validate that a payload does not exceed the size limit.

        Args:
            payload: The request body to validate.
            max_size_bytes: Maximum allowed size in bytes (default 10 MB).

        Returns:
            ``True`` if the payload is within limits.
        """
        size = len(payload.encode() if isinstance(payload, str) else payload)
        if size > max_size_bytes:
            logger.warning(
                "Payload size %d exceeds limit %d", size, max_size_bytes,
            )
            return False
        return True


# Module-level singleton
security = SecurityManager()
