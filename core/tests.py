from django.urls import reverse

from core.testing import BaseTestCase, pdf_file
from medical_records.models import LabReport, MedicalRecord, Prescription, PatientDocument


class SmokeTests(BaseTestCase):
    """Every page renders (no template/URL errors) for the roles that may open it."""

    def test_healthz_is_public_and_leaks_nothing(self):
        r = self.client.get(reverse('core:healthz')); self.assertEqual((r.status_code, r.content), (200, b'ok'))

    def test_public_pages(self):
        for name in ('core:home', 'core:about', 'core:services', 'core:contact', 'core:faq', 'users:login', 'users:register_patient'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_patient_pages(self):
        pu, p = self.make_patient(); du, d = self.make_doctor()
        rec = MedicalRecord.objects.create(patient=p, doctor=d, consultation_date='2025-01-01T10:00Z', diagnosis='x')
        Prescription.objects.create(record=rec, medication_name='m', file=pdf_file())
        LabReport.objects.create(record=rec, title='l', report_date='2025-01-01', file=pdf_file())
        doc = PatientDocument.objects.create(patient=p, title='d', file=pdf_file())
        self.login(pu)
        for name, args in [('dashboard:home', []), ('patients:my_records', []), ('patients:my_qr_card', []), ('patients:edit_profile', []),
                           ('patients:book_appointment', []), ('patients:my_appointments', []), ('emergency:my_logs', []),
                           ('medical_records:document_list', []), ('medical_records:document_upload', []),
                           ('medical_records:document_edit', [doc.pk]), ('consents:privacy_center', []), ('users:profile', []),
                           ('users:password_change', []), ('patients:record_detail', [rec.pk])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)
        r = self.client.get(reverse('patients:record_detail', args=[rec.pk]))
        self.assertIn(b'/medical-records/files/prescription/', r.content); self.assertNotIn(b'/media/', r.content)

    def test_doctor_pages(self):
        pu, p = self.make_patient(); du, d = self.make_doctor(emergency=True); self.consent(p, d, 'VIEW_ADD')
        self.login(du)
        for name, args in [('dashboard:home', []), ('doctors:search_patient', []), ('doctors:scan_qr', []), ('doctors:my_patients', []),
                           ('doctors:my_appointments', []), ('emergency:access', []), ('users:profile', []),
                           ('doctors:patient_detail', [p.medical_id]), ('doctors:create_record', [p.medical_id])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)

    def test_hospital_admin_and_sysadmin_dashboards(self):
        for user in (self.make_hospital_admin(), self.make_sysadmin()):
            self.login(user); self.assertEqual(self.client.get(reverse('dashboard:home')).status_code, 200)

    def test_hospital_share_request_is_recorded_but_grants_nothing(self):
        from hospitals.models import RecordShareRequest
        ha = self.make_hospital_admin(); pu, p = self.make_patient(); self.login(ha)
        self.client.post(reverse('hospitals:request_record_access'), {'medical_id': p.medical_id, 'reason': 'transfer'})
        self.assertTrue(RecordShareRequest.objects.filter(patient=p).exists())
        self.assertEqual(self.client.get(reverse('hospitals:share_requests')).status_code, 200)
        self.assertNotContains(self.client.get(reverse('hospitals:share_requests')), p.user.get_full_name())

    def test_error_pages_render(self):
        pu, _ = self.make_patient(); self.login(pu)
        self.assertContains(self.client.get('/nope/'), 'Page not found', status_code=404)
        du, _ = self.make_doctor(); self.login(du)
        self.assertContains(self.client.get(reverse('patients:my_records')), 'access', status_code=403)

    def test_throttle_events_store_hashes_not_usernames(self):
        from core import throttle
        from core.models import ThrottleEvent
        throttle.record('login_user', 'SomeUser')
        self.assertNotIn('someuser', ThrottleEvent.objects.get().key.lower())
        self.assertTrue(throttle.is_limited('login_user', 'someuser', 1, 60))  # case-insensitive
        throttle.reset('login_user', 'SOMEUSER'); self.assertEqual(ThrottleEvent.objects.count(), 0)
