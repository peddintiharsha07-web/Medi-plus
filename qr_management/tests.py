import re
import uuid
from datetime import timedelta
from unittest import mock

from django.urls import reverse
from django.utils import timezone

from consents.models import RecordAccessLog
from core.testing import PASSWORD, BaseTestCase
from emergency.models import EmergencyAccessLog
from qr_management import services
from qr_management.models import PatientQRCode


class QRCodeOwnerTests(BaseTestCase):
    def setUp(self):
        self.pu, self.p = self.make_patient('qr_p', first='Asha', last='Rao')
        self.qr = PatientQRCode.objects.get(patient=self.p)
        self.login(self.pu)

    def test_every_patient_gets_a_unique_qr(self):
        _, p2 = self.make_patient()
        self.assertNotEqual(self.qr.token, PatientQRCode.objects.get(patient=p2).token)

    def test_view_card_and_png_image(self):
        self.assertContains(self.client.get(reverse('patients:my_qr_card')), self.p.medical_id)
        r = self.client.get(reverse('patients:qr_image'))
        self.assertEqual((r.status_code, r['Content-Type']), (200, 'image/png'))
        self.assertTrue(r.content.startswith(b'\x89PNG'))

    def test_download_is_an_attachment_png(self):
        r = self.client.get(reverse('patients:qr_download'))
        self.assertIn(f'medgrid-qr-{self.p.medical_id}.png', r['Content-Disposition']); self.assertIn('attachment', r['Content-Disposition'])

    def test_qr_payload_is_a_url_with_opaque_token_and_no_medical_data(self):
        with mock.patch('qr_management.services.qrcode.make', wraps=services.qrcode.make) as spy:
            self.client.get(reverse('patients:qr_image'))
        payload = spy.call_args[0][0]
        self.assertEqual(payload, f'https://medgrid.test/q/{self.qr.token}/')
        for secret in (self.p.medical_id, 'Asha', 'Rao', self.pu.email, 'O+'):
            self.assertNotIn(secret, payload)

    def test_qr_endpoints_are_patient_only_and_authenticated(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('patients:qr_image')).status_code, 302)
        du, _ = self.make_doctor(); self.login(du)
        for name in ('patients:qr_image', 'patients:qr_download', 'patients:my_qr_card'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_rotation_kills_the_old_token_and_issues_a_new_one(self):
        old = self.qr.token
        self.assertEqual(self.client.post(reverse('patients:qr_rotate')).status_code, 302)
        self.qr.refresh_from_db()
        self.assertNotEqual(self.qr.token, old); self.assertIsNotNone(self.qr.rotated_at)
        self.assertIsNone(services.resolve_token(old)); self.assertIsNotNone(services.resolve_token(self.qr.token))

    def test_revoke_disables_and_rotate_reenables(self):
        self.client.post(reverse('patients:qr_revoke')); self.qr.refresh_from_db()
        self.assertFalse(self.qr.is_usable); self.assertIsNone(services.resolve_token(self.qr.token))
        self.client.post(reverse('patients:qr_rotate')); self.qr.refresh_from_db()
        self.assertTrue(self.qr.is_usable)

    def test_rotate_and_revoke_need_post(self):
        self.assertEqual(self.client.get(reverse('patients:qr_rotate')).status_code, 405)
        self.assertEqual(self.client.get(reverse('patients:qr_revoke')).status_code, 405)

    def test_new_tokens_get_an_expiry(self):
        self.assertIsNotNone(self.qr.expires_at)
        self.assertAlmostEqual((self.qr.expires_at - timezone.now()).days, 365, delta=1)

    def test_extract_token_accepts_url_legacy_and_bare_uuid(self):
        t = uuid.uuid4()
        for text in (f'https://x.test/q/{t}/', f'MEDRECORD:{t}', str(t), f'  {str(t).upper()} '):
            self.assertEqual(services.extract_token(text), t)
        self.assertIsNone(services.extract_token('hello')); self.assertIsNone(services.extract_token(''))


class QRScanTests(BaseTestCase):
    def setUp(self):
        self.pu, self.p = self.make_patient('sc_p', first='Asha', last='Rao')
        self.qr = PatientQRCode.objects.get(patient=self.p)
        self.url = reverse('qr:scan', args=[self.qr.token])

    def test_anonymous_is_sent_to_login_and_returns_to_the_scan_after_login(self):
        du, _ = self.make_doctor('sc_doc')
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302); self.assertIn(reverse('users:login'), r['Location']); self.assertIn('next=', r['Location'])
        r = self.client.post(r['Location'], {'username': 'sc_doc', 'password': PASSWORD})
        self.assertEqual(r['Location'], self.url)

    def test_anonymous_sees_no_patient_data(self):
        r = self.client.get(self.url, follow=True)
        for secret in ('Asha', self.p.medical_id): self.assertNotContains(r, secret)

    def test_doctor_with_consent_is_taken_to_the_records(self):
        du, d = self.make_doctor(); self.consent(self.p, d); self.login(du)
        r = self.client.get(self.url)
        self.assertRedirects(r, reverse('doctors:patient_detail', args=[self.p.medical_id]), fetch_redirect_response=False)
        self.assertTrue(RecordAccessLog.objects.filter(action='QR_SCAN', accessed_by=du).exists())
        self.assertContains(self.client.get(r['Location']), 'Asha')

    def test_doctor_without_consent_cannot_see_records_and_can_request_access(self):
        du, d = self.make_doctor(); self.login(du)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 403); self.assertContains(r, 'consent required', status_code=403)
        self.assertNotContains(r, 'Asha', status_code=403)
        self.assertTrue(RecordAccessLog.objects.filter(action='ACCESS_DENIED', accessed_by=du).exists())

    def test_patient_scanning_own_qr_goes_to_their_card(self):
        self.login(self.pu); self.assertRedirects(self.client.get(self.url), reverse('patients:my_qr_card'), fetch_redirect_response=False)

    def test_other_patient_hospital_admin_and_sysadmin_are_forbidden(self):
        ou, _ = self.make_patient()
        for user in (ou, self.make_hospital_admin(), self.make_sysadmin()):
            self.login(user); r = self.client.get(self.url)
            self.assertEqual(r.status_code, 403); self.assertNotContains(r, 'Asha', status_code=403)

    def test_emergency_doctor_gets_gate_then_only_critical_info(self):
        self.p.blood_group = 'O+'; self.p.emergency_contact_name = 'Ravi'; self.p.emergency_contact_phone = '555'
        self.p.chronic_diseases = 'Asthma'; self.p.save()
        self.pu.phone_number = '9876500000'; self.pu.address = '12 Secret Street'; self.pu.save()
        du, d = self.make_doctor(emergency=True); self.login(du)
        r = self.client.get(self.url)
        self.assertContains(r, 'Limited access'); self.assertNotContains(r, 'Asthma')
        self.assertFalse(EmergencyAccessLog.objects.exists())
        r = self.client.post(self.url, {'reason': ''}); self.assertContains(r, 'state the reason'); self.assertFalse(EmergencyAccessLog.objects.exists())
        r = self.client.post(self.url, {'reason': 'Unconscious in ER'})
        self.assertContains(r, 'Asthma'); self.assertContains(r, 'Ravi')
        for hidden in ('9876500000', '12 Secret Street', self.pu.email): self.assertNotContains(r, hidden)
        log = EmergencyAccessLog.objects.get(); self.assertEqual((log.patient, log.accessed_by, log.reason), (self.p, d, 'Unconscious in ER'))
        self.assertTrue(RecordAccessLog.objects.filter(action='EMERGENCY_VIEW', access_level='EMERGENCY').exists())
        self.login(self.pu); self.assertContains(self.client.get(reverse('emergency:my_logs')), 'Unconscious in ER')

    def test_emergency_doctor_cannot_open_full_records_page(self):
        du, _ = self.make_doctor(emergency=True); self.login(du)
        r = self.client.get(reverse('doctors:patient_detail', args=[self.p.medical_id]))
        self.assertEqual(r.status_code, 403)

    def test_non_emergency_doctor_cannot_use_emergency_page(self):
        du, _ = self.make_doctor(); self.login(du)
        self.assertEqual(self.client.get(reverse('emergency:access')).status_code, 403)

    def test_emergency_page_by_pasted_link_and_by_revoked_link(self):
        du, _ = self.make_doctor(emergency=True); self.login(du)
        r = self.client.post(reverse('emergency:access'), {'token': f'https://x/q/{self.qr.token}/', 'reason': 'ER intake'})
        self.assertContains(r, self.p.medical_id)
        services.revoke_qr(self.qr)
        r = self.client.post(reverse('emergency:access'), {'token': str(self.qr.token), 'reason': 'ER intake'})
        self.assertContains(r, 'Invalid, revoked or expired')

    def test_revoked_rotated_and_expired_tokens_are_all_rejected_identically(self):
        du, d = self.make_doctor(); self.consent(self.p, d); self.login(du)
        old = self.qr.token
        unknown = self.client.get(reverse('qr:scan', args=[uuid.uuid4()]))
        self.assertEqual(unknown.status_code, 404)
        services.rotate_qr(self.qr)
        self.assertEqual(self.client.get(reverse('qr:scan', args=[old])).status_code, 404)
        self.qr.refresh_from_db(); services.revoke_qr(self.qr)
        revoked = self.client.get(reverse('qr:scan', args=[self.qr.token]))
        self.qr.is_active = True; self.qr.expires_at = timezone.now() - timedelta(seconds=1); self.qr.save()
        expired = self.client.get(reverse('qr:scan', args=[self.qr.token]))
        self.assertEqual((revoked.status_code, expired.status_code), (404, 404))
        norm = lambda r: re.sub(rb'csrfmiddlewaretoken" value="[^"]+"', b'', r.content)  # CSRF token differs per render
        self.assertEqual(norm(revoked), norm(unknown)); self.assertEqual(norm(expired), norm(unknown))

    def test_token_guessing_is_throttled(self):
        du, d = self.make_doctor(); self.consent(self.p, d); self.login(du)
        for _ in range(10): self.client.get(reverse('qr:scan', args=[uuid.uuid4()]))
        r = self.client.get(self.url)  # even the VALID token is refused while throttled
        self.assertEqual(r.status_code, 429)

    def test_malformed_token_is_404(self):
        du, _ = self.make_doctor(); self.login(du)
        self.assertEqual(self.client.get('/q/not-a-uuid/').status_code, 404)

    def test_scan_page_cannot_be_reached_via_patient_id_manipulation(self):
        du, _ = self.make_doctor(); self.login(du)
        self.assertEqual(self.client.get(f'/q/{self.p.pk}/').status_code, 404)
        self.assertEqual(self.client.get(f'/q/{self.p.medical_id}/').status_code, 404)

    def test_doctor_scan_page_manual_entry(self):
        du, _ = self.make_doctor(); self.login(du)
        r = self.client.post(reverse('doctors:scan_qr'), {'token': f'https://x/q/{self.qr.token}/'})
        self.assertRedirects(r, self.url, fetch_redirect_response=False)
        self.assertContains(self.client.post(reverse('doctors:scan_qr'), {'token': 'garbage'}), 'does not look like')
