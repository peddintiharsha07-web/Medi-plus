import os

from django.conf import settings
from django.core.checks import Warning, register


@register(deploy=True)
def media_storage_is_durable(app_configs, **kwargs):
    """Warn when production would keep medical documents on a throw-away disk."""
    if settings.DEBUG or getattr(settings, 'USING_OBJECT_STORAGE', False) or os.environ.get('MEDIA_ROOT'):
        return []
    return [Warning(
        'Uploaded medical documents are stored on the local filesystem.',
        hint='On Render the local disk is wiped on every deploy. Configure S3-compatible storage '
             '(AWS_STORAGE_BUCKET_NAME ...) or attach a persistent disk and set MEDIA_ROOT to it.',
        id='medgrid.W001')]
