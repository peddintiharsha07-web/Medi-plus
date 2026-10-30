"""Shared helpers for the test-suite."""
import atexit
import io
import shutil
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from consents.models import AccessGrant
from doctors.models import DoctorProfile
from hospitals.models import Hospital
from patients.models import PatientProfile
from users.models import User

_MEDIA = tempfile.mkdtemp(prefix='medgrid-test-media-')
atexit.register(shutil.rmtree, _MEDIA, ignore_errors=True)
PASSWORD = 'Str0ng!Passw0rd#1'


@override_settings(SECURE_SSL_REDIRECT=False, MEDIA_ROOT=_MEDIA, SITE_BASE_URL='https://medgrid.test',
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
                   ALLOWED_HOSTS=['testserver', 'localhost'])
class BaseTestCase(TestCase):
    """Common fixtures: patient A/B, an approved doctor, factories."""
    _counter = 0

    @classmethod
    def _n(cls):
        BaseTestCase._counter += 1
        return BaseTestCase._counter

    def make_patient(self, username=None, first='Pat', last='Ient'):
        username = username or f'patient{self._n()}'
        user = User.objects.create_user(username=username, password=PASSWORD, email=f'{username}@x.test',
                                        first_name=first, last_name=last, role='PATIENT', status='APPROVED')
        return user, PatientProfile.objects.create(user=user)

    def make_doctor(self, username=None, emergency=False, status='APPROVED', profile=True):
        username = username or f'doctor{self._n()}'
        user = User.objects.create_user(username=username, password=PASSWORD, email=f'{username}@x.test',
                                        first_name='Doc', last_name=username.title(), role='DOCTOR', status=status)
        prof = None
        if profile:
            prof = DoctorProfile.objects.create(user=user, specialization='General', license_number=f'LIC{self._n()}',
                                                is_emergency_authorized=emergency)
        return user, prof

    def make_hospital_admin(self, username=None):
        username = username or f'hadmin{self._n()}'
        user = User.objects.create_user(username=username, password=PASSWORD, role='HOSPITAL_ADMIN', status='APPROVED')
        Hospital.objects.create(admin=user, name=f'Hosp {username}', registration_number=f'R{self._n()}',
                                address='a', city='c', state='s', phone='1', email=f'{username}@h.test', status='APPROVED')
        return user

    def make_sysadmin(self):
        return User.objects.create_user(username=f'sys{self._n()}', password=PASSWORD, role='SYSTEM_ADMIN',
                                        status='APPROVED')

    def consent(self, patient, doctor, scope=AccessGrant.Scope.VIEW, days=30):
        grant, _ = AccessGrant.objects.get_or_create(patient=patient, doctor=doctor)
        grant.activate(scope, days)
        return grant

    def login(self, user):
        self.client.logout()
        self.assertTrue(self.client.login(username=user.username, password=PASSWORD))


def pdf_file(name='report.pdf', extra=b''):
    return SimpleUploadedFile(name, b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF' + extra, content_type='application/pdf')


def png_file(name='scan.png'):
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (4, 4), 'white').save(buf, 'PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


def days_ago(n):
    return timezone.now() - timedelta(days=n)
