from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from hospitals.models import Hospital
from .models import User

class HospitalAdminRegistrationForm(UserCreationForm):
    # Hospital administrator details
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    phone_number = forms.CharField(required=True)

    # Hospital details
    hospital_name = forms.CharField(required=True)
    registration_number = forms.CharField(required=True)
    hospital_address = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=True
    )
    city = forms.CharField(required=True)
    state = forms.CharField(required=True)
    hospital_phone = forms.CharField(required=True)
    hospital_email = forms.EmailField(required=True)
    logo = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = (
            'username', 'email', 'first_name', 'last_name',
            'phone_number', 'password1', 'password2'
        )

    def clean_registration_number(self):
        registration_number = self.cleaned_data['registration_number'].strip()

        if Hospital.objects.filter(
            registration_number=registration_number
        ).exists():
            raise forms.ValidationError(
                'A hospital with this registration number is already registered.'
            )

        return registration_number

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.HOSPITAL_ADMIN
        user.status = User.Status.PENDING

        if not commit:
            return user

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
                email=self.cleaned_data['hospital_email'],
                logo=self.cleaned_data.get('logo'),
                status=Hospital.Status.PENDING,
            )

        return user