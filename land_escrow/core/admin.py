from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import User, LandParcel, Transaction, Document, AuditLog, SupportTicket, Message

class CustomUserAdmin(UserAdmin):
    # Specify the fields that should be displayed in the list view
    list_display = ('email', 'role', 'buyer_account_type', 'id_number', 'is_identity_verified', 'is_staff')
    search_fields = ('email', 'id_number')
    ordering = ('email',)
    
    # Define custom fieldsets to ensure the Admin can toggle high-security fields natively
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('id_number', 'phone_number', 'buyer_account_type')}),
        ('Security & Fencing', {'fields': ('role', 'is_identity_verified', 'gavakonect_verification_id')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    # Define add_fieldsets since AbstractUser handles creation differently
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password', 'role', 'id_number', 'phone_number', 'buyer_account_type', 'is_identity_verified'),
        }),
    )

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'buyer', 'seller', 'agent', 'land_parcel', 
        'agreed_price', 'status', 'verification_status_display',
        'reversal_status_display', 'created_at'
    )
    list_filter = (
        'status', 'land_verified', 'reversal_initiated_at',
        'created_at', 'buyer_validation_deadline'
    )
    search_fields = (
        'buyer__email', 'seller__email', 'agent__email',
        'land_parcel__parcel_number', 'escrow_reference', 'reversal_reference'
    )
    readonly_fields = (
        'id', 'created_at', 'updated_at', 'reversal_initiated_at',
        'reversal_reference', 'reversal_initiated_by'
    )
    
    fieldsets = (
        ('Transaction Details', {
            'fields': (
                'buyer', 'seller', 'agent', 'land_parcel',
                'agreed_price', 'status', 'escrow_reference'
            )
        }),
        ('Contract Information', {
            'fields': (
                'contract_agreed', 'buyer_signature', 'seller_signature'
            )
        }),
        ('Verification Status', {
            'fields': (
                'land_verification_started', 'land_verified', 
                'verification_agent', 'land_verification_notes'
            )
        }),
        ('7-Day Verification Period', {
            'fields': (
                'buyer_validation_deadline', 'buyer_accepted'
            ),
            'description': '7-day period for land location and details verification'
        }),
        ('Payment Reversal', {
            'fields': (
                'reversal_reason', 'reversal_initiated_by',
                'reversal_initiated_at', 'reversal_reference'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['start_verification_hiatus', 'complete_land_verification', 'reverse_payment_action']
    
    def verification_status_display(self, obj):
        """Display verification status with color coding"""
        if obj.is_in_verification_hiatus:
            days_left = obj.days_remaining_for_verification
            return format_html(
                '<span style="color: orange;">Hiatus - {} days left</span>',
                days_left
            )
        elif obj.land_verified:
            return format_html(
                '<span style="color: green;">✓ Verified</span>'
            )
        elif obj.verification_deadline_passed:
            return format_html(
                '<span style="color: red;">✗ Deadline Passed</span>'
            )
        else:
            return format_html(
                '<span style="color: gray;">Not Started</span>'
            )
    verification_status_display.short_description = 'Verification Status'
    
    def reversal_status_display(self, obj):
        """Display reversal status with color coding"""
        if obj.status == 'Reversed':
            return format_html(
                '<span style="color: red;">Reversed by {}</span>',
                obj.reversal_initiated_by.email if obj.reversal_initiated_by else 'Unknown'
            )
        elif obj.reversal_reference:
            return format_html(
                '<span style="color: orange;">Processing ({})</span>',
                obj.reversal_reference
            )
        else:
            return format_html(
                '<span style="color: green;">No Reversal</span>'
            )
    reversal_status_display.short_description = 'Reversal Status'
    
    def start_verification_hiatus(self, request, queryset):
        """Start 7-day verification hiatus for selected transactions"""
        count = 0
        for transaction in queryset:
            if transaction.status == 'Deposit_Paid':
                transaction.start_verification_hiatus()
                count += 1
        self.message_user(request, f'Started verification hiatus for {count} transactions.')
    start_verification_hiatus.short_description = 'Start 7-Day Verification Hiatus'
    
    def complete_land_verification(self, request, queryset):
        """Complete land verification for selected transactions"""
        count = 0
        for transaction in queryset:
            if transaction.is_in_verification_hiatus:
                transaction.complete_verification(request.user, "Verification completed by admin")
                count += 1
        self.message_user(request, f'Completed land verification for {count} transactions.')
    complete_land_verification.short_description = 'Complete Land Verification'
    
    def reverse_payment_action(self, request, queryset):
        """Reverse payment for selected transactions"""
        # This will redirect to a custom view for reversal confirmation
        selected = queryset.values_list('id', flat=True)
        request.session['reversal_transactions'] = list(selected)
        return reverse('admin:reverse_payment_confirmation')
    reverse_payment_action.short_description = 'Reverse Payment (Admin Only)'

@admin.register(LandParcel)
class LandParcelAdmin(admin.ModelAdmin):
    list_display = (
        'parcel_number', 'county', 'constituency', 'ward',
        'land_size', 'land_use_type', 'verification_status',
        'listed_by', 'assigned_agent'
    )
    list_filter = (
        'county', 'land_use_type', 'verification_status',
        'ardhisasa_last_synced'
    )
    search_fields = (
        'parcel_number', 'county', 'constituency', 'ward',
        'registered_owner_id', 'listed_by__email'
    )
    readonly_fields = ('id', 'ardhisasa_last_synced', 'current_risk_score')

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        'document_type', 'land_parcel', 'uploaded_by',
        'verification_status', 'uploaded_at'
    )
    list_filter = (
        'document_type', 'verification_status', 'uploaded_at'
    )
    search_fields = (
        'land_parcel__parcel_number', 'uploaded_by__email',
        'fraud_flag_notes'
    )

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'action', 'ip_address', 'timestamp'
    )
    list_filter = ('timestamp', 'user')
    search_fields = ('action', 'user__email', 'ip_address')
    readonly_fields = ('user', 'action', 'ip_address', 'metadata', 'timestamp')

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'subject', 'status', 'created_at'
    )
    list_filter = ('status', 'created_at')
    search_fields = ('user__email', 'subject', 'message')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        'sender', 'receiver', 'transaction', 'is_read', 'timestamp'
    )
    list_filter = ('is_read', 'timestamp')
    search_fields = (
        'sender__email', 'receiver__email', 'content'
    )

# Register the models to the secure Offline Admin Vault
admin.site.register(User, CustomUserAdmin)
