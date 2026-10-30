from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS

from core.permissions import IsApprovedAccount, IsHospitalAdmin

from .models import Department, Hospital, HospitalStaff, RecordShareRequest
from .serializers import (DepartmentSerializer, HospitalSerializer,
                          HospitalStaffSerializer, RecordShareRequestSerializer)


class HospitalViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Read-only directory of approved hospitals (sysadmin sees all; admins also see their own)."""
    serializer_class = HospitalSerializer
    permission_classes = [IsApprovedAccount]

    def get_queryset(self):
        qs = Hospital.objects.prefetch_related('departments')
        if self.request.user.role == 'SYSTEM_ADMIN':
            return qs
        return qs.filter(Q(status='APPROVED') | Q(admin=self.request.user))


class DepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer

    def get_permissions(self):
        return [IsApprovedAccount()] if self.request.method in SAFE_METHODS else [IsHospitalAdmin()]

    def get_queryset(self):
        qs = Department.objects.select_related('hospital')
        if self.request.method in SAFE_METHODS:
            return qs.filter(Q(hospital__status='APPROVED') | Q(hospital__admin=self.request.user))
        return qs.filter(hospital__admin=self.request.user)

    def perform_create(self, serializer):
        if serializer.validated_data['hospital'].admin_id != self.request.user.id:
            raise PermissionDenied('You can only add departments to your own hospital.')
        serializer.save()

    def perform_update(self, serializer):
        serializer.save(hospital=serializer.instance.hospital)


class HospitalStaffViewSet(viewsets.ModelViewSet):
    serializer_class = HospitalStaffSerializer
    permission_classes = [IsHospitalAdmin]

    def get_queryset(self):
        return HospitalStaff.objects.filter(hospital__admin=self.request.user)

    def perform_create(self, serializer):
        hospital = getattr(self.request.user, 'hospital', None)
        if hospital is None:
            raise PermissionDenied('Create your hospital profile first.')
        serializer.save(hospital=hospital)


class RecordShareRequestViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Read-only. A share request grants no access to any record (see hospitals.views)."""
    serializer_class = RecordShareRequestSerializer
    permission_classes = [IsApprovedAccount]

    def get_queryset(self):
        user, qs = self.request.user, RecordShareRequest.objects.order_by('pk')
        if user.role == 'PATIENT':
            return qs.filter(patient__user=user)
        if user.role == 'HOSPITAL_ADMIN':
            return qs.filter(hospital__admin=user)
        if user.role == 'SYSTEM_ADMIN':
            return qs
        return qs.none()
