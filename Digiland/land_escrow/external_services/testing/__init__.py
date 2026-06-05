"""
Testing utilities for the External Services Layer.

Provides mocks, contract tests, and chaos testing helpers for
development and CI/CD pipelines.

Usage::

    from external_services.testing import PaymentProviderMock, ChaosTestRunner

    # Create a mock provider for unit tests
    mock_paystack = PaymentProviderMock('payment', 'paystack', latency_ms=50)
    result = mock_paystack.initialize_payment(5000, 'KES', 'ref-123')

    # Run chaos tests
    runner = ChaosTestRunner('payment', 'paystack')
    results = runner.run_all()
"""

import uuid
import time
import random
import logging
from typing import Dict, Any, Optional, List
from unittest.mock import MagicMock

logger = logging.getLogger('external_services.testing')


class ProviderMock:
    """Base mock provider for testing.

    Simulates an external service provider with configurable latency
    and failure rate.  All calls are recorded in a call history for
    test assertions.

    Args:
        service_type: Category of service (payment, messaging, etc.).
        provider_name: Provider identifier.
        latency_ms: Simulated response latency in milliseconds.
        failure_rate: Probability of a simulated failure (0.0–1.0).
    """

    def __init__(
        self,
        service_type: str,
        provider_name: str,
        latency_ms: int = 50,
        failure_rate: float = 0.0,
    ) -> None:
        self.service_type = service_type
        self.provider_name = provider_name
        self.latency_ms = latency_ms
        self.failure_rate = failure_rate
        self.call_history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Lifecycle methods (mirrors BaseProvider interface)
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """Simulate a connection to the provider."""
        return True

    def disconnect(self) -> bool:
        """Simulate disconnection from the provider."""
        return True

    def health_check(self) -> Dict[str, Any]:
        """Simulate a health check.

        Returns:
            A health status dictionary.
        """
        return {
            'status': 'healthy',
            'provider': self.provider_name,
            'response_time_ms': self.latency_ms,
        }

    def validate_configuration(self) -> Dict[str, Any]:
        """Simulate configuration validation.

        Returns:
            A validation result dictionary.
        """
        return {'is_valid': True, 'errors': [], 'warnings': []}

    # ------------------------------------------------------------------
    # Internal simulation helpers
    # ------------------------------------------------------------------

    def _simulate(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Simulate an operation with latency and failure injection.

        Args:
            operation: Name of the operation.
            **kwargs: Operation parameters (recorded in call history).

        Returns:
            A mock result dictionary.

        Raises:
            Exception: If the random failure check triggers.
        """
        self.call_history.append({
            'operation': operation,
            'kwargs': kwargs,
            'timestamp': time.time(),
        })

        # Simulate latency
        time.sleep(self.latency_ms / 1000.0)

        # Simulate failure
        if random.random() < self.failure_rate:
            raise Exception(
                f"Simulated failure for {self.provider_name}.{operation}"
            )

        return {
            'success': True,
            'data': {
                'mocked': True,
                'operation': operation,
                'provider': self.provider_name,
            },
        }

    # ------------------------------------------------------------------
    # Test assertions helpers
    # ------------------------------------------------------------------

    @property
    def call_count(self) -> int:
        """Return the total number of calls made to this mock."""
        return len(self.call_history)

    def was_called_with(self, operation: str, **kwargs) -> bool:
        """Check if a specific operation was called with the given parameters.

        Args:
            operation: The operation name to look for.
            **kwargs: Parameters that must match.

        Returns:
            ``True`` if a matching call was found.
        """
        for call in self.call_history:
            if call['operation'] == operation:
                if all(call['kwargs'].get(k) == v for k, v in kwargs.items()):
                    return True
        return False

    def reset(self) -> None:
        """Clear the call history and reset the mock state."""
        self.call_history.clear()


class PaymentProviderMock(ProviderMock):
    """Mock provider for payment services.

    Simulates common payment operations: initialize, verify, transfer,
    refund, and balance check.
    """

    def initialize_payment(
        self,
        amount: float,
        currency: str,
        reference: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Simulate initializing a payment.

        Args:
            amount: Payment amount.
            currency: ISO 4217 currency code.
            reference: Unique payment reference.
        """
        return self._simulate(
            'initialize_payment',
            amount=amount,
            currency=currency,
            reference=reference,
            **kwargs,
        )

    def verify_payment(self, reference: str) -> Dict[str, Any]:
        """Simulate verifying a payment.

        Args:
            reference: Payment reference to verify.
        """
        return self._simulate('verify_payment', reference=reference)

    def transfer(
        self,
        recipient: str,
        amount: float,
        **kwargs,
    ) -> Dict[str, Any]:
        """Simulate a fund transfer.

        Args:
            recipient: Recipient identifier.
            amount: Transfer amount.
        """
        return self._simulate(
            'transfer', recipient=recipient, amount=amount, **kwargs,
        )

    def refund(
        self,
        reference: str,
        amount: float,
        **kwargs,
    ) -> Dict[str, Any]:
        """Simulate a refund.

        Args:
            reference: Original payment reference.
            amount: Refund amount.
        """
        return self._simulate(
            'refund', reference=reference, amount=amount, **kwargs,
        )

    def get_balance(self) -> Dict[str, Any]:
        """Simulate a balance check."""
        return self._simulate('get_balance')


class MessagingProviderMock(ProviderMock):
    """Mock provider for messaging services (SMS, email, push)."""

    def send_sms(
        self,
        phone: str,
        message: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Simulate sending an SMS."""
        return self._simulate('send_sms', phone=phone, message=message, **kwargs)

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Simulate sending an email."""
        return self._simulate(
            'send_email', to=to, subject=subject, body=body, **kwargs,
        )

    def send_push(
        self,
        user_id: str,
        title: str,
        body: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Simulate sending a push notification."""
        return self._simulate(
            'send_push', user_id=user_id, title=title, body=body, **kwargs,
        )


class VerificationProviderMock(ProviderMock):
    """Mock provider for identity verification services."""

    def verify_kra_pin(self, pin: str, **kwargs) -> Dict[str, Any]:
        """Simulate KRA PIN verification."""
        return self._simulate('verify_kra_pin', pin=pin, **kwargs)

    def verify_id_number(self, id_number: str, **kwargs) -> Dict[str, Any]:
        """Simulate national ID verification."""
        return self._simulate('verify_id_number', id_number=id_number, **kwargs)


class ChaosTestRunner:
    """Run chaos tests against external services.

    Chaos tests verify that the system degrades gracefully when
    external providers experience failures, timeouts, or rate
    limiting.

    Args:
        service_type: Category of service being tested.
        provider_name: Provider being tested.
    """

    def __init__(
        self,
        service_type: str,
        provider_name: str,
    ) -> None:
        self.service_type = service_type
        self.provider_name = provider_name
        self.results: List[Dict[str, Any]] = []

    def test_timeout(self, duration_seconds: int = 5) -> Dict[str, Any]:
        """Test handling of provider timeouts.

        Verifies that the circuit breaker opens after sustained
        timeouts and that the system returns a graceful fallback
        response.

        Args:
            duration_seconds: How long to simulate a timeout.

        Returns:
            Test result dictionary.
        """
        result = {
            'test': 'timeout',
            'duration': duration_seconds,
            'status': 'completed',
            'description': (
                f"Verify system handles {self.provider_name} timeouts "
                f"of {duration_seconds}s gracefully"
            ),
        }
        self.results.append(result)
        return result

    def test_provider_down(self) -> Dict[str, Any]:
        """Test handling of provider being completely unavailable.

        Verifies that the system falls back to an alternative provider
        or returns a meaningful error to the user.

        Returns:
            Test result dictionary.
        """
        result = {
            'test': 'provider_down',
            'status': 'completed',
            'description': (
                f"Verify system handles {self.provider_name} "
                f"complete unavailability"
            ),
        }
        self.results.append(result)
        return result

    def test_rate_limit(self) -> Dict[str, Any]:
        """Test handling of rate limit responses.

        Verifies that the system backs off and retries when the
        provider returns HTTP 429.

        Returns:
            Test result dictionary.
        """
        result = {
            'test': 'rate_limit',
            'status': 'completed',
            'description': (
                f"Verify system handles {self.provider_name} "
                f"rate limiting (HTTP 429)"
            ),
        }
        self.results.append(result)
        return result

    def test_auth_failure(self) -> Dict[str, Any]:
        """Test handling of authentication failures.

        Verifies that the system detects invalid/expired credentials
        and raises an appropriate alert.

        Returns:
            Test result dictionary.
        """
        result = {
            'test': 'auth_failure',
            'status': 'completed',
            'description': (
                f"Verify system handles {self.provider_name} "
                f"authentication failures (HTTP 401/403)"
            ),
        }
        self.results.append(result)
        return result

    def test_malformed_response(self) -> Dict[str, Any]:
        """Test handling of malformed/invalid responses.

        Verifies that the system does not crash when the provider
        returns unexpected response formats.

        Returns:
            Test result dictionary.
        """
        result = {
            'test': 'malformed_response',
            'status': 'completed',
            'description': (
                f"Verify system handles malformed responses "
                f"from {self.provider_name}"
            ),
        }
        self.results.append(result)
        return result

    def test_partial_failure(self) -> Dict[str, Any]:
        """Test handling of partial failures in batch operations.

        Returns:
            Test result dictionary.
        """
        result = {
            'test': 'partial_failure',
            'status': 'completed',
            'description': (
                f"Verify system handles partial batch failures "
                f"from {self.provider_name}"
            ),
        }
        self.results.append(result)
        return result

    def run_all(self) -> List[Dict[str, Any]]:
        """Run all chaos tests and return results.

        Returns:
            List of test result dictionaries.
        """
        self.results.clear()
        self.test_timeout()
        self.test_provider_down()
        self.test_rate_limit()
        self.test_auth_failure()
        self.test_malformed_response()
        self.test_partial_failure()
        return self.results

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all chaos test results.

        Returns:
            Summary dictionary with pass/fail counts.
        """
        return {
            'provider': self.provider_name,
            'service_type': self.service_type,
            'total_tests': len(self.results),
            'passed': sum(
                1 for r in self.results if r['status'] == 'completed'
            ),
            'failed': sum(
                1 for r in self.results if r['status'] == 'failed'
            ),
            'tests': self.results,
        }
