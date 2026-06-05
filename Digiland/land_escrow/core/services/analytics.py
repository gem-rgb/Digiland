"""Analytics service for engagement tracking"""

from decimal import Decimal
from django.utils import timezone
from django.db.models import Count, Sum, Q
from datetime import timedelta
from core.models import (
    AnalyticsEvent, AdEngagement, RecommendationLog,
    LandParcel, User, Transaction
)


class AnalyticsService:
    """Tracks and aggregates engagement analytics"""

    @staticmethod
    def track_parcel_view(parcel, user=None):
        """Log when a parcel is viewed"""
        AnalyticsEvent.objects.create(
            parcel=parcel,
            user=user,
            event_type='View',
            metadata={'ip': None},
        )

    @staticmethod
    def track_parcel_click(parcel, user=None, source='search'):
        """Log when a parcel is clicked"""
        AnalyticsEvent.objects.create(
            parcel=parcel,
            user=user,
            event_type='Click',
            metadata={'source': source},
        )

    @staticmethod
    def track_parcel_save(parcel, user):
        """Log when a parcel is favorited"""
        AnalyticsEvent.objects.create(
            parcel=parcel,
            user=user,
            event_type='Save',
        )

    @staticmethod
    def track_parcel_inquiry(parcel, user):
        """Log when buyer inquires about a parcel"""
        AnalyticsEvent.objects.create(
            parcel=parcel,
            user=user,
            event_type='Inquiry',
        )

    @staticmethod
    def get_parcel_analytics(parcel, days=30):
        """Get comprehensive analytics for a parcel"""
        start_date = timezone.now() - timedelta(days=days)

        events = AnalyticsEvent.objects.filter(
            parcel=parcel,
            timestamp__gte=start_date
        )

        views = events.filter(event_type='View').count()
        clicks = events.filter(event_type='Click').count()
        saves = events.filter(event_type='Save').count()
        inquiries = events.filter(event_type='Inquiry').count()

        ctr = (clicks / views * 100) if views > 0 else 0
        save_rate = (saves / views * 100) if views > 0 else 0
        inquiry_conversion = (inquiries / clicks * 100) if clicks > 0 else 0

        return {
            'parcel_id': str(parcel.id),
            'parcel_number': parcel.parcel_number,
            'views': views,
            'clicks': clicks,
            'saves': saves,
            'inquiries': inquiries,
            'ctr_percent': round(ctr, 2),
            'save_rate_percent': round(save_rate, 2),
            'inquiry_conversion_percent': round(inquiry_conversion, 2),
            'unique_users': events.values('user').distinct().count(),
        }

    @staticmethod
    def get_seller_ad_performance(seller, days=30):
        """Get ad performance analytics for a seller"""
        start_date = timezone.now() - timedelta(days=days)

        # Get all ads for this seller
        from core.models import SponsoredAd
        ads = SponsoredAd.objects.filter(seller=seller)

        ad_stats = []
        total_spent = Decimal('0')

        for ad in ads:
            engagement = AdEngagement.objects.filter(
                ad=ad,
                timestamp__gte=start_date
            )

            impressions = engagement.filter(event_type='Impression').count()
            clicks = engagement.filter(event_type='Click').count()
            inquiries = engagement.filter(event_type='Inquiry').count()

            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            conversion_rate = (inquiries / clicks * 100) if clicks > 0 else 0

            spent = ad.budget_spent
            total_spent += spent

            ad_stats.append({
                'ad_id': str(ad.id),
                'parcel_number': ad.parcel.parcel_number,
                'status': ad.status,
                'impressions': impressions,
                'clicks': clicks,
                'inquiries': inquiries,
                'ctr_percent': round(ctr, 2),
                'conversion_rate_percent': round(conversion_rate, 2),
                'spent': str(spent),
                'budget_remaining': str((ad.budget_total or Decimal('0')) - spent) if ad.budget_total else 'Unlimited',
            })

        return {
            'seller_id': str(seller.id),
            'seller_email': seller.email,
            'total_ads': ads.count(),
            'total_spent': str(total_spent),
            'ads': ad_stats,
        }

    @staticmethod
    def get_trending_locations(days=7, limit=20):
        """Get trending locations by engagement"""
        start_date = timezone.now() - timedelta(days=days)

        trending = AnalyticsEvent.objects.filter(
            timestamp__gte=start_date,
            parcel__county__isnull=False
        ).values('parcel__county').annotate(
            total_events=Count('id'),
            views=Count('id', filter=Q(event_type='View')),
            inquiries=Count('id', filter=Q(event_type='Inquiry')),
        ).order_by('-total_events')[:limit]

        return [{
            'county': item['parcel__county'],
            'total_events': item['total_events'],
            'views': item['views'],
            'inquiries': item['inquiries'],
        } for item in trending]

    @staticmethod
    def get_buyer_segment_analytics(days=30):
        """Get analytics by buyer segment/category"""
        start_date = timezone.now() - timedelta(days=days)

        from core.models import BuyerInterestProfile

        segments = {}

        profiles = BuyerInterestProfile.objects.all()
        for profile in profiles:
            events = AnalyticsEvent.objects.filter(
                user=profile.user,
                timestamp__gte=start_date
            )

            if events.exists():
                segments[profile.category] = {
                    'total_events': events.count(),
                    'views': events.filter(event_type='View').count(),
                    'inquiries': events.filter(event_type='Inquiry').count(),
                    'users': 1,
                }

        return segments

    @staticmethod
    def get_platform_revenue_analytics(days=365):
        """Get platform revenue analytics"""
        from core.services.service_fee import ServiceFeeService

        revenue = ServiceFeeService.get_platform_revenue(days=days)
        monthly = ServiceFeeService.get_monthly_revenue_breakdown(months=12)

        return {
            'period_days': days,
            'total_revenue': str(revenue['total']),
            'platform_fees': str(revenue['platform_fees']),
            'escrow_fees': str(revenue['escrow_fees']),
            'processing_fees': str(revenue['processing_fees']),
            'by_month': monthly,
        }

    @staticmethod
    def get_recommendation_performance(days=30, limit=10):
        """Get performance of recommendations"""
        start_date = timezone.now() - timedelta(days=days)

        recs = RecommendationLog.objects.filter(
            timestamp__gte=start_date
        ).values('algorithm_type').annotate(
            total_recommendations=Count('id'),
            clicks=Count('id', filter=Q(clicked=True)),
            saves=Count('id', filter=Q(saved=True)),
            inquiries=Count('id', filter=Q(inquired=True)),
        )

        results = []
        for rec in recs:
            total = rec['total_recommendations']
            click_rate = (rec['clicks'] / total * 100) if total > 0 else 0
            save_rate = (rec['saves'] / total * 100) if total > 0 else 0

            results.append({
                'algorithm': rec['algorithm_type'],
                'total': total,
                'clicks': rec['clicks'],
                'saves': rec['saves'],
                'inquiries': rec['inquiries'],
                'click_rate_percent': round(click_rate, 2),
                'save_rate_percent': round(save_rate, 2),
            })

        return sorted(results, key=lambda x: x['click_rate_percent'], reverse=True)[:limit]
