import secrets
import string
import uuid
from django.db import models
from django.conf import settings


def generate_medical_id():
    while True:
        candidate = 'MED-' + ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        if not PatientProfile.objects.filter(medical_id=candidate).exists():
            return candidate


class PatientProfile(models.Model):
    class BloodGroup(models.TextChoices):
        A_POS = 'A+', 'A+'
        A_NEG = 'A-', 'A-'
        B_POS = 'B+', 'B+'
        B_NEG = 'B-', 'B-'
        AB_POS = 'AB+', 'AB+'
        AB_NEG = 'AB-', 'AB-'
        O_POS = 'O+', 'O+'
        O_NEG = 'O-', 'O-'
        UNKNOWN = 'UNKNOWN', 'Unknown'

    class Gender(models.TextChoices):
        MALE = 'MALE', 'Male'
        FEMALE = 'FEMALE', 'Female'
        OTHER = 'OTHER', 'Other'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='patient_profile')
    medical_id = models.CharField(max_length=20, unique=True, default=generate_medical_id, editable=False)
    gender = models.CharField(max_length=10, choices=Gender.choices, default=Gender.OTHER)
    blood_group = models.CharField(max_length=10, choices=BloodGroup.choices, default=BloodGroup.UNKNOWN)
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    chronic_diseases = models.TextField(blank=True, help_text="Comma-separated chronic conditions")
    current_medications = models.TextField(blank=True, help_text="Comma-separated current medications")
    organ_donor = models.BooleanField(default=False)
    height_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.get_full_name()} [{self.medical_id}]"

    @property
    def critical_info(self):
        """Data shown in emergency access mode only."""
        return {
            'blood_group': self.get_blood_group_display(),
            'allergies': list(self.allergies.values_list('allergen', flat=True)),
            'current_medications': self.current_medications,
            'chronic_diseases': self.chronic_diseases,
            'emergency_contact_name': self.emergency_contact_name,
            'emergency_contact_phone': self.emergency_contact_phone,
            'organ_donor': self.organ_donor,
        }


class Allergy(models.Model):
    class Severity(models.TextChoices):
        MILD = 'MILD', 'Mild'
        MODERATE = 'MODERATE', 'Moderate'
        SEVERE = 'SEVERE', 'Severe'

    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='allergies')
    allergen = models.CharField(max_length=150)
    reaction = models.CharField(max_length=255, blank=True)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MILD)
    recorded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.allergen} ({self.severity})"


class Vaccination(models.Model):
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='vaccinations')
    vaccine_name = models.CharField(max_length=150)
    date_administered = models.DateField()
    next_due_date = models.DateField(null=True, blank=True)
    administered_by = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return f"{self.vaccine_name} - {self.patient.medical_id}"
