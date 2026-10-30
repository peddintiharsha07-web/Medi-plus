import uuid
from django.db import models


class EmergencyAccessLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey('patients.PatientProfile', on_delete=models.CASCADE,
                                 related_name='emergency_access_logs')
    accessed_by = models.ForeignKey('doctors.DoctorProfile', on_delete=models.SET_NULL, null=True,
                                     related_name='emergency_accesses')
    reason = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    accessed_at = models.DateTimeField(auto_now_add=True)
    patient_notified = models.BooleanField(default=False)

    class Meta:
        ordering = ['-accessed_at']

    def __str__(self):
        return f"Emergency access to {self.patient.medical_id} at {self.accessed_at}"
