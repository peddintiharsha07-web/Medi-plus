from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from hospitals.models import Hospital
from .models import User


class PatientRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    phone_number = forms.CharField(required=True)
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=True)
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'phone_number',
                   'date_of_birth', 'address', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.PATIENT
        user.status = User.Status.APPROVED  # patients are self-approved
        if commit:
            user.save()
        return user


class DoctorRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    phone_number = forms.CharField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'phone_number',
                   'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.DOCTOR
        user.status = User.Status.PENDING  # requires system admin approval
        if commit:
            user.save()
        return user


class HospitalAdminRegistrationForm(UserCreationForm):
    # Hospital administrator account details
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    phone_number = forms.CharField(required=True)

    # Hospital details: create the Hospital record at the same time as its admin.
    hospital_name = forms.CharField(label='Hospital name', max_length=255, required=True)
    registration_number = forms.CharField(label='Hospital registration number', max_length=100, required=True)
    hospital_address = forms.CharField(label='Hospital address', widget=forms.Textarea(attrs={'rows': 2}), required=True)
    city = forms.CharField(max_length=100, required=True)
    state = forms.CharField(max_length=100, required=True)
    hospital_phone = forms.CharField(label='Hospital phone', max_length=20, required=True)
    hospital_email = forms.EmailField(label='Hospital email', required=True)
    logo = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'phone_number',
                   'password1', 'password2')

    def clean_registration_number(self):
        registration_number = self.cleaned_data['registration_number'].strip()
        if Hospital.objects.filter(registration_number=registration_number).exists():
            raise forms.ValidationError('A hospital with this registration number is already registered.')
        return registration_number

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.HOSPITAL_ADMIN
        user.status = User.Status.PENDING  # requires system admin approval
        if not commit:
            return user

        # Keep both records in one transaction so neither is left half-created.
        with transaction.atomic():
            user.save()
            Hospital.objects.create(
                admin=user,
                name=self.cleaned_data['hospital_name'].strip(),
                registration_number=self.cleaned_data['registration_number'],
                address=self.cleaned_data['hospital_address'].strip(),
                city=self.cleaned_data['city'].strip(),
                state=self.cleaned_data['state'].strip(),
                phone=self.cleaned_data['hospital_phone'].strip(),
                email=self.cleaned_data['hospital_email'].strip(),
                logo=self.cleaned_data.get('logo'),
                status=Hospital.Status.PENDING,
            )
        return user


class LoginForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))
