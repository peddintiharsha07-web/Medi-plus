from rest_framework import serializers
from .models import User, AuditLog


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role',
                  'phone_number', 'status', 'preferred_language', 'date_of_birth', 'address']
        read_only_fields = ['id', 'username', 'role', 'status']


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.username', read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'actor', 'actor_name', 'action_type', 'description',
                  'target_object', 'ip_address', 'timestamp']
