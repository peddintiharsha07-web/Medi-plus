from core.security import client_ip
from users.models import AuditLog

from .models import RecordAccessLog
from .policy import OWNER

_AUDIT_TYPE = {
    RecordAccessLog.Action.VIEW_PROFILE: AuditLog.ActionType.RECORD_VIEW,
    RecordAccessLog.Action.DOWNLOAD_FILE: AuditLog.ActionType.RECORD_VIEW,
    RecordAccessLog.Action.ADD_RECORD: AuditLog.ActionType.RECORD_CREATE,
    RecordAccessLog.Action.EMERGENCY_VIEW: AuditLog.ActionType.EMERGENCY_ACCESS,
}


def log_access(request, patient, action, access, detail=''):
    """Record that request.user touched patient's data (owners are not logged: noise)."""
    if access.level == OWNER:
        return None
    user = request.user if request.user.is_authenticated else None
    ip = client_ip(request)
    entry = RecordAccessLog.objects.create(
        patient=patient, accessed_by=user, accessor_role=getattr(user, 'role', '') or '',
        access_level=access.level, action=action, detail=detail[:255], ip_address=ip)
    AuditLog.objects.create(
        actor=user, action_type=_AUDIT_TYPE.get(action, AuditLog.ActionType.OTHER),
        description=f'{RecordAccessLog.Action(action).label}: {patient.medical_id}' + (f' ({detail})' if detail else ''),
        target_object=patient.medical_id, ip_address=ip)
    return entry
