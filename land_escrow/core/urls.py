from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

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
]
