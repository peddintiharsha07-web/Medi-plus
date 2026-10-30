from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsApprovedAccount, IsSystemAdmin

from .models import AuditLog, User
from .serializers import AuditLogSerializer, UserSerializer


class UserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                  viewsets.GenericViewSet):
    """Everyone sees / edits only their own account; sysadmins may list all. No create/delete via API."""
    serializer_class = UserSerializer
    permission_classes = [IsApprovedAccount]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'SYSTEM_ADMIN' and self.request.method == 'GET':
            return User.objects.order_by('pk')
        return User.objects.filter(id=user.id).order_by('pk')

    @action(detail=False, methods=['get'])
    def me(self, request):
        return Response(UserSerializer(request.user).data)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related('actor').all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsSystemAdmin]
