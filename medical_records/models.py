import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .validators import sniff_content_type, validate_medical_file


class MedicalRecord(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        CLOSED = 'CLOSED', 'Closed'
        DISCHARGED = 'DISCHARGED', 'Discharged'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey('patients.PatientProfile', on_delete=models.CASCADE, related_name='medical_records')
    doctor = models.ForeignKey('doctors.DoctorProfile', on_delete=models.SET_NULL, null=True,
                                related_name='medical_records')
    hospital = models.ForeignKey('hospitals.Hospital', on_delete=models.SET_NULL, null=True,
                                  related_name='medical_records')
    consultation_date = models.DateTimeField()
    symptoms = models.TextField(blank=True)
    diagnosis = models.TextField(blank=True)
    treatment_details = models.TextField(blank=True)
    follow_up_notes = models.TextField(blank=True)
    discharge_summary = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-consultation_date']

    def __str__(self):
        return f"Record {self.id} - {self.patient.medical_id}"


class Prescription(models.Model):
    record = models.ForeignKey(MedicalRecord, on_delete=models.CASCADE, related_name='prescriptions')
    medication_name = models.CharField(max_length=200)
    dosage = models.CharField(max_length=100, blank=True)
    frequency = models.CharField(max_length=100, blank=True)
    duration = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    file = models.FileField(upload_to='prescriptions/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.medication_name} - {self.record.patient.medical_id}"


class LabReport(models.Model):
    record = models.ForeignKey(MedicalRecord, on_delete=models.CASCADE, related_name='lab_reports')
    title = models.CharField(max_length=200)
    report_date = models.DateField()
    file = models.FileField(upload_to='lab_reports/', blank=True, null=True)
    notes = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.record.patient.medical_id}"


class MedicalAttachment(models.Model):
    record = models.ForeignKey(MedicalRecord, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='attachments/')
    description = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.description or str(self.file)


def patient_document_path(instance, filename):
    """Random storage name: the original file name never reaches the storage layer."""
    ext = os.path.splitext(filename)[1].lower()
    return f'patient_documents/{instance.patient_id}/{uuid.uuid4().hex}{ext}'


class PatientDocument(models.Model):
    """
    A record the PATIENT keeps themselves: history, prescriptions, lab/diagnostic reports,
    certificates, hospital visit summaries. (Doctor-authored consultations stay in MedicalRecord.)
    """
    class Category(models.TextChoices):
        MEDICAL_HISTORY = 'MEDICAL_HISTORY', 'Medical history / previous treatment'
        PRESCRIPTION = 'PRESCRIPTION', 'Doctor prescription'
        LAB_REPORT = 'LAB_REPORT', 'Lab test report'
        DIAGNOSTIC = 'DIAGNOSTIC', 'Diagnostic result (scan, X-ray, ECG...)'
        CERTIFICATE = 'CERTIFICATE', 'Medical certificate'
        HOSPITAL_VISIT = 'HOSPITAL_VISIT', 'Hospital visit / treatment summary'
        OTHER = 'OTHER', 'Other health information'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey('patients.PatientProfile', on_delete=models.CASCADE, related_name='documents')
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    record_date = models.DateField(default=timezone.localdate, help_text='Date of the visit / test / document')
    provider_name = models.CharField('Doctor / hospital', max_length=150, blank=True)
    file = models.FileField(upload_to=patient_document_path, blank=True, null=True,
                            validators=[validate_medical_file])
    original_filename = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    shared_with_doctors = models.BooleanField(
        default=True,
        help_text='Doctors you have given access to can see this. Untick to keep it private to you.')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name='+')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-record_date', '-uploaded_at']

    def __str__(self):
        return f'{self.title} ({self.patient.medical_id})'

    def clean(self):
        if not self.file and not self.description.strip():
            raise ValidationError('Attach a file, or describe the record in the description box.')

    def save(self, *args, **kwargs):
        upload = self.file
        if upload and not upload._committed:  # a new file is being attached right now
            raw = upload.file
            self.original_filename = os.path.basename(getattr(raw, 'name', '') or upload.name)[:255]
            self.file_size = getattr(raw, 'size', 0) or 0
            self.content_type = sniff_content_type(raw) or ''
        super().save(*args, **kwargs)
