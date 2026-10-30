"""
THE access policy. Every view / API endpoint exposing a patient's data goes through here.

    OWNER       the patient themselves
    READ        doctor with an active consent grant (view only)
    READ_WRITE  doctor with a grant that also allows adding consultation notes / prescriptions
    EMERGENCY   doctor flagged is_emergency_authorized WITHOUT consent: critical data only,
                via break-glass with a logged reason
    NONE        everybody else, including hospital admins and system admins
"""
from dataclasses import dataclass

NONE, EMERGENCY, READ, READ_WRITE, OWNER = 'NONE', 'EMERGENCY', 'READ', 'READ_WRITE', 'OWNER'


@dataclass(frozen=True)
class Access:
    level: str = NONE
    grant: object = None

    @property
    def allowed(self):
        return self.level != NONE

    @property
    def can_view_full(self):
        return self.level in (READ, READ_WRITE, OWNER)

    @property
    def can_add_consultation(self):
        return self.level == READ_WRITE

    @property
    def is_emergency_only(self):
        return self.level == EMERGENCY


def _doctor_profile(user):
    return getattr(user, 'doctor_profile', None)


def resolve_access(user, patient):
    from .models import AccessGrant

    if user is None or not getattr(user, 'is_authenticated', False) or not user.in_good_standing:
        return Access()
    if user.role == 'PATIENT':
        return Access(OWNER) if patient.user_id == user.id else Access()
    if user.role == 'DOCTOR':
        if user.status != 'APPROVED':
            return Access()
        doctor = _doctor_profile(user)
        if doctor is None:
            return Access()
        grant = AccessGrant.objects.effective().filter(patient=patient, doctor=doctor).first()
        if grant is not None:
            return Access(READ_WRITE if grant.scope == AccessGrant.Scope.VIEW_ADD else READ, grant)
        if doctor.is_emergency_authorized:
            return Access(EMERGENCY)
    return Access()


def authorized_patients_for(doctor):
    """PatientProfiles with an effective consent grant for ``doctor``."""
    from patients.models import PatientProfile
    from .models import AccessGrant
    return PatientProfile.objects.filter(
        pk__in=AccessGrant.objects.effective().filter(doctor=doctor).values('patient_id'))


def patients_visible_to(user):
    """PatientProfiles whose FULL data ``user`` may see (own profile / consented patients)."""
    from patients.models import PatientProfile
    if user is None or not user.is_authenticated or not user.in_good_standing:
        return PatientProfile.objects.none()
    if user.role == 'PATIENT':
        return PatientProfile.objects.filter(user=user)
    if user.role == 'DOCTOR' and user.status == 'APPROVED':
        doctor = _doctor_profile(user)
        if doctor is not None:
            return authorized_patients_for(doctor)
    return PatientProfile.objects.none()


def visible_documents(patient, access):
    """Patient-uploaded documents the viewer may see (doctors see only 'shared' ones)."""
    from medical_records.models import PatientDocument
    qs = PatientDocument.objects.filter(patient=patient)
    if access.level == OWNER:
        return qs
    if access.can_view_full:
        return qs.filter(shared_with_doctors=True)
    return qs.none()
