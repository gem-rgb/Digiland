from django import forms
from core.models import LandParcel, Document, User, AgentKYCApplication

class CustomSignupForm(forms.Form):
    # Admin is the ONLY role that cannot self-register — CLI/superuser only
    PUBLIC_ROLE_CHOICES = [
        ('Buyer', 'Buyer'),
        ('Seller', 'Seller'),
        ('Agent', 'Agent (Requires KYC Verification)'),
    ]
    role = forms.ChoiceField(choices=PUBLIC_ROLE_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    id_number = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'placeholder': 'National ID Number', 'class': 'form-control'}))
    phone_number = forms.CharField(max_length=20, widget=forms.TextInput(attrs={'placeholder': 'Phone Number', 'class': 'form-control'}))

    def signup(self, request, user):
        user.role = self.cleaned_data['role']
        user.id_number = self.cleaned_data['id_number']
        user.phone_number = self.cleaned_data['phone_number']
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
