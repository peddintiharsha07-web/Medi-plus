from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS

from api.mixins import FileDownloadMixin
from consents.audit import log_access
from consents.models import RecordAccessLog
from consents.policy import patients_visible_to, resolve_access, visible_documents
from core.permissions import IsApprovedAccount, IsDoctor, IsPatient

from .models import LabReport, MedicalAttachment, MedicalRecord, PatientDocument, Prescription
from .serializers import (LabReportSerializer, MedicalAttachmentSerializer, MedicalRecordSerializer,
                          PatientDocumentSerializer, PrescriptionSerializer)


def _doctor(user):
    return getattr(user, 'doctor_profile', None)


class MedicalRecordViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                           mixins.ListModelMixin, viewsets.GenericViewSet):
    """Patients read their own. Doctors read consented patients'; create/edit only with an 'add notes'
    consent, and edit only records they wrote. There is deliberately no DELETE."""
    serializer_class = MedicalRecordSerializer

    def get_permissions(self):
        return [IsApprovedAccount()] if self.request.method in SAFE_METHODS else [IsDoctor()]

    def get_queryset(self):
        return (MedicalRecord.objects.filter(patient__in=patients_visible_to(self.request.user))
                .select_related('patient__user', 'doctor__user', 'hospital')
                .prefetch_related('prescriptions', 'lab_reports', 'attachments'))

    def retrieve(self, request, *args, **kwargs):
        record = self.get_object()
        log_access(request, record.patient, RecordAccessLog.Action.VIEW_PROFILE,
                   resolve_access(request.user, record.patient), detail='api record')
        return super().retrieve(request, *args, **kwargs)

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        if self.action == 'create':
            serializer.fields['patient'].queryset = patients_visible_to(self.request.user)
        return serializer

    def perform_create(self, serializer):
        patient = serializer.validated_data['patient']
        if not resolve_access(self.request.user, patient).can_add_consultation:
            raise PermissionDenied('The patient has not allowed you to add consultation notes.')
        doctor = _doctor(self.request.user)
        serializer.save(doctor=doctor, hospital=doctor.hospital)

    def perform_update(self, serializer):
        record, doctor = serializer.instance, _doctor(self.request.user)
        if record.doctor_id != getattr(doctor, 'id', None):
            raise PermissionDenied('You can only edit records you wrote.')
        if not resolve_access(self.request.user, record.patient).can_add_consultation:
            raise PermissionDenied('Your permission to add notes for this patient has ended.')
        serializer.save()


class _RecordChildViewSet(FileDownloadMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin,
                          mixins.UpdateModelMixin, mixins.DestroyModelMixin, mixins.ListModelMixin,
                          viewsets.GenericViewSet):
    model = None
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        return [IsApprovedAccount()] if self.request.method in SAFE_METHODS else [IsDoctor()]

    def get_queryset(self):
        return self.model.objects.filter(
            record__patient__in=patients_visible_to(self.request.user)).select_related('record__patient').order_by('pk')

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        if self.action == 'create':
            serializer.fields['record'].queryset = MedicalRecord.objects.filter(
                patient__in=patients_visible_to(self.request.user))
        return serializer

    def _require_write(self, record):
        doctor = _doctor(self.request.user)
        if record.doctor_id != getattr(doctor, 'id', None):
            raise PermissionDenied('You can only change items on records you wrote.')
        if not resolve_access(self.request.user, record.patient).can_add_consultation:
            raise PermissionDenied('Your permission to add notes for this patient has ended.')

    def perform_create(self, serializer):
        self._require_write(serializer.validated_data['record'])
        serializer.save()

    def perform_update(self, serializer):
        self._require_write(serializer.instance.record)
        serializer.save(record=serializer.instance.record)

    def perform_destroy(self, instance):
        self._require_write(instance.record)
        instance.delete()


class PrescriptionViewSet(_RecordChildViewSet):
    model, file_kind, serializer_class = Prescription, 'prescription', PrescriptionSerializer


class LabReportViewSet(_RecordChildViewSet):
    model, file_kind, serializer_class = LabReport, 'labreport', LabReportSerializer


class MedicalAttachmentViewSet(_RecordChildViewSet):
    model, file_kind, serializer_class = MedicalAttachment, 'attachment', MedicalAttachmentSerializer


class PatientDocumentViewSet(FileDownloadMixin, viewsets.ModelViewSet):
    """Patient-uploaded records. Patients: full CRUD on their own. Doctors: read 'shared' documents of consented patients."""
    file_kind = 'document'
    serializer_class = PatientDocumentSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        return [IsApprovedAccount()] if self.request.method in SAFE_METHODS else [IsPatient()]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'PATIENT':
            return PatientDocument.objects.filter(patient__user=user)
        qs = PatientDocument.objects.none()
        for patient in patients_visible_to(user):
            qs = qs | visible_documents(patient, resolve_access(user, patient))
        return qs

    def perform_create(self, serializer):
        serializer.save(patient=self.request.user.patient_profile, uploaded_by=self.request.user)
