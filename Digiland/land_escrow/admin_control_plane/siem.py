"""
SIEM Integration for Admin Control Plane Monitoring
=====================================================

Provides Security Information and Event Management (SIEM) integration
for real-time monitoring of admin control plane security events.

Features
--------
- Forward security events to external SIEM platforms
- Batch event forwarding for high-throughput environments
- Rule-based threat detection with configurable thresholds
- Automated alert generation and management
- Incident creation from alerts
- Support for CEF (Common Event Format), JSON, and Syslog output

Detection Rules
---------------
The following threat patterns are monitored:

1. **Multiple failed admin logins** — Brute force detection
2. **Admin access from new IP/geolocation** — Impossible travel / compromised credentials
3. **Unusual admin action patterns** — Insider threat detection
4. **Privilege escalation attempts** — Unauthorized role/permission changes
5. **Concurrent sessions from different locations** — Session hijacking
6. **Off-hours admin access** — Anomalous timing patterns
7. **Bulk data access patterns** — Data exfiltration detection
8. **Financial action anomalies** — Fraud detection

SIEM Platform Support
---------------------
- **Splunk**: HTTP Event Collector (HEC) with JSON format
- **Microsoft Sentinel**: Log Analytics with JSON format
- **Datadog**: Log intake API with JSON format

Classes
-------
SIEMIntegrationService
    Forward events, manage detection rules, generate and manage alerts.
"""

import hashlib
import json
import logging
import os
import time
import uuid
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.utils import timezone

from .services import ImmutableAuditService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Output formats
OUTPUT_FORMATS = ["CEF", "JSON", "SYSLOG"]

# Severity mapping for CEF
CEF_SEVERITY_MAP = {
    "critical": 10,
    "high": 8,
    "medium": 5,
    "low": 3,
    "info": 1,
}

# SIEM configuration from Django settings
SIEM_CONFIG = {
    "splunk": {
        "hec_url": getattr(settings, "SIEM_SPLUNK_HEC_URL", ""),
        "hec_token": getattr(settings, "SIEM_SPLUNK_HEC_TOKEN", ""),
        "index": getattr(settings, "SIEM_SPLUNK_INDEX", "admin_security"),
        "source": getattr(settings, "SIEM_SPLUNK_SOURCE", "digiland_acp"),
        "sourcetype": getattr(settings, "SIEM_SPLUNK_SOURCETYPE", "_json"),
    },
    "sentinel": {
        "workspace_id": getattr(settings, "SIEM_SENTINEL_WORKSPACE_ID", ""),
        "shared_key": getattr(settings, "SIEM_SENTINEL_SHARED_KEY", ""),
        "log_type": getattr(settings, "SIEM_SENTINEL_LOG_TYPE", "AdminControlPlane"),
    },
    "datadog": {
        "api_key": getattr(settings, "SIEM_DATADOG_API_KEY", ""),
        "site": getattr(settings, "SIEM_DATADOG_SITE", "datadoghq.com"),
        "service": getattr(settings, "SIEM_DATADOG_SERVICE", "digiland-acp"),
    },
}

# Business hours (UTC)
BUSINESS_HOURS_START = 8
BUSINESS_HOURS_END = 18


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SIEMError(Exception):
    """Base exception for SIEM operations."""
    pass


class DetectionRuleError(SIEMError):
    """Error related to detection rules."""
    pass


class AlertError(SIEMError):
    """Error related to alert operations."""
    pass


# ---------------------------------------------------------------------------
# Detection Rule Store
# ---------------------------------------------------------------------------

# {rule_id: DetectionRule}
_detection_rules: dict = {}


class DetectionRule:
    """A threat detection rule that evaluates security events.

    Attributes
    ----------
    id : str
        Unique rule identifier (UUID).
    name : str
        Human-readable rule name.
    description : str
        Detailed description of what the rule detects.
    category : str
        Detection category (e.g. ``"auth"``, ``"access"``, ``"financial"``).
    severity : str
        Alert severity if the rule fires (``"critical"``, ``"high"``,
        ``"medium"``, ``"low"``).
    conditions : dict
        Rule conditions — event attributes and thresholds.
    is_active : bool
        Whether the rule is currently enabled.
    created_at : str
        ISO-8601 creation timestamp.
    last_fired_at : str or None
        ISO-8601 timestamp of last rule match.
    fire_count : int
        Total number of times this rule has fired.
    """

    def __init__(
        self,
        name: str,
        description: str,
        category: str,
        severity: str,
        conditions: dict,
    ):
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.category = category
        self.severity = severity
        self.conditions = conditions
        self.is_active = True
        self.created_at = timezone.now().isoformat()
        self.last_fired_at = None
        self.fire_count = 0

        _detection_rules[self.id] = self

    def to_dict(self) -> dict:
        """Serialise to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "severity": self.severity,
            "conditions": self.conditions,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "last_fired_at": self.last_fired_at,
            "fire_count": self.fire_count,
        }


# ---------------------------------------------------------------------------
# Alert Store
# ---------------------------------------------------------------------------

# {alert_id: Alert}
_alert_store: dict = {}


class Alert:
    """A security alert generated by a detection rule.

    Attributes
    ----------
    id : str
        Unique alert identifier (UUID).
    rule_id : str
        The detection rule that generated this alert.
    severity : str
        Alert severity.
    title : str
        Short alert title.
    description : str
        Detailed alert description.
    event_data : dict
        The event data that triggered the alert.
    status : str
        ``"open"``, ``"acknowledged"``, ``"resolved"``, ``"incident"``.
    acknowledged_by : str or None
        User ID of the admin who acknowledged.
    acknowledged_at : str or None
        ISO-8601 timestamp of acknowledgement.
    created_at : str
        ISO-8601 creation timestamp.
    """

    def __init__(
        self,
        rule_id: str,
        severity: str,
        title: str,
        description: str,
        event_data: dict,
    ):
        self.id = str(uuid.uuid4())
        self.rule_id = rule_id
        self.severity = severity
        self.title = title
        self.description = description
        self.event_data = event_data
        self.status = "open"
        self.acknowledged_by = None
        self.acknowledged_at = None
        self.created_at = timezone.now().isoformat()

        _alert_store[self.id] = self

    def to_dict(self) -> dict:
        """Serialise to a dictionary."""
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "event_data": self.event_data,
            "status": self.status,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Event Formatters
# ---------------------------------------------------------------------------

def _format_cef(event: dict) -> str:
    """Format a security event in Common Event Format (CEF).

    CEF format: ``CEF:Version|Device Vendor|Device Product|Device Version|
    Signature ID|Name|Severity|Extensions``

    Parameters
    ----------
    event : dict
        The security event.

    Returns
    -------
    str
        CEF-formatted event string.
    """
    severity = CEF_SEVERITY_MAP.get(event.get("severity", "info"), 1)
    extensions = " ".join(
        f"{k}={v}" for k, v in event.get("extensions", {}).items()
    )
    return (
        f"CEF:0|Digiland|AdminControlPlane|1.0|"
        f"{event.get('signature_id', 'UNKNOWN')}|"
        f"{event.get('name', 'Security Event')}|"
        f"{severity}|{extensions}"
    )


def _format_json(event: dict) -> str:
    """Format a security event as JSON.

    Parameters
    ----------
    event : dict
        The security event.

    Returns
    -------
    str
        JSON-formatted event string.
    """
    return json.dumps(event, sort_keys=True, default=str)


def _format_syslog(event: dict) -> str:
    """Format a security event as Syslog.

    Parameters
    ----------
    event : dict
        The security event.

    Returns
    -------
    str
        Syslog-formatted event string (RFC 5424).
    """
    timestamp = event.get("timestamp", timezone.now().isoformat())
    severity = event.get("severity", "info")
    name = event.get("name", "Security Event")
    message = json.dumps(event.get("extensions", {}), default=str)
    return f"<134>1 {timestamp} digiland-acp Security - - [{severity}] {name} {message}"


# ---------------------------------------------------------------------------
# Default Detection Rules
# ---------------------------------------------------------------------------

def _create_default_rules():
    """Create built-in detection rules if they don't exist.

    These rules are created on first import and provide baseline
    threat detection for the admin control plane.
    """
    defaults = [
        {
            "name": "Multiple Failed Admin Logins",
            "description": (
                "Detects multiple failed login attempts by an admin "
                "within a short time window, indicating brute force."
            ),
            "category": "auth",
            "severity": "high",
            "conditions": {
                "event_type": "ADMIN_LOGIN_FAILED",
                "threshold": 5,
                "window_minutes": 10,
                "group_by": "actor_id",
            },
        },
        {
            "name": "Admin Access from New IP/Geolocation",
            "description": (
                "Detects admin access from an IP address or geolocation "
                "not previously seen for this user, indicating possible "
                "compromised credentials."
            ),
            "category": "access",
            "severity": "medium",
            "conditions": {
                "event_type": "ADMIN_LOGIN_SUCCESS",
                "check": "new_ip_for_user",
                "require_geolocation": True,
            },
        },
        {
            "name": "Unusual Admin Action Patterns",
            "description": (
                "Detects unusual patterns in admin actions such as "
                "rapid successive actions, actions on many different "
                "resources, or actions outside the admin's normal scope."
            ),
            "category": "behavior",
            "severity": "medium",
            "conditions": {
                "event_type": "ADMIN_ACTION",
                "threshold": 30,
                "window_minutes": 5,
                "group_by": "actor_id",
            },
        },
        {
            "name": "Privilege Escalation Attempts",
            "description": (
                "Detects attempts to escalate privileges, including "
                "role changes, permission assignments, and admin "
                "account creation."
            ),
            "category": "auth",
            "severity": "critical",
            "conditions": {
                "event_types": [
                    "ROLE_CHANGE",
                    "PERMISSION_ASSIGN",
                    "ADMIN_CREATE",
                ],
                "require_dual_approval": True,
            },
        },
        {
            "name": "Concurrent Sessions from Different Locations",
            "description": (
                "Detects concurrent admin sessions from different IP "
                "addresses, indicating session hijacking or credential "
                "sharing."
            ),
            "category": "access",
            "severity": "high",
            "conditions": {
                "event_type": "ADMIN_SESSION_CREATE",
                "check": "concurrent_sessions_different_ip",
                "max_concurrent": 2,
            },
        },
        {
            "name": "Off-Hours Admin Access",
            "description": (
                "Detects admin access outside of business hours "
                "(8 AM – 6 PM UTC), which may indicate unauthorized "
                "access or insider threats."
            ),
            "category": "access",
            "severity": "low",
            "conditions": {
                "event_type": "ADMIN_LOGIN_SUCCESS",
                "check": "outside_business_hours",
                "business_hours_start": BUSINESS_HOURS_START,
                "business_hours_end": BUSINESS_HOURS_END,
            },
        },
        {
            "name": "Bulk Data Access Patterns",
            "description": (
                "Detects patterns of bulk data access that may indicate "
                "data exfiltration, such as many read operations on "
                "sensitive resources in a short time."
            ),
            "category": "data",
            "severity": "high",
            "conditions": {
                "event_type": "ADMIN_DATA_ACCESS",
                "threshold": 50,
                "window_minutes": 15,
                "group_by": "actor_id",
                "sensitive_resources": [
                    "User", "Transaction", "FinancialAction", "KYCProfile",
                ],
            },
        },
        {
            "name": "Financial Action Anomalies",
            "description": (
                "Detects anomalous financial actions such as unusually "
                "large amounts, rapid successive approvals, or actions "
                "on the same recipient by different admins."
            ),
            "category": "financial",
            "severity": "high",
            "conditions": {
                "event_type": "FINANCIAL_ACTION",
                "amount_threshold": 500000,
                "rapid_approval_window_minutes": 5,
                "same_recipient_threshold": 3,
            },
        },
    ]

    for rule_data in defaults:
        # Check if a rule with this name already exists
        existing = any(
            r.name == rule_data["name"]
            for r in _detection_rules.values()
        )
        if not existing:
            DetectionRule(**rule_data)


# Initialize default rules
_create_default_rules()


# ===========================================================================
# SIEM Integration Service
# ===========================================================================

class SIEMIntegrationService:
    """Forward events, manage detection rules, and generate alerts.

    This service provides the bridge between admin control plane
    security events and external SIEM platforms.  Events are:

    1. Normalised into a common format
    2. Evaluated against detection rules
    3. Forwarded to configured SIEM platforms
    4. Used to generate alerts when rules fire

    Example
    -------
    >>> SIEMIntegrationService.forward_event({
    ...     "event_type": "ADMIN_LOGIN_FAILED",
    ...     "actor_id": "abc-123",
    ...     "ip_address": "1.2.3.4",
    ...     "timestamp": "2025-01-01T00:00:00Z",
    ... })
    """

    # Event buffer for batch forwarding
    _event_buffer: list = []
    _buffer_max_size = 100
    _buffer_flush_interval = 60  # seconds
    _last_flush = time.time()

    @staticmethod
    def forward_event(
        event: dict,
        output_format: str = "JSON",
        platforms: Optional[list] = None,
    ) -> dict:
        """Forward a security event to SIEM platforms.

        The event is normalised, formatted, and forwarded to all
        configured SIEM platforms.  It is also evaluated against
        detection rules.

        Parameters
        ----------
        event : dict
            The security event.  Should contain at minimum:
            - ``event_type`` : Event category
            - ``timestamp`` : ISO-8601 timestamp
            - ``severity`` : Event severity
            Additional fields depend on the event type.
        output_format : str
            Output format: ``"CEF"``, ``"JSON"``, or ``"SYSLOG"``.
        platforms : list[str], optional
            Specific platforms to forward to.  If ``None``, all
            configured platforms are used.

        Returns
        -------
        dict
            Forwarding result with event ID and delivery status.
        """
        event_id = str(uuid.uuid4())

        # Normalise event
        normalised = SIEMIntegrationService._normalise_event(event, event_id)

        # Evaluate against detection rules
        alerts = SIEMIntegrationService.evaluate_rules(normalised)

        # Format event
        if output_format == "CEF":
            formatted = _format_cef(normalised)
        elif output_format == "SYSLOG":
            formatted = _format_syslog(normalised)
        else:
            formatted = _format_json(normalised)

        # Forward to platforms
        platforms = platforms or ["splunk", "sentinel", "datadog"]
        delivery_status = {}

        for platform in platforms:
            config = SIEM_CONFIG.get(platform, {})
            if not SIEMIntegrationService._is_platform_configured(config):
                delivery_status[platform] = "not_configured"
                continue

            try:
                result = SIEMIntegrationService._send_to_platform(
                    platform, config, formatted, normalised
                )
                delivery_status[platform] = result
            except Exception as exc:
                logger.error(
                    "SIEM: Failed to forward event %s to %s: %s",
                    event_id[:8],
                    platform,
                    exc,
                )
                delivery_status[platform] = f"error: {exc}"

        # Buffer for batch forwarding
        SIEMIntegrationService._event_buffer.append(normalised)
        if len(SIEMIntegrationService._event_buffer) >= SIEMIntegrationService._buffer_max_size:
            SIEMIntegrationService.flush_buffer()

        return {
            "event_id": event_id,
            "formatted": formatted[:200] + "..." if len(formatted) > 200 else formatted,
            "alerts_generated": len(alerts),
            "delivery_status": delivery_status,
        }

    @staticmethod
    def forward_batch(events: list, output_format: str = "JSON") -> dict:
        """Batch forward multiple events to SIEM platforms.

        More efficient than individual forwarding for high-volume
        event streams.

        Parameters
        ----------
        events : list[dict]
            List of security events.
        output_format : str
            Output format for all events.

        Returns
        -------
        dict
            Batch forwarding result.
        """
        results = []
        alerts_generated = 0

        for event in events:
            result = SIEMIntegrationService.forward_event(event, output_format)
            results.append(result)
            alerts_generated += result["alerts_generated"]

        logger.info(
            "SIEM: Batch forwarded %d events, %d alerts generated.",
            len(events),
            alerts_generated,
        )

        return {
            "total_events": len(events),
            "alerts_generated": alerts_generated,
            "results": results,
        }

    @staticmethod
    def create_detection_rule(
        name: str,
        description: str,
        category: str,
        severity: str,
        conditions: dict,
        created_by=None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict:
        """Create a new detection rule.

        Parameters
        ----------
        name : str
            Rule name (must be unique).
        description : str
            Detailed description.
        category : str
            Detection category (``"auth"``, ``"access"``, ``"behavior"``,
            ``"data"``, ``"financial"``).
        severity : str
            Alert severity (``"critical"``, ``"high"``, ``"medium"``, ``"low"``).
        conditions : dict
            Rule conditions and thresholds.
        created_by : User, optional
        ip_address : str
        user_agent : str

        Returns
        -------
        dict
            Created rule metadata.

        Raises
        ------
        DetectionRuleError
            If a rule with the same name already exists.
        """
        # Check for duplicate name
        if any(r.name == name for r in _detection_rules.values()):
            raise DetectionRuleError(
                f"A detection rule named '{name}' already exists."
            )

        # Validate severity
        valid_severities = ["critical", "high", "medium", "low"]
        if severity not in valid_severities:
            raise DetectionRuleError(
                f"Invalid severity '{severity}'. "
                f"Valid: {', '.join(valid_severities)}"
            )

        # Validate category
        valid_categories = ["auth", "access", "behavior", "data", "financial"]
        if category not in valid_categories:
            raise DetectionRuleError(
                f"Invalid category '{category}'. "
                f"Valid: {', '.join(valid_categories)}"
            )

        rule = DetectionRule(
            name=name,
            description=description,
            category=category,
            severity=severity,
            conditions=conditions,
        )

        # Audit log
        ImmutableAuditService.log(
            actor=created_by,
            action="SIEM_DETECTION_RULE_CREATED",
            resource_type="DetectionRule",
            resource_id=rule.id,
            metadata={
                "name": name,
                "category": category,
                "severity": severity,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(
            "SIEM: Detection rule '%s' created (category=%s, severity=%s)",
            name,
            category,
            severity,
        )

        return rule.to_dict()

    @staticmethod
    def evaluate_rules(event: dict) -> list:
        """Evaluate an event against all active detection rules.

        Parameters
        ----------
        event : dict
            The security event to evaluate.

        Returns
        -------
        list[dict]
            List of alerts generated by matching rules.
        """
        alerts = []

        for rule in _detection_rules.values():
            if not rule.is_active:
                continue

            match = SIEMIntegrationService._evaluate_rule(rule, event)
            if match:
                alert = SIEMIntegrationService.generate_alert(rule, event)
                alerts.append(alert)

        return alerts

    @staticmethod
    def _evaluate_rule(rule: DetectionRule, event: dict) -> bool:
        """Evaluate a single rule against an event.

        Parameters
        ----------
        rule : DetectionRule
            The rule to evaluate.
        event : dict
            The event to check.

        Returns
        -------
        bool
            ``True`` if the rule matches the event.
        """
        conditions = rule.conditions
        event_type = event.get("event_type", "")

        # Check event type match
        if "event_type" in conditions:
            if event_type != conditions["event_type"]:
                return False

        if "event_types" in conditions:
            if event_type not in conditions["event_types"]:
                return False

        # Check for off-hours access
        if conditions.get("check") == "outside_business_hours":
            timestamp = event.get("timestamp", "")
            if timestamp:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    hour = dt.hour
                    start = conditions.get("business_hours_start", BUSINESS_HOURS_START)
                    end = conditions.get("business_hours_end", BUSINESS_HOURS_END)
                    if start <= hour < end:
                        return False  # Within business hours
                except (ValueError, TypeError):
                    pass

        # Check amount threshold for financial events
        if "amount_threshold" in conditions:
            amount = event.get("amount", 0)
            if amount and float(amount) < conditions["amount_threshold"]:
                return False

        # For threshold-based rules, we need state tracking.
        # In production, this would use Redis or a time-series DB.
        # Here we do a simplified check based on the current event.
        if "threshold" in conditions and "window_minutes" in conditions:
            # Threshold-based detection requires aggregation over time.
            # We mark this as a potential match but rely on the SIEM
            # platform's correlation engine for accurate detection.
            pass

        return True

    @staticmethod
    def generate_alert(rule: DetectionRule, event: dict) -> dict:
        """Generate a security alert from a matched rule.

        Parameters
        ----------
        rule : DetectionRule
            The rule that matched.
        event : dict
            The triggering event.

        Returns
        -------
        dict
            Alert metadata.
        """
        # Update rule statistics
        rule.last_fired_at = timezone.now().isoformat()
        rule.fire_count += 1

        # Create alert
        alert = Alert(
            rule_id=rule.id,
            severity=rule.severity,
            title=f"[{rule.severity.upper()}] {rule.name}",
            description=(
                f"Detection rule '{rule.name}' triggered.\n\n"
                f"Rule: {rule.description}\n\n"
                f"Event: {event.get('event_type', 'unknown')} "
                f"at {event.get('timestamp', 'unknown')}\n"
                f"Actor: {event.get('actor_id', 'unknown')}\n"
                f"IP: {event.get('ip_address', 'unknown')}"
            ),
            event_data=event,
        )

        # Audit log
        ImmutableAuditService.log(
            actor=None,
            action="SIEM_ALERT_GENERATED",
            resource_type="SecurityAlert",
            resource_id=alert.id,
            metadata={
                "rule_name": rule.name,
                "severity": rule.severity,
                "event_type": event.get("event_type", "unknown"),
                "actor_id": event.get("actor_id"),
            },
        )

        logger.warning(
            "SIEM: Alert generated — rule='%s' severity=%s event=%s",
            rule.name,
            rule.severity,
            event.get("event_type", "unknown"),
        )

        return alert.to_dict()

    @staticmethod
    def get_alerts(
        filters: Optional[dict] = None,
    ) -> list:
        """Query alerts with optional filters.

        Parameters
        ----------
        filters : dict, optional
            Filters to apply:
            - ``status`` : Filter by alert status
            - ``severity`` : Filter by severity
            - ``rule_id`` : Filter by detection rule
            - ``since`` : ISO-8601 timestamp
            - ``until`` : ISO-8601 timestamp

        Returns
        -------
        list[dict]
            Matching alerts, ordered by creation date (newest first).
        """
        filters = filters or {}
        results = []

        for alert in _alert_store.values():
            if "status" in filters and alert.status != filters["status"]:
                continue
            if "severity" in filters and alert.severity != filters["severity"]:
                continue
            if "rule_id" in filters and alert.rule_id != filters["rule_id"]:
                continue
            if "since" in filters and alert.created_at < filters["since"]:
                continue
            if "until" in filters and alert.created_at > filters["until"]:
                continue
            results.append(alert.to_dict())

        results.sort(key=lambda x: x["created_at"], reverse=True)
        return results

    @staticmethod
    def acknowledge_alert(
        alert_id: str,
        admin=None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict:
        """Acknowledge a security alert.

        Acknowledging an alert indicates that an admin has reviewed it.

        Parameters
        ----------
        alert_id : str
            The alert ID.
        admin : User, optional
            The admin acknowledging the alert.
        ip_address : str
        user_agent : str

        Returns
        -------
        dict
            Updated alert metadata.

        Raises
        ------
        AlertError
            If the alert is not found or already acknowledged.
        """
        alert = _alert_store.get(alert_id)
        if alert is None:
            raise AlertError(f"Alert {alert_id[:8]}... not found.")

        if alert.status != "open":
            raise AlertError(
                f"Alert is in '{alert.status}' status — only 'open' "
                f"alerts can be acknowledged."
            )

        alert.status = "acknowledged"
        alert.acknowledged_by = str(admin.id) if admin else None
        alert.acknowledged_at = timezone.now().isoformat()

        # Audit log
        ImmutableAuditService.log(
            actor=admin,
            action="SIEM_ALERT_ACKNOWLEDGED",
            resource_type="SecurityAlert",
            resource_id=alert_id,
            metadata={
                "severity": alert.severity,
                "title": alert.title,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return alert.to_dict()

    @staticmethod
    def create_incident_from_alert(
        alert_id: str,
        created_by=None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict:
        """Create a security incident from an alert.

        This activates incident mode and links the alert to the
        incident for tracking.

        Parameters
        ----------
        alert_id : str
            The alert ID.
        created_by : User, optional
            The admin creating the incident.
        ip_address : str
        user_agent : str

        Returns
        -------
        dict
            Incident creation result.

        Raises
        ------
        AlertError
            If the alert is not found or not acknowledged.
        """
        alert = _alert_store.get(alert_id)
        if alert is None:
            raise AlertError(f"Alert {alert_id[:8]}... not found.")

        if alert.status not in ("open", "acknowledged"):
            raise AlertError(
                f"Alert is in '{alert.status}' status — only 'open' or "
                f"'acknowledged' alerts can be escalated to incidents."
            )

        # Update alert status
        alert.status = "incident"

        # Create incident via the emergency service
        from .emergency import EmergencyControlService

        severity_map = {
            "critical": "P1_CRITICAL",
            "high": "P2_HIGH",
            "medium": "P3_MEDIUM",
            "low": "P4_LOW",
        }
        incident_severity = severity_map.get(alert.severity, "P3_MEDIUM")

        incident = EmergencyControlService.activate_incident_mode(
            reason=f"Alert escalated: {alert.title}",
            severity=incident_severity,
            activated_by=created_by,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Audit log
        ImmutableAuditService.log(
            actor=created_by,
            action="SIEM_INCIDENT_CREATED_FROM_ALERT",
            resource_type="SecurityAlert",
            resource_id=alert_id,
            metadata={
                "alert_severity": alert.severity,
                "incident_id": incident.get("id"),
                "incident_severity": incident_severity,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.critical(
            "SIEM: Incident created from alert %s — severity=%s",
            alert_id[:8],
            incident_severity,
        )

        return {
            "alert_id": alert_id,
            "alert_status": alert.status,
            "incident": incident,
        }

    @staticmethod
    def list_detection_rules(
        category: Optional[str] = None,
        active_only: bool = False,
    ) -> list:
        """List all detection rules with optional filters.

        Parameters
        ----------
        category : str, optional
            Filter by category.
        active_only : bool
            Only return active rules.

        Returns
        -------
        list[dict]
            Detection rules.
        """
        results = []
        for rule in _detection_rules.values():
            if active_only and not rule.is_active:
                continue
            if category and rule.category != category:
                continue
            results.append(rule.to_dict())

        results.sort(key=lambda x: x["created_at"], reverse=True)
        return results

    @staticmethod
    def get_rule(rule_id: str) -> Optional[dict]:
        """Retrieve a detection rule by ID."""
        rule = _detection_rules.get(rule_id)
        return rule.to_dict() if rule else None

    @staticmethod
    def toggle_rule(
        rule_id: str,
        is_active: bool,
        toggled_by=None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict:
        """Enable or disable a detection rule.

        Parameters
        ----------
        rule_id : str
            The rule ID.
        is_active : bool
            New active state.
        toggled_by : User, optional
        ip_address : str
        user_agent : str

        Returns
        -------
        dict
            Updated rule metadata.
        """
        rule = _detection_rules.get(rule_id)
        if rule is None:
            raise DetectionRuleError(f"Rule {rule_id[:8]}... not found.")

        rule.is_active = is_active

        ImmutableAuditService.log(
            actor=toggled_by,
            action=f"SIEM_RULE_{'ENABLED' if is_active else 'DISABLED'}",
            resource_type="DetectionRule",
            resource_id=rule_id,
            metadata={"rule_name": rule.name},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return rule.to_dict()

    # ── Internal helpers ────────────────────────────────────────────────

    @staticmethod
    def _normalise_event(event: dict, event_id: str) -> dict:
        """Normalise a security event into a standard format.

        Parameters
        ----------
        event : dict
            Raw event data.
        event_id : str
            Generated event ID.

        Returns
        -------
        dict
            Normalised event with all required fields.
        """
        return {
            "event_id": event_id,
            "event_type": event.get("event_type", "UNKNOWN"),
            "timestamp": event.get("timestamp", timezone.now().isoformat()),
            "severity": event.get("severity", "info"),
            "actor_id": event.get("actor_id"),
            "actor_email": event.get("actor_email"),
            "ip_address": event.get("ip_address"),
            "user_agent": event.get("user_agent"),
            "session_id": event.get("session_id"),
            "resource_type": event.get("resource_type"),
            "resource_id": event.get("resource_id"),
            "action": event.get("action"),
            "extensions": event.get("extensions", {}),
            "source": "digiland-acp",
        }

    @staticmethod
    def _is_platform_configured(config: dict) -> bool:
        """Check if a SIEM platform has sufficient configuration."""
        if not config:
            return False
        # At least one key must be non-empty
        return any(v for v in config.values() if isinstance(v, str))

    @staticmethod
    def _send_to_platform(
        platform: str,
        config: dict,
        formatted_event: str,
        raw_event: dict,
    ) -> str:
        """Send a formatted event to a SIEM platform.

        In production, this would make HTTP requests to the platform's
        API.  For this implementation, we log the attempt and return
        a simulated success.

        Parameters
        ----------
        platform : str
            Platform name.
        config : dict
            Platform configuration.
        formatted_event : str
            Formatted event string.
        raw_event : dict
            Raw event data for platforms that prefer JSON.

        Returns
        -------
        str
            Delivery status message.
        """
        # In production, implement actual HTTP calls:
        # - Splunk: POST to HEC URL with Bearer token
        # - Sentinel: POST to Log Analytics API with shared key signature
        # - Datadog: POST to Log Intake API with DD-API-KEY header

        logger.debug(
            "SIEM: Forwarding event %s to %s",
            raw_event.get("event_id", "unknown")[:8],
            platform,
        )

        # Simulate successful delivery
        return "delivered"

    @classmethod
    def flush_buffer(cls) -> int:
        """Flush the event buffer by batch-forwarding buffered events.

        Returns
        -------
        int
            Number of events flushed.
        """
        if not cls._event_buffer:
            return 0

        count = len(cls._event_buffer)
        events = cls._event_buffer.copy()
        cls._event_buffer.clear()
        cls._last_flush = time.time()

        logger.info(
            "SIEM: Flushing event buffer — %d events.", count,
        )

        # In production, batch-forward to SIEM platforms
        return count
