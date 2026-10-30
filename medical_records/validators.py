"""
Upload validation. Never trust the file name or browser Content-Type. A file is accepted only if:
extension is allow-listed, size <= MAX_UPLOAD_BYTES, leading bytes (magic number) match the
claimed type, and images decode cleanly with Pillow and are not absurdly large.
"""
import os

from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED_TYPES = {
    '.pdf': 'application/pdf', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.png': 'image/png', '.webp': 'image/webp',
}
ALLOWED_EXTENSIONS_TEXT = 'PDF, JPG, PNG or WEBP'
MAX_IMAGE_PIXELS = 50_000_000


def sniff_content_type(fileobj):
    """Identify the real type from the first bytes. Returns a MIME type or None."""
    try:
        fileobj.seek(0)
        head = fileobj.read(16)
        fileobj.seek(0)
    except Exception:  # noqa: BLE001
        return None
    if head.startswith(b'%PDF-'):
        return 'application/pdf'
    if head.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'image/webp'
    return None


def validate_medical_file(value):
    name = getattr(value, 'name', '') or ''
    expected = ALLOWED_TYPES.get(os.path.splitext(name)[1].lower())
    if expected is None:
        raise ValidationError(f'Unsupported file type. Allowed: {ALLOWED_EXTENSIONS_TEXT}.', code='bad_extension')
    max_bytes = getattr(settings, 'MAX_UPLOAD_BYTES', 10 * 1024 * 1024)
    size = getattr(value, 'size', 0) or 0
    if size > max_bytes:
        raise ValidationError(f'File too large (maximum {max_bytes // (1024 * 1024)} MB).', code='too_large')
    if size == 0:
        raise ValidationError('The file is empty.', code='empty')
    detected = sniff_content_type(value)
    if detected != expected:
        raise ValidationError('The file content does not match its extension, or the file is corrupt.',
                              code='content_mismatch')
    if detected.startswith('image/'):
        try:
            from PIL import Image
            value.seek(0)
            with Image.open(value) as img:
                if img.width * img.height > MAX_IMAGE_PIXELS:
                    raise ValidationError('Image dimensions are too large.', code='image_too_large')
                img.verify()
        except ValidationError:
            raise
        except Exception:  # noqa: BLE001
            raise ValidationError('The image file is invalid or corrupt.', code='bad_image')
        finally:
            try:
                value.seek(0)
            except Exception:  # noqa: BLE001
                pass
