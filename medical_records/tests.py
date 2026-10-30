import os

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from consents.models import AccessGrant, RecordAccessLog
from core.testing import BaseTestCase, pdf_file, png_file
from medical_records.models import PatientDocument


class DocumentUploadTests(BaseTestCase):
    def setUp(self):
        self.pat, self.profile = self.make_patient('owner')
        self.login(self.pat)
        self.url = reverse('medical_records:document_upload')

    def upload(self, f, **extra):
        data = {'category': 'LAB_REPORT', 'title': 'Blood test', 'record_date': '2025-01-10',
                'provider_name': 'City Lab', 'description': '', 'shared_with_doctors': 'on', **extra}
        if f is not None:
            data['file'] = f
        return self.client.post(self.url, data)

    def test_pdf_and_image_uploads_are_saved_and_listed(self):
        self.assertEqual(self.upload(pdf_file()).status_code, 302)
        self.assertEqual(self.upload(png_file(), title='X-ray').status_code, 302)
        self.assertEqual(self.profile.documents.count(), 2)
        resp = self.client.get(reverse('medical_records:document_list'))
        self.assertContains(resp, 'Blood test'); self.assertContains(resp, 'X-ray')

    def test_record_fields_are_stored(self):
        self.upload(pdf_file())
        d = self.profile.documents.get()
        self.assertEqual((d.patient, d.category, d.uploaded_by), (self.profile, 'LAB_REPORT', self.pat))
        self.assertEqual((d.original_filename, d.content_type), ('report.pdf', 'application/pdf'))
        self.assertTrue(d.file_size > 0 and d.uploaded_at)

    def test_storage_name_is_random_not_the_user_supplied_name(self):
        self.upload(pdf_file('../../etc/passwd.pdf'))
        d = self.profile.documents.get()
        self.assertNotIn('passwd', d.file.name)
        self.assertTrue(d.file.name.startswith(f'patient_documents/{self.profile.pk}/'))

    def test_text_file_renamed_to_pdf_is_rejected(self):
        resp = self.upload(SimpleUploadedFile('fake.pdf', b'just some text, not a pdf'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'does not match its extension')
        self.assertEqual(PatientDocument.objects.count(), 0)

    def test_html_and_svg_and_executables_rejected(self):
        for name, body in [('x.html', b'<script>alert(1)</script>'), ('x.svg', b'<svg onload=alert(1)>'),
                           ('x.exe', b'MZ\x90\x00'), ('x.php', b'<?php ?>'), ('noext', b'%PDF-1.4')]:
            self.assertEqual(self.upload(SimpleUploadedFile(name, body)).status_code, 200, name)
        self.assertEqual(PatientDocument.objects.count(), 0)

    def test_pdf_content_with_image_extension_rejected(self):
        resp = self.upload(SimpleUploadedFile('x.png', b'%PDF-1.4 hello'))
        self.assertContains(resp, 'does not match')

    def test_corrupt_image_rejected(self):
        resp = self.upload(SimpleUploadedFile('x.png', b'\x89PNG\r\n\x1a\n' + b'garbage' * 10))
        self.assertContains(resp, 'invalid or corrupt')

    @override_settings(MAX_UPLOAD_BYTES=100)
    def test_oversized_file_rejected(self):
        resp = self.upload(pdf_file(extra=b'0' * 500))
        self.assertContains(resp, 'too large')
        self.assertEqual(PatientDocument.objects.count(), 0)

    def test_empty_file_rejected(self):
        self.assertEqual(self.upload(SimpleUploadedFile('e.pdf', b'')).status_code, 200)
        self.assertEqual(PatientDocument.objects.count(), 0)

    def test_text_only_record_allowed_but_not_a_completely_empty_one(self):
        self.assertEqual(self.upload(None, description='Appendectomy in 2018').status_code, 302)
        resp = self.upload(None, title='Nothing')
        self.assertContains(resp, 'Attach a file, or describe')

    def test_future_date_rejected(self):
        self.assertContains(self.upload(pdf_file(), record_date='2999-01-01'), 'cannot be in the future')

    def test_edit_and_delete_own_record_and_file_is_removed(self):
        self.upload(pdf_file())
        d = self.profile.documents.get()
        path = d.file.path
        self.assertTrue(os.path.exists(path))
        resp = self.client.post(reverse('medical_records:document_edit', args=[d.pk]), {
            'category': 'CERTIFICATE', 'title': 'Renamed', 'record_date': '2025-01-10', 'provider_name': '', 'description': 'd'})
        self.assertEqual(resp.status_code, 302)
        d.refresh_from_db(); self.assertEqual((d.title, d.category, d.shared_with_doctors), ('Renamed', 'CERTIFICATE', False))
        self.client.post(reverse('medical_records:document_delete', args=[d.pk]))
        self.assertFalse(PatientDocument.objects.exists())
        self.assertFalse(os.path.exists(path))

    def test_delete_requires_post(self):
        self.upload(pdf_file()); d = self.profile.documents.get()
        self.assertEqual(self.client.get(reverse('medical_records:document_delete', args=[d.pk])).status_code, 405)
        self.assertTrue(PatientDocument.objects.exists())


class DocumentPrivacyTests(BaseTestCase):
    """Patients must not see/modify/delete one another's records; doctors need consent."""
    def setUp(self):
        self.a, self.pa = self.make_patient('alice')
        self.b, self.pb = self.make_patient('bob')
        self.login(self.a)
        self.client.post(reverse('medical_records:document_upload'), {
            'category': 'LAB_REPORT', 'title': 'Alice secret', 'record_date': '2025-01-10', 'file': pdf_file(),
            'shared_with_doctors': 'on'})
        self.doc = self.pa.documents.get()
        self.file_url = reverse('medical_records:file', args=['document', self.doc.pk])

    def test_owner_can_open_and_download_file(self):
        r = self.client.get(self.file_url)
        self.assertEqual((r.status_code, r['Content-Type']), (200, 'application/pdf'))
        self.assertEqual(r['X-Content-Type-Options'], 'nosniff'); self.assertIn('no-store', r['Cache-Control'])
        self.assertTrue(b''.join(r.streaming_content).startswith(b'%PDF'))
        self.assertIn('attachment', self.client.get(self.file_url + '?download=1')['Content-Disposition'])

    def test_other_patient_cannot_view_edit_or_delete(self):
        self.login(self.b)
        self.assertEqual(self.client.get(self.file_url).status_code, 404)
        self.assertEqual(self.client.get(reverse('medical_records:document_edit', args=[self.doc.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('medical_records:document_edit', args=[self.doc.pk]),
                                          {'category': 'OTHER', 'title': 'pwned', 'record_date': '2025-01-01'}).status_code, 404)
        self.assertEqual(self.client.post(reverse('medical_records:document_delete', args=[self.doc.pk])).status_code, 404)
        self.doc.refresh_from_db(); self.assertEqual(self.doc.title, 'Alice secret')
        self.assertNotContains(self.client.get(reverse('medical_records:document_list')), 'Alice secret')

    def test_anonymous_cannot_download(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.file_url).status_code, 302)

    def test_files_are_not_reachable_via_public_media_url(self):
        self.assertEqual(self.client.get('/media/' + self.doc.file.name).status_code, 404)

    def test_doctor_without_consent_is_refused_and_attempt_is_logged(self):
        doc, _ = self.make_doctor()
        self.login(doc)
        self.assertEqual(self.client.get(self.file_url).status_code, 404)
        self.assertTrue(RecordAccessLog.objects.filter(patient=self.pa, accessed_by=doc, action='ACCESS_DENIED').exists())

    def test_doctor_with_consent_can_open_shared_document_and_it_is_logged(self):
        doc, prof = self.make_doctor(); self.consent(self.pa, prof)
        self.login(doc)
        self.assertEqual(self.client.get(self.file_url).status_code, 200)
        self.assertTrue(RecordAccessLog.objects.filter(patient=self.pa, accessed_by=doc, action='DOWNLOAD_FILE').exists())

    def test_private_document_hidden_from_consented_doctor(self):
        PatientDocument.objects.filter(pk=self.doc.pk).update(shared_with_doctors=False)
        doc, prof = self.make_doctor(); self.consent(self.pa, prof)
        self.login(doc)
        self.assertEqual(self.client.get(self.file_url).status_code, 404)
        self.assertNotContains(self.client.get(reverse('doctors:patient_detail', args=[self.pa.medical_id])), 'Alice secret')

    def test_consent_revoked_or_expired_stops_file_access(self):
        doc, prof = self.make_doctor(); grant = self.consent(self.pa, prof)
        self.login(doc); self.assertEqual(self.client.get(self.file_url).status_code, 200)
        grant.revoke(); self.assertEqual(self.client.get(self.file_url).status_code, 404)
        grant.activate(AccessGrant.Scope.VIEW, 30); self.assertEqual(self.client.get(self.file_url).status_code, 200)
        AccessGrant.objects.filter(pk=grant.pk).update(expires_at=grant.created_at)
        self.assertEqual(self.client.get(self.file_url).status_code, 404)

    def test_hospital_admin_and_sysadmin_cannot_download(self):
        for user in (self.make_hospital_admin(), self.make_sysadmin()):
            self.login(user); self.assertEqual(self.client.get(self.file_url).status_code, 404)

    def test_unknown_kind_or_bad_id_is_404(self):
        self.assertEqual(self.client.get('/medical-records/files/evil/1/').status_code, 404)
        self.assertEqual(self.client.get('/medical-records/files/document/not-a-uuid/').status_code, 404)
