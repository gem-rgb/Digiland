from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import User, LandParcel, Transaction, PurchaseCommission, Document, AuditLog, SupportTicket, Message, PlatformLegalDocument, KYCProfile, JointMemberRemovalRequest, PopupAdCampaign, PopupAdEvent

@admin.register(PlatformLegalDocument)
class PlatformLegalDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'updated_at')
    search_fields = ('title', 'content')
    readonly_fields = ('updated_at',)


@admin.register(PopupAdCampaign)
class PopupAdCampaignAdmin(admin.ModelAdmin):
    list_display = (
        'campaign_name',
        'popup_type',
        'billing_model',
        'status',
        'payment_status',
        'parcel',
        'created_by',
        'impressions_count',
        'clicks_count',
        'leads_count',
        'roi_score',
        'created_at',
    )
    list_filter = (
        'popup_type',
        'billing_model',
        'status',
        'payment_status',
        'geo_exclusive',
        'seller_verified_only',
        'created_at',
    )
    search_fields = (
        'campaign_name',
        'headline',
        'subheadline',
        'parcel__parcel_number',
        'created_by__email',
        'target_counties',
        'target_locations',
        'target_buyer_categories',
        'target_intent_tags',
    )
    readonly_fields = (
        'created_at',
        'updated_at',
        'last_scored_at',
        'spent_amount',
        'revenue_value',
        'impressions_count',
        'clicks_count',
        'leads_count',
        'dismissals_count',
        'quality_score',
        'engagement_score',
        'auction_score',
        'roi_score',
    )
    autocomplete_fields = ('parcel', 'created_by')


@admin.register(PopupAdEvent)
class PopupAdEventAdmin(admin.ModelAdmin):
    list_display = (
        'campaign',
        'event_type',
        'placement_area',
        'buyer_category',
        'county_context',
        'intent_score',
        'relevance_score',
        'charge_amount',
        'created_at',
    )
    list_filter = (
        'event_type',
        'placement_area',
        'buyer_category',
        'county_context',
        'created_at',
    )
    search_fields = (
        'campaign__campaign_name',
        'campaign__parcel__parcel_number',
        'user__email',
        'session_key',
    )
    readonly_fields = (
        'created_at',
        'charge_amount',
        'conversion_value',
        'metadata',
    )


@admin.register(KYCProfile)
class KYCProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'status', 'id_number', 'id_number_hash', 'liveness_score',
        'created_at', 'updated_at'
    )
    list_filter = ('status', 'created_at', 'updated_at')
    search_fields = (
        'user__email', 'user__id_number', 'full_name',
        'id_number', 'id_number_hash', 'audit_log'
    )
    readonly_fields = (
        'created_at', 'updated_at', 'audit_log',
        'id_number_hash',
        'face_embedding', 'id_front_image', 'selfie_image'
    )
    ordering = ('-updated_at',)
    actions = ('mark_approved', 'mark_rejected', 'mark_flagged_for_review', 'mark_locked')

    def _apply_status(self, request, queryset, status, *, note, active=None, verified=None):
        count = 0
        for profile in queryset.select_related('user'):
            profile.status = status
            audit = dict(profile.audit_log or {})
            audit['admin_note'] = note
            audit['status'] = status
            profile.audit_log = audit
            profile.save(update_fields=['status', 'audit_log', 'updated_at'])

            user = profile.user
            if user:
                if active is not None:
                    user.is_active = active
                if verified is not None:
                    user.is_identity_verified = verified
                user.save(update_fields=['is_active', 'is_identity_verified'])

            AuditLog.objects.create(
                user=request.user,
                action=f'KYC admin {status.lower()} for {profile.user.email}',
                metadata={
                    'kyc_profile_id': str(profile.id),
                    'user_id': str(profile.user_id),
                    'status': status,
                    'note': note,
                },
            )
            count += 1

        self.message_user(request, f'{count} KYC profile(s) updated to {status}.')

    def mark_approved(self, request, queryset):
        self._apply_status(
            request,
            queryset,
            'APPROVED',
            note='Approved by manual review.',
            active=True,
            verified=True,
        )
    mark_approved.short_description = 'Mark selected profiles approved'

    def mark_rejected(self, request, queryset):
        self._apply_status(
            request,
            queryset,
            'REJECTED',
            note='Rejected by manual review.',
            active=True,
            verified=False,
        )
    mark_rejected.short_description = 'Mark selected profiles rejected'

    def mark_flagged_for_review(self, request, queryset):
        self._apply_status(
            request,
            queryset,
            'FLAGGED_FOR_REVIEW',
            note='Flagged for manual review.',
            active=True,
            verified=False,
        )
    mark_flagged_for_review.short_description = 'Flag selected profiles for review'

    def mark_locked(self, request, queryset):
        self._apply_status(
            request,
            queryset,
            'LOCKED',
            note='Locked for suspected fraud.',
            active=False,
            verified=False,
        )
    mark_locked.short_description = 'Lock selected profiles'


@admin.register(JointMemberRemovalRequest)
class JointMemberRemovalRequestAdmin(admin.ModelAdmin):
    list_display = (
        'group', 'member', 'requested_by', 'status', 'consent_confirmed',
        'compensation_confirmed', 'compensation_amount', 'created_at', 'processed_at'
    )
    list_filter = ('status', 'consent_confirmed', 'compensation_confirmed', 'created_at', 'processed_at')
    search_fields = (
        'group__name',
        'member__full_name',
        'requested_by__email',
        'admin_notes',
        'notes',
    )
    readonly_fields = ('created_at', 'admin_reviewed_at', 'processed_at')
    ordering = ('-created_at',)

class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'role', 'is_email_verified', 'is_identity_verified', 'id_number', 'phone_number', 'is_staff', 'is_active')
    list_filter = ('role', 'is_identity_verified', 'is_email_verified', 'is_staff', 'is_active')
    search_fields = ('email', 'id_number', 'phone_number')
    ordering = ('email',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('id_number', 'phone_number', 'buyer_account_type', 'agent_county', 'agent_constituency')}),
        ('Security & Roles', {'fields': ('role', 'is_email_verified', 'is_identity_verified', 'gavakonect_verification_id')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password', 'role', 'id_number', 'phone_number', 'is_email_verified', 'is_identity_verified', 'is_staff'),
        }),
    )

    actions = ['promote_to_cooperation_lawyer', 'verify_email_address']

    @admin.action(description='Provision selected user(s) as Verified Cooperation Lawyer')
    def promote_to_cooperation_lawyer(self, request, queryset):
        from allauth.account.models import EmailAddress
        updated_count = 0
        for user in queryset:
            user.role = 'Lawyer'
            user.is_email_verified = True
            user.is_identity_verified = True
            user.is_onboarded = True
            user.save()
            EmailAddress.objects.update_or_create(
                user=user,
                email=user.email,
                defaults={'verified': True, 'primary': True}
            )
            updated_count += 1
        self.message_user(request, f'Successfully provisioned {updated_count} user(s) as Cooperation Lawyers.')

    @admin.action(description='Verify email address for selected user(s)')
    def verify_email_address(self, request, queryset):
        from allauth.account.models import EmailAddress
        for user in queryset:
            user.is_email_verified = True
            user.save()
            EmailAddress.objects.update_or_create(
                user=user,
                email=user.email,
                defaults={'verified': True, 'primary': True}
            )
        self.message_user(request, f'Successfully verified email for {queryset.count()} user(s).')

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

@admin.register(PurchaseCommission)
class PurchaseCommissionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'buyer', 'land_parcel', 'status', 'accepted_by', 'assigned_lawyer', 'transaction', 'created_at', 'updated_at'
    )
    list_filter = ('status', 'target_county', 'target_constituency', 'created_at', 'updated_at')
    search_fields = (
        'buyer__email',
        'land_parcel__parcel_number',
        'accepted_by__email',
        'assigned_lawyer__email',
        'target_county',
        'target_constituency',
    )
    readonly_fields = ('created_at', 'updated_at', 'accepted_at', 'documents_reviewed_at', 'lawyer_submitted_at', 'lawyer_verified_at', 'site_visit_completed_at', 'closed_at')
    autocomplete_fields = ('buyer', 'land_parcel', 'accepted_by', 'assigned_lawyer', 'transaction')


# ── Verification Engine Models ──
from .models_verification import (
    PropertyVerificationCase,
    VerificationDocumentRequirement,
    VerificationDocument,
    VerificationLayer,
    VerificationCheckItem,
    VerificationRiskFlag,
    VerificationAuditEvent,
    BuyerInterestCase,
)

@admin.register(PropertyVerificationCase)
class PropertyVerificationCaseAdmin(admin.ModelAdmin):
    list_display = ('case_number', 'property', 'seller', 'current_phase', 'status', 'verification_level', 'overall_risk_level', 'created_at')
    list_filter = ('current_phase', 'status', 'verification_level', 'overall_risk_level', 'property_type', 'tenure_type', 'ownership_type')
    search_fields = ('case_number', 'property__parcel_number', 'seller__email', 'registered_owner_name')
    readonly_fields = ('id', 'case_number', 'created_at', 'updated_at')
    autocomplete_fields = ('property', 'seller', 'assigned_agent', 'assigned_surveyor', 'assigned_lawyer')

@admin.register(VerificationDocumentRequirement)
class VerificationDocumentRequirementAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'document_type', 'phase', 'is_core', 'ai_screening_enabled', 'customer_visible', 'sort_order', 'is_active')
    list_filter = ('phase', 'is_core', 'ai_screening_enabled', 'is_active', 'primary_reviewer_role')
    search_fields = ('display_name', 'document_type', 'description')
    list_editable = ('sort_order', 'is_active', 'is_core')

@admin.register(VerificationDocument)
class VerificationDocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'case', 'document_type', 'verification_status', 'ai_status', 'ai_confidence_level', 'human_status', 'version', 'uploaded_at')
    list_filter = ('verification_status', 'ai_status', 'ai_confidence_level', 'human_status', 'document_type')
    search_fields = ('case__case_number', 'original_filename', 'file_hash')
    readonly_fields = ('id', 'file_hash', 'created_at', 'updated_at', 'uploaded_at', 'ai_processed_at')

@admin.register(VerificationLayer)
class VerificationLayerAdmin(admin.ModelAdmin):
    list_display = ('case', 'layer_type', 'status', 'risk_level', 'assigned_to', 'started_at', 'completed_at')
    list_filter = ('layer_type', 'status', 'risk_level')
    search_fields = ('case__case_number',)

@admin.register(VerificationCheckItem)
class VerificationCheckItemAdmin(admin.ModelAdmin):
    list_display = ('check_name', 'layer', 'status', 'customer_visible', 'checked_by', 'checked_at')
    list_filter = ('status', 'customer_visible')
    search_fields = ('check_name', 'layer__case__case_number')

@admin.register(VerificationRiskFlag)
class VerificationRiskFlagAdmin(admin.ModelAdmin):
    list_display = ('case', 'flag_type', 'severity', 'source', 'resolved', 'auto_escalate', 'created_at')
    list_filter = ('severity', 'source', 'resolved', 'auto_escalate', 'flag_type')
    search_fields = ('case__case_number', 'description')

@admin.register(VerificationAuditEvent)
class VerificationAuditEventAdmin(admin.ModelAdmin):
    list_display = ('case', 'event_type', 'actor', 'customer_visible', 'timestamp')
    list_filter = ('event_type', 'customer_visible')
    search_fields = ('case__case_number', 'description', 'customer_display')
    readonly_fields = ('timestamp',)

@admin.register(BuyerInterestCase)
class BuyerInterestCaseAdmin(admin.ModelAdmin):
    list_display = ('interest_number', 'buyer', 'property', 'status', 'payment_status', 'created_at')
    list_filter = ('status', 'payment_status')
    search_fields = ('interest_number', 'buyer__email', 'property__parcel_number')
    readonly_fields = ('interest_number', 'created_at', 'updated_at')

