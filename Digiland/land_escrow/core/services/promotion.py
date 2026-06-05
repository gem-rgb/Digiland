"""Promotion tier management service"""

from decimal import Decimal
from django.utils import timezone
from core.models import PromotionTier, PromotionPlan, User, LandParcel


class PromotionTierService:
    """Manages promotion tiers and seller plans"""

    TIER_FEATURES = {
        'Basic': {
            'name': 'Basic - Free',
            'price': Decimal('0'),
            'included_ads': 0,
            'visibility_boost': Decimal('1.0'),
            'featured_badge': False,
            'search_priority': 0,
            'appears_in_feed': False,
            'appears_in_trending': False,
            'push_notifications': 0,
            'email_campaigns': False,
            'analytics_level': 'basic',
            'support': 'community',
        },
        'Pro': {
            'name': 'Pro - $100/month',
            'price': Decimal('100'),
            'included_ads': 1,
            'visibility_boost': Decimal('1.5'),
            'featured_badge': True,
            'search_priority': 3,
            'appears_in_feed': True,
            'appears_in_trending': False,
            'push_notifications': 0,
            'email_campaigns': False,
            'analytics_level': 'advanced',
            'support': 'email',
        },
        'Elite': {
            'name': 'Elite - $500/month',
            'price': Decimal('500'),
            'included_ads': 5,
            'visibility_boost': Decimal('2.5'),
            'featured_badge': True,
            'search_priority': 1,
            'appears_in_feed': True,
            'appears_in_trending': True,
            'push_notifications': 5,
            'email_campaigns': True,
            'analytics_level': 'premium',
            'support': 'dedicated',
        },
    }

    @staticmethod
    def _normalize_tier_slug(tier_slug):
        return (tier_slug or 'Basic').strip().title()

    @staticmethod
    def _tier_defaults(tier_slug):
        normalized = PromotionTierService._normalize_tier_slug(tier_slug)
        features = PromotionTierService.TIER_FEATURES.get(normalized, PromotionTierService.TIER_FEATURES['Basic'])
        tier_level = {'Basic': 0, 'Pro': 1, 'Elite': 2}.get(normalized, 0)
        return {
            'name': normalized,
            'slug': normalized,
            'tier_level': tier_level,
            'monthly_price': features.get('price', Decimal('0')),
            'features_json': features,
            'active': True,
        }

    @staticmethod
    def get_or_create_tier(tier_slug):
        normalized = PromotionTierService._normalize_tier_slug(tier_slug)
        tier, _ = PromotionTier.objects.get_or_create(
            slug=normalized,
            defaults=PromotionTierService._tier_defaults(normalized),
        )
        return tier

    @staticmethod
    def ensure_default_tiers():
        for tier_slug in ('Basic', 'Pro', 'Elite'):
            PromotionTierService.get_or_create_tier(tier_slug)
        return PromotionTier.objects.filter(active=True).order_by('tier_level')

    @staticmethod
    def get_available_tiers():
        """Get all active promotion tiers"""
        PromotionTierService.ensure_default_tiers()
        return PromotionTier.objects.filter(active=True).order_by('tier_level')

    @staticmethod
    def get_seller_current_plan(seller):
        """Get seller's current active promotion plan"""
        try:
            plan = PromotionPlan.objects.get(seller=seller)
            if plan.is_active:
                return plan
        except PromotionPlan.DoesNotExist:
            pass
        return None

    @staticmethod
    def get_seller_tier_level(seller):
        """Get seller's current tier level (basic, pro, elite)"""
        plan = PromotionTierService.get_seller_current_plan(seller)
        if plan:
            return plan.tier.slug
        return 'Basic'

    @staticmethod
    def upgrade_to_tier(seller, tier_slug):
        """
        Upgrade seller to a new tier.
        If they already have a plan, update it.
        """
        tier = PromotionTierService.get_or_create_tier(tier_slug)

        plan, created = PromotionPlan.objects.update_or_create(
            seller=seller,
            defaults={
                'tier': tier,
                'status': 'Active',
                'auto_renew': True,
                'end_date': None,  # Reset end date on upgrade
            }
        )

        return plan

    @staticmethod
    def downgrade_to_basic(seller):
        """Downgrade seller back to Basic (free) tier"""
        basic_tier = PromotionTierService.get_or_create_tier('Basic')
        plan, created = PromotionPlan.objects.update_or_create(
            seller=seller,
            defaults={
                'tier': basic_tier,
                'status': 'Active',
                'auto_renew': False,
            }
        )
        return plan

    @staticmethod
    def calculate_listing_visibility_boost(parcel):
        """
        Calculate visibility multiplier for a parcel based on seller's tier.
        Used to boost ranking/impressions.
        """
        seller = parcel.listed_by
        plan = PromotionTierService.get_seller_current_plan(seller)

        if not plan or not plan.is_active:
            return Decimal('1.0')  # No boost

        tier_features = PromotionTierService.TIER_FEATURES.get(plan.tier.slug, {})
        return tier_features.get('visibility_boost', Decimal('1.0'))

    @staticmethod
    def get_search_rank_boost(parcel):
        """
        Get search ranking boost for a parcel based on tier.
        Lower number = higher rank (1 = top, higher = lower rank)
        """
        seller = parcel.listed_by
        plan = PromotionTierService.get_seller_current_plan(seller)

        if not plan or not plan.is_active:
            return 999  # Last

        tier_features = PromotionTierService.TIER_FEATURES.get(plan.tier.slug, {})
        return tier_features.get('search_priority', 999)

    @staticmethod
    def should_appear_in_recommendations_feed(parcel):
        """Determine if parcel should appear in buyer recommendations"""
        seller = parcel.listed_by
        plan = PromotionTierService.get_seller_current_plan(seller)

        if not plan or not plan.is_active:
            return False

        tier_features = PromotionTierService.TIER_FEATURES.get(plan.tier.slug, {})
        return tier_features.get('appears_in_feed', False)

    @staticmethod
    def should_appear_in_trending(parcel):
        """Determine if parcel should appear in trending section"""
        seller = parcel.listed_by
        plan = PromotionTierService.get_seller_current_plan(seller)

        if not plan or not plan.is_active:
            return False

        tier_features = PromotionTierService.TIER_FEATURES.get(plan.tier.slug, {})
        return tier_features.get('appears_in_trending', False)

    @staticmethod
    def get_tier_features(tier_slug):
        """Get features for a specific tier"""
        return PromotionTierService.TIER_FEATURES.get(tier_slug, {})

    @staticmethod
    def get_seller_tier_features(seller):
        """Get features for seller's current tier"""
        tier_slug = PromotionTierService.get_seller_tier_level(seller)
        return PromotionTierService.get_tier_features(tier_slug)

    @staticmethod
    def cancel_plan(seller):
        """Cancel seller's promotion plan"""
        try:
            plan = PromotionPlan.objects.get(seller=seller)
            plan.status = 'Cancelled'
            plan.auto_renew = False
            plan.save()
            return plan
        except PromotionPlan.DoesNotExist:
            return None

    @staticmethod
    def expire_expired_plans():
        """
        Find and mark expired plans.
        Should be run periodically as a background task.
        """
        now = timezone.now()
        expired_plans = PromotionPlan.objects.filter(
            status='Active',
            end_date__lte=now
        )

        count = 0
        for plan in expired_plans:
            plan.status = 'Expired'
            plan.save()
            count += 1

        return count

    @staticmethod
    def auto_renew_expiring_plans():
        """
        Auto-renew plans that are expiring and have auto_renew enabled.
        Should be run periodically as a background task.
        """
        from datetime import timedelta

        now = timezone.now()
        renewal_window = timedelta(days=7)

        expiring_plans = PromotionPlan.objects.filter(
            status='Active',
            auto_renew=True,
            end_date__lte=now + renewal_window,
            end_date__gt=now,
        )

        count = 0
        for plan in expiring_plans:
            # TODO: Integrate with payment system to charge for renewal
            # For now, just extend the end date
            plan.end_date = now + timedelta(days=30)
            plan.save()
            count += 1

        return count
