from rest_framework import serializers
from .models import PatientProfile, Allergy, Vaccination


class AllergySerializer(serializers.ModelSerializer):
    class Meta:
        model = Allergy
        fields = ['id', 'allergen', 'reaction', 'severity', 'recorded_at']
        read_only_fields = ['id', 'recorded_at']


class VaccinationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vaccination
        fields = ['id', 'vaccine_name', 'date_administered', 'next_due_date', 'administered_by']
        read_only_fields = ['id']


class PatientProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    allergies = AllergySerializer(many=True, read_only=True)
    vaccinations = VaccinationSerializer(many=True, read_only=True)

    class Meta:
        model = PatientProfile
        fields = ['id', 'full_name', 'medical_id', 'gender', 'blood_group',
                  'emergency_contact_name', 'emergency_contact_phone', 'chronic_diseases',
                  'current_medications', 'organ_donor', 'height_cm', 'weight_kg',
                  'allergies', 'vaccinations', 'created_at']
        read_only_fields = ['id', 'full_name', 'medical_id', 'created_at']
