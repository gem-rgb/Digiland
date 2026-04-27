"""
Personalized Parcel Recommendation Engine
==========================================
Netflix-style content-based filtering using cosine similarity.

User profile is built from implicit signals (page views, favorites, escrow initiations)
weighted by interaction strength and recency.
"""
import logging
from collections import Counter
from decimal import Decimal

from django.db.models import Count, Q

logger = logging.getLogger(__name__)


def _build_user_profile(user):
    """
    Build a weighted preference profile from the user's interaction history.
    Returns a dict of feature weights: {county: weight, land_use: weight, ...}
    """
    from core.models import ParcelView, UserFavorite, Transaction, LandParcel

    profile = {
        'counties': Counter(),
        'land_uses': Counter(),
        'constituencies': Counter(),
        'price_sum': Decimal('0'),
        'price_count': 0,
        'size_sum': Decimal('0'),
        'size_count': 0,
    }

    # ── Implicit signal 1: Page views (weight=1) ──
    views = ParcelView.objects.filter(user=user).select_related('parcel').order_by('-viewed_at')[:100]
    for i, v in enumerate(views):
        # Recency decay: most recent views get higher weight
        recency_weight = max(0.3, 1.0 - (i * 0.01))
        weight = 1.0 * recency_weight
        p = v.parcel
        profile['counties'][p.county] += weight
        profile['land_uses'][p.land_use_type] += weight
        profile['constituencies'][p.constituency] += weight
        if p.asking_price:
            profile['price_sum'] += p.asking_price * Decimal(str(weight))
            profile['price_count'] += weight
        profile['size_sum'] += p.land_size * Decimal(str(weight))
        profile['size_count'] += weight

    # ── Implicit signal 2: Favorites (weight=3) ──
    favorites = UserFavorite.objects.filter(user=user).select_related('parcel')
    for fav in favorites:
        weight = 3.0
        p = fav.parcel
        profile['counties'][p.county] += weight
        profile['land_uses'][p.land_use_type] += weight
        profile['constituencies'][p.constituency] += weight
        if p.asking_price:
            profile['price_sum'] += p.asking_price * Decimal(str(weight))
            profile['price_count'] += weight
        profile['size_sum'] += p.land_size * Decimal(str(weight))
        profile['size_count'] += weight

    # ── Implicit signal 3: Escrow initiations (weight=5) ──
    transactions = Transaction.objects.filter(buyer=user).select_related('land_parcel')
    for tx in transactions:
        weight = 5.0
        p = tx.land_parcel
        profile['counties'][p.county] += weight
        profile['land_uses'][p.land_use_type] += weight
        profile['constituencies'][p.constituency] += weight
        if p.asking_price:
            profile['price_sum'] += p.asking_price * Decimal(str(weight))
            profile['price_count'] += weight
        profile['size_sum'] += p.land_size * Decimal(str(weight))
        profile['size_count'] += weight

    return profile


def _score_parcel(parcel, profile):
    """
    Score a parcel against the user profile.
    Higher score = better match.
    """
    score = 0.0

    # County match (strongest signal)
    if profile['counties']:
        max_county_weight = max(profile['counties'].values()) if profile['counties'] else 1
        county_score = profile['counties'].get(parcel.county, 0) / max_county_weight
        score += county_score * 40  # 40% weight

    # Land use match
    if profile['land_uses']:
        max_lu_weight = max(profile['land_uses'].values()) if profile['land_uses'] else 1
        lu_score = profile['land_uses'].get(parcel.land_use_type, 0) / max_lu_weight
        score += lu_score * 25  # 25% weight

    # Constituency match (locality bonus)
    if profile['constituencies']:
        max_con_weight = max(profile['constituencies'].values()) if profile['constituencies'] else 1
        con_score = profile['constituencies'].get(parcel.constituency, 0) / max_con_weight
        score += con_score * 15  # 15% weight

    # Price similarity (prefer parcels near the user's average browsed price)
    if profile['price_count'] > 0 and parcel.asking_price:
        avg_price = profile['price_sum'] / Decimal(str(profile['price_count']))
        if avg_price > 0:
            price_ratio = float(min(parcel.asking_price, avg_price) / max(parcel.asking_price, avg_price))
            score += price_ratio * 12  # 12% weight

    # Size similarity
    if profile['size_count'] > 0:
        avg_size = profile['size_sum'] / Decimal(str(profile['size_count']))
        if avg_size > 0:
            size_ratio = float(min(parcel.land_size, avg_size) / max(parcel.land_size, avg_size))
            score += size_ratio * 8  # 8% weight

    return round(score, 2)


def get_recommendations(user, limit=12):
    """
    Get personalized parcel recommendations for a user.
    Returns a list of (parcel, score) tuples sorted by relevance.
    """
    from core.models import LandParcel, ParcelView, UserFavorite, Transaction

    # Only recommend verified parcels not already in active transactions
    active_tx_statuses = ['Initiated', 'Deposit_Paid', 'Under_Verification', 'Completed']
    available_parcels = LandParcel.objects.filter(
        verification_status='Verified'
    ).exclude(
        transactions__status__in=active_tx_statuses
    ).exclude(
        listed_by=user  # Don't recommend user's own parcels
    )

    profile = _build_user_profile(user)

    # Check if user has any interaction history
    has_history = bool(profile['counties'])

    if not has_history:
        # Cold start: return most popular parcels by view count
        popular = available_parcels.annotate(
            view_count=Count('views')
        ).order_by('-view_count', '-ardhisasa_last_synced')[:limit]
        return [(p, 0) for p in popular], 'popular'

    # Score each available parcel
    scored = []
    # Exclude already-viewed and already-purchased parcels from primary recommendations
    viewed_ids = set(
        ParcelView.objects.filter(user=user).values_list('parcel_id', flat=True)
    )
    purchased_ids = set(
        Transaction.objects.filter(buyer=user).values_list('land_parcel_id', flat=True)
    )
    exclude_ids = viewed_ids | purchased_ids

    for parcel in available_parcels:
        if parcel.id in exclude_ids:
            continue
        score = _score_parcel(parcel, profile)
        scored.append((parcel, score))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    # If we don't have enough unseen parcels, fill with viewed but not purchased
    if len(scored) < limit:
        for parcel in available_parcels:
            if parcel.id in purchased_ids:
                continue
            if parcel.id not in exclude_ids:
                continue
            score = _score_parcel(parcel, profile)
            scored.append((parcel, score * 0.7))  # Slightly lower score for re-recommendations

        scored.sort(key=lambda x: x[1], reverse=True)

    return scored[:limit], 'personalized'


def get_popular_in_county(user, county=None, limit=6):
    """
    Get most popular parcels in a specific county.
    If no county specified, uses the user's most-browsed county.
    """
    from core.models import LandParcel, ParcelView

    if not county:
        # Find user's most browsed county
        profile = _build_user_profile(user)
        if profile['counties']:
            county = profile['counties'].most_common(1)[0][0]
        else:
            county = 'Nairobi'  # Default fallback

    active_tx_statuses = ['Initiated', 'Deposit_Paid', 'Under_Verification', 'Completed']
    parcels = LandParcel.objects.filter(
        verification_status='Verified',
        county=county
    ).exclude(
        transactions__status__in=active_tx_statuses
    ).exclude(
        listed_by=user
    ).annotate(
        view_count=Count('views')
    ).order_by('-view_count', '-ardhisasa_last_synced')[:limit]

    return parcels, county


def get_recently_viewed(user, limit=6):
    """Get user's recently viewed parcels."""
    from core.models import ParcelView

    recent_views = ParcelView.objects.filter(
        user=user
    ).select_related('parcel').order_by('-viewed_at')

    # Deduplicate while preserving order
    seen_ids = set()
    parcels = []
    for view in recent_views:
        if view.parcel_id not in seen_ids:
            seen_ids.add(view.parcel_id)
            parcels.append(view.parcel)
            if len(parcels) >= limit:
                break

    return parcels
