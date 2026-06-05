from django.urls import path
from . import admin_views

urlpatterns = [
    # Admin payment reversal views
    path('reverse-payment-confirmation/', admin_views.reverse_payment_confirmation, name='reverse_payment_confirmation'),
    
    # Admin verification dashboard
    path('verification-dashboard/', admin_views.verification_dashboard, name='verification_dashboard'),
    
    # AJAX endpoints for admin actions
    path('ajax-reverse-single-payment/', admin_views.ajax_reverse_single_payment, name='ajax_reverse_single_payment'),
    path('ajax-complete-verification/', admin_views.ajax_complete_verification, name='ajax_complete_verification'),
    path('ajax-start-hiatus/', admin_views.ajax_start_hiatus, name='ajax_start_hiatus'),
]
