from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from . import api_views

router = DefaultRouter()
router.register(r'land-parcels', views.LandParcelViewSet)
router.register(r'transactions', views.TransactionViewSet)
router.register(r'documents', views.DocumentViewSet)

urlpatterns = [
    path('auth/register', views.register_user, name='register'),
    path('auth/login', views.login_user, name='login'),
    path('users/<uuid:id>/verify-identity', views.verify_identity, name='verify-identity'),
    
    path('', include(router.urls)),
    
    path('payments/deposit', views.payment_deposit, name='payment-deposit'),
    path('payments/callback', views.payment_callback, name='payment-callback'),
    path('payments/<uuid:transaction_id>/release', views.payment_release, name='payment-release'),
    path('payments/<uuid:transaction_id>/refund', views.payment_refund, name='payment-refund'),
    
    # GavaConnect API endpoints
    path('verification/kra-pin', api_views.verify_kra_pin_view, name='verify-kra-pin'),
    path('verification/identity', api_views.verify_identity_view, name='verify-identity-api'),
    path('verification/business', api_views.verify_business_view, name='verify-business'),
    
    # M-PESA Daraja API endpoints
    path('mpesa/initiate', api_views.initiate_mpesa_payment_view, name='initiate-mpesa'),
    path('mpesa/status', api_views.query_mpesa_status_view, name='query-mpesa-status'),
    path('mpesa/callback', api_views.MpesaCallbackView.as_view(), name='mpesa-callback'),
]
