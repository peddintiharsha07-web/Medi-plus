import io
import re
import uuid
from datetime import timedelta

import qrcode
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .models import PatientQRCode

_UUID_RE = re.compile(r'[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}')


def _default_expiry():
    days = getattr(settings, 'QR_TOKEN_LIFETIME_DAYS', 0)
    return timezone.now() + timedelta(days=days) if days else None


def generate_qr_for_patient(patient_profile):
    """Ensure the patient has a QR record (called at registration). Idempotent."""
    qr_obj, _ = PatientQRCode.objects.get_or_create(patient=patient_profile, defaults={'expires_at': _default_expiry()})
    return qr_obj


def rotate_qr(qr_obj):
    """Issue a brand-new token; the previous one stops working immediately."""
    qr_obj.token = uuid.uuid4()
    qr_obj.is_active = True
    qr_obj.rotated_at = timezone.now()
    qr_obj.expires_at = _default_expiry()
    if qr_obj.image:
        try:
            qr_obj.image.delete(save=False)  # legacy stored image would hold the old token
        except Exception:  # noqa: BLE001
            qr_obj.image = None
    qr_obj.save()
    return qr_obj


def revoke_qr(qr_obj):
    qr_obj.is_active = False
    qr_obj.save(update_fields=['is_active'])
    return qr_obj


def resolve_token(token):
    """PatientQRCode for a *usable* token, else None (unknown, revoked or expired)."""
    try:
        qr = PatientQRCode.objects.select_related('patient__user').get(token=token)
    except (PatientQRCode.DoesNotExist, ValueError, TypeError):
        return None
    return qr if qr.is_usable else None


def extract_token(text):
    """Pull a token out of a pasted scan URL, legacy 'MEDRECORD:<uuid>' or a bare uuid."""
    match = _UUID_RE.search(text or '')
    if not match:
        return None
    try:
        return uuid.UUID(match.group(0))
    except ValueError:
        return None


def scan_url(token, request=None):
    path = reverse('qr:scan', args=[token])
    base = getattr(settings, 'SITE_BASE_URL', '')
    if base:
        return f'{base}{path}'
    if request is not None:
        return request.build_absolute_uri(path)
    return path


def render_qr_png(payload):
    img = qrcode.make(payload, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()
