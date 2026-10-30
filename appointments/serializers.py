from rest_framework import serializers
from .models import Appointment


class AppointmentSerializer(serializers.ModelSerializer):
    patient_medical_id = serializers.CharField(source='patient.medical_id', read_only=True)
    doctor_name = serializers.CharField(source='doctor.user.get_full_name', read_only=True)
    hospital_name = serializers.CharField(source='hospital.name', read_only=True)

    class Meta:
        model = Appointment
        fields = ['id', 'patient', 'patient_medical_id', 'doctor', 'doctor_name', 'hospital',
                  'hospital_name', 'appointment_date', 'appointment_time', 'reason', 'status',
                  'notes', 'created_at', 'updated_at']
        read_only_fields = ['id', 'patient', 'hospital', 'created_at', 'updated_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = self.context['request'].user
        if user.id not in (instance.patient.user_id, instance.doctor.user_id):  # reason/notes may be clinical
            data.pop('reason', None)
            data.pop('notes', None)
        return data
