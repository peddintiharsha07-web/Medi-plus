from django import forms
from django.utils import timezone

from doctors.models import DoctorProfile
from users.models import User

from .models import Allergy, PatientProfile


class PatientUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'date_of_birth', 'address']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'address': forms.Textarea(attrs={'rows': 2}),
        }

    def clean_date_of_birth(self):
        value = self.cleaned_data.get('date_of_birth')
        if value and value > timezone.localdate():
            raise forms.ValidationError('Date of birth cannot be in the future.')
        return value


class PatientHealthForm(forms.ModelForm):
    class Meta:
        model = PatientProfile
        fields = ['gender', 'blood_group', 'height_cm', 'weight_kg', 'emergency_contact_name',
                  'emergency_contact_phone', 'chronic_diseases', 'current_medications', 'organ_donor']
        widgets = {'chronic_diseases': forms.Textarea(attrs={'rows': 2}),
                   'current_medications': forms.Textarea(attrs={'rows': 2})}

    def clean_height_cm(self):
        value = self.cleaned_data.get('height_cm')
        if value is not None and not (30 <= value <= 272):
            raise forms.ValidationError('Enter a realistic height in centimetres.')
        return value

    def clean_weight_kg(self):
        value = self.cleaned_data.get('weight_kg')
        if value is not None and not (1 <= value <= 700):
            raise forms.ValidationError('Enter a realistic weight in kilograms.')
        return value


class AllergyForm(forms.ModelForm):
    class Meta:
        model = Allergy
        fields = ['allergen', 'reaction', 'severity']


class AppointmentRequestForm(forms.Form):
    doctor = forms.ModelChoiceField(queryset=DoctorProfile.objects.none())
    appointment_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    appointment_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))
    reason = forms.CharField(max_length=255, required=False)
    share_records = forms.BooleanField(
        required=False, label='Let this doctor view my records and add consultation notes for 30 days')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['doctor'].queryset = DoctorProfile.objects.filter(
            user__status='APPROVED', user__is_active=True).select_related('user', 'hospital')

    def clean_appointment_date(self):
        value = self.cleaned_data['appointment_date']
        if value < timezone.localdate():
            raise forms.ValidationError('Choose today or a future date.')
        return value
