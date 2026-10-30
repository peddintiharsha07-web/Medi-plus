from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.reverse import reverse

from .models import LabReport, MedicalAttachment, MedicalRecord, PatientDocument, Prescription
from .validators import validate_medical_file


def _check_upload(value):
    try:
        validate_medical_file(value)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.messages)
    return value


class _FileChildSerializer(serializers.ModelSerializer):
    """Never expose a raw storage URL; give an authenticated download endpoint instead."""
    route = None
    download_url = serializers.SerializerMethodField()

    def get_download_url(self, obj):
        if not obj.file:
            return None
        return reverse(f'{self.route}-download', args=[obj.pk], request=self.context.get('request'))

    def validate_file(self, value):
        return _check_upload(value)


class PrescriptionSerializer(_FileChildSerializer):
    route = 'prescription'

    class Meta:
        model = Prescription
        fields = ['id', 'record', 'medication_name', 'dosage', 'frequency', 'duration',
                  'notes', 'file', 'download_url', 'created_at']
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {'file': {'write_only': True}}


class LabReportSerializer(_FileChildSerializer):
    route = 'labreport'

    class Meta:
        model = LabReport
        fields = ['id', 'record', 'title', 'report_date', 'file', 'download_url', 'notes', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']
        extra_kwargs = {'file': {'write_only': True}}


class MedicalAttachmentSerializer(_FileChildSerializer):
    route = 'attachment'

    class Meta:
        model = MedicalAttachment
        fields = ['id', 'record', 'file', 'download_url', 'description', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']
        extra_kwargs = {'file': {'write_only': True}}


class MedicalRecordSerializer(serializers.ModelSerializer):
    patient_medical_id = serializers.CharField(source='patient.medical_id', read_only=True)
    doctor_name = serializers.CharField(source='doctor.user.get_full_name', read_only=True)
    hospital_name = serializers.CharField(source='hospital.name', read_only=True)
    prescriptions = PrescriptionSerializer(many=True, read_only=True)
    lab_reports = LabReportSerializer(many=True, read_only=True)
    attachments = MedicalAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = MedicalRecord
        fields = ['id', 'patient', 'patient_medical_id', 'doctor', 'doctor_name', 'hospital',
                  'hospital_name', 'consultation_date', 'symptoms', 'diagnosis',
                  'treatment_details', 'follow_up_notes', 'discharge_summary', 'status',
                  'prescriptions', 'lab_reports', 'attachments', 'created_at', 'updated_at']
        read_only_fields = ['id', 'doctor', 'hospital', 'created_at', 'updated_at']

    def update(self, instance, validated_data):
        validated_data.pop('patient', None)  # a record can never be moved to another patient
        return super().update(instance, validated_data)


class PatientDocumentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = PatientDocument
        fields = ['id', 'category', 'title', 'description', 'record_date', 'provider_name', 'file',
                  'original_filename', 'content_type', 'file_size', 'shared_with_doctors',
                  'download_url', 'uploaded_at', 'updated_at']
        read_only_fields = ['id', 'original_filename', 'content_type', 'file_size', 'uploaded_at', 'updated_at']
        extra_kwargs = {'file': {'write_only': True}}

    def get_download_url(self, obj):
        if not obj.file:
            return None
        return reverse('patientdocument-download', args=[obj.pk], request=self.context.get('request'))

    def validate_file(self, value):
        return _check_upload(value)

    def validate(self, attrs):
        if self.instance is None and not attrs.get('file') and not (attrs.get('description') or '').strip():
            raise serializers.ValidationError('Provide a file or a description.')
        if self.instance is not None and 'file' in attrs:
            raise serializers.ValidationError({'file': 'The file cannot be replaced; delete and re-upload.'})
        return attrs
