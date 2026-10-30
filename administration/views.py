from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import PermissionDenied

from users.models import User, AuditLog
from hospitals.models import Hospital, RecordShareRequest
from patients.models import PatientProfile
from doctors.models import DoctorProfile
from medical_records.models import MedicalRecord
from appointments.models import Appointment


def _require_system_admin(request):
    if request.user.role != 'SYSTEM_ADMIN':
        raise PermissionDenied("Only system administrators can access this page.")


@login_required
def pending_hospitals(request):
    _require_system_admin(request)
    hospitals = Hospital.objects.filter(status='PENDING').select_related('admin')
    return render(request, 'administration/pending_hospitals.html', {'hospitals': hospitals})


@login_required
def approve_hospital(request, hospital_id):
    _require_system_admin(request)
    hospital = get_object_or_404(Hospital, id=hospital_id)
    hospital.status = 'APPROVED'
    hospital.save(update_fields=['status'])
    hospital.admin.status = 'APPROVED'
    hospital.admin.save(update_fields=['status'])
    AuditLog.objects.create(actor=request.user, action_type=AuditLog.ActionType.HOSPITAL_APPROVED,
                             description=f'Approved hospital {hospital.name}', target_object=str(hospital.id))
    messages.success(request, f'{hospital.name} approved.')
    return redirect('administration:pending_hospitals')


@login_required
def reject_hospital(request, hospital_id):
    _require_system_admin(request)
    hospital = get_object_or_404(Hospital, id=hospital_id)
    hospital.admin.status = 'REJECTED'
    hospital.admin.save(update_fields=['status'])
    hospital.delete()
    messages.info(request, 'Hospital registration rejected.')
    return redirect('administration:pending_hospitals')


@login_required
def pending_doctors(request):
    _require_system_admin(request)
    doctors = User.objects.filter(role='DOCTOR', status='PENDING')
    return render(request, 'administration/pending_doctors.html', {'doctors': doctors})


@login_required
def approve_doctor(request, user_id):
    _require_system_admin(request)
    doctor = get_object_or_404(User, id=user_id, role='DOCTOR')
    doctor.status = 'APPROVED'
    doctor.save(update_fields=['status'])
    AuditLog.objects.create(actor=request.user, action_type=AuditLog.ActionType.DOCTOR_APPROVED,
                             description=f'Approved doctor {doctor.get_full_name()}', target_object=str(doctor.id))
    messages.success(request, f'Dr. {doctor.get_full_name()} approved.')
    return redirect('administration:pending_doctors')


@login_required
def reject_doctor(request, user_id):
    _require_system_admin(request)
    doctor = get_object_or_404(User, id=user_id, role='DOCTOR')
    doctor.status = 'REJECTED'
    doctor.save(update_fields=['status'])
    messages.info(request, 'Doctor registration rejected.')
    return redirect('administration:pending_doctors')


@login_required
def manage_patients(request):
    _require_system_admin(request)
    patients = PatientProfile.objects.select_related('user').all()
    return render(request, 'administration/manage_patients.html', {'patients': patients})


@login_required
def manage_hospitals(request):
    _require_system_admin(request)
    hospitals = Hospital.objects.select_related('admin').all()
    return render(request, 'administration/manage_hospitals.html', {'hospitals': hospitals})


@login_required
def manage_doctors(request):
    _require_system_admin(request)
    doctors = User.objects.filter(role='DOCTOR')
    return render(request, 'administration/manage_doctors.html', {'doctors': doctors})


@login_required
def toggle_suspend(request, user_id):
    _require_system_admin(request)
    user = get_object_or_404(User, id=user_id)
    user.status = 'SUSPENDED' if user.status == 'APPROVED' else 'APPROVED'
    user.save(update_fields=['status'])
    AuditLog.objects.create(actor=request.user, action_type=AuditLog.ActionType.ACCOUNT_SUSPENDED,
                             description=f'Toggled status for {user.username} to {user.status}',
                             target_object=str(user.id))
    messages.success(request, f'{user.username} status set to {user.status}.')
    return redirect(request.META.get('HTTP_REFERER', 'administration:manage_patients'))


@login_required
def audit_logs(request):
    _require_system_admin(request)
    logs = AuditLog.objects.select_related('actor').all()[:200]
    return render(request, 'administration/audit_logs.html', {'logs': logs})


@login_required
def analytics(request):
    _require_system_admin(request)
    from django.db.models import Count
    context = {
        'total_hospitals': Hospital.objects.filter(status='APPROVED').count(),
        'total_doctors': DoctorProfile.objects.count(),
        'total_patients': PatientProfile.objects.count(),
        'total_records': MedicalRecord.objects.count(),
        'total_appointments': Appointment.objects.count(),
        'appointments_by_status': Appointment.objects.values('status').annotate(count=Count('id')).order_by('status'),
    }
    return render(request, 'administration/analytics.html', context)
