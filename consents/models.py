import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class AccessGrantQuerySet(models.QuerySet):
    def effective(self):
        """Grants that are ACTIVE and not past their expiry."""
        return self.filter(status=AccessGrant.Status.ACTIVE).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))


class AccessGrant(models.Model):
    """A patient's consent allowing ONE doctor to see their records (patient- or doctor-initiated)."""
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Awaiting patient decision'
        ACTIVE = 'ACTIVE', 'Active'
        DENIED = 'DENIED', 'Denied'
        REVOKED = 'REVOKED', 'Revoked'

    class Scope(models.TextChoices):
        VIEW = 'VIEW', 'View records only'
        VIEW_ADD = 'VIEW_ADD', 'View records and add consultation notes / prescriptions'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey('patients.PatientProfile', on_delete=models.CASCADE, related_name='access_grants')
    doctor = models.ForeignKey('doctors.DoctorProfile', on_delete=models.CASCADE, related_name='access_grants')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    scope = models.CharField(max_length=10, choices=Scope.choices, default=Scope.VIEW)
    initiated_by_doctor = models.BooleanField(default=False)
    request_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    objects = AccessGrantQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['patient', 'doctor'], name='uniq_access_grant_patient_doctor')]

    def __str__(self):
        return f'{self.patient.medical_id} -> {self.doctor} [{self.status}]'

    @property
    def is_expired(self):
        return self.expires_at is not None and self.expires_at <= timezone.now()

    @property
    def is_effective(self):
        return self.status == self.Status.ACTIVE and not self.is_expired

    @property
    def state_label(self):
        if self.status == self.Status.ACTIVE and self.is_expired:
            return 'Expired'
        return self.get_status_display()

    def activate(self, scope, days):
        now = timezone.now()
        self.status = self.Status.ACTIVE
        self.scope = scope
        self.decided_at = now
        self.revoked_at = None
        self.expires_at = now + timedelta(days=days) if days else None
        self.save()

    def deny(self):
        self.status = self.Status.DENIED
        self.decided_at = timezone.now()
        self.save(update_fields=['status', 'decided_at'])

    def revoke(self):
        self.status = self.Status.REVOKED
        self.revoked_at = timezone.now()
        self.save(update_fields=['status', 'revoked_at'])


class RecordAccessLog(models.Model):
    """Who looked at (or tried to look at) a patient's data. Visible to the patient. Metadata only."""
    class Action(models.TextChoices):
        VIEW_PROFILE = 'VIEW_PROFILE', 'Viewed patient records'
        DOWNLOAD_FILE = 'DOWNLOAD_FILE', 'Opened / downloaded a file'
        ADD_RECORD = 'ADD_RECORD', 'Added a consultation record'
        QR_SCAN = 'QR_SCAN', 'Scanned QR code'
        EMERGENCY_VIEW = 'EMERGENCY_VIEW', 'Emergency access (limited data)'
        REQUEST_ACCESS = 'REQUEST_ACCESS', 'Requested access'
        ACCESS_DENIED = 'ACCESS_DENIED', 'Access denied'

    patient = models.ForeignKey('patients.PatientProfile', on_delete=models.CASCADE, related_name='access_logs')
    accessed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    related_name='record_access_logs')
    accessor_role = models.CharField(max_length=20, blank=True)
    access_level = models.CharField(max_length=12, blank=True)
    action = models.CharField(max_length=20, choices=Action.choices)
    detail = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
