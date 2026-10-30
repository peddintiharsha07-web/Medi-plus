from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_POST

from .models import Hospital, Department, HospitalStaff, RecordShareRequest
from .forms import HospitalProfileForm, DepartmentForm
from doctors.models import DoctorProfile
from core import throttle
from users.models import AuditLog


def _require_hospital_admin(request):
    if request.user.role != 'HOSPITAL_ADMIN':
        raise PermissionDenied("Only hospital administrators can access this page.")


@login_required
def complete_profile(request):
    _require_hospital_admin(request)
    if hasattr(request.user, 'hospital'):
        return redirect('dashboard:home')
    if request.method == 'POST':
        form = HospitalProfileForm(request.POST, request.FILES)
        if form.is_valid():
            hospital = form.save(commit=False)
            hospital.admin = request.user
            hospital.save()
            messages.success(request, 'Hospital profile submitted for system administrator approval.')
            return redirect('dashboard:home')
    else:
        form = HospitalProfileForm()
    return render(request, 'hospitals/complete_profile.html', {'form': form})


@login_required
def manage_departments(request):
    _require_hospital_admin(request)
    hospital = request.user.hospital
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            dept = form.save(commit=False)
            dept.hospital = hospital
            dept.save()
            messages.success(request, 'Department added.')
            return redirect('hospitals:manage_departments')
    else:
        form = DepartmentForm()
    return render(request, 'hospitals/manage_departments.html', {
        'hospital': hospital, 'departments': hospital.departments.all(), 'form': form})


@login_required
def manage_doctors(request):
    _require_hospital_admin(request)
    hospital = request.user.hospital
    doctors = DoctorProfile.objects.filter(hospital=hospital).select_related('user', 'department')
    return render(request, 'hospitals/manage_doctors.html', {'hospital': hospital, 'doctors': doctors})


@login_required
def manage_staff(request):
    _require_hospital_admin(request)
    hospital = request.user.hospital
    if request.method == 'POST':
        HospitalStaff.objects.create(
            hospital=hospital,
            full_name=request.POST.get('full_name'),
            role_title=request.POST.get('role_title'),
            phone=request.POST.get('phone', ''),
            email=request.POST.get('email', ''),
        )
        messages.success(request, 'Staff member added.')
        return redirect('hospitals:manage_staff')
    return render(request, 'hospitals/manage_staff.html', {
        'hospital': hospital, 'staff': hospital.staff.all()})


@login_required
def manage_appointments(request):
    _require_hospital_admin(request)
    hospital = request.user.hospital
    appointments = hospital.appointments.select_related('patient__user', 'doctor__user').all()
    return render(request, 'hospitals/manage_appointments.html', {'appointments': appointments})


@login_required
def share_requests(request):
    _require_hospital_admin(request)
    hospital = request.user.hospital
    requests_qs = hospital.share_requests.select_related('patient__user').all()
    return render(request, 'hospitals/share_requests.html', {'requests': requests_qs})


@login_required
@require_POST
def request_record_access(request):
    """
    Hospital admin RECORDS a request for a patient by Medical ID. It grants NO access to any
    record: doctors are only ever authorized by an individual patient consent (consents.AccessGrant),
    because doctor-to-hospital affiliation is not verified anywhere in the system.
    """
    _require_hospital_admin(request)
    hospital = getattr(request.user, 'hospital', None)
    if hospital is None or hospital.status != 'APPROVED':
        messages.error(request, 'Your hospital must be approved before you can send requests.')
        return redirect('dashboard:home')
    if throttle.is_limited('sharereq', request.user.pk, 20, 3600):
        messages.error(request, 'Too many requests. Please try again later.')
        return redirect('hospitals:share_requests')
    throttle.record('sharereq', request.user.pk)

    from patients.models import PatientProfile
    medical_id = request.POST.get('medical_id', '').strip().upper()
    try:
        patient = PatientProfile.objects.get(medical_id=medical_id)
    except PatientProfile.DoesNotExist:
        messages.error(request, 'No patient found with that Medical ID.')
        return redirect('hospitals:share_requests')

    reason = request.POST.get('reason', '')[:255]
    share, created = RecordShareRequest.objects.get_or_create(hospital=hospital, patient=patient,
                                                              defaults={'reason': reason})
    if not created and share.status in (RecordShareRequest.Status.DENIED, RecordShareRequest.Status.REVOKED):
        share.status, share.reason, share.decided_at = RecordShareRequest.Status.PENDING, reason, None
        share.save()
    messages.success(request, f'Access request recorded for patient {medical_id}.')
    return redirect('hospitals:share_requests')
