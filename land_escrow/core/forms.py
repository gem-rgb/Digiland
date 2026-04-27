from django import forms
from core.models import LandParcel, Document, User, AgentKYCApplication
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
