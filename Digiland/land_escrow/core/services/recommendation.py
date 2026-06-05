"""
Premium Land Recommendation & Discovery Engine
=============================================
Social-media grade hybrid recommendation system combining:
1. Content-Based Filtering (Cosine proximity on county, size, land use, infrastructure)
2. Collaborative Filtering (User-to-user similarity, search patterns)
3. Geo-Spatial Layer (Radius search, demand density, coordinate math)
4. Engagement Optimization (Boosts listings with high CTR, save rate, and conversions)
5. Promotion Injection (Basic, Pro, and Elite sponsored ads placement)
"""

import logging
import math
from collections import Counter, defaultdict
from decimal import Decimal
from django.db.models import Count, Q, Avg
from core.models import (
    LandParcel, ParcelView, UserFavorite, Transaction,
    LandPromotion, PromotionAnalyticsLog, SearchQueryLog,
    BuyerInterestProfile, BuyerEngagementSignal, User
)

logger = logging.getLogger(__name__)

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in km between two coordinate pairs."""
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None
    try:
        lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 6371.0  # Earth's radius in kilometers
        return c * r
    except Exception as e:
        logger.error(f"Error computing distance: {e}")
        return None

def update_buyer_interest_profile(user):
    """Automatically categorize buyer and compute preference statistics based on signals."""
    if not user.is_authenticated or user.role != 'Buyer':
        return None

    # Get or create interest profile
    profile, created = BuyerInterestProfile.objects.get_or_create(user=user)

    # 1. Gather signals
    views = ParcelView.objects.filter(user=user).select_related('parcel')
    favorites = UserFavorite.objects.filter(user=user).select_related('parcel')
    purchases = Transaction.objects.filter(buyer=user).select_related('land_parcel')
    searches = SearchQueryLog.objects.filter(user=user)
    signals = BuyerEngagementSignal.objects.filter(user=user).select_related('parcel')

    # Count categories and features
    counties = Counter()
    land_uses = Counter()
    prices = []
    sizes = []
    latitudes = []
    longitudes = []

    # Map signals
    for v in views:
        counties[v.parcel.county] += 1
        land_uses[v.parcel.land_use_type] += 1
        if v.parcel.asking_price:
            prices.append(v.parcel.asking_price)
        sizes.append(v.parcel.land_size)
        if v.parcel.latitude and v.parcel.longitude:
            latitudes.append(v.parcel.latitude)
            longitudes.append(v.parcel.longitude)

    for f in favorites:
        counties[f.parcel.county] += 3
        land_uses[f.parcel.land_use_type] += 3
        if f.parcel.asking_price:
            prices.append(f.parcel.asking_price)
        sizes.append(f.parcel.land_size)

    for p in purchases:
        counties[p.land_parcel.county] += 5
        land_uses[p.land_parcel.land_use_type] += 5
        if p.land_parcel.asking_price:
            prices.append(p.land_parcel.asking_price)
        sizes.append(p.land_parcel.land_size)

    # Set preferred county list (top 3)
    profile.preferred_counties = [c for c, _ in counties.most_common(3)]

    # Set budget bounds
    if prices:
        avg_price = sum(prices) / len(prices)
        profile.budget_min = max(Decimal('0'), avg_price * Decimal('0.6'))
        profile.budget_max = avg_price * Decimal('1.6')
    else:
        profile.budget_min = None
        profile.budget_max = None

    # Set acreage bounds
    if sizes:
        avg_size = sum(sizes) / len(sizes)
        profile.preferred_acreage_min = max(Decimal('0'), avg_size * Decimal('0.5'))
        profile.preferred_acreage_max = avg_size * Decimal('2.0')
    else:
        profile.preferred_acreage_min = None
        profile.preferred_acreage_max = None

    # Set preferred land use
    if land_uses:
        profile.preferred_land_use = land_uses.most_common(1)[0][0]

    # Set centroid coordinates
    if latitudes and longitudes:
        profile.last_location_lat = sum(latitudes) / len(latitudes)
        profile.last_location_lng = sum(longitudes) / len(longitudes)

    # Automatically categorize buyer
    # Rules:
    # - Average budget > KES 15M -> Luxury Buyer
    # - Mostly agricultural land -> Agricultural Investor
    # - Mostly commercial land -> Commercial Developer
    # - Speculator: highly active saves, searches, views, and inquiry signals
    # - Diaspora: indicator based on search text or user custom tags (mock check)
    total_signals = views.count() + favorites.count() + purchases.count() + signals.count()
    avg_price_num = float(sum(prices) / len(prices)) if prices else 0.0

    category = 'Residential'
    if avg_price_num > 15000000:
        category = 'Luxury'
    elif profile.preferred_land_use == 'Agricultural':
        category = 'Agricultural'
    elif profile.preferred_land_use == 'Commercial':
        category = 'Commercial'
    elif total_signals > 40:
        category = 'Speculator'
    
    # Check for diaspora indicators in query keywords
    for search in searches:
        if any(kw in search.query.lower() for kw in ['diaspora', 'abroad', 'foreign', 'investment', 'currency']):
            category = 'Diaspora'
            break

    profile.category = category
    profile.save()
    return profile

def get_listings_ctr_boosts():
    """Calculate Click-Through Rate (CTR) and Save Rate boosts for active listings."""
    boosts = {}
    promotions = LandPromotion.objects.filter(is_active=True, payment_status='Paid')
    
    for promo in promotions:
        impressions = PromotionAnalyticsLog.objects.filter(promotion=promo, event_type='Impression').count()
        clicks = PromotionAnalyticsLog.objects.filter(promotion=promo, event_type='Click').count()
        saves = UserFavorite.objects.filter(parcel=promo.parcel).count()
        views = ParcelView.objects.filter(parcel=promo.parcel).count()
        
        ctr = clicks / max(impressions, 1)
        save_rate = saves / max(views, 1)
        
        # Boost factor based on tier and organic performance
        tier_weight = {'Elite': 2.0, 'Pro': 1.5, 'Basic': 1.1}.get(promo.tier, 1.0)
        performance_boost = (ctr * 10) + (save_rate * 5)
        
        boosts[promo.parcel.id] = float(tier_weight) + performance_boost
        
        # Write back to cached fields
        promo.impressions_count = impressions
        promo.clicks_count = clicks
        promo.views_count = views
        promo.inquiries_count = PromotionAnalyticsLog.objects.filter(promotion=promo, event_type='Inquiry').count()
        promo.save(update_fields=['impressions_count', 'clicks_count', 'views_count', 'inquiries_count'])
        
    return boosts

def _score_listing(parcel, profile, ctr_boosts, user=None):
    """Compute premium hybrid matching score (0 to 100) for a parcel."""
    score = 50.0 # base score

    # 1. Content-based: Land use type alignment
    if profile.preferred_land_use:
        if parcel.land_use_type == profile.preferred_land_use:
            score += 15.0
        else:
            score -= 5.0

    # 2. Location intelligence: Preferred county
    if profile.preferred_counties:
        if parcel.county in profile.preferred_counties:
            score += 10.0
            if profile.preferred_counties[0] == parcel.county:
                score += 5.0  # Top county bonus
        else:
            score -= 10.0

    # 3. Financial signals: Budget alignment
    if profile.budget_min and profile.budget_max and parcel.asking_price:
        if profile.budget_min <= parcel.asking_price <= profile.budget_max:
            score += 10.0
        else:
            # Out of bounds penalty
            diff_pct = float(abs(parcel.asking_price - (profile.budget_min + profile.budget_max)/2) / ((profile.budget_min + profile.budget_max)/2))
            score -= min(15.0, diff_pct * 10.0)

    # 4. Geospatial proximity
    if profile.last_location_lat and profile.last_location_lng and parcel.latitude and parcel.longitude:
        distance = haversine_distance(profile.last_location_lat, profile.last_location_lng, parcel.latitude, parcel.longitude)
        if distance is not None:
            if distance < 5.0:
                score += 10.0  # within 5km radius
            elif distance < 20.0:
                score += 5.0   # within 20km radius
            else:
                score -= min(5.0, distance * 0.1)

    # 5. Infrastructure proximity bonuses
    # Prefer parcels with close access to roads, transport hubs, schools
    infra_points = 0.0
    if parcel.dist_to_road <= 0.5: infra_points += 2.0
    if parcel.dist_to_transport_hub <= 2.0: infra_points += 2.0
    if parcel.dist_to_school <= 2.0: infra_points += 1.0
    if parcel.dist_to_hospital <= 3.0: infra_points += 1.0
    score += infra_points

    # 6. Engagement & CTR Boost
    boost = ctr_boosts.get(parcel.id, 1.0)
    score = score * boost

    # 7. Promotion boosts (Elite gets massive rank boost, Pro gets moderate, Basic gets minor)
    active_promos = LandPromotion.objects.filter(parcel=parcel, is_active=True, payment_status='Paid')
    if active_promos.exists():
        tier = active_promos.first().tier
        promo_boost = {'Elite': 20.0, 'Pro': 12.0, 'Basic': 5.0}.get(tier, 0.0)
        score += promo_boost

    # Cap between 0 and 100
    return round(max(0.0, min(100.0, score)), 2)

def _available_recommendation_parcels(user, exclude_self=True):
    """Return verified parcels that are available for recommendation surfaces."""
    active_tx_statuses = ['Initiated', 'Deposit_Paid', 'Under_Verification', 'Completed']
    parcels = LandParcel.objects.filter(
        verification_status='Verified'
    ).exclude(
        transactions__status__in=active_tx_statuses
    )

    if exclude_self and getattr(user, 'is_authenticated', False):
        parcels = parcels.exclude(listed_by=user)

    return parcels.distinct()

def _primary_promotion(parcel):
    """Return the most relevant active paid promotion for a parcel, if any."""
    return parcel.promotions.filter(is_active=True, payment_status='Paid').first()

def _promotion_rank(tier):
    return {'Elite': 0, 'Pro': 1, 'Basic': 2}.get(tier, 99)

def get_popular_in_county(user, limit=6, profile=None):
    """Popular parcels in the buyer's top county or a Nairobi fallback."""
    county = 'Nairobi'
    if user.is_authenticated and user.role == 'Buyer':
        profile = profile or update_buyer_interest_profile(user)
        if profile and profile.preferred_counties:
            county = profile.preferred_counties[0]

    parcels = _available_recommendation_parcels(user).filter(county=county).annotate(
        view_count=Count('views', distinct=True),
        favorite_count=Count('favorited_by', distinct=True),
    ).order_by('-view_count', '-favorite_count', '-ardhisasa_last_synced')

    return list(parcels[:limit]), county

def get_recently_viewed(user, limit=6):
    """Return the user's most recently viewed verified parcels."""
    if not user.is_authenticated or user.role != 'Buyer':
        return []

    recent_views = ParcelView.objects.filter(user=user).select_related('parcel').order_by('-viewed_at')
    parcels = []
    seen_ids = set()

    for view in recent_views:
        parcel = view.parcel
        if not parcel or parcel.id in seen_ids:
            continue
        if parcel.verification_status != 'Verified':
            continue
        if parcel.listed_by_id == user.id:
            continue
        parcels.append(parcel)
        seen_ids.add(parcel.id)
        if len(parcels) >= limit:
            break

    return parcels

def build_recommendation_feed(user, limit=12):
    """Build every recommendation section used by the buyer feed."""
    recommended, rec_type = get_recommendations(user, limit=limit)
    profile = BuyerInterestProfile.objects.filter(user=user).first() if getattr(user, 'is_authenticated', False) and getattr(user, 'role', None) == 'Buyer' else None
    popular_parcels, popular_county = get_popular_in_county(user, limit=min(6, limit), profile=profile)
    recently_viewed = get_recently_viewed(user, limit=min(6, limit))
    recently_viewed_similar = get_recently_viewed_similar(user, limit=min(6, limit))
    hot_deals = get_hot_deals(user, limit=min(6, limit))
    trending_in_target_area = get_trending_in_target_area(user, limit=min(6, limit), profile=profile)
    people_also_viewed = get_people_also_viewed(user, limit=min(6, limit))
    sponsored_listings = get_sponsored_listings(user, limit=min(6, limit))

    return {
        'recommended': recommended,
        'rec_type': rec_type,
        'popular_parcels': popular_parcels,
        'popular_county': popular_county,
        'recently_viewed': recently_viewed,
        'recently_viewed_similar': recently_viewed_similar,
        'hot_deals': hot_deals,
        'trending_in_target_area': trending_in_target_area,
        'people_also_viewed': people_also_viewed,
        'sponsored_listings': sponsored_listings,
        'buyer_category': getattr(profile, 'category', None),
    }

def get_recommendations(user, limit=12):
    """
    Personalized Recommendations Feed: 'Recommended Land For You'.
    Injects sponsored Elite and Pro campaigns matching targeted parameters.
    """
    # 1. Warm start vs Cold Start checking
    if not user.is_authenticated or user.role != 'Buyer':
        # Guest cold start: return trending listings
        trending = LandParcel.objects.filter(verification_status='Verified').exclude(
            transactions__status__in=['Initiated', 'Deposit_Paid', 'Under_Verification', 'Completed']
        ).annotate(view_count=Count('views')).order_by('-view_count')[:limit]
        return [(p, 80.0) for p in trending], 'popular'

    # 2. Get/Update profile
    profile = update_buyer_interest_profile(user)
    ctr_boosts = get_listings_ctr_boosts()

    # 3. Fetch potential recommendations
    available_parcels = _available_recommendation_parcels(user)

    scored_list = []
    for parcel in available_parcels:
        score = _score_listing(parcel, profile, ctr_boosts, user)
        scored_list.append((parcel, score))

    # Sort descending by score
    scored_list.sort(key=lambda x: x[1], reverse=True)

    # 4. Inject the most relevant sponsored listings at the very top.
    sponsored_candidates = []
    score_lookup = {parcel.id: score for parcel, score in scored_list}
    parcel_lookup = {parcel.parcel_number: parcel for parcel in available_parcels}
    for parcel in available_parcels.filter(
        promotions__is_active=True,
        promotions__payment_status='Paid'
    ).distinct():
        promo = _primary_promotion(parcel)
        if not promo:
            continue
        asking_price_rank = -float(parcel.asking_price) if parcel.asking_price else 0.0
        sponsored_candidates.append((
            _promotion_rank(promo.tier),
            -score_lookup.get(parcel.id, 0.0),
            asking_price_rank,
            parcel.parcel_number,
        ))
    sponsored_candidates.sort()

    final_results = []
    injected_ids = set()

    # Place top sponsored listings first while respecting the feed limit.
    for index, (_, _, _, parcel_number) in enumerate(sponsored_candidates[:3]):
        promoted_parcel = parcel_lookup.get(parcel_number)
        if not promoted_parcel:
            continue
        final_results.append((promoted_parcel, 99.9 - (index * 0.1)))
        injected_ids.add(promoted_parcel.id)
        if len(final_results) >= limit:
            break

    # Add remaining personalized recommendations
    for p, score in scored_list:
        if p.id not in injected_ids:
            final_results.append((p, score))
            injected_ids.add(p.id)
        if len(final_results) >= limit:
            break

    return final_results, 'personalized'

def get_hot_deals(user, limit=6):
    """Hot Deals Near You: listing discounts and radius proximity matching."""
    active_tx_statuses = ['Initiated', 'Deposit_Paid', 'Under_Verification', 'Completed']
    parcels = LandParcel.objects.filter(verification_status='Verified').exclude(
        transactions__status__in=active_tx_statuses
    )

    if user.is_authenticated and user.role == 'Buyer':
        parcels = parcels.exclude(listed_by=user)

    # Sort by lowest asking price relative to area averages or average overall
    avg_price = parcels.aggregate(avg=Avg('asking_price'))['avg'] or Decimal('5000000')
    
    # Calculate a custom discount/deal score
    scored = []
    for p in parcels:
        deal_score = 50.0
        if p.asking_price and p.asking_price < avg_price:
            deal_score += float((avg_price - p.asking_price) / avg_price) * 30.0
            
        # Proximity bonus if user location is known
        if user.is_authenticated and user.role == 'Buyer':
            profile = getattr(user, 'interest_profile', None)
            if profile and profile.last_location_lat and profile.last_location_lng and p.latitude and p.longitude:
                dist = haversine_distance(profile.last_location_lat, profile.last_location_lng, p.latitude, p.longitude)
                if dist and dist < 15.0:
                    deal_score += 20.0
                    
        # Sponsored listings boost
        if p.promotions.filter(is_active=True, payment_status='Paid').exists():
            deal_score += 10.0
            
        scored.append((p, round(min(100.0, deal_score), 2)))
        
    scored.sort(key=lambda x: x[1], reverse=True)
    return [item[0] for item in scored[:limit]]

def get_trending_in_target_area(user, limit=6, profile=None):
    """Trending In Your Target Area: county popularity and view rate spikes."""
    target_county = 'Nairobi'
    if user.is_authenticated and user.role == 'Buyer':
        profile = profile or update_buyer_interest_profile(user)
        if profile and profile.preferred_counties:
            target_county = profile.preferred_counties[0]

    active_tx_statuses = ['Initiated', 'Deposit_Paid', 'Under_Verification', 'Completed']
    parcels = LandParcel.objects.filter(
        verification_status='Verified',
        county=target_county
    ).exclude(
        transactions__status__in=active_tx_statuses
    ).annotate(
        views_count=Count('views'),
        favorites_count=Count('favorited_by')
    )

    if user.is_authenticated and user.role == 'Buyer':
        parcels = parcels.exclude(listed_by=user)

    # Sort by views + 2*favorites + active elite/pro boosts
    scored = []
    for p in parcels:
        trend_score = p.views_count + (p.favorites_count * 3)
        promotions = p.promotions.filter(is_active=True, payment_status='Paid')
        if promotions.exists():
            trend_score += 15
        scored.append((p, trend_score))
        
    scored.sort(key=lambda x: x[1], reverse=True)
    return [item[0] for item in scored[:limit]]

def get_recently_viewed_similar(user, limit=6):
    """Recently Viewed Similar Lands: Content matching on county and type."""
    if not user.is_authenticated or user.role != 'Buyer':
        return []

    # Get user's last viewed parcel
    last_view = ParcelView.objects.filter(user=user).order_by('-viewed_at').first()
    if not last_view:
        return []

    source_parcel = last_view.parcel
    active_tx_statuses = ['Initiated', 'Deposit_Paid', 'Under_Verification', 'Completed']
    similar_parcels = LandParcel.objects.filter(
        verification_status='Verified',
        county=source_parcel.county,
        land_use_type=source_parcel.land_use_type
    ).exclude(
        id=source_parcel.id
    ).exclude(
        transactions__status__in=active_tx_statuses
    ).exclude(
        listed_by=user
    )[:limit]

    return list(similar_parcels)

def get_people_also_viewed(user, limit=6):
    """People Also Viewed: Collaborative filtering overlap match."""
    if not user.is_authenticated or user.role != 'Buyer':
        return []

    # 1. Find other users who viewed what current user viewed
    my_viewed_ids = set(ParcelView.objects.filter(user=user).values_list('parcel_id', flat=True))
    if not my_viewed_ids:
        # Fallback to general popular
        return get_hot_deals(user, limit)

    similar_users = ParcelView.objects.filter(
        parcel_id__in=my_viewed_ids
    ).exclude(
        user=user
    ).values_list('user_id', flat=True).distinct()

    # 2. Query what those users viewed that current user has NOT viewed
    active_tx_statuses = ['Initiated', 'Deposit_Paid', 'Under_Verification', 'Completed']
    recommendations = LandParcel.objects.filter(
        views__user_id__in=similar_users,
        verification_status='Verified'
    ).exclude(
        id__in=my_viewed_ids
    ).exclude(
        transactions__status__in=active_tx_statuses
    ).exclude(
        listed_by=user
    ).annotate(
        similar_views=Count('views')
    ).order_by('-similar_views')[:limit]

    return list(recommendations)

def get_sponsored_listings(user, limit=6):
    """Premium Sponsored Lands: exclusively Basic, Pro, Elite promotions."""
    active_tx_statuses = ['Initiated', 'Deposit_Paid', 'Under_Verification', 'Completed']
    sponsored_parcels = LandParcel.objects.filter(
        verification_status='Verified',
        promotions__is_active=True,
        promotions__payment_status='Paid'
    ).exclude(
        transactions__status__in=active_tx_statuses
    ).distinct()

    if user.is_authenticated and user.role == 'Buyer':
        sponsored_parcels = sponsored_parcels.exclude(listed_by=user)

    # Sort Elite first, then Pro, then Basic
    scored = []
    for p in sponsored_parcels:
        promo = p.promotions.filter(is_active=True, payment_status='Paid').first()
        tier_score = {'Elite': 3, 'Pro': 2, 'Basic': 1}.get(promo.tier, 0)
        scored.append((p, tier_score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [item[0] for item in scored[:limit]]
