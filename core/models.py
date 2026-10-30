from django.db import models
from django.utils import timezone


class ThrottleEvent(models.Model):
    """One row per *failed* attempt (bad login, bad QR token ...). Stored in the DB so the
    limit is shared by every worker and needs nothing beyond ``migrate``. ``key`` is a hash."""
    scope = models.CharField(max_length=32)
    key = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=['scope', 'key', 'created_at'])]
