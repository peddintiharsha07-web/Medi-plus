from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsApprovedAccount, IsDoctor

from .models import DoctorProfile
from .serializers import DoctorProfileSerializer, DoctorSelfUpdateSerializer


class DoctorProfileViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Read-only doctor directory. Licence number / emergency flag only for the owner and sysadmins."""
    serializer_class = DoctorProfileSerializer
    permission_classes = [IsApprovedAccount]

    def get_queryset(self):
        qs = DoctorProfile.objects.select_related('user', 'hospital', 'department').order_by('pk')
        if self.request.user.role == 'SYSTEM_ADMIN':
            return qs
        return qs.filter(user__status='APPROVED', user__is_active=True)

    @action(detail=False, methods=['get', 'patch'], permission_classes=[IsDoctor])
    def me(self, request):
        profile = getattr(request.user, 'doctor_profile', None)
        if profile is None:
            return Response({'detail': 'Doctor profile not found.'}, status=404)
        if request.method == 'PATCH':
            ser = DoctorSelfUpdateSerializer(profile, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
        return Response(DoctorProfileSerializer(profile, context={'request': request}).data)
