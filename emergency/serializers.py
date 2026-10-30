from rest_framework import serializers
from .models import EmergencyAccessLog


class EmergencyAccessLogSerializer(serializers.ModelSerializer):
    patient_medical_id = serializers.CharField(source='patient.medical_id', read_only=True)
    accessed_by_name = serializers.CharField(source='accessed_by.user.get_full_name', read_only=True)

    class Meta:
        model = EmergencyAccessLog
        fields = ['id', 'patient', 'patient_medical_id', 'accessed_by', 'accessed_by_name',
                  'reason', 'ip_address', 'accessed_at', 'patient_notified']
        read_only_fields = ['id', 'accessed_at']
