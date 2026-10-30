from django import forms
from .models import DoctorProfile


class DoctorProfileCompletionForm(forms.ModelForm):
    class Meta:
        model = DoctorProfile
        fields = ['hospital', 'department', 'specialization', 'license_number',
                  'years_of_experience', 'consultation_fee', 'bio']


# ---------------------------------------------------------------------------
# Consultation notes + prescriptions
# ---------------------------------------------------------------------------
from datetime import timedelta  # noqa: E402
from itertools import zip_longest  # noqa: E402

from django.utils import timezone  # noqa: E402

from medical_records.models import MedicalRecord  # noqa: E402

MAX_PRESCRIPTION_ROWS = 20


class ConsultationForm(forms.ModelForm):
    consultation_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M'])

    class Meta:
        model = MedicalRecord
        fields = ['consultation_date', 'symptoms', 'diagnosis', 'treatment_details',
                  'follow_up_notes', 'discharge_summary', 'status']
        widgets = {name: forms.Textarea(attrs={'rows': 3}) for name in
                   ('symptoms', 'diagnosis', 'treatment_details', 'follow_up_notes', 'discharge_summary')}

    def clean_consultation_date(self):
        value = self.cleaned_data['consultation_date']
        if value > timezone.now() + timedelta(days=1):
            raise forms.ValidationError('The consultation date cannot be in the future.')
        return value


def parse_prescriptions(post):
    """Read repeated medication_name/dosage/frequency/duration inputs -> (rows, errors)."""
    limits = {'medication_name': 200, 'dosage': 100, 'frequency': 100, 'duration': 100}
    columns = [post.getlist(key) for key in limits]
    rows, errors = [], []
    for values in zip_longest(*columns, fillvalue=''):
        row = {key: value.strip() for key, value in zip(limits, values)}
        if not row['medication_name']:
            continue
        for key, max_len in limits.items():
            if len(row[key]) > max_len:
                errors.append(f'{key.replace("_", " ").capitalize()} is too long (max {max_len} characters).')
        rows.append(row)
    if len(rows) > MAX_PRESCRIPTION_ROWS:
        errors.append(f'At most {MAX_PRESCRIPTION_ROWS} medications per record.')
    return rows, errors
