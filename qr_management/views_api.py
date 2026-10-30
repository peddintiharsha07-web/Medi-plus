from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from consents.audit import log_access
from consents.models import RecordAccessLog
from consents.policy import EMERGENCY, resolve_access
from core import throttle
from core.permissions import IsApprovedAccount, IsPatient
from emergency.services import MIN_REASON_LENGTH, perform_emergency_access

from . import services
from .models import PatientQRCode
from .serializers import PatientQRCodeSerializer


class PatientQRCodeViewSet(viewsets.ReadOnlyModelViewSet):
    """A patient's own QR code. Patients only; there is no listing of anybody else's token."""
    serializer_class = PatientQRCodeSerializer
    permission_classes = [IsPatient]

    def get_queryset(self):
        return PatientQRCode.objects.select_related('patient__user').filter(patient__user=self.request.user).order_by('pk')

    @action(detail=False, methods=['post'])
    def rotate(self, request):
        qr = services.rotate_qr(services.generate_qr_for_patient(request.user.patient_profile))
        return Response(self.get_serializer(qr).data)

    @action(detail=False, methods=['post'])
    def revoke(self, request):
        qr = services.revoke_qr(services.generate_qr_for_patient(request.user.patient_profile))
        return Response(self.get_serializer(qr).data)


def _resolve_or_404(request, token):
    if throttle.is_limited('qrscan_fail', request.user.pk, 10, 600):
        raise NotFound()
    qr = services.resolve_token(token)
    if qr is None:
        throttle.record('qrscan_fail', request.user.pk)
        raise NotFound()
    return qr


@api_view(['GET'])
@permission_classes([IsApprovedAccount])
def qr_resolve(request, token):
    """Identify a scanned QR for an authorized doctor. Unauthorized callers get the same 404 as a bad token."""
    qr = _resolve_or_404(request, token)
    access = resolve_access(request.user, qr.patient)
    if access.can_view_full and request.user.role == 'DOCTOR':
        log_access(request, qr.patient, RecordAccessLog.Action.QR_SCAN, access, detail='api')
        return Response({'access_level': access.level, 'medical_id': qr.patient.medical_id,
                         'full_name': qr.patient.user.get_full_name()})
    if access.level == EMERGENCY:
        return Response({'access_level': EMERGENCY,
                         'detail': 'No consent on file. POST a reason to emergency/ for critical info only.'})
    raise NotFound()


@api_view(['POST'])
@permission_classes([IsApprovedAccount])
def qr_emergency(request, token):
    qr = _resolve_or_404(request, token)
    reason = str(request.data.get('reason', '')).strip()
    if request.user.role != 'DOCTOR' or not request.user.doctor_profile.is_emergency_authorized:
        raise NotFound()
    if len(reason) < MIN_REASON_LENGTH:
        return Response({'reason': 'A reason is required.'}, status=400)
    info = perform_emergency_access(request, request.user.doctor_profile, qr.patient, reason)
    return Response({'medical_id': qr.patient.medical_id, 'critical_info': info})
