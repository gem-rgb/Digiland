from rest_framework import serializers
from decimal import Decimal
from .models import (
    User, AgentRating, AgentKYCApplication, KYCProfile,
    LandParcel, Transaction, Document, AuditLog,
    SupportTicket, Message,
    ParcelView, UserFavorite,
    JointBuyerGroup, JointBuyerMember, JointPaymentContribution,
    LandPromotion, PromotionTier, PromotionPlan, PromotionPlanPayment, PromotionAnalyticsLog,
    PopupAdCampaign, PopupAdEvent,
    SponsoredAd, AdEngagement, AdBillingEvent,
    BuyerInterestProfile, BuyerEngagementSignal, SearchQueryLog,
    FraudScore, VerificationBadge,
    ServiceFee, AnalyticsEvent, RecommendationLog,
)


# ==================== USER & AUTH SERIALIZERS ====================

class UserSerializer(serializers.ModelSerializer):
    """Comprehensive user serializer with nested relations."""
    average_rating = serializers.ReadOnlyField()
    total_tasks_completed = serializers.ReadOnlyField()
    kyc_status = serializers.SerializerMethodField()
    promotion_plan_tier = serializers.SerializerMethodField()
    fraud_risk_level = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'id_number',
            'phone_number', 'kra_pin', 'role', 'buyer_account_type',
            'is_identity_verified', 'gavakonect_verification_id',
            'average_rating', 'total_tasks_completed', 'kyc_status',
            'promotion_plan_tier', 'fraud_risk_level',
        ]
        read_only_fields = ['id', 'is_identity_verified', 'gavakonect_verification_id']

    def get_kyc_status(self, obj):
        if hasattr(obj, 'kyc_profile'):
            return obj.kyc_profile.status
        return None

    def get_promotion_plan_tier(self, obj):
        if hasattr(obj, 'promotion_plan') and obj.promotion_plan.status == 'Active':
            return obj.promotion_plan.tier.name
        return None

    def get_fraud_risk_level(self, obj):
        if hasattr(obj, 'fraud_score'):
            return obj.fraud_score.risk_level
        return None


class UserMinimalSerializer(serializers.ModelSerializer):
    """Lightweight user serializer for nested usage."""
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role', 'is_identity_verified']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=10)
    full_name = serializers.CharField(write_only=True, max_length=200, required=False, default='')
    role = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    id_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    kra_pin = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = User
        fields = ['email', 'password', 'full_name', 'role', 'id_number', 'phone_number', 'kra_pin']

    def validate_role(self, value):
        if not value:
            return None
        valid_roles = [r for r, _ in User.ROLE_CHOICES]
        if value == 'Admin':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Admin role cannot be self-assigned.")
        if value not in valid_roles:
            raise serializers.ValidationError("Invalid role assigned.")
        return value

    def create(self, validated_data):
        full_name = validated_data.pop('full_name', '').strip()
        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0] if name_parts else ''
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        role = validated_data.get('role')
        is_onboarded = False
        if role in ['Buyer', 'Seller', 'Agent']:
            is_onboarded = True

        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=first_name,
            last_name=last_name,
            role=role,
            is_onboarded=is_onboarded,
            phone_number=validated_data.get('phone_number'),
            id_number=validated_data.get('id_number'),
            kra_pin=validated_data.get('kra_pin'),
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


# ==================== LAND PARCEL SERIALIZERS ====================

class LandParcelListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    listed_by_email = serializers.CharField(source='listed_by.email', read_only=True, default=None)
    displayed_price = serializers.ReadOnlyField()
    verification_badges_count = serializers.SerializerMethodField()
    is_favorited = serializers.SerializerMethodField()

    class Meta:
        model = LandParcel
        fields = [
            'id', 'parcel_number', 'land_use_type', 'county', 'constituency',
            'ward', 'land_size', 'asking_price', 'displayed_price',
            'verification_status', 'image', 'listed_by_email',
            'latitude', 'longitude', 'verification_badges_count', 'is_favorited',
        ]

    def get_verification_badges_count(self, obj):
        return obj.verification_badges.filter(revoked=False).count()

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return UserFavorite.objects.filter(user=request.user, parcel=obj).exists()
        return False


class LandParcelSerializer(serializers.ModelSerializer):
    """Comprehensive land parcel serializer with nested relations."""
    listed_by = UserMinimalSerializer(read_only=True)
    assigned_agent = UserMinimalSerializer(read_only=True)
    displayed_price = serializers.ReadOnlyField()
    promotions_count = serializers.SerializerMethodField()
    views_count = serializers.SerializerMethodField()
    verification_badges = serializers.SerializerMethodField()
    is_favorited = serializers.SerializerMethodField()

    class Meta:
        model = LandParcel
        fields = [
            'id', 'parcel_number', 'land_use_type', 'county', 'constituency',
            'ward', 'land_size', 'registered_owner_id', 'verification_status',
            'ardhisasa_last_synced', 'current_risk_score', 'image',
            'listed_by', 'assigned_agent', 'asking_price',
            # SECURITY: 'lowest_negotiable_price' is EXCLUDED from API responses.
            # It must only be accessible server-side for auto-negotiation logic.
            'displayed_price',
            'latitude', 'longitude',
            'dist_to_road', 'dist_to_school', 'dist_to_hospital',
            'dist_to_mall', 'dist_to_industrial_zone', 'dist_to_transport_hub',
            'promotions_count', 'views_count', 'verification_badges', 'is_favorited',
        ]
        read_only_fields = [
            'id', 'verification_status', 'ardhisasa_last_synced',
            'current_risk_score', 'displayed_price',
        ]

    def get_promotions_count(self, obj):
        return obj.promotions.filter(is_active=True).count()

    def get_views_count(self, obj):
        return obj.views.count()

    def get_verification_badges(self, obj):
        badges = obj.verification_badges.filter(revoked=False)
        return VerificationBadgeSerializer(badges, many=True).data

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return UserFavorite.objects.filter(user=request.user, parcel=obj).exists()
        return False


# ==================== TRANSACTION SERIALIZERS ====================

class TransactionListSerializer(serializers.ModelSerializer):
    """Lightweight transaction serializer for lists."""
    buyer_email = serializers.CharField(source='buyer.email', read_only=True)
    seller_email = serializers.CharField(source='seller.email', read_only=True)
    parcel_number = serializers.CharField(source='land_parcel.parcel_number', read_only=True)
    days_remaining = serializers.ReadOnlyField(source='days_remaining_for_verification')

    class Meta:
        model = Transaction
        fields = [
            'id', 'buyer_email', 'seller_email', 'parcel_number',
            'agreed_price', 'status', 'escrow_reference',
            'total_payable', 'is_joint_purchase', 'created_at',
            'days_remaining',
        ]


class TransactionSerializer(serializers.ModelSerializer):
    """Comprehensive transaction serializer."""
    buyer = UserMinimalSerializer(read_only=True)
    seller = UserMinimalSerializer(read_only=True)
    agent = UserMinimalSerializer(read_only=True)
    land_parcel = LandParcelListSerializer(read_only=True)
    is_in_verification_hiatus = serializers.ReadOnlyField()
    verification_deadline_passed = serializers.ReadOnlyField()
    days_remaining_for_verification = serializers.ReadOnlyField()
    service_fee_breakdown = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            'id', 'buyer', 'seller', 'agent', 'land_parcel',
            'agreed_price', 'status', 'escrow_reference',
            'platform_service_fee', 'escrow_fee', 'processing_fee',
            'legal_verification_fee', 'due_diligence_fee',
            'include_legal_verification', 'include_due_diligence',
            'total_payable',
            'buyer_signature', 'seller_signature', 'contract_agreed',
            'buyer_validation_deadline', 'buyer_accepted',
            'land_verification_started', 'land_verified', 'land_verification_notes',
            'is_in_verification_hiatus', 'verification_deadline_passed',
            'days_remaining_for_verification',
            'reversal_reason', 'reversal_initiated_at', 'reversal_reference',
            'is_joint_purchase', 'joint_group',
            'created_at', 'updated_at', 'service_fee_breakdown',
        ]
        read_only_fields = [
            'status', 'escrow_reference',
            'platform_service_fee', 'escrow_fee', 'processing_fee',
            'legal_verification_fee', 'due_diligence_fee', 'total_payable',
        ]

    def get_service_fee_breakdown(self, obj):
        if hasattr(obj, 'service_fee'):
            return ServiceFeeSerializer(obj.service_fee).data
        return None


# ==================== DOCUMENT SERIALIZERS ====================

class DocumentSerializer(serializers.ModelSerializer):
    uploaded_by_email = serializers.CharField(source='uploaded_by.email', read_only=True)
    parcel_number = serializers.CharField(source='land_parcel.parcel_number', read_only=True, default=None)

    class Meta:
        model = Document
        fields = [
            'id', 'uploaded_by', 'uploaded_by_email', 'land_parcel',
            'parcel_number', 'document_type', 'file_url',
            'verification_status', 'fraud_flag_notes', 'uploaded_at',
        ]
        read_only_fields = ['verification_status', 'fraud_flag_notes', 'uploaded_by']


# ==================== AUDIT LOG SERIALIZER ====================

class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = ['id', 'user', 'user_email', 'action', 'ip_address', 'metadata', 'timestamp']
        read_only_fields = fields


# ==================== PROMOTION SERIALIZERS ====================

class LandPromotionSerializer(serializers.ModelSerializer):
    """Serializer for land promotions (boosted listings)."""
    parcel_number = serializers.CharField(source='parcel.parcel_number', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    tier_display = serializers.CharField(source='get_tier_display', read_only=True)
    billing_model_display = serializers.CharField(source='get_billing_model_display', read_only=True)

    class Meta:
        model = LandPromotion
        fields = [
            'id', 'parcel', 'parcel_number', 'tier', 'tier_display',
            'billing_model', 'billing_model_display', 'created_by', 'created_by_email',
            'start_date', 'end_date', 'is_active',
            'target_counties', 'target_budget_min', 'target_budget_max',
            'target_buyer_intents',
            'payment_reference', 'payment_status', 'price_paid',
            'views_count', 'impressions_count', 'clicks_count', 'inquiries_count',
        ]
        read_only_fields = [
            'created_by', 'start_date', 'views_count', 'impressions_count',
            'clicks_count', 'inquiries_count', 'payment_reference', 'payment_status',
        ]


class PromotionTierSerializer(serializers.ModelSerializer):
    """Serializer for promotion subscription tiers."""
    features = serializers.JSONField(source='features_json', required=False)

    class Meta:
        model = PromotionTier
        fields = [
            'id', 'name', 'slug', 'tier_level', 'monthly_price',
            'features', 'features_json', 'active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class PromotionPlanSerializer(serializers.ModelSerializer):
    """Serializer for seller promotion subscription plans."""
    seller_email = serializers.CharField(source='seller.email', read_only=True)
    tier_name = serializers.CharField(source='tier.name', read_only=True)
    tier_details = PromotionTierSerializer(source='tier', read_only=True)
    is_active = serializers.ReadOnlyField()

    class Meta:
        model = PromotionPlan
        fields = [
            'id', 'seller', 'seller_email', 'tier', 'tier_name', 'tier_details',
            'start_date', 'end_date', 'auto_renew', 'status', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['seller', 'start_date', 'created_at', 'updated_at']


# ==================== POPUP AD SERIALIZERS ====================

class PopupAdCampaignSerializer(serializers.ModelSerializer):
    """Serializer for popup ad campaigns."""
    parcel_number = serializers.CharField(source='parcel.parcel_number', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    popup_type_display = serializers.CharField(source='get_popup_type_display', read_only=True)
    billing_model_display = serializers.CharField(source='get_billing_model_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    remaining_budget = serializers.ReadOnlyField()
    is_delivery_ready = serializers.ReadOnlyField()

    class Meta:
        model = PopupAdCampaign
        fields = [
            'id', 'parcel', 'parcel_number', 'created_by', 'created_by_email',
            'campaign_name', 'popup_type', 'popup_type_display',
            'billing_model', 'billing_model_display',
            'headline', 'subheadline', 'cta_text', 'landing_url',
            'target_counties', 'target_locations',
            'target_buyer_categories', 'target_intent_tags',
            'target_budget_min', 'target_budget_max',
            'target_acreage_min', 'target_acreage_max',
            'travel_radius_km', 'frequency_cap_per_session', 'cooldown_minutes',
            'duration_days', 'daily_budget', 'total_budget', 'priority_bid',
            'geo_exclusive', 'seller_verified_only',
            'creative_image', 'creative_video_url',
            'status', 'status_display',
            'payment_reference', 'payment_status',
            'spent_amount', 'revenue_value', 'remaining_budget',
            'impressions_count', 'clicks_count', 'leads_count', 'dismissals_count',
            'quality_score', 'engagement_score', 'auction_score', 'roi_score',
            'last_scored_at', 'notes',
            'start_date', 'end_date',
            'is_delivery_ready',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'created_by', 'start_date',
            'spent_amount', 'revenue_value',
            'impressions_count', 'clicks_count', 'leads_count', 'dismissals_count',
            'quality_score', 'engagement_score', 'auction_score', 'roi_score',
            'last_scored_at', 'created_at', 'updated_at',
        ]

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Prevent updating metrics fields directly
        for field in ['impressions_count', 'clicks_count', 'leads_count', 'dismissals_count',
                      'quality_score', 'engagement_score', 'auction_score', 'roi_score',
                      'spent_amount', 'revenue_value']:
            validated_data.pop(field, None)
        return super().update(instance, validated_data)


class PopupAdCampaignListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for campaign lists."""
    parcel_number = serializers.CharField(source='parcel.parcel_number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    remaining_budget = serializers.ReadOnlyField()

    class Meta:
        model = PopupAdCampaign
        fields = [
            'id', 'campaign_name', 'parcel_number', 'popup_type',
            'status', 'status_display', 'total_budget', 'spent_amount',
            'remaining_budget', 'impressions_count', 'clicks_count',
            'start_date', 'end_date', 'created_at',
        ]


class PopupAdEventSerializer(serializers.ModelSerializer):
    """Serializer for popup ad events."""
    campaign_name = serializers.CharField(source='campaign.campaign_name', read_only=True)

    class Meta:
        model = PopupAdEvent
        fields = [
            'id', 'campaign', 'campaign_name', 'user',
            'event_type', 'placement_area', 'session_key',
            'page_context', 'buyer_category', 'county_context',
            'intent_score', 'relevance_score', 'dwell_seconds',
            'charge_amount', 'conversion_value', 'metadata', 'created_at',
        ]
        read_only_fields = ['created_at']


# ==================== SPONSORED AD SERIALIZERS ====================

class SponsoredAdSerializer(serializers.ModelSerializer):
    """Serializer for sponsored ad campaigns."""
    parcel_number = serializers.CharField(source='parcel.parcel_number', read_only=True)
    seller_email = serializers.CharField(source='seller.email', read_only=True)
    is_active = serializers.ReadOnlyField()
    engagement_summary = serializers.SerializerMethodField()

    class Meta:
        model = SponsoredAd
        fields = [
            'id', 'parcel', 'parcel_number', 'seller', 'seller_email',
            'tier', 'title', 'description', 'image_url',
            'status', 'billing_model',
            'budget_daily', 'budget_total', 'budget_spent',
            'targeting_criteria', 'is_active',
            'engagement_summary',
            'created_at', 'starts_at', 'ends_at', 'updated_at',
        ]
        read_only_fields = ['seller', 'budget_spent', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['seller'] = self.context['request'].user
        return super().create(validated_data)

    def get_engagement_summary(self, obj):
        engagements = obj.engagements.all()
        if not engagements.exists():
            return {'impressions': 0, 'clicks': 0, 'saves': 0, 'inquiries': 0, 'shares': 0}
        return {
            'impressions': engagements.filter(event_type='Impression').count(),
            'clicks': engagements.filter(event_type='Click').count(),
            'saves': engagements.filter(event_type='Save').count(),
            'inquiries': engagements.filter(event_type='Inquiry').count(),
            'shares': engagements.filter(event_type='Share').count(),
        }


class AdEngagementSerializer(serializers.ModelSerializer):
    """Serializer for ad engagement events."""
    ad_parcel = serializers.CharField(source='ad.parcel.parcel_number', read_only=True)

    class Meta:
        model = AdEngagement
        fields = [
            'id', 'ad', 'ad_parcel', 'user', 'event_type',
            'timestamp', 'source_page', 'device_type', 'geolocation',
        ]
        read_only_fields = ['timestamp']


# ==================== BUYER / RECOMMENDATION SERIALIZERS ====================

class BuyerInterestProfileSerializer(serializers.ModelSerializer):
    """Serializer for buyer interest profiles."""
    user_email = serializers.CharField(source='user.email', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = BuyerInterestProfile
        fields = [
            'id', 'user', 'user_email', 'category', 'category_display',
            'preferred_counties', 'budget_min', 'budget_max',
            'preferred_acreage_min', 'preferred_acreage_max',
            'preferred_land_use', 'last_location_lat', 'last_location_lng',
            'updated_at',
        ]
        read_only_fields = ['user', 'updated_at']


class BuyerEngagementSignalSerializer(serializers.ModelSerializer):
    """Serializer for buyer engagement signals."""
    user_email = serializers.CharField(source='user.email', read_only=True)
    parcel_number = serializers.CharField(source='parcel.parcel_number', read_only=True)

    class Meta:
        model = BuyerEngagementSignal
        fields = [
            'id', 'user', 'user_email', 'parcel', 'parcel_number',
            'signal_type', 'value', 'timestamp',
        ]
        read_only_fields = ['timestamp']


class SearchQueryLogSerializer(serializers.ModelSerializer):
    """Serializer for search query logs."""
    user_email = serializers.CharField(source='user.email', read_only=True, default=None)

    class Meta:
        model = SearchQueryLog
        fields = ['id', 'user', 'user_email', 'query', 'filters', 'timestamp']
        read_only_fields = ['timestamp']


class ParcelViewSerializer(serializers.ModelSerializer):
    """Serializer for parcel view tracking."""
    user_email = serializers.CharField(source='user.email', read_only=True)
    parcel_number = serializers.CharField(source='parcel.parcel_number', read_only=True)

    class Meta:
        model = ParcelView
        fields = ['id', 'user', 'user_email', 'parcel', 'parcel_number', 'viewed_at']
        read_only_fields = ['viewed_at']


class UserFavoriteSerializer(serializers.ModelSerializer):
    """Serializer for user favorites."""
    user_email = serializers.CharField(source='user.email', read_only=True)
    parcel_number = serializers.CharField(source='parcel.parcel_number', read_only=True)
    parcel_county = serializers.CharField(source='parcel.county', read_only=True)
    parcel_asking_price = serializers.DecimalField(
        source='parcel.asking_price', max_digits=15, decimal_places=2,
        read_only=True, default=None
    )

    class Meta:
        model = UserFavorite
        fields = [
            'id', 'user', 'user_email', 'parcel', 'parcel_number',
            'parcel_county', 'parcel_asking_price', 'saved_at',
        ]
        read_only_fields = ['user', 'saved_at']


# ==================== FRAUD & TRUST SERIALIZERS ====================

class FraudScoreSerializer(serializers.ModelSerializer):
    """Serializer for fraud scores."""
    user_email = serializers.CharField(source='user.email', read_only=True)
    risk_level = serializers.ReadOnlyField()
    reviewed_by_email = serializers.CharField(source='reviewed_by.email', read_only=True, default=None)

    class Meta:
        model = FraudScore
        fields = [
            'id', 'user', 'user_email', 'score', 'risk_level',
            'risk_factors', 'flagged_for_review',
            'review_notes', 'reviewed_by', 'reviewed_by_email',
            'last_calculated', 'created_at',
        ]
        read_only_fields = ['last_calculated', 'created_at']


class VerificationBadgeSerializer(serializers.ModelSerializer):
    """Serializer for verification badges."""
    parcel_number = serializers.CharField(source='parcel.parcel_number', read_only=True)
    issued_by_email = serializers.CharField(source='issued_by.email', read_only=True, default=None)
    is_active = serializers.ReadOnlyField()
    badge_type_display = serializers.CharField(source='get_badge_type_display', read_only=True)

    class Meta:
        model = VerificationBadge
        fields = [
            'id', 'parcel', 'parcel_number', 'badge_type', 'badge_type_display',
            'issued_by', 'issued_by_email', 'issued_at', 'expires_at',
            'revoked', 'is_active',
        ]
        read_only_fields = ['issued_at', 'issued_by']


# ==================== SERVICE FEE SERIALIZER ====================

class ServiceFeeSerializer(serializers.ModelSerializer):
    """Serializer for service fees."""
    transaction_id = serializers.UUIDField(source='transaction.id', read_only=True)
    total_with_fees = serializers.ReadOnlyField()

    class Meta:
        model = ServiceFee
        fields = [
            'id', 'transaction', 'transaction_id',
            'platform_fee', 'escrow_fee', 'processing_fee',
            'verification_fee', 'due_diligence_fee',
            'total_fees', 'breakdown', 'total_with_fees',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


# ==================== ANALYTICS SERIALIZERS ====================

class AnalyticsEventSerializer(serializers.ModelSerializer):
    """Serializer for analytics events."""
    parcel_number = serializers.CharField(source='parcel.parcel_number', read_only=True)

    class Meta:
        model = AnalyticsEvent
        fields = [
            'id', 'parcel', 'parcel_number', 'user',
            'event_type', 'timestamp', 'metadata',
        ]
        read_only_fields = ['timestamp']


class RecommendationLogSerializer(serializers.ModelSerializer):
    """Serializer for recommendation logs."""
    user_email = serializers.CharField(source='user.email', read_only=True)
    parcel_number = serializers.CharField(source='parcel.parcel_number', read_only=True)
    algorithm_type_display = serializers.CharField(source='get_algorithm_type_display', read_only=True)

    class Meta:
        model = RecommendationLog
        fields = [
            'id', 'user', 'user_email', 'parcel', 'parcel_number',
            'algorithm_type', 'algorithm_type_display',
            'rank', 'score', 'clicked', 'saved', 'inquired',
            'timestamp', 'feedback_score',
        ]
        read_only_fields = ['timestamp']


# ==================== KYC SERIALIZERS ====================

class AgentKYCApplicationSerializer(serializers.ModelSerializer):
    """Serializer for agent KYC applications."""
    agent_email = serializers.CharField(source='agent.email', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = AgentKYCApplication
        fields = [
            'id', 'agent', 'agent_email',
            'kra_pin', 'id_number',
            'id_photo', 'resume', 'certificate_of_good_conduct',
            'practicing_certificate',
            'kyc_submitted', 'status', 'status_display',
            'submitted_at', 'reviewed_at',
        ]
        read_only_fields = ['agent', 'kyc_submitted', 'status', 'submitted_at', 'reviewed_at']

    def create(self, validated_data):
        validated_data['agent'] = self.context['request'].user
        validated_data['kyc_submitted'] = True
        return super().create(validated_data)


class KYCProfileSerializer(serializers.ModelSerializer):
    """Serializer for KYC profiles (admin/staff use)."""
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = KYCProfile
        fields = [
            'id', 'user', 'user_email', 'status',
            'id_number', 'id_number_hash', 'full_name',
            'date_of_birth', 'expiry_date',
            'face_embedding', 'liveness_score',
            'id_front_image', 'selfie_image',
            'audit_log', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'face_embedding': {'write_only': True},
            'id_number_hash': {'write_only': True},
        }


# ==================== JOINT BUYER SERIALIZERS ====================

class JointBuyerMemberSerializer(serializers.ModelSerializer):
    """Serializer for joint buyer group members."""
    group_name = serializers.CharField(source='group.name', read_only=True)

    class Meta:
        model = JointBuyerMember
        fields = [
            'id', 'group', 'group_name',
            'full_name', 'id_number', 'kra_pin',
            'phone_number', 'email', 'share_percentage',
            'signature', 'has_signed', 'is_leader', 'added_at',
        ]
        read_only_fields = ['added_at']


class JointPaymentContributionSerializer(serializers.ModelSerializer):
    """Serializer for joint payment contributions."""
    member_name = serializers.CharField(source='member.full_name', read_only=True, default=None)

    class Meta:
        model = JointPaymentContribution
        fields = [
            'id', 'transaction', 'member', 'member_name',
            'amount', 'payment_channel', 'phone_number', 'status',
            'checkout_request_id', 'mpesa_receipt', 'bank_reference',
            'depositor_name', 'bank_name', 'bank_account_number',
            'bank_account_name', 'bank_branch', 'created_at',
        ]
        read_only_fields = ['created_at']


class JointBuyerGroupSerializer(serializers.ModelSerializer):
    """Serializer for joint buyer groups with nested members."""
    leader_email = serializers.CharField(source='leader.email', read_only=True)
    members = JointBuyerMemberSerializer(many=True, read_only=True)
    total_share = serializers.ReadOnlyField()
    is_valid = serializers.ReadOnlyField()
    all_signed = serializers.ReadOnlyField()
    members_count = serializers.SerializerMethodField()

    class Meta:
        model = JointBuyerGroup
        fields = [
            'id', 'name', 'group_type', 'ownership_type',
            'preferred_payment_method',
            'bank_name', 'bank_account_name', 'bank_account_number', 'bank_branch',
            'leader', 'leader_email',
            'members', 'members_count',
            'total_share', 'is_valid', 'all_signed',
            'created_at',
        ]
        read_only_fields = ['leader', 'created_at']

    def get_members_count(self, obj):
        return obj.members.count()
