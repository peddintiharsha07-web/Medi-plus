from rest_framework import serializers
from .models import PatientQRCode
from .services import scan_url


class PatientQRCodeSerializer(serializers.ModelSerializer):
    """Owner-only. The raw token is never a field; the scan URL (which embeds it) is shown to the patient only."""
    medical_id = serializers.CharField(source='patient.medical_id', read_only=True)
    scan_url = serializers.SerializerMethodField()
    state = serializers.CharField(source='state_label', read_only=True)

    class Meta:
        model = PatientQRCode
        fields = ['id', 'medical_id', 'scan_url', 'state', 'is_active', 'created_at', 'rotated_at', 'expires_at']
        read_only_fields = fields

    def get_scan_url(self, obj):
        return scan_url(obj.token, self.context.get('request'))
