import os

from django.http import FileResponse, Http404
from django.utils.text import slugify

from .validators import ALLOWED_TYPES


def serve_file(fieldfile, display_name='', as_attachment=False):
    """Stream a stored file through Django (caller already checked permissions); never a public URL."""
    if not fieldfile:
        raise Http404('No file.')
    ext = os.path.splitext(fieldfile.name)[1].lower()
    content_type = ALLOWED_TYPES.get(ext)
    if content_type is None:  # legacy type we would not accept today: never render inline
        content_type, as_attachment = 'application/octet-stream', True
    try:
        handle = fieldfile.open('rb')
    except (FileNotFoundError, OSError):
        raise Http404('File is missing from storage.')
    base = slugify(display_name)[:60] or 'document'
    response = FileResponse(handle, content_type=content_type, as_attachment=as_attachment, filename=f'{base}{ext}')
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    if content_type != 'application/pdf':  # Chrome's PDF viewer does not work inside a CSP sandbox
        response['Content-Security-Policy'] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    return response
