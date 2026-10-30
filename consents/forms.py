from django import forms

from doctors.models import DoctorProfile

from .models import AccessGrant

DURATION_CHOICES = [(7, '7 days'), (30, '30 days'), (90, '90 days'), (180, '6 months'), (365, '1 year')]


class DecisionForm(forms.Form):
    duration_days = forms.TypedChoiceField(choices=DURATION_CHOICES, coerce=int, initial=30, label='Access lasts for')
    scope = forms.ChoiceField(choices=AccessGrant.Scope.choices, initial=AccessGrant.Scope.VIEW,
                              widget=forms.RadioSelect, label='What the doctor may do')


class GrantForm(DecisionForm):
    doctor = forms.ModelChoiceField(queryset=DoctorProfile.objects.none(), label='Doctor')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['doctor'].queryset = DoctorProfile.objects.filter(
            user__status='APPROVED', user__is_active=True).select_related('user', 'hospital')
        self.fields['doctor'].label_from_instance = lambda d: (
            f'Dr. {d.user.get_full_name()} - {d.specialization}' + (f' ({d.hospital.name})' if d.hospital else ''))


class RequestAccessForm(forms.Form):
    medical_id = forms.CharField(max_length=20)
    note = forms.CharField(max_length=255, required=False)

    def clean_medical_id(self):
        return self.cleaned_data['medical_id'].strip().upper()
