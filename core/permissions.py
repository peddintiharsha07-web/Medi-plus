from rest_framework.permissions import BasePermission


class IsApprovedAccount(BasePermission):
    """Default API permission: authenticated AND an account in good standing."""
    message = 'Your account is not active.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.in_good_standing)


class _RolePermission(BasePermission):
    role = None

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.in_good_standing and user.role == self.role)


class IsPatient(_RolePermission):
    role = 'PATIENT'


class IsDoctor(_RolePermission):
    role = 'DOCTOR'


class IsHospitalAdmin(_RolePermission):
    role = 'HOSPITAL_ADMIN'


class IsSystemAdmin(_RolePermission):
    role = 'SYSTEM_ADMIN'


class HasPatientAccess(BasePermission):
    """Object-level: must be a patient the user may see per the central consent policy."""
    def has_object_permission(self, request, view, obj):
        from consents.policy import resolve_access
        return resolve_access(request.user, getattr(obj, 'patient', obj)).can_view_full
