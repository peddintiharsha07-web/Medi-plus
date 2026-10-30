"""Failure-based throttle backed by the database (see ThrottleEvent)."""
import hashlib
import random
from datetime import timedelta

from django.utils import timezone

from .models import ThrottleEvent


def _key(ident):
    return hashlib.sha256(str(ident).strip().lower().encode('utf-8')).hexdigest()[:40]


def count(scope, ident, window):
    since = timezone.now() - timedelta(seconds=window)
    return ThrottleEvent.objects.filter(scope=scope, key=_key(ident), created_at__gte=since).count()


def is_limited(scope, ident, limit, window):
    return count(scope, ident, window) >= limit


def record(scope, ident):
    ThrottleEvent.objects.create(scope=scope, key=_key(ident))
    if random.random() < 0.02:  # opportunistic clean-up
        ThrottleEvent.objects.filter(created_at__lt=timezone.now() - timedelta(days=1)).delete()


def reset(scope, ident):
    ThrottleEvent.objects.filter(scope=scope, key=_key(ident)).delete()
