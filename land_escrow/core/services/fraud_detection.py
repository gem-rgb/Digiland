"""Fraud detection and risk scoring service"""

from decimal import Decimal
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta
from core.models import (
    FraudScore, LandParcel, Transaction, Document, User
)


class FraudDetectionService:
    """Detects fraudulent behavior and calculates risk scores"""

    FRAUD_FACTORS = {
        'unverified_user': 8,
        'high_volume_new_seller': 15,
        'price_drop_suspicious': 10,
        'duplicate_listing': 25,
        'no_verified_documents': 12,
        'rapid_transaction_sequence': 20,
        'high_chargeback_rate': 30,
        'geolocation_mismatch': 15,
        'multiple_flags_from_users': 10,
    }

    @staticmethod
    def calculate_user_fraud_score(user):
        """
        Calculate comprehensive fraud risk score for a user.
        Returns score 0-100 and list of risk factors.
        """
        score = 0
        factors = []

        # Factor 1: KYC Verification
        if not user.is_identity_verified:
            score += FraudDetectionService.FRAUD_FACTORS['unverified_user']
            factors.append('Not KYC verified')

        # Factor 2: Recent listing volume (for sellers)
        if user.role in ['Seller', 'Agent']:
            recent_listings = LandParcel.objects.filter(
                listed_by=user,
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count()

            if recent_listings > 5:
                score += FraudDetectionService.FRAUD_FACTORS['high_volume_new_seller']
                factors.append(f'High volume recent listings ({recent_listings})')

        # Factor 3: Unverified documents
        if user.role in ['Seller', 'Agent']:
            unverified_docs = Document.objects.filter(
                parcel__listed_by=user,
                verification_status='Pending'
            ).count()

            if unverified_docs > 2:
                score += FraudDetectionService.FRAUD_FACTORS['no_verified_documents']
                factors.append(f'Unverified documents ({unverified_docs})')

        # Factor 4: Chargeback rate
        if user.role in ['Seller', 'Agent']:
            completed_transactions = Transaction.objects.filter(
                seller=user,
                status='Completed'
            ).count()

            reversed_transactions = Transaction.objects.filter(
                seller=user,
                status='Reversed'
            ).count()

            chargeback_rate = (reversed_transactions / completed_transactions * 100) \
                if completed_transactions > 0 else 0

            if chargeback_rate > 10:
                score += FraudDetectionService.FRAUD_FACTORS['high_chargeback_rate']
                factors.append(f'High chargeback rate ({chargeback_rate:.1f}%)')

        # Cap score at 100
        score = min(score, 100)

        # Store or update fraud score
        fraud_score, created = FraudScore.objects.update_or_create(
            user=user,
            defaults={
                'score': score,
                'risk_factors': factors,
                'last_calculated': timezone.now(),
            }
        )

        return fraud_score

    @staticmethod
    def detect_duplicate_listings(parcel):
        """
        Find duplicate or near-duplicate listings.
        Returns list of suspicious parcels.
        """
        # Exact duplicates: same location + similar size
        exact_dupes = LandParcel.objects.filter(
            latitude=parcel.latitude,
            longitude=parcel.longitude,
            land_size__range=(
                parcel.land_size * Decimal('0.95'),
                parcel.land_size * Decimal('1.05')
            ),
            created_at__gte=timezone.now() - timedelta(days=180),
        ).exclude(id=parcel.id)

        # Near duplicates: same county + similar price + similar size
        near_dupes = LandParcel.objects.filter(
            county=parcel.county,
            land_size__range=(
                parcel.land_size * Decimal('0.9'),
                parcel.land_size * Decimal('1.1')
            ),
            asking_price__range=(
                parcel.asking_price * Decimal('0.95'),
                parcel.asking_price * Decimal('1.05')
            ),
            created_at__gte=timezone.now() - timedelta(days=30),
        ).exclude(id=parcel.id)

        return {
            'exact_duplicates': list(exact_dupes.values('id', 'parcel_number', 'listed_by')),
            'near_duplicates': list(near_dupes.values('id', 'parcel_number', 'listed_by')),
        }

    @staticmethod
    def validate_geolocation(parcel):
        """
        Validate that coordinates match stated county.
        Returns True if valid, False if suspicious.
        """
        if not parcel.latitude or not parcel.longitude:
            return False

        # Kenya county boundaries (simplified check)
        # In production, would use a GIS library like GeoPy
        # For now, just check that coordinates are in Kenya range
        if not (-5 <= float(parcel.latitude) <= 5):
            return False
        if not (33 <= float(parcel.longitude) <= 42):
            return False

        return True

    @staticmethod
    def check_price_drop_suspicious(parcel, prev_price):
        """Check if price drop is suspiciously large"""
        if not prev_price:
            return False

        price_drop_percent = ((prev_price - parcel.asking_price) / prev_price) * 100

        # Flag if price drops more than 30% in short time
        return price_drop_percent > 30

    @staticmethod
    def detect_rapid_transactions(user):
        """
        Detect if user is doing unusually rapid transactions.
        Could indicate fraud scheme.
        """
        two_days_ago = timezone.now() - timedelta(days=2)

        rapid_transactions = Transaction.objects.filter(
            seller=user,
            created_at__gte=two_days_ago
        ).count()

        return rapid_transactions >= 3

    @staticmethod
    def flag_for_manual_review(user, reason):
        """Flag user's account for manual review by admin"""
        fraud_score, created = FraudScore.objects.get_or_create(user=user)
        fraud_score.flagged_for_review = True
        fraud_score.review_notes = reason
        fraud_score.save()

    @staticmethod
    def unflag_user(user):
        """Clear manual review flag after investigation"""
        try:
            fraud_score = FraudScore.objects.get(user=user)
            fraud_score.flagged_for_review = False
            fraud_score.review_notes = ''
            fraud_score.save()
        except FraudScore.DoesNotExist:
            pass

    @staticmethod
    def get_high_risk_users(threshold=70):
        """Get all users with fraud score above threshold"""
        return FraudScore.objects.filter(score__gte=threshold).select_related('user')

    @staticmethod
    def get_flagged_users():
        """Get all users flagged for manual review"""
        return FraudScore.objects.filter(flagged_for_review=True).select_related('user')

    @staticmethod
    def approve_flagged_user(user, reviewed_by):
        """Clear risk flags after manual review approval"""
        fraud_score = FraudScore.objects.get(user=user)
        fraud_score.flagged_for_review = False
        fraud_score.reviewed_by = reviewed_by
        fraud_score.review_notes = f'Approved by {reviewed_by.email}'
        fraud_score.save()

    @staticmethod
    def get_fraud_risk_summary():
        """Get summary of fraud risk across platform"""
        low_risk = FraudScore.objects.filter(score__lt=20).count()
        medium_risk = FraudScore.objects.filter(score__gte=20, score__lt=50).count()
        high_risk = FraudScore.objects.filter(score__gte=50, score__lt=75).count()
        critical_risk = FraudScore.objects.filter(score__gte=75).count()

        return {
            'low_risk_users': low_risk,
            'medium_risk_users': medium_risk,
            'high_risk_users': high_risk,
            'critical_risk_users': critical_risk,
            'flagged_for_review': FraudScore.objects.filter(flagged_for_review=True).count(),
            'total_users_scored': FraudScore.objects.count(),
        }
