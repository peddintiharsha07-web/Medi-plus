import uuid
from django.db import models
from django.conf import settings


class DoctorProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='doctor_profile')
    hospital = models.ForeignKey('hospitals.Hospital', on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='doctors')
    department = models.ForeignKey('hospitals.Department', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='doctors')
    specialization = models.CharField(max_length=150)
    license_number = models.CharField(max_length=100, unique=True)
    years_of_experience = models.PositiveIntegerField(default=0)
    consultation_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    bio = models.TextField(blank=True)
    is_emergency_authorized = models.BooleanField(
        default=False, help_text="Can this doctor use one-click emergency access mode?")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Dr. {self.user.get_full_name()} ({self.specialization})"
