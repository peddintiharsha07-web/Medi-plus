import uuid

from django.db import models
from django.utils import timezone


class PatientQRCode(models.Model):
    """
    QR code tied to a patient. Encodes ONLY a URL holding this opaque random token
    (UUID4, 122 bits) -- never a Medical ID or health data. Scanning identifies which
    patient; what the scanner then sees is decided by consents.policy.resolve_access.
    Can be rotated (old token dies at once), revoked, and expires.
    """
    patient = models.OneToOneField('patients.PatientProfile', on_delete=models.CASCADE, related_name='qr_code')
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    # Deprecated: images are rendered on demand and never stored. Column kept to avoid a destructive migration.
    image = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rotated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"QR for {self.patient.medical_id}"

    @property
    def is_expired(self):
        return self.expires_at is not None and self.expires_at <= timezone.now()

    @property
    def is_usable(self):
        return self.is_active and not self.is_expired

    @property
    def state_label(self):
        if not self.is_active:
            return 'Revoked'
        return 'Expired' if self.is_expired else 'Active'
