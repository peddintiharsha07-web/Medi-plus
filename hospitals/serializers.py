from rest_framework import serializers
from .models import Hospital, Department, HospitalStaff, RecordShareRequest


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'hospital', 'name', 'description']


class HospitalSerializer(serializers.ModelSerializer):
    departments = DepartmentSerializer(many=True, read_only=True)

    class Meta:
        model = Hospital
        fields = ['id', 'admin', 'name', 'registration_number', 'address', 'city', 'state',
                  'phone', 'email', 'logo', 'status', 'departments', 'created_at']
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = self.context['request'].user
        if not (user.role == 'SYSTEM_ADMIN' or instance.admin_id == user.id):
            data.pop('admin', None)
            data.pop('registration_number', None)
        return data


class HospitalStaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = HospitalStaff
        fields = ['id', 'hospital', 'full_name', 'role_title', 'phone', 'email', 'is_active']
        read_only_fields = ['id', 'hospital']


class RecordShareRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecordShareRequest
        fields = ['id', 'hospital', 'patient', 'status', 'requested_at', 'decided_at', 'reason']
        read_only_fields = fields
