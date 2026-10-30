from consents.audit import log_access
from consents.models import RecordAccessLog
from consents.policy import Access, EMERGENCY
from core.security import client_ip

from .models import EmergencyAccessLog

MIN_REASON_LENGTH = 5


def perform_emergency_access(request, doctor_profile, patient, reason):
    """Break-glass: returns ONLY patient.critical_info; logs to the emergency log AND the audit trail.
    ``patient_notified`` stays False: there is no push/e-mail channel, the patient sees it in their log."""
    EmergencyAccessLog.objects.create(patient=patient, accessed_by=doctor_profile, reason=reason[:255],
                                      ip_address=client_ip(request), patient_notified=False)
    log_access(request, patient, RecordAccessLog.Action.EMERGENCY_VIEW, Access(EMERGENCY),
               detail=f'reason: {reason[:150]}')
    return patient.critical_info
