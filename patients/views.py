from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from appointments.models import Appointment
from consents.models import AccessGrant
from core.decorators import patient_required
from qr_management import services as qr_services
from users.models import AuditLog

from .forms import AllergyForm, AppointmentRequestForm, PatientHealthForm, PatientUserForm
from .models import Allergy


def _qr(profile):
    return qr_services.generate_qr_for_patient(profile)  # get-or-create


@patient_required
def my_records(request):
    profile = request.user.patient_profile
    records = profile.medical_records.select_related('doctor__user', 'hospital').prefetch_related(
        'prescriptions', 'lab_reports', 'attachments')
    return render(request, 'patients/my_records.html', {
        'records': records, 'profile': profile,
        'recent_documents': profile.documents.all()[:5], 'document_count': profile.documents.count()})


@patient_required
def record_detail(request, record_id):
    profile = request.user.patient_profile
    record = get_object_or_404(profile.medical_records.select_related('doctor__user', 'hospital'), id=record_id)
    return render(request, 'patients/record_detail.html', {'record': record})


@patient_required
def my_qr_card(request):
    profile = request.user.patient_profile
    qr = _qr(profile)
    return render(request, 'patients/qr_card.html', {
        'profile': profile, 'qr': qr, 'scan_url': qr_services.scan_url(qr.token, request)})


def _png_response(profile, qr, request, download=False):
    response = HttpResponse(qr_services.render_qr_png(qr_services.scan_url(qr.token, request)),
                            content_type='image/png')
    response['Cache-Control'] = 'private, no-store'
    if download:
        response['Content-Disposition'] = f'attachment; filename="medgrid-qr-{profile.medical_id}.png"'
    return response


@patient_required
def qr_image(request):
    profile = request.user.patient_profile
    return _png_response(profile, _qr(profile), request)


@patient_required
def qr_download(request):
    profile = request.user.patient_profile
    return _png_response(profile, _qr(profile), request, download=True)


@patient_required
@require_POST
def qr_rotate(request):
    qr_services.rotate_qr(_qr(request.user.patient_profile))
    AuditLog.objects.create(actor=request.user, action_type=AuditLog.ActionType.OTHER,
                            description='Patient generated a new QR code (old one disabled)')
    messages.success(request, 'A new QR code was generated. Your old QR code no longer works - '
                              'download and share the new one.')
    return redirect('patients:my_qr_card')


@patient_required
@require_POST
def qr_revoke(request):
    qr_services.revoke_qr(_qr(request.user.patient_profile))
    AuditLog.objects.create(actor=request.user, action_type=AuditLog.ActionType.OTHER,
                            description='Patient disabled their QR code')
    messages.success(request, 'Your QR code is disabled. Nobody can open your records with it. '
                              'Generate a new one whenever you need it.')
    return redirect('patients:my_qr_card')


@patient_required
def edit_profile(request):
    profile = request.user.patient_profile
    if request.method == 'POST':
        user_form = PatientUserForm(request.POST, instance=request.user)
        health_form = PatientHealthForm(request.POST, instance=profile)
        if user_form.is_valid() and health_form.is_valid():
            user_form.save()
            health_form.save()
            messages.success(request, 'Profile updated.')
            return redirect('patients:edit_profile')
        messages.error(request, 'Please correct the errors below.')
    else:
        user_form = PatientUserForm(instance=request.user)
        health_form = PatientHealthForm(instance=profile)
    return render(request, 'patients/edit_profile.html', {
        'profile': profile, 'user_form': user_form, 'health_form': health_form,
        'allergies': profile.allergies.all(), 'allergy_form': AllergyForm()})


@patient_required
@require_POST
def allergy_add(request):
    form = AllergyForm(request.POST)
    if form.is_valid():
        allergy = form.save(commit=False)
        allergy.patient = request.user.patient_profile
        allergy.save()
        messages.success(request, 'Allergy added.')
    else:
        messages.error(request, 'Could not add the allergy. Please check the details.')
    return redirect('patients:edit_profile')


@patient_required
@require_POST
def allergy_delete(request, allergy_id):
    get_object_or_404(Allergy, pk=allergy_id, patient=request.user.patient_profile).delete()
    messages.info(request, 'Allergy removed.')
    return redirect('patients:edit_profile')


@patient_required
def book_appointment(request):
    profile = request.user.patient_profile
    if request.method == 'POST':
        form = AppointmentRequestForm(request.POST)
        if form.is_valid():
            doctor = form.cleaned_data['doctor']
            Appointment.objects.create(
                patient=profile, doctor=doctor, hospital=doctor.hospital,
                appointment_date=form.cleaned_data['appointment_date'],
                appointment_time=form.cleaned_data['appointment_time'],
                reason=form.cleaned_data['reason'])
            if form.cleaned_data['share_records']:
                grant, _ = AccessGrant.objects.get_or_create(patient=profile, doctor=doctor)
                grant.activate(AccessGrant.Scope.VIEW_ADD, 30)
            messages.success(request, 'Appointment requested. You will be notified once the doctor responds.')
            return redirect('patients:my_appointments')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = AppointmentRequestForm()
    return render(request, 'patients/book_appointment.html', {'form': form})


@patient_required
def my_appointments(request):
    appts = request.user.patient_profile.appointments.select_related('doctor__user', 'hospital').all()
    return render(request, 'patients/my_appointments.html', {'appointments': appts})


@patient_required
@require_POST
def cancel_appointment(request, appointment_id):
    appt = get_object_or_404(Appointment, id=appointment_id, patient=request.user.patient_profile)
    appt.status = 'CANCELLED'
    appt.save(update_fields=['status'])
    messages.info(request, 'Appointment cancelled.')
    return redirect('patients:my_appointments')
