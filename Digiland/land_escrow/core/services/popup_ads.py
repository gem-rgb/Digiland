import math
import re
from collections import Counter, defaultdict
from decimal import Decimal

from django.db import transaction as db_transaction
from django.db.models import Avg, Count, Q, Sum
from django.urls import reverse
from django.utils import timezone

from core.models import (
    BuyerEngagementSignal,
    BuyerInterestProfile,
    LandParcel,
    ParcelView,
    PopupAdCampaign,
    PopupAdEvent,
    SearchQueryLog,
    Transaction,
    User,
    UserFavorite,
)


BLOCKED_PAGES = {
    'transactions',
    'checkout',
    'checkout-fullpage',
    'contract',
    'contract-fullpage',
    'messages',
    'support',
    'finance',
    'admin-dashboard',
    'agent-dashboard',
    'seller-withdraw',
    'agent-withdraw',
    'admin-withdraw',
    'task-management',
    'approvals',
    'user-review',
    'buyer-choice',
    'payment-onboarding',
    'staff-login',
    'agent-kyc',
    'ai-kyc',
}

BUYER_PAGES = {
    'landing',
    'dashboard',
    'parcel-list',
    'parcel-detail',
    'recommendations',
    'content',
    'simple',
}

PRIMARY_TRIGGER_ORDER = ['retargeting', 'geo', 'urgency', 'smart']
EXIT_TRIGGER_ORDER = ['exit_intent']


def _as_list(value):
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        raw = value
    else:
        raw = re.split(r'[,;\n]+', str(value))
    return [str(item).strip() for item in raw if str(item).strip()]


def _lower_list(value):
    return [item.lower() for item in _as_list(value)]


def _decimal(value):
    if value in {None, ''}:
        return Decimal('0.00')
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal('0.00')


def _round_float(value, digits=2):
    try:
        return round(float(value), digits)
    except Exception:
        return 0.0


def _safe_string(value, default=''):
    return default if value in {None, ''} else str(value)


def _page_allowed(page, user):
    if page in BLOCKED_PAGES:
        return False
    if getattr(user, 'is_authenticated', False) and getattr(user, 'role', None) not in {'Buyer'}:
        return False
    if not getattr(user, 'is_authenticated', False):
        return page in BUYER_PAGES
    return page in BUYER_PAGES


def _session_state(request):
    state = request.session.get('popup_ads_state') or {}
    state.setdefault('campaigns', {})
    state.setdefault('show_count', 0)
    return state


def _store_session_state(request, state):
    request.session['popup_ads_state'] = state
    request.session.modified = True


def _get_seller_trust_score(user):
    if not user:
        return 0.0

    score = 35.0
    if getattr(user, 'is_identity_verified', False):
        score += 20.0

    role = getattr(user, 'role', None)
    if role == 'Agent':
        rating = getattr(user, 'average_rating', None)
        if rating:
            score += float(rating) * 8.0
        verified_count = LandParcel.objects.filter(
            Q(assigned_agent=user) | Q(listed_by=user),
            verification_status='Verified',
        ).count()
        score += min(20.0, verified_count * 2.0)
    elif role == 'Seller':
        verified_count = LandParcel.objects.filter(
            listed_by=user,
            verification_status='Verified',
        ).count()
        score += min(20.0, verified_count * 2.2)

    completed_transactions = Transaction.objects.filter(
        seller=user,
        status='Completed',
    ).count()
    score += min(15.0, completed_transactions * 1.5)

    return max(0.0, min(100.0, score))


def _get_parcel_quality_score(parcel):
    score = 45.0
    if parcel.verification_status == 'Verified':
        score += 25.0
    elif parcel.verification_status == 'Pending':
        score += 5.0
    else:
        score -= 10.0

    if parcel.image:
        score += 7.0

    if parcel.asking_price:
        score += 3.0

    risk = float(getattr(parcel, 'current_risk_score', 0.0) or 0.0)
    if risk <= 15:
        score += 12.0
    elif risk <= 35:
        score += 6.0
    elif risk >= 70:
        score -= 12.0

    infra_score = 0.0
    if float(getattr(parcel, 'dist_to_road', 10.0) or 10.0) <= 0.75:
        infra_score += 3.0
    if float(getattr(parcel, 'dist_to_transport_hub', 10.0) or 10.0) <= 2.5:
        infra_score += 3.0
    if float(getattr(parcel, 'dist_to_school', 10.0) or 10.0) <= 2.5:
        infra_score += 2.0
    if float(getattr(parcel, 'dist_to_hospital', 10.0) or 10.0) <= 3.5:
        infra_score += 2.0
    score += infra_score

    return max(0.0, min(100.0, score))


def _build_buyer_context(request, page, context=None):
    context = context or {}
    user = request.user

    buyer_profile = None
    if getattr(user, 'is_authenticated', False) and getattr(user, 'role', None) == 'Buyer':
        try:
            from core.services.recommendation import update_buyer_interest_profile

            buyer_profile = update_buyer_interest_profile(user)
        except Exception:
            buyer_profile = BuyerInterestProfile.objects.filter(user=user).first()

    recent_views = []
    recent_favorites = []
    recent_searches = []
    recent_signals = []
    recent_counties = []
    recent_keywords = []
    recent_parcels = []

    if getattr(user, 'is_authenticated', False) and getattr(user, 'role', None) == 'Buyer':
        recent_views = list(
            ParcelView.objects.filter(user=user)
            .select_related('parcel')
            .order_by('-viewed_at')[:30]
        )
        recent_favorites = list(
            UserFavorite.objects.filter(user=user)
            .select_related('parcel')
            .order_by('-saved_at')[:20]
        )
        recent_searches = list(
            SearchQueryLog.objects.filter(user=user).order_by('-timestamp')[:20]
        )
        recent_signals = list(
            BuyerEngagementSignal.objects.filter(user=user)
            .select_related('parcel')
            .order_by('-timestamp')[:30]
        )

        recent_parcels = [view.parcel for view in recent_views]
        recent_counties = [parcel.county for parcel in recent_parcels if getattr(parcel, 'county', None)]
        recent_counties.extend([fav.parcel.county for fav in recent_favorites if getattr(fav.parcel, 'county', None)])

        for search in recent_searches:
            recent_keywords.extend(re.split(r'\s+', search.query.lower()))
            filters = search.filters or {}
            if filters.get('county'):
                recent_counties.append(filters['county'])

    preferred_counties = list(getattr(buyer_profile, 'preferred_counties', []) or [])
    budget_min = getattr(buyer_profile, 'budget_min', None)
    budget_max = getattr(buyer_profile, 'budget_max', None)
    acreage_min = getattr(buyer_profile, 'preferred_acreage_min', None)
    acreage_max = getattr(buyer_profile, 'preferred_acreage_max', None)
    buyer_category = getattr(buyer_profile, 'category', None) or 'Residential'
    geo_lat = getattr(buyer_profile, 'last_location_lat', None)
    geo_lng = getattr(buyer_profile, 'last_location_lng', None)

    county = (
        context.get('county')
        or context.get('target_county')
        or (preferred_counties[0] if preferred_counties else None)
        or (recent_counties[0] if recent_counties else None)
    )
    constituency = context.get('constituency')
    ward = context.get('ward')
    parcel = context.get('parcel')
    if parcel is not None and getattr(parcel, 'county', None):
        county = getattr(parcel, 'county', county)
        constituency = getattr(parcel, 'constituency', constituency)
        ward = getattr(parcel, 'ward', ward)

    if getattr(user, 'is_authenticated', False) and getattr(user, 'role', None) == 'Buyer':
        intent_score = 18.0
    else:
        intent_score = 8.0

    if len(recent_views) >= 3:
        intent_score += 18.0
    elif len(recent_views) >= 1:
        intent_score += 8.0

    if len(recent_favorites) >= 2:
        intent_score += 16.0
    elif len(recent_favorites) == 1:
        intent_score += 7.0

    if len(recent_searches) >= 4:
        intent_score += 12.0
    elif len(recent_searches) >= 2:
        intent_score += 6.0

    if any(keyword in recent_keywords for keyword in ['buy', 'purchase', 'land', 'plot', 'investment', 'invest']):
        intent_score += 8.0

    if any(signal.signal_type in {'Inquiry', 'Offer_Submitted', 'Favorite'} for signal in recent_signals):
        intent_score += 14.0

    if buyer_category in {'Commercial', 'Luxury', 'Diaspora', 'Speculator'}:
        intent_score += 8.0
    if getattr(user, 'buyer_account_type', None) == 'Joint':
        intent_score += 8.0

    if county and county in preferred_counties:
        intent_score += 10.0
    if recent_counties and county and county in recent_counties:
        intent_score += 6.0

    intent_score = max(0.0, min(100.0, intent_score))

    if intent_score >= 75:
        intent_label = 'high'
    elif intent_score >= 50:
        intent_label = 'warm'
    elif intent_score >= 25:
        intent_label = 'active'
    else:
        intent_label = 'browse'

    if intent_score >= 70:
        recommended_delay_ms = 1200
    elif intent_score >= 45:
        recommended_delay_ms = 2200
    else:
        recommended_delay_ms = 3200

    placement = context.get('placement') or page
    if placement == 'parcel-detail' and context.get('exit_intent'):
        trigger_hint = 'exit_intent'
    elif placement == 'parcel-detail':
        trigger_hint = 'smart'
    elif placement in {'recommendations', 'parcel-list', 'landing', 'dashboard'}:
        trigger_hint = 'smart'
    else:
        trigger_hint = 'smart'

    return {
        'page': page,
        'placement': placement,
        'county': county,
        'constituency': constituency,
        'ward': ward,
        'buyer_category': buyer_category,
        'budget_min': budget_min,
        'budget_max': budget_max,
        'acreage_min': acreage_min,
        'acreage_max': acreage_max,
        'geo_lat': geo_lat,
        'geo_lng': geo_lng,
        'intent_score': intent_score,
        'intent_label': intent_label,
        'recommended_delay_ms': recommended_delay_ms,
        'trigger_hint': trigger_hint,
        'recent_views': recent_views,
        'recent_favorites': recent_favorites,
        'recent_searches': recent_searches,
        'recent_signals': recent_signals,
        'recent_counties': recent_counties,
        'recent_keywords': recent_keywords,
        'recent_parcels': recent_parcels,
        'session_state': _session_state(request),
        'buyer_profile': buyer_profile,
        'user': user,
    }


def _calculate_charge_amount(campaign, event_type):
    bid = _decimal(campaign.priority_bid)
    if campaign.billing_model == 'Subscription':
        return Decimal('0.00')

    if campaign.billing_model == 'PPV':
        if event_type == 'Impression':
            return bid
        if event_type == 'Click':
            return bid * Decimal('0.75')
        if event_type == 'Lead':
            return bid * Decimal('1.5')
    elif campaign.billing_model == 'PPC':
        if event_type == 'Click':
            return bid
        if event_type == 'Lead':
            return bid * Decimal('1.4')
    elif campaign.billing_model == 'PPL':
        if event_type == 'Lead':
            return max(bid, Decimal('1.00'))
    elif campaign.billing_model == 'Geo_Exclusive':
        if event_type == 'Impression':
            return bid * Decimal('1.25')
        if event_type == 'Click':
            return bid * Decimal('1.75')
        if event_type == 'Lead':
            return bid * Decimal('2.5')

    return Decimal('0.00')


def _estimate_conversion_value(campaign, event_type):
    parcel = campaign.parcel
    price = _decimal(getattr(parcel, 'asking_price', None))
    if event_type == 'Lead':
        return price * Decimal('0.10')
    if event_type == 'Click':
        return price * Decimal('0.02')
    return Decimal('0.00')


def _build_social_proof(parcel):
    today = timezone.now().date()
    start_of_day = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

    views_today = ParcelView.objects.filter(parcel=parcel, viewed_at__gte=start_of_day).count()
    favorites_today = UserFavorite.objects.filter(parcel=parcel, saved_at__gte=start_of_day).count()
    active_transactions = Transaction.objects.filter(
        land_parcel=parcel,
        status__in=['Initiated', 'Deposit_Paid', 'Under_Verification', 'Verification_Hiatus'],
    ).count()

    proof_bits = []
    if views_today:
        proof_bits.append(f'{views_today} buyers viewed this property today')
    if favorites_today:
        proof_bits.append(f'{favorites_today} buyers saved this listing today')
    if active_transactions:
        proof_bits.append(f'{active_transactions} active escrow conversation{"" if active_transactions == 1 else "s"}')

    if not proof_bits:
        proof_bits.append('Trending in your market right now')
    return proof_bits


def _build_scarcity_message(parcel):
    active_transactions = Transaction.objects.filter(
        land_parcel=parcel,
        status__in=['Initiated', 'Deposit_Paid', 'Under_Verification', 'Verification_Hiatus'],
    ).count()
    remaining = max(0, 5 - active_transactions)
    if remaining == 0:
        return 'Demand is strong. Limited availability left.'
    if remaining == 1:
        return 'Only 1 prime slot remains before this area cools off.'
    return f'{remaining} prime slots remain in this price band.'


def serialize_popup_campaign(campaign, *, user=None, score=0.0, reasons=None, trigger=None):
    parcel = campaign.parcel
    seller = campaign.created_by
    seller_trust_score = _get_seller_trust_score(seller)
    parcel_quality_score = _get_parcel_quality_score(parcel)
    clicks = campaign.clicks_count or 0
    impressions = campaign.impressions_count or 0
    leads = campaign.leads_count or 0
    dismissals = campaign.dismissals_count or 0
    ctr = (clicks / impressions) if impressions else 0.0
    lead_rate = (leads / clicks) if clicks else 0.0
    spend = _decimal(campaign.spent_amount)
    revenue = _decimal(campaign.revenue_value)
    roi = float(revenue / spend) if spend > 0 else float(revenue)

    if not campaign.landing_url:
        try:
            landing_url = reverse('frontend:parcel_detail', args=[parcel.parcel_number])
        except Exception:
            landing_url = ''
    else:
        landing_url = campaign.landing_url

    if not campaign.headline:
        if campaign.popup_type == 'Exit_Intent':
            headline = f'Before you leave, similar land is available in {parcel.county}.'
        elif campaign.popup_type == 'Urgency':
            headline = f'Hot opportunity in {parcel.county} with strong buyer demand.'
        elif campaign.popup_type == 'Geo_Targeted':
            headline = f'Trending investment land in {parcel.county}.'
        elif campaign.popup_type == 'Behavioral_Retargeting':
            headline = f'Still considering {parcel.county}? New options are live now.'
        else:
            headline = f'Premium land available in {parcel.county}.'
    else:
        headline = campaign.headline

    subheadline = campaign.subheadline or (
        f'{parcel.land_size} acres in {parcel.constituency}, {parcel.county}. '
        f'Ideal for {parcel.land_use_type.lower()} buyers who value verified listings.'
    )

    amenities = [
        {'label': 'Size', 'value': f'{parcel.land_size} acres'},
        {'label': 'Road access', 'value': f'{parcel.dist_to_road} km'},
        {'label': 'Transport hub', 'value': f'{parcel.dist_to_transport_hub} km'},
        {'label': 'School', 'value': f'{parcel.dist_to_school} km'},
        {'label': 'Hospital', 'value': f'{parcel.dist_to_hospital} km'},
    ]

    targeting = {
        'counties': list(campaign.target_counties or []),
        'locations': list(campaign.target_locations or []),
        'buyer_categories': list(campaign.target_buyer_categories or []),
        'intent_tags': list(campaign.target_intent_tags or []),
        'budget_min': str(campaign.target_budget_min) if campaign.target_budget_min is not None else None,
        'budget_max': str(campaign.target_budget_max) if campaign.target_budget_max is not None else None,
        'acreage_min': str(campaign.target_acreage_min) if campaign.target_acreage_min is not None else None,
        'acreage_max': str(campaign.target_acreage_max) if campaign.target_acreage_max is not None else None,
        'travel_radius_km': campaign.travel_radius_km,
        'geo_exclusive': bool(campaign.geo_exclusive),
    }

    budget = {
        'daily_budget': str(campaign.daily_budget),
        'total_budget': str(campaign.total_budget),
        'spent_amount': str(spend),
        'remaining_budget': str(campaign.remaining_budget),
        'priority_bid': str(campaign.priority_bid),
        'billing_model': campaign.billing_model,
        'billing_model_label': campaign.get_billing_model_display(),
    }

    metrics = {
        'impressions': impressions,
        'clicks': clicks,
        'leads': leads,
        'dismissals': dismissals,
        'ctr': round(ctr * 100, 2),
        'lead_rate': round(lead_rate * 100, 2),
        'spend': str(spend),
        'revenue': str(revenue),
        'roi': round(roi, 2),
        'quality_score': round(parcel_quality_score, 2),
        'engagement_score': round(campaign.engagement_score or 0.0, 2),
        'auction_score': round(campaign.auction_score or score, 2),
        'seller_trust_score': round(seller_trust_score, 2),
    }

    social_proof = _build_social_proof(parcel)
    scarcity_text = _build_scarcity_message(parcel)

    return {
        'id': str(campaign.id),
        'campaign_name': campaign.campaign_name,
        'popup_type': campaign.popup_type,
        'popup_type_label': campaign.get_popup_type_display(),
        'billing_model': campaign.billing_model,
        'billing_model_label': campaign.get_billing_model_display(),
        'status': campaign.status,
        'status_label': campaign.get_status_display() if hasattr(campaign, 'get_status_display') else campaign.status,
        'status_tone': 'success' if campaign.status == 'Active' else 'warning' if campaign.status == 'Draft' else 'muted',
        'headline': headline,
        'subheadline': subheadline,
        'cta_text': campaign.cta_text or 'View listing',
        'landing_url': landing_url,
        'creative_image_url': campaign.creative_image.url if getattr(campaign, 'creative_image', None) else None,
        'creative_video_url': campaign.creative_video_url,
        'parcel': {
            'parcel_number': parcel.parcel_number,
            'county': parcel.county,
            'constituency': parcel.constituency,
            'ward': parcel.ward,
            'land_size': str(parcel.land_size),
            'land_use_type': parcel.land_use_type,
            'verification_status': parcel.verification_status,
            'image_url': parcel.image.url if getattr(parcel, 'image', None) else None,
            'displayed_price': str(parcel.displayed_price),
            'asking_price': str(parcel.asking_price) if parcel.asking_price is not None else None,
            'details_url': reverse('frontend:parcel_detail', args=[parcel.parcel_number]),
        },
        'seller': {
            'email': seller.email,
            'role': seller.role,
            'is_verified': bool(getattr(seller, 'is_identity_verified', False)),
            'trust_score': round(seller_trust_score, 2),
            'label': 'Verified seller' if getattr(seller, 'is_identity_verified', False) else 'Seller',
        },
        'targeting': targeting,
        'frequency': {
            'frequency_cap_per_session': campaign.frequency_cap_per_session,
            'cooldown_minutes': campaign.cooldown_minutes,
            'duration_days': campaign.duration_days,
            'geo_exclusive': bool(campaign.geo_exclusive),
        },
        'budget': budget,
        'metrics': metrics,
        'amenities': amenities,
        'score': round(float(score), 2),
        'match_reasons': reasons or [],
        'trigger': trigger,
        'social_proof': social_proof,
        'scarcity_text': scarcity_text,
        'created_at': campaign.created_at.strftime('%b %d, %Y'),
        'updated_at': campaign.updated_at.strftime('%b %d, %Y'),
    }


def _matches_text_terms(source_values, search_terms):
    source = {item.lower() for item in _as_list(source_values)}
    terms = {item.lower() for item in _as_list(search_terms)}
    if not source or not terms:
        return False
    return bool(source.intersection(terms))


def _score_campaign(campaign, buyer_context, page):
    if not campaign.is_delivery_ready:
        return None

    parcel = campaign.parcel
    user = buyer_context['user']
    if campaign.seller_verified_only and not getattr(campaign.created_by, 'is_identity_verified', False):
        return None

    active_tx_statuses = ['Initiated', 'Deposit_Paid', 'Under_Verification', 'Verification_Hiatus']
    if Transaction.objects.filter(land_parcel=parcel, status__in=active_tx_statuses).exists():
        return None

    trigger = {
        'Smart_Recommendation': 'smart',
        'Exit_Intent': 'exit_intent',
        'Geo_Targeted': 'geo',
        'Urgency': 'urgency',
        'Behavioral_Retargeting': 'retargeting',
    }.get(campaign.popup_type, 'smart')

    if trigger == 'exit_intent' and page not in {'parcel-detail', 'recommendations', 'parcel-list', 'dashboard', 'landing'}:
        return None

    score = 0.0
    reasons = []
    county = buyer_context.get('county')
    constituency = buyer_context.get('constituency')
    ward = buyer_context.get('ward')
    buyer_category = buyer_context.get('buyer_category')
    budget_min = buyer_context.get('budget_min')
    budget_max = buyer_context.get('budget_max')
    acreage_min = buyer_context.get('acreage_min')
    acreage_max = buyer_context.get('acreage_max')
    intent_score = buyer_context.get('intent_score', 0.0)

    bid_component = min(24.0, math.log1p(float(_decimal(campaign.priority_bid))) * 6.5)
    score += bid_component
    reasons.append(f'Bid strength {bid_component:.1f}')

    quality = _get_parcel_quality_score(parcel)
    trust = _get_seller_trust_score(campaign.created_by)
    score += quality * 0.18
    score += trust * 0.12
    score += min(8.0, (campaign.engagement_score or 0.0) / 10.0)

    if campaign.popup_type == 'Smart_Recommendation':
        if page in {'landing', 'dashboard', 'parcel-list', 'recommendations', 'parcel-detail'}:
            score += 12.0
            reasons.append('Smart discovery surface')
    elif campaign.popup_type == 'Exit_Intent':
        if page == 'parcel-detail':
            score += 20.0
            reasons.append('Exit intent ready')
        else:
            score += 6.0
    elif campaign.popup_type == 'Geo_Targeted':
        if county and county in _as_list(campaign.target_counties):
            score += 22.0
            reasons.append(f'County match {county}')
        elif constituency and _matches_text_terms(campaign.target_locations, [constituency]):
            score += 14.0
        elif ward and _matches_text_terms(campaign.target_locations, [ward]):
            score += 12.0
        elif campaign.geo_exclusive:
            return None
    elif campaign.popup_type == 'Urgency':
        if intent_score >= 50:
            score += 18.0
            reasons.append('High-intent buyer')
        social_proof = len(_build_social_proof(parcel))
        score += min(10.0, social_proof * 2.0)
    elif campaign.popup_type == 'Behavioral_Retargeting':
        viewed_ids = {view.parcel_id for view in buyer_context.get('recent_views', [])}
        saved_ids = {fav.parcel_id for fav in buyer_context.get('recent_favorites', [])}
        if parcel.id in viewed_ids or parcel.id in saved_ids:
            score += 24.0
            reasons.append('Retargeting recent parcel')
        elif county and county in buyer_context.get('recent_counties', []):
            score += 14.0
            reasons.append('Retargeting county interest')
        else:
            score += 4.0

    if county and _as_list(campaign.target_counties):
        if county in _as_list(campaign.target_counties):
            score += 18.0
            reasons.append(f'County target {county}')
        else:
            score -= 5.0

    if _as_list(campaign.target_locations):
        location_terms = [county, constituency, ward]
        if any(term and _matches_text_terms(campaign.target_locations, [term]) for term in location_terms):
            score += 10.0
            reasons.append('Location cluster match')

    if buyer_category and _as_list(campaign.target_buyer_categories):
        if buyer_category in _as_list(campaign.target_buyer_categories):
            score += 14.0
            reasons.append(f'Audience fit {buyer_category}')
        else:
            score -= 3.0

    if _as_list(campaign.target_intent_tags):
        search_terms = buyer_context.get('recent_keywords', [])
        if _matches_text_terms(campaign.target_intent_tags, search_terms):
            score += 10.0
            reasons.append('Intent keyword match')
        elif intent_score >= 65:
            score += 6.0

    parcel_price = _decimal(parcel.asking_price)
    if budget_min is not None and budget_max is not None and parcel_price:
        if _decimal(budget_min) <= parcel_price <= _decimal(budget_max):
            score += 15.0
            reasons.append('Budget band fit')
        else:
            score -= 4.0

    parcel_size = _decimal(parcel.land_size)
    if acreage_min is not None and acreage_max is not None:
        if _decimal(acreage_min) <= parcel_size <= _decimal(acreage_max):
            score += 8.0
            reasons.append('Acreage fit')
        else:
            score -= 2.0

    if campaign.geo_exclusive and county and county not in _as_list(campaign.target_counties):
        score -= 8.0

    if intent_score >= 75:
        score += 8.0
    elif intent_score >= 50:
        score += 4.0

    dismissed_count = _session_state_history_count(buyer_context, campaign.id, 'dismissed')
    if dismissed_count >= campaign.frequency_cap_per_session:
        return None

    recency_penalty = _recent_campaign_suppression_penalty(buyer_context, campaign.id)
    if recency_penalty:
        score -= recency_penalty

    score = max(0.0, min(100.0, score))
    if score < 25:
        return None

    return {
        'trigger': trigger,
        'score': round(score, 2),
        'reasons': reasons,
    }


def _session_campaign_state(buyer_context):
    state = buyer_context.get('session_state') or {}
    campaigns = state.get('campaigns') or {}
    return campaigns


def _session_state_history_count(buyer_context, campaign_id, key):
    campaigns = _session_campaign_state(buyer_context)
    entry = campaigns.get(str(campaign_id)) or {}
    if key == 'dismissed':
        return int(entry.get('dismiss_count', 0) or 0)
    if key == 'shown':
        return int(entry.get('show_count', 0) or 0)
    return 0


def _recent_campaign_suppression_penalty(buyer_context, campaign_id):
    campaigns = _session_campaign_state(buyer_context)
    entry = campaigns.get(str(campaign_id)) or {}
    last_shown_at = entry.get('last_shown_at')
    if not last_shown_at:
        return 0.0
    try:
        last_dt = timezone.datetime.fromisoformat(last_shown_at)
        if timezone.is_naive(last_dt):
            last_dt = timezone.make_aware(last_dt, timezone.get_current_timezone())
    except Exception:
        return 0.0

    cooldown_minutes = int(entry.get('cooldown_minutes') or 0)
    if cooldown_minutes <= 0:
        return 0.0

    elapsed = (timezone.now() - last_dt).total_seconds() / 60.0
    if elapsed < cooldown_minutes:
        return 100.0
    if elapsed < cooldown_minutes * 2:
        return 18.0
    return 0.0


def _choose_primary_candidate(candidates_by_trigger, *, order=None):
    order = order or PRIMARY_TRIGGER_ORDER
    for trigger in order:
        trigger_candidates = candidates_by_trigger.get(trigger) or []
        if trigger_candidates:
            return trigger_candidates[0]
    return None


def build_popup_ads_payload(request, page, context=None):
    user = getattr(request, 'user', None)
    if not _page_allowed(page, user):
        return {
            'enabled': False,
            'page': page,
            'reason': 'page_or_role_not_eligible',
            'candidates': {},
            'primary': None,
        }

    buyer_context = _build_buyer_context(request, page, context=context)
    active_campaigns = (
        PopupAdCampaign.objects.select_related('parcel', 'created_by')
        .filter(status='Active', payment_status='Paid')
        .order_by('-priority_bid', '-updated_at')
    )

    candidates_by_trigger = {trigger: [] for trigger in [*PRIMARY_TRIGGER_ORDER, *EXIT_TRIGGER_ORDER]}
    for campaign in active_campaigns:
        score_data = _score_campaign(campaign, buyer_context, page)
        if not score_data:
            continue
        serialized = serialize_popup_campaign(
            campaign,
            user=user,
            score=score_data['score'],
            reasons=score_data['reasons'],
            trigger=score_data['trigger'],
        )
        serialized['display_delay_ms'] = buyer_context['recommended_delay_ms']
        candidates_by_trigger[score_data['trigger']].append(serialized)

    for trigger in candidates_by_trigger:
        candidates_by_trigger[trigger] = sorted(
            candidates_by_trigger[trigger],
            key=lambda item: (
                item['score'],
                float(item['budget']['priority_bid'] or 0.0),
                item['metrics']['ctr'],
                item['metrics']['roi'],
            ),
            reverse=True,
        )[:3]

    primary = _choose_primary_candidate(candidates_by_trigger, order=PRIMARY_TRIGGER_ORDER)
    session_state = _session_state(request)
    shown_count = int(session_state.get('show_count', 0) or 0)
    if primary and shown_count >= 1:
        primary = None

    return {
        'enabled': bool(primary or any(candidates_by_trigger.values())),
        'page': page,
        'placement': buyer_context['placement'],
        'intent_score': buyer_context['intent_score'],
        'intent_label': buyer_context['intent_label'],
        'buyer_category': buyer_context['buyer_category'],
        'county': buyer_context['county'],
        'constituency': buyer_context['constituency'],
        'ward': buyer_context['ward'],
        'recommended_delay_ms': buyer_context['recommended_delay_ms'],
        'frequency_cap_per_session': (primary['frequency']['frequency_cap_per_session'] if primary else (candidates_by_trigger.get('exit_intent') or [{'frequency': {'frequency_cap_per_session': 1}}])[0]['frequency']['frequency_cap_per_session']),
        'session_show_count': shown_count,
        'candidates': candidates_by_trigger,
        'primary': primary,
        'exit_candidate': _choose_primary_candidate(candidates_by_trigger, order=EXIT_TRIGGER_ORDER),
        'recent_search_terms': buyer_context['recent_keywords'][:20],
        'suppressed_reason': None if primary else 'session_limit_or_no_match',
    }


def record_popup_event(
    campaign,
    *,
    user=None,
    request=None,
    event_type='Impression',
    placement_area=None,
    page_context=None,
    buyer_category=None,
    county_context=None,
    intent_score=0.0,
    relevance_score=0.0,
    dwell_seconds=0.0,
    metadata=None,
):
    charge_amount = _calculate_charge_amount(campaign, event_type)
    conversion_value = _estimate_conversion_value(campaign, event_type)
    metadata = metadata or {}
    session_key = None
    if request is not None and getattr(request, 'session', None) is not None:
        session_key = request.session.session_key

    event = PopupAdEvent.objects.create(
        campaign=campaign,
        user=user if getattr(user, 'is_authenticated', False) else None,
        event_type=event_type,
        placement_area=placement_area or page_context or 'marketplace',
        session_key=session_key,
        page_context=page_context or placement_area or 'marketplace',
        buyer_category=buyer_category,
        county_context=county_context,
        intent_score=float(intent_score or 0.0),
        relevance_score=float(relevance_score or 0.0),
        dwell_seconds=float(dwell_seconds or 0.0),
        charge_amount=charge_amount,
        conversion_value=conversion_value,
        metadata=metadata,
    )

    with db_transaction.atomic():
        campaign = PopupAdCampaign.objects.select_for_update().get(pk=campaign.pk)
        if event_type == 'Impression':
            campaign.impressions_count += 1
        elif event_type == 'Click':
            campaign.clicks_count += 1
        elif event_type == 'Lead':
            campaign.leads_count += 1
        elif event_type in {'Dismissed', 'Suppressed'}:
            campaign.dismissals_count += 1
        elif event_type == 'Exit_Intent':
            campaign.dismissals_count += 0

        campaign.spent_amount = _decimal(campaign.spent_amount) + _decimal(charge_amount)
        campaign.revenue_value = _decimal(campaign.revenue_value) + _decimal(conversion_value)

        clicks = campaign.clicks_count or 0
        impressions = campaign.impressions_count or 0
        leads = campaign.leads_count or 0
        dismissals = campaign.dismissals_count or 0
        ctr = (clicks / impressions) if impressions else 0.0
        lead_rate = (leads / clicks) if clicks else 0.0
        parcel_quality = _get_parcel_quality_score(campaign.parcel)
        seller_trust = _get_seller_trust_score(campaign.created_by)
        engagement_score = min(100.0, (ctr * 100.0 * 0.45) + (lead_rate * 100.0 * 0.35) + max(0.0, 35.0 - (dismissals * 2.5)))
        auction_score = min(100.0, _round_float(_decimal(campaign.priority_bid) / Decimal('1000.0') * 15.0) + parcel_quality * 0.25 + seller_trust * 0.15 + engagement_score * 0.4)
        spend = _decimal(campaign.spent_amount)
        revenue = _decimal(campaign.revenue_value)
        roi_score = float(revenue / spend) if spend > 0 else float(revenue)

        campaign.quality_score = parcel_quality
        campaign.engagement_score = engagement_score
        campaign.auction_score = auction_score
        campaign.roi_score = roi_score
        campaign.last_scored_at = timezone.now()
        campaign.save(
            update_fields=[
                'impressions_count',
                'clicks_count',
                'leads_count',
                'dismissals_count',
                'spent_amount',
                'revenue_value',
                'quality_score',
                'engagement_score',
                'auction_score',
                'roi_score',
                'last_scored_at',
                'updated_at',
            ]
        )

    if request is not None and getattr(request, 'session', None) is not None:
        state = _session_state(request)
        campaign_state = state['campaigns'].get(str(campaign.id), {})
        campaign_state['last_shown_at'] = timezone.now().isoformat()
        campaign_state['cooldown_minutes'] = campaign.cooldown_minutes
        campaign_state['frequency_cap_per_session'] = campaign.frequency_cap_per_session
        campaign_state['show_count'] = int(campaign_state.get('show_count', 0) or 0) + (1 if event_type == 'Impression' else 0)
        if event_type in {'Dismissed', 'Suppressed'}:
            campaign_state['dismiss_count'] = int(campaign_state.get('dismiss_count', 0) or 0) + 1
        if event_type == 'Click':
            campaign_state['click_count'] = int(campaign_state.get('click_count', 0) or 0) + 1
        state['campaigns'][str(campaign.id)] = campaign_state
        state['show_count'] = int(state.get('show_count', 0) or 0) + (1 if event_type in {'Impression', 'Exit_Intent'} else 0)
        _store_session_state(request, state)

    return {
        'event_id': str(event.id),
        'campaign_id': str(campaign.id),
        'event_type': event_type,
        'charge_amount': str(charge_amount),
        'conversion_value': str(conversion_value),
        'campaign': serialize_popup_campaign(campaign, user=user),
    }


def build_seller_promotions_dashboard(user):
    campaigns = PopupAdCampaign.objects.select_related('parcel', 'created_by')
    if getattr(user, 'role', None) != 'Admin':
        campaigns = campaigns.filter(created_by=user)

    campaigns = campaigns.order_by('-updated_at', '-created_at')
    events = PopupAdEvent.objects.filter(campaign__in=campaigns)

    total_impressions = sum(c.impressions_count for c in campaigns)
    total_clicks = sum(c.clicks_count for c in campaigns)
    total_leads = sum(c.leads_count for c in campaigns)
    total_dismissals = sum(c.dismissals_count for c in campaigns)
    total_spend = sum(_decimal(c.spent_amount) for c in campaigns)
    total_revenue = sum(_decimal(c.revenue_value) for c in campaigns)
    ctr = (total_clicks / total_impressions * 100.0) if total_impressions else 0.0
    lead_rate = (total_leads / total_clicks * 100.0) if total_clicks else 0.0
    roi = float(total_revenue / total_spend) if total_spend > 0 else float(total_revenue)

    county_rows = (
        events.values('county_context')
        .annotate(
            impressions=Count('id', filter=Q(event_type='Impression')),
            clicks=Count('id', filter=Q(event_type='Click')),
            leads=Count('id', filter=Q(event_type='Lead')),
            dismissals=Count('id', filter=Q(event_type='Dismissed')),
        )
        .order_by('-impressions', '-clicks')[:10]
    )

    trigger_rows = (
        events.values('campaign__popup_type')
        .annotate(
            impressions=Count('id', filter=Q(event_type='Impression')),
            clicks=Count('id', filter=Q(event_type='Click')),
            leads=Count('id', filter=Q(event_type='Lead')),
        )
        .order_by('-impressions')
    )

    top_campaigns = sorted(
        [serialize_popup_campaign(campaign, user=user) for campaign in campaigns],
        key=lambda item: (
            item['metrics']['roi'],
            item['metrics']['ctr'],
            item['metrics']['leads'],
            item['score'],
        ),
        reverse=True,
    )

    top_county = county_rows[0]['county_context'] if county_rows else None
    recommendations = []
    if top_county:
        recommendations.append(
            {
                'title': f'Lean into {top_county}',
                'body': 'This region is producing the most popup engagement. Raise bids or expand the radius to nearby wards.',
            }
        )
    if total_impressions and total_dismissals > total_impressions * 0.25:
        recommendations.append(
            {
                'title': 'Tighten frequency controls',
                'body': 'Dismissals are high. Reduce impression volume and lengthen the cooldown window.',
            }
        )
    if total_clicks and total_leads / max(total_clicks, 1) > 0.25:
        recommendations.append(
            {
                'title': 'Scale winning creatives',
                'body': 'Lead conversion is strong. Duplicate the best performing creative with a higher budget ceiling.',
            }
        )
    if not recommendations:
        recommendations.append(
            {
                'title': 'Keep learning',
                'body': 'The engine is still gathering data. Use active campaigns to feed the ranking loop and refine copy.',
            }
        )

    return {
        'campaigns': top_campaigns,
        'summary': {
            'total_campaigns': campaigns.count(),
            'active_campaigns': campaigns.filter(status='Active').count(),
            'paused_campaigns': campaigns.filter(status='Paused').count(),
            'draft_campaigns': campaigns.filter(status='Draft').count(),
            'total_impressions': total_impressions,
            'total_clicks': total_clicks,
            'total_leads': total_leads,
            'total_dismissals': total_dismissals,
            'ctr': round(ctr, 2),
            'lead_rate': round(lead_rate, 2),
            'total_spend': str(total_spend),
            'total_revenue': str(total_revenue),
            'roi': round(roi, 2),
        },
        'heatmap': [
            {
                'county': row['county_context'] or 'Unknown',
                'impressions': row['impressions'],
                'clicks': row['clicks'],
                'leads': row['leads'],
                'dismissals': row['dismissals'],
            }
            for row in county_rows
        ],
        'trigger_breakdown': [
            {
                'popup_type': row['campaign__popup_type'],
                'impressions': row['impressions'],
                'clicks': row['clicks'],
                'leads': row['leads'],
            }
            for row in trigger_rows
        ],
        'recommendations': recommendations,
        'supported_popup_types': [label for _, label in PopupAdCampaign.POPUP_TYPE_CHOICES],
        'supported_billing_models': [label for _, label in PopupAdCampaign.BILLING_CHOICES],
        'campaign_action_url': reverse('frontend:seller_promotions'),
        'events_count': events.count(),
    }
