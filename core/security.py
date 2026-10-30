import ipaddress

from django.conf import settings


def client_ip(request):
    """Best-effort client IP for audit logs (X-Forwarded-For only trusted behind Render's proxy)."""
    remote = request.META.get('REMOTE_ADDR')
    if getattr(settings, 'TRUST_X_FORWARDED_FOR', False):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded:
            candidate = forwarded.split(',')[0].strip()
            try:
                ipaddress.ip_address(candidate)
                return candidate
            except ValueError:
                pass
    try:
        ipaddress.ip_address(remote or '')
        return remote
    except ValueError:
        return None
