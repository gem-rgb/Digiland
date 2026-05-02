from django import forms
from django.forms import formset_factory
from core.models import LandParcel, Document, User, AgentKYCApplication, JointBuyerGroup, JointBuyerMember
import re
import requests
import logging

logger = logging.getLogger(__name__)

class CustomSignupForm(forms.Form):
    # Admin is the ONLY role that cannot self-register — CLI/superuser only
    PUBLIC_ROLE_CHOICES = [
        ('Buyer', 'Buyer'),
        ('Seller', 'Seller'),
        ('Agent', 'Agent (Requires KYC Verification)'),
    ]
    role = forms.ChoiceField(choices=PUBLIC_ROLE_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    id_number = forms.CharField(
        max_length=9,
        min_length=7,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. 12345678',
            'class': 'form-control',
            'pattern': r'\d{7,9}',
            'title': 'Enter 7, 8, or 9 digits',
        }),
        help_text='Your National ID number (7–9 digits).',
    )
    phone_number = forms.CharField(
        max_length=13,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. 0712345678 or +254712345678',
            'class': 'form-control',
            'title': 'Phone must start with +254 or 07',
        }),
        help_text='Kenyan phone number starting with +254 or 07.',
    )
    kra_pin = forms.CharField(
        max_length=11,
        min_length=11,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. A123456789B',
            'class': 'form-control',
            'style': 'text-transform: uppercase;',
            'title': 'Letter + 9 digits + Letter',
        }),
        help_text='Your KRA PIN (11 chars: Letter + 9 digits + Letter).',
    )

    def clean_id_number(self):
        value = self.cleaned_data['id_number'].strip()
        if not re.fullmatch(r'\d{7,9}', value):
            raise forms.ValidationError('ID number must be 7, 8, or 9 digits only.')
        return value

    def clean_phone_number(self):
        value = self.cleaned_data['phone_number'].strip().replace(' ', '').replace('-', '')
        # Normalise 07... to +254...
        if value.startswith('07') and len(value) == 10:
            value = '+254' + value[1:]
        elif value.startswith('01') and len(value) == 10:
            value = '+254' + value[1:]
        elif value.startswith('+254') and len(value) == 13:
            pass  # already correct
        elif value.startswith('254') and len(value) == 12:
            value = '+' + value
        else:
            raise forms.ValidationError(
                'Phone number must start with +254 or 07 and have 10 digits (e.g. 0712345678 or +254712345678).'
            )
        # Final sanity check
        if not re.fullmatch(r'\+254\d{9}', value):
            raise forms.ValidationError('Invalid phone number format.')
        return value

    def clean_kra_pin(self):
        value = self.cleaned_data['kra_pin'].strip().upper()
        # Format-only validation (Letter + 9 digits + Letter)
        if not re.fullmatch(r'[A-Z]\d{9}[A-Z]', value):
            raise forms.ValidationError(
                'KRA PIN must be 11 characters: Letter + 9 digits + Letter (e.g. A123456789B).'
            )
        return value

    def signup(self, request, user):
        user.role = self.cleaned_data['role']
        user.id_number = self.cleaned_data['id_number']
        user.phone_number = self.cleaned_data['phone_number']
        user.kra_pin = self.cleaned_data['kra_pin']
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
        # KRA database verification (graceful fallback if API is down)
        try:
            resp = requests.get(
                f'https://itax.kra.go.ke/KRA-Portal/pinChecker.htm?taxPayerPin={value}',
                timeout=5,
            )
            if resp.status_code == 200 and 'Invalid' in resp.text:
                raise forms.ValidationError('This KRA PIN was not found in the KRA database.')
        except requests.RequestException:
            logger.info(f'KRA PIN Checker API unavailable, using format validation for {value[:3]}***')
        return value


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
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='County',
    )
    constituency = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Westlands',
        }),
        label='Constituency',
        help_text='Leave blank to use the selected county as the fallback location.',
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

    def __init__(self, *args, counties=None, land_use_types=None, **kwargs):
        super().__init__(*args, **kwargs)

        if counties is not None:
            self.fields['county'].choices = [(county, county) for county in counties]
        if land_use_types is not None:
            self.fields['land_use'].choices = [(value, value) for value in land_use_types]
