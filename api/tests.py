import uuid

from rest_framework.test import APIClient

from consents.models import AccessGrant
from core.testing import PASSWORD, BaseTestCase, pdf_file
from medical_records.models import LabReport, MedicalAttachment, MedicalRecord, PatientDocument, Prescription
from qr_management.models import PatientQRCode


class APIBase(BaseTestCase):
    def api(self, user=None):
        c = APIClient()
        if user is not None:
            token = c.post('/api/auth/token/', {'username': user.username, 'password': PASSWORD}, format='json').data['access']
            c.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return c

    def seed_patient_data(self, patient, doctor_profile):
        rec = MedicalRecord.objects.create(patient=patient, doctor=doctor_profile, consultation_date='2025-01-01T10:00Z',
                                           diagnosis='SECRET-DIAGNOSIS')
        rx = Prescription.objects.create(record=rec, medication_name='SecretMed', file=pdf_file())
        lab = LabReport.objects.create(record=rec, title='SecretLab', report_date='2025-01-01', file=pdf_file())
        att = MedicalAttachment.objects.create(record=rec, description='SecretAtt', file=pdf_file())
        doc = PatientDocument.objects.create(patient=patient, title='SecretDoc', file=pdf_file())
        return rec, rx, lab, att, doc


class AuthTests(APIBase):
    def test_unauthenticated_requests_are_rejected(self):
        for url in ('/api/patients/', '/api/medical-records/', '/api/prescriptions/', '/api/lab-reports/', '/api/attachments/',
                    '/api/documents/', '/api/qr-codes/', '/api/doctors/', '/api/appointments/', '/api/users/'):
            self.assertEqual(APIClient().get(url).status_code, 401, url)

    def test_unapproved_and_suspended_accounts_get_no_token(self):
        self.make_doctor('pend', status='PENDING'); u, _ = self.make_patient('susp'); u.status = 'SUSPENDED'; u.save()
        for name in ('pend', 'susp'):
            r = APIClient().post('/api/auth/token/', {'username': name, 'password': PASSWORD}, format='json')
            self.assertEqual(r.status_code, 401, name)

    def test_existing_token_stops_working_after_suspension(self):
        du, _ = self.make_doctor(); c = self.api(du)
        self.assertEqual(c.get('/api/doctors/').status_code, 200)
        du.status = 'SUSPENDED'; du.save()
        self.assertEqual(c.get('/api/doctors/').status_code, 403)

    def test_token_endpoint_is_throttled(self):
        self.make_patient('thr')
        for _ in range(5): APIClient().post('/api/auth/token/', {'username': 'thr', 'password': 'bad'}, format='json')
        self.assertEqual(APIClient().post('/api/auth/token/', {'username': 'thr', 'password': PASSWORD}, format='json').status_code, 429)


class ClinicalDataLeakTests(APIBase):
    """Regression tests for the original holes: any logged-in user could read every patient's files and records."""
    def setUp(self):
        self.au, self.a = self.make_patient('api_a'); self.bu, self.b = self.make_patient('api_b')
        self.du, self.d = self.make_doctor('api_doc')
        self.rec, self.rx, self.lab, self.att, self.docu = self.seed_patient_data(self.a, self.d)
        self.endpoints = {'medical-records': self.rec.pk, 'prescriptions': self.rx.pk, 'lab-reports': self.lab.pk,
                          'attachments': self.att.pk, 'documents': self.docu.pk}

    def test_owner_can_read_everything(self):
        c = self.api(self.au)
        for ep, pk in self.endpoints.items():
            self.assertEqual(c.get(f'/api/{ep}/{pk}/').status_code, 200, ep)
            self.assertEqual(c.get(f'/api/{ep}/').data['count'], 1, ep)

    def test_other_patient_sees_nothing(self):
        c = self.api(self.bu)
        for ep, pk in self.endpoints.items():
            self.assertEqual(c.get(f'/api/{ep}/').data['count'], 0, ep)
            self.assertEqual(c.get(f'/api/{ep}/{pk}/').status_code, 404, ep)
            if ep != 'medical-records':
                self.assertEqual(c.get(f'/api/{ep}/{pk}/download/').status_code, 404, ep)
        self.assertEqual(c.get(f'/api/patients/{self.a.pk}/').status_code, 404)

    def test_doctor_without_consent_sees_nothing(self):
        c = self.api(self.du)
        for ep, pk in self.endpoints.items():
            self.assertEqual(c.get(f'/api/{ep}/').data['count'], 0, ep)
            self.assertEqual(c.get(f'/api/{ep}/{pk}/').status_code, 404, ep)
        self.assertEqual(c.get('/api/patients/').data['count'], 0)

    def test_doctor_with_consent_sees_shared_data_only(self):
        self.consent(self.a, self.d); c = self.api(self.du)
        for ep, pk in self.endpoints.items():
            self.assertEqual(c.get(f'/api/{ep}/{pk}/').status_code, 200, ep)
        PatientDocument.objects.filter(pk=self.docu.pk).update(shared_with_doctors=False)
        self.assertEqual(c.get(f'/api/documents/{self.docu.pk}/').status_code, 404)
        self.assertEqual(c.get('/api/patients/').data['count'], 1)

    def test_revoked_consent_closes_the_api(self):
        g = self.consent(self.a, self.d); c = self.api(self.du); g.revoke()
        self.assertEqual(c.get('/api/medical-records/').data['count'], 0)

    def test_hospital_admin_and_sysadmin_see_no_clinical_data(self):
        for user in (self.make_hospital_admin(), self.make_sysadmin()):
            c = self.api(user)
            for ep in self.endpoints: self.assertEqual(c.get(f'/api/{ep}/').data['count'], 0, ep)
            self.assertEqual(c.get('/api/patients/').data['count'], 0)

    def test_responses_never_contain_raw_storage_paths(self):
        body = self.api(self.au).get(f'/api/medical-records/{self.rec.pk}/').content.decode()
        self.assertNotIn('/media/', body); self.assertNotIn('patient_documents/', body)
        self.assertIn('/download/', body)

    def test_download_endpoint_streams_file_for_owner(self):
        r = self.api(self.au).get(f'/api/documents/{self.docu.pk}/download/')
        self.assertEqual((r.status_code, r['Content-Type']), (200, 'application/pdf'))

    def test_patient_cannot_modify_or_create_doctor_authored_records(self):
        c = self.api(self.au)
        self.assertEqual(c.patch(f'/api/medical-records/{self.rec.pk}/', {'diagnosis': 'x'}, format='json').status_code, 403)
        self.assertEqual(c.post('/api/prescriptions/', {'record': self.rec.pk, 'medication_name': 'x'}, format='json').status_code, 403)
        self.assertEqual(c.delete(f'/api/prescriptions/{self.rx.pk}/').status_code, 403)
        self.assertIn(c.delete(f'/api/medical-records/{self.rec.pk}/').status_code, (403, 405))
        self.assertTrue(MedicalRecord.objects.filter(pk=self.rec.pk).exists())

    def test_doctor_write_rules(self):
        c = self.api(self.du)
        payload = {'patient': self.a.pk, 'consultation_date': '2025-03-01T10:00:00Z', 'diagnosis': 'new'}
        self.assertEqual(c.post('/api/medical-records/', payload, format='json').status_code, 400)  # not even visible
        self.consent(self.a, self.d, AccessGrant.Scope.VIEW)
        self.assertEqual(c.post('/api/medical-records/', payload, format='json').status_code, 403)  # view-only consent
        self.consent(self.a, self.d, AccessGrant.Scope.VIEW_ADD)
        r = c.post('/api/medical-records/', payload, format='json'); self.assertEqual(r.status_code, 201)
        self.assertEqual(MedicalRecord.objects.get(pk=r.data['id']).doctor, self.d)
        self.assertEqual(c.delete(f'/api/medical-records/{r.data["id"]}/').status_code, 405)
        # cannot move a record to another patient
        c.patch(f'/api/medical-records/{r.data["id"]}/', {'patient': self.b.pk}, format='json')
        self.assertEqual(MedicalRecord.objects.get(pk=r.data['id']).patient, self.a)

    def test_doctor_cannot_edit_another_doctors_record(self):
        du2, d2 = self.make_doctor(); self.consent(self.a, d2, AccessGrant.Scope.VIEW_ADD)
        r = self.api(du2).patch(f'/api/medical-records/{self.rec.pk}/', {'diagnosis': 'hacked'}, format='json')
        self.assertEqual(r.status_code, 403); self.rec.refresh_from_db(); self.assertEqual(self.rec.diagnosis, 'SECRET-DIAGNOSIS')

    def test_patient_document_api_upload_validates_files(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        c = self.api(self.au)
        ok = c.post('/api/documents/', {'title': 'T', 'category': 'LAB_REPORT', 'record_date': '2025-01-01', 'file': pdf_file()}, format='multipart')
        self.assertEqual(ok.status_code, 201); self.assertNotIn('file', ok.data)
        bad = c.post('/api/documents/', {'title': 'T', 'file': SimpleUploadedFile('x.pdf', b'not a pdf')}, format='multipart')
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.api(self.bu).delete(f'/api/documents/{ok.data["id"]}/').status_code, 404)

    def test_doctor_cannot_write_patient_documents(self):
        self.consent(self.a, self.d, AccessGrant.Scope.VIEW_ADD)
        self.assertEqual(self.api(self.du).post('/api/documents/', {'title': 'x', 'description': 'y'}, format='json').status_code, 403)


class ProfilesAndDirectoryTests(APIBase):
    def test_patient_cannot_hijack_profile_or_change_medical_id(self):
        au, a = self.make_patient(); bu, b = self.make_patient(); c = self.api(au)
        old = a.medical_id
        r = c.patch(f'/api/patients/{a.pk}/', {'medical_id': 'MED-HACKED00', 'user': bu.pk, 'blood_group': 'A+'}, format='json')
        self.assertEqual(r.status_code, 200); a.refresh_from_db()
        self.assertEqual((a.medical_id, a.user_id, a.blood_group), (old, au.pk, 'A+'))
        self.assertEqual(c.patch(f'/api/patients/{b.pk}/', {'blood_group': 'B+'}, format='json').status_code, 404)
        self.assertEqual(c.post('/api/patients/', {}, format='json').status_code, 405)
        self.assertEqual(c.delete(f'/api/patients/{a.pk}/').status_code, 405)

    def test_patient_cannot_escalate_a_doctor_profile(self):
        au, _ = self.make_patient(); du, d = self.make_doctor()
        c = self.api(au)
        for method in (c.patch, c.put):
            self.assertEqual(method(f'/api/doctors/{d.pk}/', {'is_emergency_authorized': True}, format='json').status_code, 405)
        d.refresh_from_db(); self.assertFalse(d.is_emergency_authorized)

    def test_doctor_cannot_self_grant_emergency_or_change_licence(self):
        du, d = self.make_doctor(); lic = d.license_number
        r = self.api(du).patch('/api/doctors/me/', {'is_emergency_authorized': True, 'license_number': 'X', 'bio': 'hi'}, format='json')
        self.assertEqual(r.status_code, 200); d.refresh_from_db()
        self.assertEqual((d.is_emergency_authorized, d.license_number, d.bio), (False, lic, 'hi'))

    def test_doctor_directory_hides_licence_and_emergency_flag_from_others(self):
        au, _ = self.make_patient(); du, d = self.make_doctor()
        row = self.api(au).get(f'/api/doctors/{d.pk}/').data
        self.assertNotIn('license_number', row); self.assertNotIn('is_emergency_authorized', row)
        self.assertIn('license_number', self.api(du).get(f'/api/doctors/{d.pk}/').data)

    def test_users_endpoint_is_self_only_and_not_creatable(self):
        au, _ = self.make_patient(); bu, _ = self.make_patient(); c = self.api(au)
        self.assertEqual(c.get('/api/users/').data['count'], 1)
        self.assertEqual(c.get(f'/api/users/{bu.pk}/').status_code, 404)
        self.assertEqual(c.post('/api/users/', {'username': 'new'}, format='json').status_code, 405)
        self.assertEqual(c.delete(f'/api/users/{au.pk}/').status_code, 405)
        c.patch(f'/api/users/{au.pk}/', {'role': 'SYSTEM_ADMIN', 'status': 'APPROVED'}, format='json')
        au.refresh_from_db(); self.assertEqual(au.role, 'PATIENT')

    def test_hospital_data_is_read_only_and_hides_admin_details(self):
        au, _ = self.make_patient(); ha = self.make_hospital_admin(); h = ha.hospital
        c = self.api(au); row = c.get(f'/api/hospitals/{h.pk}/').data
        self.assertNotIn('registration_number', row); self.assertNotIn('admin', row)
        self.assertEqual(c.patch(f'/api/hospitals/{h.pk}/', {'name': 'pwn'}, format='json').status_code, 405)
        self.assertEqual(c.post('/api/departments/', {'hospital': h.pk, 'name': 'x'}, format='json').status_code, 403)

    def test_share_requests_are_read_only_and_scoped(self):
        from hospitals.models import RecordShareRequest
        au, a = self.make_patient(); bu, _ = self.make_patient(); ha = self.make_hospital_admin()
        s = RecordShareRequest.objects.create(hospital=ha.hospital, patient=a)
        self.assertEqual(self.api(au).get('/api/share-requests/').data['count'], 1)
        self.assertEqual(self.api(bu).get('/api/share-requests/').data['count'], 0)
        for user in (au, ha): self.assertEqual(self.api(user).patch(f'/api/share-requests/{s.pk}/', {'status': 'APPROVED'}, format='json').status_code, 405)


class QRApiTests(APIBase):
    def test_qr_endpoint_lists_only_own_and_never_exposes_raw_token_field(self):
        au, a = self.make_patient(); bu, b = self.make_patient(); du, d = self.make_doctor()
        r = self.api(au).get('/api/qr-codes/')
        self.assertEqual(r.data['count'], 1); self.assertNotIn('token', r.data['results'][0])
        self.assertEqual(self.api(du).get('/api/qr-codes/').status_code, 403)   # doctors can no longer list every token
        self.assertEqual(self.api(bu).get(f'/api/qr-codes/{PatientQRCode.objects.get(patient=a).pk}/').status_code, 404)

    def test_rotate_and_revoke_via_api(self):
        au, a = self.make_patient(); c = self.api(au); old = PatientQRCode.objects.get(patient=a).token
        self.assertEqual(c.post('/api/qr-codes/rotate/').status_code, 200)
        self.assertNotEqual(PatientQRCode.objects.get(patient=a).token, old)
        self.assertEqual(c.post('/api/qr-codes/revoke/').data['state'], 'Revoked')

    def test_resolve_endpoint_respects_consent_and_hides_existence(self):
        au, a = self.make_patient(); du, d = self.make_doctor(); tok = PatientQRCode.objects.get(patient=a).token
        c = self.api(du)
        self.assertEqual(c.get(f'/api/qr/{tok}/').status_code, 404)      # no consent: same as an invalid token
        self.consent(a, d)
        r = c.get(f'/api/qr/{tok}/'); self.assertEqual((r.status_code, r.data['medical_id']), (200, a.medical_id))
        self.assertEqual(self.api(au).get(f'/api/qr/{tok}/').status_code, 404)
        self.assertEqual(c.get(f'/api/qr/{uuid.uuid4()}/').status_code, 404)

    def test_emergency_api_only_for_authorized_doctors_and_returns_limited_data(self):
        au, a = self.make_patient(); a.chronic_diseases = 'Asthma'; a.save(); tok = PatientQRCode.objects.get(patient=a).token
        plain, _ = self.make_doctor(); em, _ = self.make_doctor(emergency=True)
        self.assertEqual(self.api(plain).post(f'/api/qr/{tok}/emergency/', {'reason': 'ER intake'}, format='json').status_code, 404)
        c = self.api(em)
        self.assertEqual(c.post(f'/api/qr/{tok}/emergency/', {'reason': ''}, format='json').status_code, 400)
        r = c.post(f'/api/qr/{tok}/emergency/', {'reason': 'ER intake'}, format='json')
        self.assertEqual(r.status_code, 200); self.assertEqual(r.data['critical_info']['chronic_diseases'], 'Asthma')
        self.assertNotIn('address', str(r.data))


class AppointmentApiTests(APIBase):
    def test_patient_cannot_book_for_someone_else_or_self_approve(self):
        au, a = self.make_patient(); bu, b = self.make_patient(); du, d = self.make_doctor()
        c = self.api(au)
        r = c.post('/api/appointments/', {'patient': b.pk, 'doctor': d.pk, 'appointment_date': '2999-01-01',
                                          'appointment_time': '10:00', 'status': 'ACCEPTED'}, format='json')
        self.assertEqual(r.status_code, 201)
        from appointments.models import Appointment
        appt = Appointment.objects.get(pk=r.data['id']); self.assertEqual((appt.patient, appt.status), (a, 'PENDING'))
        self.assertEqual(c.patch(f'/api/appointments/{appt.pk}/', {'status': 'ACCEPTED'}, format='json').status_code, 403)
        self.assertEqual(c.patch(f'/api/appointments/{appt.pk}/', {'status': 'CANCELLED'}, format='json').status_code, 200)
        self.assertEqual(self.api(bu).get(f'/api/appointments/{appt.pk}/').status_code, 404)
        self.assertEqual(c.delete(f'/api/appointments/{appt.pk}/').status_code, 405)
        self.assertEqual(c.post('/api/appointments/', {'doctor': d.pk, 'appointment_date': '2001-01-01', 'appointment_time': '10:00'}, format='json').status_code, 400)

    def test_hospital_admin_does_not_see_reason_text(self):
        from appointments.models import Appointment
        au, a = self.make_patient(); du, d = self.make_doctor(); ha = self.make_hospital_admin()
        d.hospital = ha.hospital; d.save()
        Appointment.objects.create(patient=a, doctor=d, hospital=ha.hospital, appointment_date='2999-01-01', appointment_time='10:00', reason='SECRET-REASON')
        row = self.api(ha).get('/api/appointments/').data['results'][0]
        self.assertNotIn('reason', row); self.assertIn('SECRET-REASON', str(self.api(au).get('/api/appointments/').data))
