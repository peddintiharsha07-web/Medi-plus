from django.db.models.signals import post_delete

from .models import LabReport, MedicalAttachment, PatientDocument, Prescription


def _delete_file(sender, instance, **kwargs):
    """Remove the stored file when its row is deleted so no orphaned medical files linger."""
    if instance.file:
        try:
            instance.file.delete(save=False)
        except Exception:  # noqa: BLE001
            pass


for _model in (PatientDocument, Prescription, LabReport, MedicalAttachment):
    post_delete.connect(_delete_file, sender=_model, dispatch_uid=f'delete_file_{_model.__name__}')
