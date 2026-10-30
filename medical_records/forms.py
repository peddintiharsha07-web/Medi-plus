from django import forms
from django.conf import settings
from django.utils import timezone

from .models import PatientDocument

_FIELDS = ['category', 'title', 'record_date', 'provider_name', 'description', 'shared_with_doctors']


class _DateMixin:
    def clean_record_date(self):
        value = self.cleaned_data['record_date']
        if value > timezone.localdate():
            raise forms.ValidationError('The date cannot be in the future.')
        return value


class PatientDocumentForm(_DateMixin, forms.ModelForm):
    class Meta:
        model = PatientDocument
        fields = _FIELDS[:5] + ['file'] + _FIELDS[5:]
        widgets = {
            'record_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'description': forms.Textarea(attrs={'rows': 3}),
            'file': forms.FileInput(attrs={'accept': '.pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file'].help_text = (f'PDF, JPG, PNG or WEBP, up to {settings.MAX_UPLOAD_MB} MB. '
                                         'Optional if you describe the record below.')


class PatientDocumentEditForm(_DateMixin, forms.ModelForm):
    """Edit details only (the file cannot be swapped; delete and re-upload)."""
    class Meta:
        model = PatientDocument
        fields = _FIELDS
        widgets = {
            'record_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
