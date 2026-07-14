from django import forms
from django.forms import formset_factory
from django.db import models
from core.models import LandParcel, Document, User, AgentKYCApplication, JointBuyerGroup, JointBuyerMember, PopupAdCampaign
import re
import logging

logger = logging.getLogger(__name__)

class CustomSignupForm(forms.Form):
    full_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your full name',
            'class': 'form-control',
        }),
        help_text='Your full name.',
    )

    def signup(self, request, user):
        full_name = self.cleaned_data.get('full_name', '').strip()
        if full_name:
            name_parts = full_name.split(' ', 1)
            user.first_name = name_parts[0]
            user.last_name = name_parts[1] if len(name_parts) > 1 else ''
        user.role = None
        user.is_onboarded = False
        user.save()

class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['document_type', 'file_url']
        widgets = {
            'document_type': forms.Select(attrs={'class': 'form-select'}),
            'file_url': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'file_url': 'Select File'
        }


class AgentKYCForm(forms.ModelForm):
    MAX_DOC_SIZE_MB = 10
    ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
    ALLOWED_PDF_TYPES = {'application/pdf'}

    class Meta:
        model = AgentKYCApplication
        fields = [
            'kra_pin',
            'id_number',
            'id_photo',
            'resume',
            'certificate_of_good_conduct',
            'practicing_certificate',
        ]
        widgets = {
            'kra_pin': forms.TextInput(attrs={
                'class': 'form-control bg-light border-0',
                'placeholder': 'e.g. A001234567B',
            }),
            'id_number': forms.TextInput(attrs={
                'class': 'form-control bg-light border-0',
                'placeholder': 'National ID or Passport Number',
            }),
            'id_photo': forms.ClearableFileInput(attrs={'class': 'form-control bg-light border-0'}),
            'resume': forms.ClearableFileInput(attrs={'class': 'form-control bg-light border-0'}),
            'certificate_of_good_conduct': forms.ClearableFileInput(attrs={'class': 'form-control bg-light border-0'}),
            'practicing_certificate': forms.ClearableFileInput(attrs={'class': 'form-control bg-light border-0'}),
        }
        labels = {
            'kra_pin': 'KRA PIN',
            'id_number': 'National ID / Passport Number',
            'id_photo': 'National ID / Passport Photo (scan)',
            'resume': 'Curriculum Vitae / Resume (PDF)',
            'certificate_of_good_conduct': 'DCI Certificate of Good Conduct (PDF)',
            'practicing_certificate': 'LSK / Real Estate Practicing Certificate (optional)',
        }
        help_texts = {
            'practicing_certificate': 'Upload only if you hold a current LSK or Real Estate Board certificate.',
        }

    def clean_kra_pin(self):
        value = self.cleaned_data['kra_pin'].strip().upper()
        # Format validation
        if not re.fullmatch(r'[A-Z]\d{9}[A-Z]', value):
            raise forms.ValidationError(
                'KRA PIN must be 11 characters: Letter + 9 digits + Letter (e.g. A123456789B).'
            )
        # NOTE: KRA database validation is disabled during agent KYC.
        # Format validation is sufficient for the KYC submission.
        # Database verification (GavaConnect / iTax) runs later as a
        # failover in production when KRA_DB_VALIDATION_ENABLED=True.
        logger.debug(f'KRA PIN format validation passed for agent KYC: {value[:3]}***')
        return value

    def _validate_uploaded_file(self, field_name, uploaded_file, *, allow_pdf=False, required=True):
        if not uploaded_file:
            if required:
                raise forms.ValidationError('This file is required.')
            return uploaded_file

        content_type = getattr(uploaded_file, 'content_type', '') or ''
        size_mb = getattr(uploaded_file, 'size', 0) / (1024 * 1024)

        allowed_types = set(self.ALLOWED_IMAGE_TYPES)
        if allow_pdf:
            allowed_types |= self.ALLOWED_PDF_TYPES

        if content_type and content_type.lower() not in allowed_types:
            raise forms.ValidationError(
                'Unsupported file type. Use JPG, PNG, WEBP, or PDF where applicable.'
            )

        if size_mb > self.MAX_DOC_SIZE_MB:
            raise forms.ValidationError(
                f'File is too large. Keep uploads at or below {self.MAX_DOC_SIZE_MB} MB.'
            )

        return uploaded_file

    def clean_id_photo(self):
        return self._validate_uploaded_file(
            'id_photo',
            self.cleaned_data.get('id_photo'),
            allow_pdf=False,
            required=True,
        )

    def clean_resume(self):
        return self._validate_uploaded_file(
            'resume',
            self.cleaned_data.get('resume'),
            allow_pdf=True,
            required=True,
        )

    def clean_certificate_of_good_conduct(self):
        return self._validate_uploaded_file(
            'certificate_of_good_conduct',
            self.cleaned_data.get('certificate_of_good_conduct'),
            allow_pdf=True,
            required=True,
        )

    def clean_practicing_certificate(self):
        return self._validate_uploaded_file(
            'practicing_certificate',
            self.cleaned_data.get('practicing_certificate'),
            allow_pdf=True,
            required=False,
        )


class JointBuyerGroupForm(forms.ModelForm):
    """Form for creating/editing a joint buyer group."""
    leader_share_percentage = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=1,
        max_value=100,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. 50',
            'min': '1',
            'max': '100',
            'step': '0.01',
        }),
        help_text="Leader's ownership share. Combined with co-buyers must total 100%.",
    )

    class Meta:
        model = JointBuyerGroup
        fields = [
            'name',
            'group_type',
            'ownership_type',
            'preferred_payment_method',
            'bank_name',
            'bank_account_name',
            'bank_account_number',
            'bank_branch',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "e.g. Wanjiku Family Trust, Mwamba Chama",
            }),
            'group_type': forms.Select(attrs={'class': 'form-select'}),
            'ownership_type': forms.RadioSelect(),
            'preferred_payment_method': forms.RadioSelect(),
            'bank_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Co-op Bank',
            }),
            'bank_account_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Wanjiku Family Trust',
            }),
            'bank_account_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 0123456789012',
            }),
            'bank_branch': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Nairobi CBD',
            }),
        }
        labels = {
            'name': 'Group / Chama Name',
            'group_type': 'Type of Group',
            'ownership_type': 'Ownership Structure',
            'preferred_payment_method': 'Preferred Payment Method',
            'bank_name': 'Joint Bank Name',
            'bank_account_name': 'Joint Bank Account Name',
            'bank_account_number': 'Joint Bank Account Number',
            'bank_branch': 'Bank Branch',
        }
    help_texts = {
            'ownership_type': 'For most non-spousal group purchases, Kenyan land law points to tenancy in common. '
                              'Joint tenancy is generally reserved for spouses or cases approved by court.',
            'preferred_payment_method': 'Choose how the group wants to pay during checkout. Bank account details are optional unless you choose joint bank transfer.',
            'bank_name': 'Optional, but required if the group will use a joint bank account for purchase contributions.',
            'bank_account_name': 'Must match the bank mandate for the joint account.',
            'bank_account_number': 'Enter the exact account number used for the joint account.',
        }

    def clean(self):
        cleaned = super().clean()
        group_type = cleaned.get('group_type')
        ownership_type = cleaned.get('ownership_type')
        method = cleaned.get('preferred_payment_method')
        bank_fields = ['bank_name', 'bank_account_name', 'bank_account_number']

        if ownership_type == 'Joint_Tenancy' and group_type and group_type != 'Couple':
            self.add_error(
                'ownership_type',
                'Joint tenancy is generally only suitable for spouses or court-approved cases. '
                'Choose tenancy in common for a group purchase.'
            )

        if method == 'Joint_Bank_Account':
            missing = [field for field in bank_fields if not cleaned.get(field)]
            if missing:
                for field in missing:
                    self.add_error(field, 'This field is required for the joint bank account payment method.')
        return cleaned


class JointBuyerMemberForm(forms.ModelForm):
    """Form for adding a single member to a joint buyer group."""
    class Meta:
        model = JointBuyerMember
        fields = ['full_name', 'id_number', 'kra_pin', 'phone_number', 'email', 'share_percentage']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full legal name as per National ID',
            }),
            'id_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 12345678',
            }),
            'kra_pin': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. A123456789B',
                'style': 'text-transform: uppercase;',
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 0712345678',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional email',
            }),
            'share_percentage': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 50',
                'min': '1',
                'max': '100',
                'step': '0.01',
            }),
        }
        labels = {
            'full_name': 'Full Legal Name',
            'id_number': 'National ID Number',
            'kra_pin': 'KRA PIN',
            'phone_number': 'Phone Number (M-PESA)',
            'email': 'Email (Optional)',
            'share_percentage': 'Ownership Share (%)',
        }

    def clean_kra_pin(self):
        value = self.cleaned_data['kra_pin'].strip().upper()
        if not re.fullmatch(r'[A-Z]\d{9}[A-Z]', value):
            raise forms.ValidationError('KRA PIN must be 11 characters: Letter + 9 digits + Letter.')
        return value

    def clean_id_number(self):
        value = self.cleaned_data['id_number'].strip()
        if not re.fullmatch(r'\d{7,9}', value):
            raise forms.ValidationError('ID number must be 7–9 digits.')
        return value

    def clean_phone_number(self):
        value = self.cleaned_data['phone_number'].strip().replace(' ', '').replace('-', '')
        if value.startswith('07') and len(value) == 10:
            value = '+254' + value[1:]
        elif value.startswith('01') and len(value) == 10:
            value = '+254' + value[1:]
        elif value.startswith('+254') and len(value) == 13:
            pass
        elif value.startswith('254') and len(value) == 12:
            value = '+' + value
        else:
            raise forms.ValidationError('Phone number must start with +254 or 07.')
        if not re.fullmatch(r'\+254\d{9}', value):
            raise forms.ValidationError('Invalid phone number format.')
        return value


JointBuyerMemberFormSet = formset_factory(JointBuyerMemberForm, extra=2, can_delete=True)


class JointLeaderTransferForm(forms.Form):
    """Transfer the leadership title to another eligible group member."""

    new_leader_member_id = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='New leader',
        help_text='The member must already have a Buyer account on the platform.',
    )
    transfer_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Optional reason for the leadership change.',
        }),
        label='Reason for transfer',
    )


class JointMemberRemovalRequestForm(forms.Form):
    """Capture the leader and admin acknowledgements needed before removing a member."""

    consent_confirmed = forms.BooleanField(
        required=True,
        label='The exiting member has agreed to the removal',
        help_text='Confirm that the member leaving the group has consented to the change.',
    )
    compensation_confirmed = forms.BooleanField(
        required=True,
        label='The exiting member has received their compensation',
        help_text='Confirm that the member leaving the group has been paid their share.',
    )
    compensation_amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. 250000',
            'step': '0.01',
        }),
        label='Compensation amount (KES)',
        help_text='Optional, but useful for admin review and audit records.',
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Any supporting details for the admin reviewer.',
        }),
        label='Notes for admin review',
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('compensation_confirmed') and cleaned.get('compensation_amount') in {None, ''}:
            self.add_error('compensation_amount', 'Enter the compensation amount if payment has been confirmed.')
        return cleaned


class AgentRatingForm(forms.Form):
    rating = forms.ChoiceField(
        choices=[(str(i), f'{i} Stars') for i in range(1, 6)],
        widget=forms.RadioSelect,
        label='Rating',
    )
    review = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Share what the agent handled well and what should improve.',
        }),
        label='Review',
        help_text='Optional, but useful for performance feedback and coaching.',
    )


class PricePredictionForm(forms.Form):
    county = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select', 'data-action': 'load-constituencies'}),
        label='County',
    )
    constituency = forms.ChoiceField(
        choices=[],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'data-action': 'load-towns'}),
        label='Constituency',
        help_text='Select a constituency within the chosen county.',
    )
    town = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Karen, Westlands, Kitengela',
        }),
        label='Town / Neighborhood',
        help_text='Specific town or neighborhood for a more precise estimate.',
    )
    land_use = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Land use',
    )
    size_acres = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '1.00',
            'step': '0.01',
        }),
        label='Size in acres',
    )
    has_road_access = forms.BooleanField(
        required=False,
        label='Road access',
        help_text='Tick if the parcel has usable road access.',
    )
    has_water = forms.BooleanField(
        required=False,
        label='Water access',
        help_text='Tick if the parcel has a reliable water source.',
    )
    has_electricity = forms.BooleanField(
        required=False,
        label='Electricity access',
        help_text='Tick if the parcel has power connectivity.',
    )
    proximity_to_tarmac_km = forms.FloatField(
        required=False,
        min_value=0,
        max_value=50,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Distance to tarmac road (km)',
            'step': '0.5',
        }),
        label='Distance to tarmac road (km)',
        help_text='Optional. Leave blank for auto-estimate.',
    )
    proximity_to_school_km = forms.FloatField(
        required=False,
        min_value=0,
        max_value=50,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Distance to nearest school (km)',
            'step': '0.5',
        }),
        label='Distance to nearest school (km)',
        help_text='Optional. Leave blank for auto-estimate.',
    )
    proximity_to_hospital_km = forms.FloatField(
        required=False,
        min_value=0,
        max_value=50,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Distance to nearest hospital (km)',
            'step': '0.5',
        }),
        label='Distance to nearest hospital (km)',
        help_text='Optional. Leave blank for auto-estimate.',
    )
    plot_grade = forms.ChoiceField(
        choices=[('', 'Auto-detect'), ('A', 'A — Premium'), ('B', 'B — Good'), ('C', 'C — Average'), ('D', 'D — Developing')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Plot grade',
        help_text='Optional. Leave as Auto-detect for automatic grading.',
    )

    def __init__(self, *args, counties=None, land_use_types=None, constituencies=None, **kwargs):
        super().__init__(*args, **kwargs)

        if counties is not None:
            self.fields['county'].choices = [('', '-- Select County --')] + [(county, county) for county in counties]
        if land_use_types is not None:
            self.fields['land_use'].choices = [(value, value) for value in land_use_types]
        if constituencies is not None:
            self.fields['constituency'].choices = [('', '-- Select Constituency --')] + [(c, c) for c in constituencies]
        else:
            self.fields['constituency'].choices = [('', '-- Select County first --')]


def _split_popup_targets(raw_value):
    if not raw_value:
        return []
    if isinstance(raw_value, (list, tuple)):
        values = raw_value
    else:
        values = re.split(r'[,;\n]+', str(raw_value))
    return [value.strip() for value in values if str(value).strip()]


class PopupAdCampaignForm(forms.ModelForm):
    target_counties_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Kiambu, Nairobi, Machakos',
        }),
        label='Target counties',
        help_text='Comma-separated counties or regions to prioritise in the auction.',
    )
    target_locations_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Karen, Ruiru, Kitengela',
        }),
        label='Target locations',
        help_text='Specific towns, wards, estates, or search locations.',
    )
    target_buyer_categories_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Residential, Commercial, Diaspora',
        }),
        label='Preferred audience',
        help_text='Comma-separated buyer categories to target.',
    )
    target_intent_tags_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'high intent, investor, urgent buyer',
        }),
        label='Intent tags',
        help_text='Describe the buyer intent signals you want to match.',
    )

    class Meta:
        model = PopupAdCampaign
        fields = [
            'parcel',
            'campaign_name',
            'popup_type',
            'billing_model',
            'headline',
            'subheadline',
            'cta_text',
            'landing_url',
            'target_budget_min',
            'target_budget_max',
            'target_acreage_min',
            'target_acreage_max',
            'travel_radius_km',
            'frequency_cap_per_session',
            'cooldown_minutes',
            'duration_days',
            'daily_budget',
            'total_budget',
            'priority_bid',
            'geo_exclusive',
            'seller_verified_only',
            'creative_image',
            'creative_video_url',
            'status',
            'notes',
        ]
        widgets = {
            'parcel': forms.Select(attrs={'class': 'form-select'}),
            'campaign_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Karen luxury land push',
            }),
            'popup_type': forms.Select(attrs={'class': 'form-select'}),
            'billing_model': forms.Select(attrs={'class': 'form-select'}),
            'headline': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Headline buyers will see first',
            }),
            'subheadline': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'A short persuasive description',
            }),
            'cta_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'View listing',
            }),
            'landing_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://...',
            }),
            'target_budget_min': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'target_budget_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'target_acreage_min': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'target_acreage_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'travel_radius_km': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0'}),
            'frequency_cap_per_session': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'cooldown_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'duration_days': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'daily_budget': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'total_budget': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'priority_bid': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'geo_exclusive': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'seller_verified_only': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'creative_image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'creative_video_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
        labels = {
            'parcel': 'Land listing',
            'campaign_name': 'Campaign name',
            'popup_type': 'Popup type',
            'billing_model': 'Billing model',
            'headline': 'Headline',
            'subheadline': 'Supporting copy',
            'cta_text': 'CTA text',
            'landing_url': 'Landing URL',
            'target_budget_min': 'Target budget min',
            'target_budget_max': 'Target budget max',
            'target_acreage_min': 'Target acreage min',
            'target_acreage_max': 'Target acreage max',
            'travel_radius_km': 'Travel radius (km)',
            'frequency_cap_per_session': 'Frequency cap per session',
            'cooldown_minutes': 'Cooldown (minutes)',
            'duration_days': 'Campaign duration (days)',
            'daily_budget': 'Daily budget',
            'total_budget': 'Campaign budget',
            'priority_bid': 'Priority bid',
            'geo_exclusive': 'Geo-exclusive campaign',
            'seller_verified_only': 'Verified seller only',
            'creative_image': 'Creative image',
            'creative_video_url': 'Creative video URL',
            'status': 'Campaign status',
            'notes': 'Notes',
        }
        help_texts = {
            'landing_url': 'Leave blank to route buyers to the parcel detail page automatically.',
            'priority_bid': 'Higher bids improve auction rank when relevance is close.',
            'geo_exclusive': 'Restrict delivery to the target area and nearby travel radius.',
            'seller_verified_only': 'Only show if the seller or agent trust gate is satisfied.',
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

        parcel_qs = LandParcel.objects.none()
        if user is not None:
            if getattr(user, 'role', None) == 'Admin':
                parcel_qs = LandParcel.objects.all().order_by('-ardhisasa_last_synced')
            elif getattr(user, 'role', None) == 'Agent':
                parcel_qs = LandParcel.objects.filter(
                    models.Q(listed_by=user) | models.Q(assigned_agent=user)
                ).order_by('-ardhisasa_last_synced')
            else:
                parcel_qs = LandParcel.objects.filter(listed_by=user).order_by('-ardhisasa_last_synced')
        self.fields['parcel'].queryset = parcel_qs

        if self.instance and self.instance.pk:
            self.fields['target_counties_text'].initial = ', '.join(self.instance.target_counties or [])
            self.fields['target_locations_text'].initial = ', '.join(self.instance.target_locations or [])
            self.fields['target_buyer_categories_text'].initial = ', '.join(self.instance.target_buyer_categories or [])
            self.fields['target_intent_tags_text'].initial = ', '.join(self.instance.target_intent_tags or [])

    def clean(self):
        cleaned = super().clean()
        budget_min = cleaned.get('target_budget_min')
        budget_max = cleaned.get('target_budget_max')
        acreage_min = cleaned.get('target_acreage_min')
        acreage_max = cleaned.get('target_acreage_max')
        total_budget = cleaned.get('total_budget')
        daily_budget = cleaned.get('daily_budget')

        if budget_min and budget_max and budget_min > budget_max:
            self.add_error('target_budget_max', 'Budget max must be greater than or equal to budget min.')
        if acreage_min and acreage_max and acreage_min > acreage_max:
            self.add_error('target_acreage_max', 'Acreage max must be greater than or equal to acreage min.')
        if total_budget and daily_budget and daily_budget > total_budget:
            self.add_error('daily_budget', 'Daily budget cannot exceed the total campaign budget.')
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.target_counties = _split_popup_targets(self.cleaned_data.get('target_counties_text'))
        instance.target_locations = _split_popup_targets(self.cleaned_data.get('target_locations_text'))
        instance.target_buyer_categories = _split_popup_targets(self.cleaned_data.get('target_buyer_categories_text'))
        instance.target_intent_tags = _split_popup_targets(self.cleaned_data.get('target_intent_tags_text'))

        if not instance.landing_url and instance.parcel_id:
            try:
                from django.urls import reverse
                instance.landing_url = reverse('frontend:parcel_detail', args=[instance.parcel.parcel_number])
            except Exception:
                instance.landing_url = ''

        if commit:
            instance.save()
        return instance
