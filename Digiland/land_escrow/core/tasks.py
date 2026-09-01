"""
Celery background tasks for the Digiland land_escrow platform.

Tasks are registered via ``land_escrow.celery.app`` and auto-discovered.
Each task is idempotent and safe to retry.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Promotion & Listing Maintenance ───────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def expire_promotions(self):
    """
    Find and deactivate LandPromotion records whose end_date has passed.
    Runs periodically (every 30 min in dev; via Beat in prod).
    """
    try:
        from core.models import LandPromotion

        today = timezone.now().date()
        expired = LandPromotion.objects.filter(
            is_active=True,
            end_date__isnull=False,
            end_date__lt=today,
        )
        count = expired.update(is_active=False)
        logger.info("expire_promotions: deactivated %d promotions", count)
        return count
    except Exception as exc:
        logger.exception("expire_promotions failed")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def deactivate_expired_ads(self):
    """
    Deactivate SponsoredAd campaigns whose end time has passed.
    """
    try:
        from core.models import SponsoredAd

        now = timezone.now()
        expired = SponsoredAd.objects.filter(
            status="Active",
            ends_at__lte=now,
        )
        count = expired.update(status="Ended")
        logger.info("deactivate_expired_ads: ended %d ads", count)
        return count
    except Exception as exc:
        logger.exception("deactivate_expired_ads failed")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def deactivate_budget_exhausted_ads(self):
    """
    Deactivate SponsoredAd campaigns whose budget is exhausted
    (budget_spent >= budget_total).
    """
    try:
        from django.db.models import F
        from core.models import SponsoredAd

        exhausted = SponsoredAd.objects.filter(
            status="Active",
            budget_total__isnull=False,
        ).exclude(
            budget_spent__lt=F("budget_total"),
        )
        count = exhausted.update(status="Ended")
        logger.info("deactivate_budget_exhausted_ads: ended %d ads", count)
        return count
    except Exception as exc:
        logger.exception("deactivate_budget_exhausted_ads failed")
        raise self.retry(exc=exc)


# ── Plan Lifecycle ────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def auto_renew_expiring_plans(self):
    """
    Auto-renew PromotionPlan records that are expiring soon and have
    auto_renew enabled. Delegates to the promotion service.
    """
    try:
        from core.services.promotion import PromotionTierService

        count = PromotionTierService.auto_renew_expiring_plans()
        logger.info("auto_renew_expiring_plans: renewed %d plans", count)
        return count
    except Exception as exc:
        logger.exception("auto_renew_expiring_plans failed")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def expire_expired_plans(self):
    """
    Mark PromotionPlan records whose end_date has passed as Expired.
    Delegates to the promotion service.
    """
    try:
        from core.services.promotion import PromotionTierService

        count = PromotionTierService.expire_expired_plans()
        logger.info("expire_expired_plans: expired %d plans", count)
        return count
    except Exception as exc:
        logger.exception("expire_expired_plans failed")
        raise self.retry(exc=exc)


# ── Buyer Profile Updates ─────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def update_buyer_profiles(self):
    """
    Recalculate BuyerInterestProfile for all active buyer users.
    Uses the recommendation service to refresh interest signals.
    """
    try:
        from core.models import User
        from core.services.recommendation import update_buyer_interest_profile

        buyers = User.objects.filter(role="Buyer", is_active=True)
        updated = 0
        errors = 0

        for buyer in buyers.iterator(chunk_size=200):
            try:
                update_buyer_interest_profile(buyer)
                updated += 1
            except Exception:
                errors += 1
                logger.warning(
                    "update_buyer_profiles: failed for user %s", buyer.email
                )

        logger.info(
            "update_buyer_profiles: updated=%d errors=%d", updated, errors
        )
        return {"updated": updated, "errors": errors}
    except Exception as exc:
        logger.exception("update_buyer_profiles failed")
        raise self.retry(exc=exc)


# ── Fraud Detection ───────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def calculate_fraud_scores(self):
    """
    Recalculate FraudScore for all users with active roles
    (Seller, Agent). High-risk users are flagged for manual review.
    """
    try:
        from core.models import User
        from core.services.fraud_detection import FraudDetectionService

        users = User.objects.filter(
            role__in=["Seller", "Agent"],
            is_active=True,
        )
        scored = 0
        flagged = 0

        for user in users.iterator(chunk_size=200):
            try:
                fraud_score = FraudDetectionService.calculate_user_fraud_score(user)
                scored += 1
                if fraud_score.score >= 70:
                    flagged += 1
            except Exception:
                logger.warning(
                    "calculate_fraud_scores: failed for user %s", user.email
                )

        logger.info(
            "calculate_fraud_scores: scored=%d flagged=%d", scored, flagged
        )
        return {"scored": scored, "flagged": flagged}
    except Exception as exc:
        logger.exception("calculate_fraud_scores failed")
        raise self.retry(exc=exc)


# ── Analytics ─────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def generate_daily_analytics(self):
    """
    Generate a daily analytics snapshot for the platform.

    Aggregates key metrics: transaction counts, revenue, user sign-ups,
    parcel listings, and ad performance. Stores the result in the
    PromotionAnalyticsLog for dashboard consumption.
    """
    try:
        from django.db.models import Count, Sum, Q
        from core.models import (
            Transaction,
            LandParcel,
            User,
            SponsoredAd,
            PopupAdCampaign,
            PromotionAnalyticsLog,
        )

        today = timezone.now().date()
        start_of_day = timezone.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_of_day = start_of_day + timedelta(days=1)

        # Transaction metrics
        transactions_today = Transaction.objects.filter(
            created_at__gte=start_of_day, created_at__lt=end_of_day
        )
        tx_count = transactions_today.count()
        tx_completed = transactions_today.filter(status="Completed").count()
        tx_revenue = transactions_today.filter(status="Completed").aggregate(
            total=Sum("agreed_price")
        )["total"] or 0

        # New user sign-ups
        new_users = User.objects.filter(
            date_joined__gte=start_of_day, date_joined__lt=end_of_day
        ).count()

        # New parcel listings
        new_parcels = LandParcel.objects.filter(
            created_at__gte=start_of_day, created_at__lt=end_of_day
        ).count()

        # Ad metrics
        active_sponsored = SponsoredAd.objects.filter(status="Active").count()
        active_popup = PopupAdCampaign.objects.filter(status="Active").count()

        metrics = {
            "date": today.isoformat(),
            "transactions_total": tx_count,
            "transactions_completed": tx_completed,
            "revenue_total": float(tx_revenue),
            "new_users": new_users,
            "new_parcels": new_parcels,
            "active_sponsored_ads": active_sponsored,
            "active_popup_campaigns": active_popup,
        }

        # Persist snapshot
        PromotionAnalyticsLog.objects.create(
            event_type="DailySnapshot",
            metadata=metrics,
        )

        logger.info("generate_daily_analytics: %s", metrics)
        return metrics
    except Exception as exc:
        logger.exception("generate_daily_analytics failed")
        raise self.retry(exc=exc)


# ── Popup Ad Billing ──────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def process_popup_ad_billing(self):
    """
    Process daily billing for active popup ad campaigns.

    For campaigns with daily budgets, check if the day's spend exceeds
    the daily limit and pause campaigns that have exhausted their
    daily or total budget.
    """
    try:
        from decimal import Decimal
        from django.db import transaction as db_transaction
        from core.models import PopupAdCampaign

        now = timezone.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

        active_campaigns = PopupAdCampaign.objects.filter(
            status="Active",
            payment_status="Paid",
        ).select_related("parcel", "created_by")

        paused_count = 0
        ended_count = 0

        for campaign in active_campaigns:
            try:
                with db_transaction.atomic():
                    # Re-fetch with lock
                    campaign = PopupAdCampaign.objects.select_for_update().get(
                        pk=campaign.pk
                    )

                    # Check total budget exhaustion
                    if campaign.total_budget and campaign.total_budget > 0:
                        if campaign.spent_amount >= campaign.total_budget:
                            campaign.status = "Completed"
                            campaign.save(update_fields=["status", "updated_at"])
                            ended_count += 1
                            continue

                    # Check daily budget
                    if campaign.daily_budget and campaign.daily_budget > 0:
                        today_spend = Decimal("0.00")
                        from core.models import PopupAdEvent

                        today_events = PopupAdEvent.objects.filter(
                            campaign=campaign,
                            event_type="Impression",
                            created_at__gte=start_of_day,
                        )
                        today_spend = today_events.aggregate(
                            total=Sum("charge_amount")
                        )["total"] or Decimal("0.00")

                        if today_spend >= campaign.daily_budget:
                            campaign.status = "Paused"
                            campaign.notes = (
                                f"Auto-paused: daily budget of {campaign.daily_budget} "
                                f"reached at {now.isoformat()}"
                            )
                            campaign.save(
                                update_fields=["status", "notes", "updated_at"]
                            )
                            paused_count += 1
                            continue

            except Exception:
                logger.warning(
                    "process_popup_ad_billing: failed for campaign %s",
                    campaign.id,
                )

        logger.info(
            "process_popup_ad_billing: paused=%d ended=%d",
            paused_count,
            ended_count,
        )
        return {"paused": paused_count, "ended": ended_count}
    except Exception as exc:
        logger.exception("process_popup_ad_billing failed")
        raise self.retry(exc=exc)


# ── Notification & Communication Tasks ───────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_notification_task(
    self,
    user_id: str,
    notification_type: str,
    subject: str,
    html_body: str,
    text_body: str = '',
    action_url: str = '',
    idempotency_key: str = None,
    metadata: dict = None,
):
    """
    Celery background task to send an email notification via NotificationService.
    Safely retries up to 3 times on transient delivery failures.
    """
    try:
        from core.models import User
        from core.services.notifications import NotificationService

        user = User.objects.get(id=user_id)
        notification = NotificationService.send_email(
            user=user,
            notification_type=notification_type,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            action_url=action_url,
            idempotency_key=idempotency_key,
            metadata=metadata or {},
        )
        if notification.status == 'FAILED':
            logger.warning(
                "send_notification_task: notification %s status is FAILED, retrying...",
                notification.id,
            )
            raise RuntimeError(f"Email send failed: {notification.last_error}")
        return str(notification.id)
    except Exception as exc:
        logger.exception("send_notification_task failed for user %s", user_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def process_resend_webhook_task(self, event_type: str, event_data: dict):
    """
    Process incoming Resend webhook events asynchronously.
    Updates Notification records based on delivery, bounce, or complaint events.
    """
    try:
        from core.services.notifications import NotificationService

        email_id = event_data.get("email_id") or event_data.get("id")
        if not email_id:
            logger.warning("process_resend_webhook_task: missing email_id in event_data")
            return None

        status_map = {
            "email.sent": "SENT",
            "email.delivered": "DELIVERED",
            "email.bounced": "BOUNCED",
            "email.complained": "BOUNCED",
            "email.delivery_delayed": "SENDING",
        }
        mapped_status = status_map.get(event_type)
        if mapped_status:
            NotificationService.update_from_webhook(
                provider_message_id=email_id,
                status=mapped_status,
                metadata={"webhook_event": event_type, "webhook_payload": event_data},
            )
            logger.info("Resend webhook processed: %s -> %s for email %s", event_type, mapped_status, email_id)
        return True
    except Exception as exc:
        logger.exception("process_resend_webhook_task failed")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def send_offline_message_email_task(self, message_id: str):
    """
    Check if a message remains unread after a delay (e.g. 5 minutes).
    If the recipient has not read it, send an email notification alerting them.
    """
    try:
        from django.template.loader import render_to_string
        from core.models import Message
        from core.services.notifications import NotificationService

        message = Message.objects.select_related('sender', 'receiver', 'conversation').filter(id=message_id).first()
        if not message or not message.receiver:
            return None

        # If already read or deleted, do not email
        if message.is_read or message.read_at or message.deleted_at:
            return None

        recipient = message.receiver
        sender_name = message.sender.get_full_name() or message.sender.email
        preview = message.content[:150] + ('...' if len(message.content) > 150 else '')
        message_url = f"https://digiland.co.ke/messages/thread/{message.sender.id}/"

        html_body = render_to_string("emails/new_message.html", {
            "recipient_email": recipient.email,
            "sender_name": sender_name,
            "message_preview": preview,
            "message_url": message_url,
            "year": timezone.now().year,
        })

        NotificationService.send_email(
            user=recipient,
            notification_type="OFFLINE_MESSAGE_ALERT",
            subject=f"New message from {sender_name} on Digiland",
            html_body=html_body,
            text_body=f"You have a new message from {sender_name} on Digiland:\n\n\"{preview}\"\n\nView it at: {message_url}",
            action_url=message_url,
            idempotency_key=f"offline_msg_{message.id}_{recipient.id}",
            metadata={"message_id": str(message.id), "sender_id": str(message.sender.id)},
        )
        return True
    except Exception as exc:
        logger.exception("send_offline_message_email_task failed for message %s", message_id)
        raise self.retry(exc=exc)

