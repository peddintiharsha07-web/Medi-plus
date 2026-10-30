from rest_framework import serializers
from .models import DoctorProfile

_PRIVATE = ('license_number', 'is_emergency_authorized')


class DoctorProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    hospital_name = serializers.CharField(source='hospital.name', read_only=True)

    class Meta:
        model = DoctorProfile
        fields = ['id', 'full_name', 'hospital', 'hospital_name', 'department', 'specialization',
                  'license_number', 'years_of_experience', 'consultation_fee', 'bio',
                  'is_emergency_authorized', 'created_at']
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = self.context['request'].user
        if not (user.role == 'SYSTEM_ADMIN' or instance.user_id == user.id):
            for key in _PRIVATE:
                data.pop(key, None)
        return data


class DoctorSelfUpdateSerializer(serializers.ModelSerializer):
    """The only fields a doctor may change themselves (never licence / emergency flag / hospital)."""
    class Meta:
        model = DoctorProfile
        fields = ['specialization', 'years_of_experience', 'consultation_fee', 'bio']
