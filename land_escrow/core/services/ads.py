"""Sponsored ads service for ad campaign management"""

from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, Q
from datetime import timedelta
from core.models import SponsoredAd, AdEngagement, AdBillingEvent, User, LandParcel


class SponsoredAdService:
    """Manages sponsored ad campaigns and billing"""

    # Billing rates
    CPM_RATE = Decimal('100')  # KES 100 per 1000 impressions
    CPC_RATE = Decimal('250')   # KES 250 per click
    CPA_RATE = Decimal('500')   # KES 500 per conversion/inquiry

    @staticmethod
    def create_ad_campaign(seller, parcel, tier='Basic', billing_model='PayPerDay',
                          budget_daily=None, budget_total=None, targeting_criteria=None):
        """Create a new sponsored ad campaign"""

        ad = SponsoredAd.objects.create(
            seller=seller,
            parcel=parcel,
            tier=tier,
            status='Draft',
            billing_model=billing_model,
            budget_daily=budget_daily,
            budget_total=budget_total,
            targeting_criteria=targeting_criteria or {},
        )

        return ad

    @staticmethod
    def activate_ad_campaign(ad, start_date=None, end_date=None):
        """Activate an ad campaign (move from draft to active)"""
        ad.status = 'Active'
        ad.starts_at = start_date or timezone.now()
        if end_date:
            ad.ends_at = end_date
        else:
            # Default 30-day campaign
            ad.ends_at = (start_date or timezone.now()) + timedelta(days=30)
        ad.save()
        return ad

    @staticmethod
    def pause_ad_campaign(ad):
        """Pause an active campaign"""
        ad.status = 'Paused'
        ad.save()
        return ad

    @staticmethod
    def end_ad_campaign(ad):
        """End an ad campaign"""
        ad.status = 'Ended'
        ad.save()
        return ad

    @staticmethod
    def get_featured_ads_for_feed(limit=10):
        """Get top active ads for displaying in feed"""
        now = timezone.now()
        featured = SponsoredAd.objects.filter(
            status='Active',
            starts_at__lte=now,
            ends_at__gte=now,
            tier__in=['Pro', 'Elite']
        ).order_by('-created_at')[:limit]

        return featured

    @staticmethod
    def get_targeted_ads_for_user(user, limit=5):
        """Get ads targeted for a specific user based on profile"""
        from core.models import BuyerInterestProfile

        try:
            profile = BuyerInterestProfile.objects.get(user=user)
        except BuyerInterestProfile.DoesNotExist:
            return []

        now = timezone.now()

        # Find ads matching user's interests
        matching_ads = SponsoredAd.objects.filter(
            status='Active',
            starts_at__lte=now,
            ends_at__gte=now,
        ).filter(
            Q(parcel__county__in=profile.preferred_counties) |
            Q(parcel__land_use_type=profile.preferred_land_use)
        )

        return matching_ads[:limit]

    @staticmethod
    def log_ad_engagement(ad, user, event_type, source_page='unknown'):
        """Log an engagement event for an ad"""
        engagement = AdEngagement.objects.create(
            ad=ad,
            user=user,
            event_type=event_type,
            source_page=source_page,
        )

        # Calculate and record billing event if needed
        if ad.billing_model == 'PayPerImpression':
            if event_type == 'Impression':
                SponsoredAdService._record_billing_event(ad, event_type, SponsoredAdService.CPM_RATE / Decimal('1000'))

        elif ad.billing_model == 'PayPerClick':
            if event_type == 'Click':
                SponsoredAdService._record_billing_event(ad, event_type, SponsoredAdService.CPC_RATE)

        elif ad.billing_model == 'PayPerDay':
            # Daily billing handled separately, not per-event
            pass

        return engagement

    @staticmethod
    def _record_billing_event(ad, event_type, amount):
        """Record a billable event"""
        billing_event = AdBillingEvent.objects.create(
            ad=ad,
            event_type=event_type,
            amount_charged=amount,
            billing_status='Pending',
        )

        # Update ad's total spent
        ad.budget_spent += amount
        ad.save()

        return billing_event

    @staticmethod
    def calculate_ad_placement_score(ad):
        """
        Calculate placement score for an ad.
        Higher score = better placement/visibility.
        """
        score = 0

        # Tier boost
        tier_boosts = {'Basic': 0, 'Pro': 10, 'Elite': 20}
        score += tier_boosts.get(ad.tier, 0)

        # Recent engagement boost
        engagements = AdEngagement.objects.filter(
            ad=ad,
            timestamp__gte=timezone.now() - timedelta(days=7)
        ).count()

        if engagements > 100:
            score += 20
        elif engagements > 50:
            score += 15
        elif engagements > 10:
            score += 10

        # CTR boost
        impressions = AdEngagement.objects.filter(
            ad=ad,
            event_type='Impression'
        ).count()

        clicks = AdEngagement.objects.filter(
            ad=ad,
            event_type='Click'
        ).count()

        if impressions > 0:
            ctr = clicks / impressions
            if ctr > 0.1:
                score += 10
            elif ctr > 0.05:
                score += 5

        # Budget remaining (penalize low budget)
        if ad.budget_total and ad.budget_spent < ad.budget_total:
            remaining_percent = (ad.budget_total - ad.budget_spent) / ad.budget_total
            if remaining_percent < 0.2:
                score -= 10

        return max(0, score)  # Don't go below 0

    @staticmethod
    def deactivate_expired_ads():
        """Find and deactivate expired ad campaigns"""
        now = timezone.now()
        expired_ads = SponsoredAd.objects.filter(
            status='Active',
            ends_at__lte=now
        )

        count = 0
        for ad in expired_ads:
            ad.status = 'Ended'
            ad.save()
            count += 1

        return count

    @staticmethod
    def deactivate_budget_exhausted_ads():
        """Deactivate ads that have reached their budget limit"""
        over_budget_ads = SponsoredAd.objects.filter(
            status='Active',
            budget_total__isnull=False,
        ).exclude(
            budget_spent__lt=models.F('budget_total')
        )

        count = 0
        for ad in over_budget_ads:
            ad.status = 'Ended'
            ad.save()
            count += 1

        return count

    @staticmethod
    def get_seller_active_campaigns(seller):
        """Get all active campaigns for a seller"""
        return SponsoredAd.objects.filter(
            seller=seller,
            status='Active'
        ).order_by('-created_at')

    @staticmethod
    def get_campaign_performance(ad):
        """Get performance metrics for a campaign"""
        impressions = AdEngagement.objects.filter(
            ad=ad,
            event_type='Impression'
        ).count()

        clicks = AdEngagement.objects.filter(
            ad=ad,
            event_type='Click'
        ).count()

        inquiries = AdEngagement.objects.filter(
            ad=ad,
            event_type='Inquiry'
        ).count()

        ctr = (clicks / impressions * 100) if impressions > 0 else 0
        conversion_rate = (inquiries / clicks * 100) if clicks > 0 else 0

        return {
            'ad_id': str(ad.id),
            'parcel_number': ad.parcel.parcel_number,
            'status': ad.status,
            'impressions': impressions,
            'clicks': clicks,
            'inquiries': inquiries,
            'ctr_percent': round(ctr, 2),
            'conversion_rate_percent': round(conversion_rate, 2),
            'spent': str(ad.budget_spent),
            'budget_remaining': str((ad.budget_total or Decimal('0')) - ad.budget_spent) if ad.budget_total else 'Unlimited',
        }

    @staticmethod
    def get_top_performing_ads(limit=10, days=30):
        """Get top-performing ads by engagement"""
        start_date = timezone.now() - timedelta(days=days)

        top_ads = SponsoredAd.objects.filter(
            created_at__gte=start_date
        ).annotate(
            total_engagements=Count('engagements')
        ).order_by('-total_engagements')[:limit]

        return top_ads
