import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        PATIENT = 'PATIENT', 'Patient'
        DOCTOR = 'DOCTOR', 'Doctor'
        HOSPITAL_ADMIN = 'HOSPITAL_ADMIN', 'Hospital Administrator'
        SYSTEM_ADMIN = 'SYSTEM_ADMIN', 'System Administrator'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Approval'
        APPROVED = 'APPROVED', 'Approved'
        SUSPENDED = 'SUSPENDED', 'Suspended'
        REJECTED = 'REJECTED', 'Rejected'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=Role.choices)
    phone_number = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    preferred_language = models.CharField(max_length=10, default='en')
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_patient(self):
        return self.role == self.Role.PATIENT

    @property
    def is_doctor(self):
        return self.role == self.Role.DOCTOR

    @property
    def is_hospital_admin(self):
        return self.role == self.Role.HOSPITAL_ADMIN

    @property
    def is_system_admin(self):
        return self.role == self.Role.SYSTEM_ADMIN

    @property
    def is_approved(self):
        return self.status == self.Status.APPROVED

    @property
    def in_good_standing(self):
        """False for deactivated/suspended/rejected accounts and for unapproved doctors / hospital admins."""
        if not self.is_active:
            return False
        if self.status in (self.Status.SUSPENDED, self.Status.REJECTED):
            return False
        if self.role in (self.Role.DOCTOR, self.Role.HOSPITAL_ADMIN) and self.status != self.Status.APPROVED:
            return False
        return True


class AuditLog(models.Model):
    class ActionType(models.TextChoices):
        LOGIN = 'LOGIN', 'Login'
        LOGOUT = 'LOGOUT', 'Logout'
        RECORD_CREATE = 'RECORD_CREATE', 'Medical Record Created'
        RECORD_UPDATE = 'RECORD_UPDATE', 'Medical Record Updated'
        RECORD_VIEW = 'RECORD_VIEW', 'Medical Record Viewed'
        EMERGENCY_ACCESS = 'EMERGENCY_ACCESS', 'Emergency Access Used'
        HOSPITAL_APPROVED = 'HOSPITAL_APPROVED', 'Hospital Approved'
        DOCTOR_APPROVED = 'DOCTOR_APPROVED', 'Doctor Approved'
        ACCOUNT_SUSPENDED = 'ACCOUNT_SUSPENDED', 'Account Suspended'
        SHARE_GRANTED = 'SHARE_GRANTED', 'Record Share Granted'
        APPOINTMENT_BOOKED = 'APPOINTMENT_BOOKED', 'Appointment Booked'
        OTHER = 'OTHER', 'Other'

    id = models.BigAutoField(primary_key=True)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_actions')
    action_type = models.CharField(max_length=30, choices=ActionType.choices)
    description = models.TextField()
    target_object = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp}] {self.action_type} by {self.actor}"
