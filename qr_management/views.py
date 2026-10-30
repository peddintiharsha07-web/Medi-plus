from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from consents.audit import log_access
from consents.models import RecordAccessLog
from consents.policy import EMERGENCY, OWNER, resolve_access
from core import throttle
from emergency.services import MIN_REASON_LENGTH, perform_emergency_access
from users.models import AuditLog

from .services import resolve_token

FAIL_LIMIT, FAIL_WINDOW = 10, 600  # invalid scans allowed per user per 10 minutes


@login_required
def scan(request, token):
    """Landing page for a scanned QR code: authenticate, then show only what role + consent allow."""
    user = request.user
    if throttle.is_limited('qrscan_fail', user.pk, FAIL_LIMIT, FAIL_WINDOW):
        return render(request, 'qr_management/invalid.html', {'throttled': True}, status=429)

    qr = resolve_token(token)
    if qr is None:  # identical response for unknown / revoked / expired
        throttle.record('qrscan_fail', user.pk)
        AuditLog.objects.create(actor=user, action_type=AuditLog.ActionType.OTHER,
                                description='Invalid, revoked or expired QR code scanned')
        return render(request, 'qr_management/invalid.html', status=404)

    patient = qr.patient
    access = resolve_access(user, patient)
    if access.level == OWNER:
        return redirect('patients:my_qr_card')
    if access.can_view_full:
        log_access(request, patient, RecordAccessLog.Action.QR_SCAN, access, detail='QR scan')
        return redirect('doctors:patient_detail', medical_id=patient.medical_id)
    if access.level == EMERGENCY:
        return _emergency_gate(request, patient, access)

    log_access(request, patient, RecordAccessLog.Action.ACCESS_DENIED, access, detail='QR scan without consent')
    if user.role == 'DOCTOR':
        return render(request, 'doctors/access_required.html', {'patient': patient}, status=403)
    raise PermissionDenied('You are not authorized to view this patient.')


def _emergency_gate(request, patient, access):
    critical_info = error = None
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if len(reason) < MIN_REASON_LENGTH:
            error = 'Please state the reason for emergency access.'
        else:
            critical_info = perform_emergency_access(request, request.user.doctor_profile, patient, reason)
            messages.warning(request, 'Emergency access has been logged and is visible to the patient.')
    else:
        log_access(request, patient, RecordAccessLog.Action.QR_SCAN, access, detail='QR scan (limited access)')
    return render(request, 'qr_management/emergency_gate.html',
                  {'patient': patient, 'critical_info': critical_info, 'error': error})
