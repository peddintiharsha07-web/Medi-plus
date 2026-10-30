from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core import throttle
from core.decorators import doctor_required, patient_required
from patients.models import PatientProfile

from .audit import log_access
from .forms import DecisionForm, GrantForm, RequestAccessForm
from .models import AccessGrant, RecordAccessLog
from .policy import Access, NONE

REQUEST_LIMIT, REQUEST_WINDOW = 20, 3600
DENIED_COOLDOWN = timedelta(days=7)


@patient_required
def privacy_center(request):
    profile = request.user.patient_profile
    grants = list(profile.access_grants.select_related('doctor__user', 'doctor__hospital'))
    return render(request, 'consents/privacy_center.html', {
        'profile': profile,
        'pending': [g for g in grants if g.status == AccessGrant.Status.PENDING],
        'active': [g for g in grants if g.is_effective],
        'past': [g for g in grants if g.status in (AccessGrant.Status.DENIED, AccessGrant.Status.REVOKED)
                 or (g.status == AccessGrant.Status.ACTIVE and g.is_expired)],
        'logs': profile.access_logs.select_related('accessed_by')[:50],
        'grant_form': GrantForm(),
        'decision_form': DecisionForm(),
    })


@patient_required
@require_POST
def grant_access(request):
    profile = request.user.patient_profile
    form = GrantForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Please choose a doctor, a duration and what the doctor may do.')
        return redirect('consents:privacy_center')
    doctor = form.cleaned_data['doctor']
    grant, _ = AccessGrant.objects.get_or_create(patient=profile, doctor=doctor)
    grant.activate(form.cleaned_data['scope'], form.cleaned_data['duration_days'])
    messages.success(request, f'Dr. {doctor.user.get_full_name()} can now access your records '
                              f'until {grant.expires_at:%b %d, %Y}.')
    return redirect('consents:privacy_center')


def _own_grant(request, grant_id):
    # Scoped to the logged-in patient: nobody can act on someone else's grant.
    return get_object_or_404(AccessGrant, pk=grant_id, patient=request.user.patient_profile)


@patient_required
@require_POST
def approve_request(request, grant_id):
    grant = _own_grant(request, grant_id)
    form = DecisionForm(request.POST)
    if grant.status != AccessGrant.Status.PENDING or not form.is_valid():
        messages.error(request, 'That request can no longer be approved.')
        return redirect('consents:privacy_center')
    grant.activate(form.cleaned_data['scope'], form.cleaned_data['duration_days'])
    messages.success(request, f'Access approved for Dr. {grant.doctor.user.get_full_name()}.')
    return redirect('consents:privacy_center')


@patient_required
@require_POST
def deny_request(request, grant_id):
    grant = _own_grant(request, grant_id)
    if grant.status == AccessGrant.Status.PENDING:
        grant.deny()
        messages.info(request, 'Request denied.')
    return redirect('consents:privacy_center')


@patient_required
@require_POST
def revoke_grant(request, grant_id):
    grant = _own_grant(request, grant_id)
    if grant.status == AccessGrant.Status.ACTIVE:
        grant.revoke()
        messages.success(request, f'Access removed for Dr. {grant.doctor.user.get_full_name()}.')
    return redirect('consents:privacy_center')


@doctor_required
@require_POST
def request_access(request):
    """A doctor asks a patient for consent; the patient decides in their privacy centre."""
    doctor = getattr(request.user, 'doctor_profile', None)
    back = request.POST.get('next_url') or ''
    destination = (back if back and url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()})
                   else 'doctors:search_patient')
    if doctor is None or not request.user.in_good_standing:
        raise PermissionDenied

    form = RequestAccessForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Enter a valid Medical ID.')
        return redirect(destination)
    if throttle.is_limited('accessreq', request.user.pk, REQUEST_LIMIT, REQUEST_WINDOW):
        messages.error(request, 'Too many requests. Please try again later.')
        return redirect(destination)
    throttle.record('accessreq', request.user.pk)

    try:
        patient = PatientProfile.objects.select_related('user').get(medical_id=form.cleaned_data['medical_id'])
    except PatientProfile.DoesNotExist:
        messages.error(request, 'No patient found with that Medical ID.')
        return redirect(destination)

    grant, created = AccessGrant.objects.get_or_create(
        patient=patient, doctor=doctor,
        defaults={'initiated_by_doctor': True, 'request_note': form.cleaned_data['note']})
    if not created:
        if grant.is_effective:
            messages.info(request, 'You already have access to this patient.')
            return redirect(destination)
        if grant.status == AccessGrant.Status.PENDING:
            messages.info(request, 'A request is already waiting for the patient to respond.')
            return redirect(destination)
        if (grant.status == AccessGrant.Status.DENIED and grant.decided_at
                and timezone.now() - grant.decided_at < DENIED_COOLDOWN):
            messages.error(request, 'The patient declined a recent request. You can ask again after 7 days.')
            return redirect(destination)
        grant.status = AccessGrant.Status.PENDING
        grant.initiated_by_doctor = True
        grant.request_note = form.cleaned_data['note']
        grant.decided_at = None
        grant.save()

    log_access(request, patient, RecordAccessLog.Action.REQUEST_ACCESS, Access(NONE), detail='consent requested')
    messages.success(request, 'Request sent. You will see the patient under "My patients" once they approve.')
    return redirect(destination)


@doctor_required
def my_patients(request):
    doctor = getattr(request.user, 'doctor_profile', None)
    grants = list(doctor.access_grants.select_related('patient__user')) if doctor else []
    return render(request, 'doctors/my_patients.html', {
        'active': [g for g in grants if g.is_effective],
        'pending': [g for g in grants if g.status == AccessGrant.Status.PENDING],
        'ended': [g for g in grants if g.status in (AccessGrant.Status.DENIED, AccessGrant.Status.REVOKED)
                  or (g.status == AccessGrant.Status.ACTIVE and g.is_expired)],
    })
