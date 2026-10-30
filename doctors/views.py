from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from appointments.models import Appointment
from consents.audit import log_access
from consents.models import RecordAccessLog
from consents.policy import EMERGENCY, resolve_access, visible_documents
from core import throttle
from core.decorators import doctor_required
from medical_records.models import Prescription
from patients.models import PatientProfile
from qr_management.services import extract_token

from .forms import ConsultationForm, DoctorProfileCompletionForm, parse_prescriptions

SEARCH_LIMIT, SEARCH_WINDOW = 30, 3600  # patient look-ups per doctor per hour


def mask_name(user):
    """'Asha Rao' -> 'Asha R.' (enough to confirm identity, not enough to expose it)."""
    last = (user.last_name or '').strip()
    return f'{user.first_name} {last[:1]}.'.strip() if last else user.first_name


@doctor_required
def complete_profile(request):
    if hasattr(request.user, 'doctor_profile'):
        return redirect('dashboard:home')
    if request.method == 'POST':
        form = DoctorProfileCompletionForm(request.POST)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            messages.success(request, 'Profile completed.')
            return redirect('dashboard:home')
    else:
        form = DoctorProfileCompletionForm()
    return render(request, 'doctors/complete_profile.html', {'form': form})


@doctor_required
def search_patient(request):
    """Find a patient by Medical ID: masked identity + what the doctor may do next."""
    query = request.GET.get('q', '').strip()
    patient = access = error = None
    if query:
        if throttle.is_limited('patientsearch', request.user.pk, SEARCH_LIMIT, SEARCH_WINDOW):
            error = 'Too many searches. Please try again later.'
        else:
            throttle.record('patientsearch', request.user.pk)
            try:
                patient = PatientProfile.objects.select_related('user').get(medical_id=query.upper())
                access = resolve_access(request.user, patient)
            except PatientProfile.DoesNotExist:
                error = 'No patient found with that Medical ID.'
    return render(request, 'doctors/search_patient.html', {
        'query': query, 'patient': patient, 'access': access, 'error': error,
        'masked_name': mask_name(patient.user) if patient else '', 'EMERGENCY': EMERGENCY})


@doctor_required
def scan_qr(request):
    """Manual fallback: paste the scanned link (phones can simply scan the QR with their camera)."""
    error = None
    if request.method == 'POST':
        token = extract_token(request.POST.get('token', ''))
        if token:
            return redirect('qr:scan', token=token)
        error = 'That does not look like a MedGrid QR link.'
    return render(request, 'doctors/scan_qr.html', {'error': error})


def _denied_response(request, patient, access):
    log_access(request, patient, RecordAccessLog.Action.ACCESS_DENIED, access, detail='records page')
    if access.level == EMERGENCY:
        messages.warning(request, "You do not have the patient's consent. Emergency access shows "
                                  "critical information only - scan the patient's QR code to use it.")
    return render(request, 'doctors/access_required.html', {'patient': patient}, status=403)


@doctor_required
def patient_detail(request, medical_id):
    patient = get_object_or_404(PatientProfile.objects.select_related('user'), medical_id=medical_id)
    access = resolve_access(request.user, patient)
    if not access.can_view_full:
        return _denied_response(request, patient, access)

    log_access(request, patient, RecordAccessLog.Action.VIEW_PROFILE, access, detail='records page')
    records = patient.medical_records.select_related('doctor__user', 'hospital').prefetch_related(
        'prescriptions', 'lab_reports', 'attachments')
    dob, today = patient.user.date_of_birth, timezone.localdate()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day)) if dob else None
    return render(request, 'doctors/patient_detail.html', {
        'patient': patient, 'access': access, 'records': records, 'age': age,
        'documents': visible_documents(patient, access),
        'allergies': patient.allergies.all(), 'vaccinations': patient.vaccinations.all()})


@doctor_required
def create_record(request, medical_id):
    patient = get_object_or_404(PatientProfile.objects.select_related('user'), medical_id=medical_id)
    doctor_profile = getattr(request.user, 'doctor_profile', None)
    if doctor_profile is None:
        messages.error(request, 'Complete your doctor profile first.')
        return redirect('doctors:complete_profile')

    access = resolve_access(request.user, patient)
    if not access.can_add_consultation:
        if access.can_view_full:
            messages.error(request, 'The patient allowed you to view their records only, '
                                    'not to add consultation notes.')
            return redirect('doctors:patient_detail', medical_id=medical_id)
        return _denied_response(request, patient, access)

    rows = [{}]
    if request.method == 'POST':
        form = ConsultationForm(request.POST)
        rows, row_errors = parse_prescriptions(request.POST)
        if form.is_valid() and not row_errors:
            with transaction.atomic():
                record = form.save(commit=False)
                record.patient, record.doctor, record.hospital = patient, doctor_profile, doctor_profile.hospital
                record.save()
                for row in rows:
                    Prescription.objects.create(record=record, **row)
            log_access(request, patient, RecordAccessLog.Action.ADD_RECORD, access, detail=f'consultation {record.pk}')
            messages.success(request, 'Medical record created successfully.')
            return redirect('doctors:patient_detail', medical_id=medical_id)
        for message in row_errors:
            messages.error(request, message)
        rows = rows or [{}]
    else:
        form = ConsultationForm(initial={'consultation_date': timezone.now().strftime('%Y-%m-%dT%H:%M')})
    return render(request, 'doctors/create_record.html', {'patient': patient, 'form': form, 'rows': rows})


@doctor_required
def my_appointments(request):
    doctor_profile = getattr(request.user, 'doctor_profile', None)
    appts = doctor_profile.appointments.select_related('patient__user').all() if doctor_profile else []
    return render(request, 'doctors/my_appointments.html', {'appointments': appts})


@doctor_required
@require_POST
def update_appointment_status(request, appointment_id):
    appt = get_object_or_404(Appointment, id=appointment_id, doctor__user=request.user)
    new_status = request.POST.get('status')
    if new_status in dict(Appointment.Status.choices):
        appt.status = new_status
        appt.save(update_fields=['status'])
        messages.success(request, f'Appointment marked as {appt.get_status_display()}.')
    return redirect('doctors:my_appointments')
