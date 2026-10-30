from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from core import throttle
from qr_management.services import extract_token, resolve_token

from .services import MIN_REASON_LENGTH, perform_emergency_access


@login_required
def emergency_access(request):
    """Break-glass lookup for emergency-authorized doctors: link + reason -> critical info only. Always logged."""
    user = request.user
    doctor_profile = getattr(user, 'doctor_profile', None)
    if (user.role != 'DOCTOR' or doctor_profile is None or not user.in_good_standing
            or not doctor_profile.is_emergency_authorized):
        raise PermissionDenied('Only emergency-authorized doctors can use emergency access mode.')

    patient = critical_info = error = None
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        token = extract_token(request.POST.get('token', ''))
        if throttle.is_limited('qrscan_fail', user.pk, 10, 600):
            error = 'Too many invalid attempts. Please wait a few minutes.'
        elif len(reason) < MIN_REASON_LENGTH:
            error = 'Please state the reason for emergency access.'
        else:
            qr = resolve_token(token) if token else None
            if qr is None:
                throttle.record('qrscan_fail', user.pk)
                error = 'Invalid, revoked or expired QR code.'
            else:
                patient = qr.patient
                critical_info = perform_emergency_access(request, doctor_profile, patient, reason)
                messages.warning(request, f'Emergency access to {patient.medical_id} has been logged '
                                          f'and is visible to the patient in their access history.')
    return render(request, 'emergency/access.html', {'patient': patient, 'critical_info': critical_info, 'error': error})


@login_required
def my_emergency_logs(request):
    if request.user.role != 'PATIENT':
        raise PermissionDenied
    logs = request.user.patient_profile.emergency_access_logs.select_related('accessed_by__user').all()
    return render(request, 'emergency/my_logs.html', {'logs': logs})
