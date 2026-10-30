from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from appointments.models import Appointment
from consents.policy import authorized_patients_for
from core.permissions import IsApprovedAccount
from doctors.models import DoctorProfile
from hospitals.models import Hospital
from medical_records.models import MedicalRecord
from patients.models import PatientProfile


@api_view(['GET'])
@permission_classes([IsApprovedAccount])
def dashboard_stats(request):
    user = request.user
    if user.role == 'PATIENT':
        profile = getattr(user, 'patient_profile', None)
        if not profile:
            return Response({'detail': 'Patient profile not found.'}, status=404)
        return Response({
            'medical_id': profile.medical_id,
            'total_appointments': profile.appointments.count(),
            'total_records': profile.medical_records.count(),
            'total_documents': profile.documents.count(),
            'upcoming_appointments': profile.appointments.filter(status='ACCEPTED').count(),
        })
    if user.role == 'DOCTOR':
        profile = getattr(user, 'doctor_profile', None)
        if not profile:
            return Response({'detail': 'Doctor profile not found.'}, status=404)
        return Response({
            'total_patients': authorized_patients_for(profile).count(),
            'todays_appointments': profile.appointments.filter(appointment_date=timezone.now().date()).count(),
            'pending_appointments': profile.appointments.filter(status='PENDING').count(),
        })
    if user.role == 'HOSPITAL_ADMIN':
        hospital = getattr(user, 'hospital', None)
        if not hospital:
            return Response({'detail': 'Hospital profile not found.'}, status=404)
        return Response({'total_doctors': hospital.doctors.count(),
                         'total_appointments': hospital.appointments.count()})
    if user.role == 'SYSTEM_ADMIN':
        return Response({
            'total_hospitals': Hospital.objects.count(), 'total_doctors': DoctorProfile.objects.count(),
            'total_patients': PatientProfile.objects.count(), 'total_records': MedicalRecord.objects.count(),
            'total_appointments': Appointment.objects.count()})
    return Response({})
