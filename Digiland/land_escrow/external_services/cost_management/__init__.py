"""
Cost management and tracking for external service usage.

Tracks per-provider, per-operation costs and provides budget
threshold enforcement to prevent unexpected spend.

Usage::

    from external_services.cost_management import cost_tracker

    # Record a cost
    cost_tracker.record_cost(
        provider_name='paystack',
        service_type='payment',
        operation='initialize_payment',
        units=1,
        cost=0.015,
        currency='USD',
    )

    # Check if a provider has exceeded its daily budget
    if cost_tracker.check_budget_threshold('paystack', daily_budget=50.0):
        logger.warning("Paystack daily budget exceeded!")

    # Get cost summary
    summary = cost_tracker.get_provider_costs('paystack', period_days=30)
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from django.utils import timezone

logger = logging.getLogger('external_services.cost_management')


class CostTracker:
    """Track and report costs for all external service operations.

    Cost entries are stored in memory and should be periodically
    persisted to the database for long-term analytics.  The tracker
    supports:

    * Per-provider cost aggregation.
    * Daily budget threshold alerts.
    * Cost summaries by time period.
    * Multi-currency cost tracking.

    For production use, integrate with a time-series database or
    export metrics to Prometheus via the :class:`MetricsCollector`.
    """

    def __init__(self) -> None:
        self._costs: Dict[str, List[Dict[str, Any]]] = {}
        self._budget_alerts: Dict[str, bool] = {}

    def record_cost(
        self,
        provider_name: str,
        service_type: str,
        operation: str,
        units: int,
        cost: float,
        currency: str = 'USD',
    ) -> None:
        """Record a cost entry for an external service operation.

        Args:
            provider_name: Provider identifier.
            service_type: Category of service.
            operation: Operation name.
            units: Number of billing units consumed.
            cost: Monetary cost.
            currency: ISO 4217 currency code.
        """
        entry = {
            'provider': provider_name,
            'service_type': service_type,
            'operation': operation,
            'units': units,
            'cost': cost,
            'currency': currency,
            'timestamp': timezone.now().isoformat(),
        }
        self._costs.setdefault(provider_name, []).append(entry)

        logger.info(
            "Cost recorded: %s/%s/%s = %.4f %s (%d units)",
            provider_name,
            service_type,
            operation,
            cost,
            currency,
            units,
        )

    def get_provider_costs(
        self,
        provider_name: str,
        period_days: int = 30,
    ) -> Dict[str, Any]:
        """Get cost summary for a specific provider.

        Args:
            provider_name: Provider identifier.
            period_days: Number of days to look back.

        Returns:
            Dictionary with total cost, entry count, and detailed entries.
        """
        cutoff = (timezone.now() - timedelta(days=period_days)).isoformat()
        entries = [
            e for e in self._costs.get(provider_name, [])
            if e['timestamp'] >= cutoff
        ]
        total = sum(e['cost'] for e in entries)
        total_units = sum(e['units'] for e in entries)

        # Break down by service type
        by_service: Dict[str, float] = {}
        for entry in entries:
            key = entry['service_type']
            by_service[key] = by_service.get(key, 0) + entry['cost']

        return {
            'provider': provider_name,
            'period_days': period_days,
            'total_cost': total,
            'total_units': total_units,
            'entry_count': len(entries),
            'by_service_type': by_service,
            'entries': entries,
        }

    def get_all_costs(self, period_days: int = 30) -> Dict[str, Dict[str, Any]]:
        """Get cost summaries for all providers.

        Args:
            period_days: Number of days to look back.

        Returns:
            Dictionary mapping provider names to their cost summaries.
        """
        result = {}
        for provider in self._costs:
            result[provider] = self.get_provider_costs(provider, period_days)
        return result

    def check_budget_threshold(
        self,
        provider_name: str,
        daily_budget: float,
    ) -> bool:
        """Check whether a provider has exceeded its daily budget.

        Also emits a warning log the first time the threshold is crossed.

        Args:
            provider_name: Provider identifier.
            daily_budget: Maximum daily spend in the provider's currency.

        Returns:
            ``True`` if the budget has been exceeded.
        """
        today = timezone.now().date().isoformat()
        today_cost = sum(
            e['cost']
            for e in self._costs.get(provider_name, [])
            if e['timestamp'].startswith(today)
        )

        if today_cost >= daily_budget:
            alert_key = f"{provider_name}:{today}"
            if not self._budget_alerts.get(alert_key):
                logger.warning(
                    "Budget threshold reached for %s: %.2f/%.2f",
                    provider_name,
                    today_cost,
                    daily_budget,
                )
                self._budget_alerts[alert_key] = True
            return True

        return False

    def get_daily_costs(
        self,
        provider_name: str,
        days: int = 7,
    ) -> List[Dict[str, Any]]:
        """Get daily cost totals for a provider over the last N days.

        Args:
            provider_name: Provider identifier.
            days: Number of days to include.

        Returns:
            List of dictionaries with ``date`` and ``total_cost`` keys.
        """
        daily: Dict[str, float] = {}
        cutoff = (timezone.now() - timedelta(days=days)).date()

        for entry in self._costs.get(provider_name, []):
            entry_date = datetime.fromisoformat(entry['timestamp']).date()
            if entry_date >= cutoff:
                date_key = entry_date.isoformat()
                daily[date_key] = daily.get(date_key, 0) + entry['cost']

        return [
            {'date': date, 'total_cost': cost}
            for date, cost in sorted(daily.items())
        ]

    def get_cost_by_operation(
        self,
        provider_name: str,
        period_days: int = 30,
    ) -> Dict[str, float]:
        """Get cost breakdown by operation for a provider.

        Args:
            provider_name: Provider identifier.
            period_days: Number of days to look back.

        Returns:
            Dictionary mapping operation names to total costs.
        """
        cutoff = (timezone.now() - timedelta(days=period_days)).isoformat()
        by_operation: Dict[str, float] = {}

        for entry in self._costs.get(provider_name, []):
            if entry['timestamp'] >= cutoff:
                key = f"{entry['service_type']}/{entry['operation']}"
                by_operation[key] = by_operation.get(key, 0) + entry['cost']

        return by_operation

    def reset(self, provider_name: Optional[str] = None) -> None:
        """Clear cost tracking data.

        Args:
            provider_name: If provided, only reset data for this
                provider.  If ``None``, reset all data.
        """
        if provider_name:
            self._costs.pop(provider_name, None)
            # Clear related budget alerts
            self._budget_alerts = {
                k: v for k, v in self._budget_alerts.items()
                if not k.startswith(f"{provider_name}:")
            }
        else:
            self._costs.clear()
            self._budget_alerts.clear()


# Module-level singleton
cost_tracker = CostTracker()
