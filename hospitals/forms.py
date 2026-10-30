from django import forms
from .models import Hospital, Department


class HospitalProfileForm(forms.ModelForm):
    class Meta:
        model = Hospital
        fields = ['name', 'registration_number', 'address', 'city', 'state', 'phone', 'email', 'logo']


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'description']
