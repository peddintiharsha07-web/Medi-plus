from django.utils import timezone
from rest_framework import mixins, serializers, viewsets
from rest_framework.exceptions import PermissionDenied

from core.permissions import IsApprovedAccount
from .models import Appointment
from .serializers import AppointmentSerializer


class AppointmentViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                         mixins.ListModelMixin, viewsets.GenericViewSet):
    """Patients create PENDING requests for themselves and may only cancel. Doctors update status/notes
    of their own appointments. Admins read only. No DELETE."""
    serializer_class = AppointmentSerializer
    permission_classes = [IsApprovedAccount]

    def get_queryset(self):
        user = self.request.user
        qs = Appointment.objects.select_related('patient__user', 'doctor__user', 'hospital')
        if user.role == 'PATIENT':
            return qs.filter(patient__user=user)
        if user.role == 'DOCTOR':
            return qs.filter(doctor__user=user)
        if user.role == 'HOSPITAL_ADMIN':
            return qs.filter(hospital__admin=user)
        if user.role == 'SYSTEM_ADMIN':
            return qs
        return qs.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.role != 'PATIENT':
            raise PermissionDenied('Only patients can request appointments.')
        doctor = serializer.validated_data['doctor']
        if doctor.user.status != 'APPROVED':
            raise serializers.ValidationError({'doctor': 'This doctor is not available.'})
        if serializer.validated_data['appointment_date'] < timezone.localdate():
            raise serializers.ValidationError({'appointment_date': 'Choose today or a future date.'})
        serializer.save(patient=user.patient_profile, hospital=doctor.hospital, status=Appointment.Status.PENDING)

    def perform_update(self, serializer):
        user, data = self.request.user, serializer.validated_data
        if user.role == 'PATIENT':
            if set(data) - {'status'} or data.get('status') != Appointment.Status.CANCELLED:
                raise PermissionDenied('Patients can only cancel an appointment.')
        elif user.role == 'DOCTOR':
            if set(data) - {'status', 'notes'}:
                raise PermissionDenied('Doctors can only change the status and notes.')
        else:
            raise PermissionDenied('Read-only for your role.')
        serializer.save(doctor=serializer.instance.doctor, patient=serializer.instance.patient)
