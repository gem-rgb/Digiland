"""Django signals for the Enterprise Admin Control Plane.

Signals handle cross-cutting concerns that must fire automatically when
certain model-level events occur, regardless of which code path triggered
them.

Signals
-------
auto_terminate_admin_sessions_on_suspend
    When a User is deactivated (``is_active=False``), all their active
    ``AdminSession`` records are terminated.

auto_create_audit_log_for_admin_changes
    When an admin-controlled model (``EmergencyControl``,
    ``DualApprovalRequest``, etc.) is saved, an ``AdminActionLog``
    entry is created to capture the change.

alert_on_suspicious_admin_behavior
    Monitors rapid successive admin actions and multiple failed MFA
    attempts, logging warnings and optionally locking the account.

auto_expire_dual_approval_requests
    Periodic signal (triggered via ``m2m_changed`` or model save)
    that marks past-deadline pending ``DualApprovalRequest`` records
    as ``EXPIRED``.
"""

import logging
from datetime import timedelta

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver, Signal
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom signals
# ---------------------------------------------------------------------------

# Fired when suspicious admin behaviour is detected (for external handlers)
suspicious_admin_activity = Signal()


# ---------------------------------------------------------------------------
# 1. Auto-terminate admin sessions when user is suspended
# ---------------------------------------------------------------------------

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def auto_terminate_admin_sessions_on_suspend(sender, instance, **kwargs):
    """Terminate all active admin sessions when a user is deactivated.

    This signal fires on every User save.  It checks the ``is_active``
    flag and, if the user has just been deactivated, terminates all
    their active ``AdminSession`` records and logs the event.

    Parameters
    ----------
    sender : Model class
        The User model.
    instance : User
        The user instance that was just saved.
    """
    if instance.is_active:
        return  # User is active; nothing to do.

    from .models import AdminSession, AdminActionLog

    active_sessions = AdminSession.objects.filter(
        user=instance,
        is_active=True,
    )

    if not active_sessions.exists():
        return  # No sessions to terminate.

    count = active_sessions.update(
        is_active=False,
        terminated_at=timezone.now(),
    )

    # Create an audit log entry
    AdminActionLog.objects.create(
        actor=None,  # System-initiated
        action_type='ADMIN_SESSIONS_AUTO_TERMINATED',
        resource_type='User',
        resource_id=str(instance.id),
        metadata={
            'reason': 'User account deactivated',
            'sessions_terminated': count,
            'user_email': instance.email,
        },
    )

    logger.info(
        'Auto-terminated %d admin session(s) for deactivated user %s.',
        count,
        instance.email,
    )


# ---------------------------------------------------------------------------
# 2. Auto-create audit log entries for admin model changes
# ---------------------------------------------------------------------------

# Track which models should be auto-audited
_AUDITED_MODELS = set()


def register_audited_model(model_class):
    """Register a model for automatic audit logging on save.

    Usage::

        register_audited_model(EmergencyControl)
        register_audited_model(DualApprovalRequest)
    """
    _AUDITED_MODELS.add(model_class)


@receiver(pre_save)
def auto_create_audit_log_for_admin_changes(sender, instance, **kwargs):
    """Create an audit log entry when an audited admin model is saved.

    Only models registered via ``register_audited_model()`` are tracked.
    The audit entry is created in ``post_save`` (see below) to ensure
    the instance has been fully saved first.  This ``pre_save`` handler
    stashes the change context on the instance.
    """
    if sender not in _AUDITED_MODELS:
        return

    # Mark that this save should be audited
    instance._audit_this_save = True

    # Detect if this is a create or update
    if instance.pk:
        try:
            instance._audit_is_create = not sender.objects.filter(
                pk=instance.pk
            ).exists()
        except Exception:
            instance._audit_is_create = True
    else:
        instance._audit_is_create = True


@receiver(post_save)
def _write_audit_for_admin_model_change(sender, instance, created, **kwargs):
    """Write the audit log entry after the audited model is saved.

    This is the companion to ``auto_create_audit_log_for_admin_changes``
    that runs in ``pre_save``.
    """
    if sender not in _AUDITED_MODELS:
        return

    if not getattr(instance, '_audit_this_save', False):
        return

    from .models import AdminActionLog

    action_prefix = 'CREATED' if created else 'UPDATED'
    action = f'{sender.__name__.upper()}_{action_prefix}'

    AdminActionLog.objects.create(
        actor=getattr(instance, 'updated_by', None)
        or getattr(instance, 'requested_by', None)
        or getattr(instance, 'activated_by', None),
        action_type=action,
        resource_type=sender.__name__,
        resource_id=str(instance.pk),
        metadata={
            'model': sender.__name__,
            'is_create': created,
        },
    )

    # Clean up the flag
    instance._audit_this_save = False


# Register the models that should be auto-audited
def _register_default_audited_models():
    """Register built-in admin control plane models for auto-auditing."""
    try:
        from .models import EmergencyControl, DualApprovalRequest
        register_audited_model(EmergencyControl)
        register_audited_model(DualApprovalRequest)
    except ImportError:
        pass  # Models may not be available during initial migrations


_register_default_audited_models()


# ---------------------------------------------------------------------------
# 3. Alert on suspicious admin behavior
# ---------------------------------------------------------------------------

# Configurable thresholds
_SUSPICIOUS_ACTION_WINDOW = timedelta(minutes=5)
_SUSPICIOUS_ACTION_THRESHOLD = getattr(
    settings, 'SUSPICIOUS_ACTION_THRESHOLD', 20
)  # actions within window
_SUSPICIOUS_MFA_FAIL_THRESHOLD = getattr(
    settings, 'SUSPICIOUS_MFA_FAIL_THRESHOLD', 5
)  # failed MFA attempts within window


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def alert_on_suspicious_admin_behavior(sender, instance, **kwargs):
    """Monitor admin user accounts for suspicious activity patterns.

    This signal checks for two patterns after every User save:

    1. **Rapid successive admin actions**: More than
       ``SUSPICIOUS_ACTION_THRESHOLD`` actions within
       ``_SUSPICIOUS_ACTION_WINDOW``.

    2. **Multiple failed MFA attempts**: More than
       ``SUSPICIOUS_MFA_FAIL_THRESHOLD`` failed MFA verifications
       within the same window.

    When suspicious behaviour is detected, the signal:

    - Logs a critical warning.
    - Fires the ``suspicious_admin_activity`` custom signal (for
      external handlers like email alerts or account locking).
    - Creates an ``AdminActionLog`` entry with action
      ``SUSPICIOUS_ACTIVITY_DETECTED``.
    """
    if instance.role != 'Admin':
        return

    from .models import AdminActionLog

    now = timezone.now()
    window_start = now - _SUSPICIOUS_ACTION_WINDOW

    # Check for rapid actions
    recent_actions = AdminActionLog.objects.filter(
        actor=instance,
        timestamp__gte=window_start,
    ).count()

    if recent_actions >= _SUSPICIOUS_ACTION_THRESHOLD:
        logger.critical(
            'SUSPICIOUS: Admin %s performed %d actions in %d minutes.',
            instance.email,
            recent_actions,
            _SUSPICIOUS_ACTION_WINDOW.seconds // 60,
        )

        AdminActionLog.objects.create(
            actor=instance,
            action_type='SUSPICIOUS_ACTIVITY_DETECTED',
            resource_type='User',
            resource_id=str(instance.id),
            metadata={
                'reason': 'Rapid successive admin actions',
                'action_count': recent_actions,
                'window_minutes': _SUSPICIOUS_ACTION_WINDOW.seconds // 60,
            },
        )

        # Fire custom signal for external handlers
        suspicious_admin_activity.send(
            sender=instance.__class__,
            instance=instance,
            reason='rapid_actions',
            action_count=recent_actions,
        )

    # Check for multiple failed MFA attempts
    recent_mfa_fails = AdminActionLog.objects.filter(
        actor=instance,
        action_type='MFA_STEP_UP_FAILED',
        timestamp__gte=window_start,
    ).count()

    if recent_mfa_fails >= _SUSPICIOUS_MFA_FAIL_THRESHOLD:
        logger.critical(
            'SUSPICIOUS: Admin %s had %d failed MFA attempts in %d minutes.',
            instance.email,
            recent_mfa_fails,
            _SUSPICIOUS_ACTION_WINDOW.seconds // 60,
        )

        AdminActionLog.objects.create(
            actor=instance,
            action_type='SUSPICIOUS_ACTIVITY_DETECTED',
            resource_type='User',
            resource_id=str(instance.id),
            metadata={
                'reason': 'Multiple failed MFA attempts',
                'fail_count': recent_mfa_fails,
                'window_minutes': _SUSPICIOUS_ACTION_WINDOW.seconds // 60,
            },
        )

        suspicious_admin_activity.send(
            sender=instance.__class__,
            instance=instance,
            reason='mfa_failures',
            fail_count=recent_mfa_fails,
        )


# ---------------------------------------------------------------------------
# 4. Auto-expire dual approval requests past deadline
# ---------------------------------------------------------------------------

@receiver(post_save, sender='admin_control_plane.DualApprovalRequest')
def auto_expire_dual_approval_requests(sender, instance, **kwargs):
    """Mark past-deadline pending dual-approval requests as EXPIRED.

    While the primary expiry mechanism is the
    ``DualApprovalService.expire_stale_requests()`` method (called by
    a periodic Celery task), this signal provides a belt-and-suspenders
    check on every ``DualApprovalRequest`` save.

    If the saved instance is still PENDING and past its deadline, it is
    immediately transitioned to EXPIRED.
    """
    if instance.status != 'PENDING':
        return

    if instance.deadline and instance.deadline < timezone.now():
        # Use update to avoid recursive signal firing
        sender.objects.filter(pk=instance.pk).update(status='EXPIRED')
        logger.info(
            'Auto-expired dual approval request %s (deadline: %s).',
            instance.pk,
            instance.deadline.isoformat(),
        )
