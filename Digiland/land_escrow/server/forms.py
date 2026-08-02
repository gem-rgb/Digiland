from django import forms
from core.models import LandParcel

class LandParcelUploadForm(forms.ModelForm):
    class Meta:
        model = LandParcel
        fields = ['parcel_number', 'land_use_type', 'county', 'constituency', 'ward', 'land_size', 'registered_owner_id', 'image', 'asking_price', 'lowest_negotiable_price']
        widgets = {
            'parcel_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., LR-1234/56'}),
            'land_use_type': forms.Select(attrs={'class': 'form-control'}),
            'county': forms.TextInput(attrs={'class': 'form-control'}),
            'constituency': forms.TextInput(attrs={'class': 'form-control'}),
            'ward': forms.TextInput(attrs={'class': 'form-control'}),
            'land_size': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'registered_owner_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'National ID'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'asking_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Target Price in KES'}),
            'lowest_negotiable_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Lowest Acceptable Price in KES'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        asking_price = cleaned_data.get('asking_price')
        lowest_negotiable_price = cleaned_data.get('lowest_negotiable_price')

        if asking_price is not None and lowest_negotiable_price is not None:
            if lowest_negotiable_price >= asking_price:
                self.add_error(
                    'lowest_negotiable_price',
                    'The lowest negotiable price must be strictly lower than the asking price.'
                )
        return cleaned_data
