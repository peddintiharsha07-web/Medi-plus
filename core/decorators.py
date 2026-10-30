from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """login_required + the user must hold one of ``roles`` (else 403)."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied('You do not have permission to view this page.')
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


patient_required = role_required('PATIENT')
doctor_required = role_required('DOCTOR')
