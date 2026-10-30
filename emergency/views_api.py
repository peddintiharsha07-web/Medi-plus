from rest_framework import viewsets

from core.permissions import IsApprovedAccount

from .models import EmergencyAccessLog
from .serializers import EmergencyAccessLogSerializer


class EmergencyAccessLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Patients see accesses to their data; doctors see their own; sysadmins (audit) see all."""
    serializer_class = EmergencyAccessLogSerializer
    permission_classes = [IsApprovedAccount]

    def get_queryset(self):
        user = self.request.user
        qs = EmergencyAccessLog.objects.select_related('patient__user', 'accessed_by__user')
        if user.role == 'PATIENT':
            return qs.filter(patient__user=user)
        if user.role == 'DOCTOR':
            return qs.filter(accessed_by__user=user)
        if user.role == 'SYSTEM_ADMIN':
            return qs
        return qs.none()
