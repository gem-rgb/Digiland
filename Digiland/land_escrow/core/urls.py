from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from . import api_views
from . import sse_views
from . import webhook_views

router = DefaultRouter()
router.register(r'land-parcels', views.LandParcelViewSet)
router.register(r'transactions', views.TransactionViewSet)
router.register(r'documents', views.DocumentViewSet)

# New ViewSets
router.register(r'promotions', api_views.LandPromotionViewSet, basename='land-promotion')
router.register(r'popup-campaigns', api_views.PopupAdCampaignViewSet, basename='popup-campaign')
router.register(r'sponsored-ads', api_views.SponsoredAdViewSet, basename='sponsored-ad')
router.register(r'kyc-applications', api_views.AgentKYCApplicationViewSet, basename='kyc-application')
router.register(r'kyc-profiles', api_views.KYCProfileViewSet, basename='kyc-profile')
router.register(r'joint-groups', api_views.JointBuyerGroupViewSet, basename='joint-group')
router.register(r'joint-members', api_views.JointBuyerMemberViewSet, basename='joint-member')
router.register(r'joint-contributions', api_views.JointPaymentContributionViewSet, basename='joint-contribution')
router.register(r'accounts', api_views.AccountViewSet, basename='account')
router.register(r'decisions', api_views.AccountDecisionViewSet, basename='account-decision')
router.register(r'property-owners', api_views.PropertyOwnerViewSet, basename='property-owner')

urlpatterns = [
    # ==================== ACCOUNT & MULTI-MEMBER ====================
    path('accounts/current/', api_views.current_user_accounts_api, name='accounts-current'),
    path('accounts/<uuid:account_id>/dashboard/', api_views.account_dashboard_feed_api, name='account-dashboard-feed'),

    # ==================== AUTH ====================
    path('auth/register', views.register_user, name='register'),
    path('auth/login', views.login_user, name='login'),
    path('users/<uuid:id>/verify-identity', views.verify_identity, name='verify-identity'),

    # ==================== CORE (from existing views.py) ====================
    path('', include(router.urls)),

    # ==================== PAYMENTS (existing) ====================
    path('payments/deposit', views.payment_deposit, name='payment-deposit'),
    path('payments/callback', views.payment_callback, name='payment-callback'),
    path('payments/<uuid:transaction_id>/release', views.payment_release, name='payment-release'),
    path('payments/<uuid:transaction_id>/refund', views.payment_refund, name='payment-refund'),

    # ==================== GAVACONNECT VERIFICATION (preserved) ====================
    path('verification/kra-pin', api_views.verify_kra_pin_view, name='verify-kra-pin'),
    path('verification/identity', api_views.verify_identity_view, name='verify-identity-api'),
    path('verification/business', api_views.verify_business_view, name='verify-business'),

    # ==================== M-PESA DARAJA (preserved) ====================
    path('mpesa/initiate', api_views.initiate_mpesa_payment_view, name='initiate-mpesa'),
    path('mpesa/status', api_views.query_mpesa_status_view, name='query-mpesa-status'),
    path('mpesa/callback', api_views.MpesaCallbackView.as_view(), name='mpesa-callback'),
    path('mpesa/callback/', api_views.MpesaCallbackView.as_view(), name='mpesa-callback-slash'),
    path('mpesa/b2b', api_views.b2b_payment_view, name='b2b-payment'),
    path('mpesa/reverse', api_views.reverse_transaction_view, name='reverse-transaction'),
    path('mpesa/transaction-status', api_views.query_transaction_status_view, name='query-transaction-status'),
    path('mpesa/balance', api_views.query_account_balance_view, name='query-account-balance'),
    path('mpesa/c2b-simulate', api_views.simulate_c2b_payment_view, name='simulate-c2b-payment'),
    path('mpesa/bonga-redeem', api_views.redeem_bonga_points_view, name='redeem-bonga-points'),
    path('mpesa/bonga-calculate', api_views.calculate_bonga_points_view, name='calculate-bonga-points'),
    path('mpesa/check-checkout-status/', api_views.check_checkout_status_view, name='check-checkout-status'),
    path('payments/<uuid:payment_id>/status/', api_views.payment_status_api_view, name='payment-status-api'),
    path('transactions/<str:transaction_ref>/payment-status/', api_views.transaction_payment_status_api_view, name='transaction-payment-status-api'),
    path('payments/reconciliation/', api_views.payment_reconciliation_api_view, name='payment-reconciliation-api'),
    path('payments/reconciliation/summary/', api_views.payment_reconciliation_summary_api_view, name='payment-reconciliation-summary-api'),

    # ==================== PROMOTION TIERS & PLANS ====================
    path('promotion-tiers/', api_views.PromotionTierListView.as_view(), name='promotion-tiers'),
    path('promotion-plans/', api_views.PromotionPlanCreateView.as_view(), name='promotion-plans-create'),
    path('promotion-plans/mine/', api_views.PromotionPlanMineView.as_view(), name='promotion-plans-mine'),

    # ==================== RECOMMENDATIONS ====================
    path('recommendations/', api_views.recommendations_feed, name='recommendations-feed'),
    path('recommendations/popular/', api_views.popular_listings, name='popular-listings'),
    path('recommendations/trending/', api_views.trending_listings, name='trending-listings'),
    path('recommendations/sponsored/', api_views.sponsored_listings, name='sponsored-listings'),
    path('recommendations/track-view/', api_views.track_parcel_view, name='track-view'),
    path('recommendations/track-favorite/', api_views.track_favorite, name='track-favorite'),
    path('recommendations/track-search/', api_views.track_search_query, name='track-search'),
    path('buyer-profile/', api_views.BuyerInterestProfileView.as_view(), name='buyer-profile'),

    # ==================== POPUP ADS ====================
    path('popup-ads/', api_views.popup_ads_for_page, name='popup-ads'),
    path('popup-ads/<uuid:pk>/event/', api_views.record_popup_ad_event, name='popup-ad-event'),

    # ==================== SERVICE FEES ====================
    path('service-fees/calculate/', api_views.calculate_service_fees, name='calculate-service-fees'),
    path('service-fees/explanations/', api_views.fee_explanations, name='fee-explanations'),
    path('service-fees/<uuid:transaction_id>/', api_views.transaction_service_fees, name='transaction-service-fees'),

    # ==================== ANALYTICS ====================
    path('analytics/parcel/<uuid:pk>/', api_views.parcel_analytics, name='parcel-analytics'),
    path('analytics/seller/ads/', api_views.seller_ad_performance, name='seller-ad-performance'),
    path('analytics/trending/', api_views.trending_locations, name='trending-locations'),
    path('analytics/recommendations/', api_views.recommendation_performance, name='recommendation-performance'),
    path('analytics/buyer-segments/', api_views.buyer_segment_analytics, name='buyer-segments'),
    path('analytics/platform-revenue/', api_views.platform_revenue, name='platform-revenue'),

    # ==================== ADMIN ====================
    path('admin/dashboard/', api_views.admin_dashboard, name='admin-dashboard'),
    path('admin/search/', api_views.admin_global_search_api, name='admin-global-search'),
    path('admin/revenue/', api_views.admin_revenue, name='admin-revenue'),
    path('admin/revenue/monthly/', api_views.admin_revenue_monthly, name='admin-revenue-monthly'),
    path('admin/fraud/high-risk/', api_views.high_risk_users, name='high-risk-users'),
    path('admin/fraud/flagged/', api_views.flagged_users, name='flagged-users'),
    path('admin/fraud/<uuid:pk>/approve/', api_views.approve_flagged_user, name='approve-flagged-user'),
    path('audit-logs/', api_views.AuditLogListView.as_view(), name='audit-logs'),

    # ==================== FRAUD ====================
    path('fraud/user/<uuid:pk>/score/', api_views.user_fraud_score, name='user-fraud-score'),
    path('fraud/parcel/<uuid:pk>/duplicates/', api_views.check_duplicate_listings, name='check-duplicate-listings'),
    path('fraud/flag/', api_views.flag_user_for_review, name='flag-user'),

    # ==================== STRIPE ====================
    path('payments/stripe/create/', api_views.stripe_create_payment_intent, name='stripe-create-payment-intent'),
    path('payments/stripe/webhook/', api_views.stripe_webhook_view, name='stripe-webhook'),

    # ==================== PRICE PREDICTION ====================
    path('price-prediction/', api_views.price_prediction_api, name='price-prediction-api'),

    # ==================== REALTIME MESSAGING & NOTIFICATIONS ====================
    path('messages/stream/', sse_views.message_stream, name='messages-stream-api'),
    path('messages/acknowledge/', sse_views.acknowledge_delivery, name='messages-acknowledge-api'),
    path('webhooks/resend/', webhook_views.resend_webhook, name='resend-webhook'),
]

