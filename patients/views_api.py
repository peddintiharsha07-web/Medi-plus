from rest_framework import mixins, viewsets
from rest_framework.permissions import SAFE_METHODS

from consents.audit import log_access
from consents.models import RecordAccessLog
from consents.policy import patients_visible_to, resolve_access
from core.permissions import IsApprovedAccount, IsPatient

from .models import Allergy, Vaccination
from .serializers import AllergySerializer, PatientProfileSerializer, VaccinationSerializer


class PatientProfileViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                            mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Patients: own profile (read/update). Doctors: consented patients (read-only). Nobody else."""
    serializer_class = PatientProfileSerializer

    def get_permissions(self):
        return [IsApprovedAccount()] if self.request.method in SAFE_METHODS else [IsPatient()]

    def get_queryset(self):
        return (patients_visible_to(self.request.user).select_related('user')
                .prefetch_related('allergies', 'vaccinations'))

    def retrieve(self, request, *args, **kwargs):
        patient = self.get_object()
        log_access(request, patient, RecordAccessLog.Action.VIEW_PROFILE,
                   resolve_access(request.user, patient), detail='api')
        return super().retrieve(request, *args, **kwargs)


class _PatientOwnedViewSet(viewsets.ModelViewSet):
    model = None

    def get_permissions(self):
        return [IsApprovedAccount()] if self.request.method in SAFE_METHODS else [IsPatient()]

    def get_queryset(self):
        return self.model.objects.filter(patient__in=patients_visible_to(self.request.user))

    def perform_create(self, serializer):
        serializer.save(patient=self.request.user.patient_profile)


class AllergyViewSet(_PatientOwnedViewSet):
    model = Allergy
    serializer_class = AllergySerializer


class VaccinationViewSet(_PatientOwnedViewSet):
    model = Vaccination
    serializer_class = VaccinationSerializer
