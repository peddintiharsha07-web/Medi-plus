from django.urls import reverse

from consents.models import AccessGrant, RecordAccessLog
from consents.policy import EMERGENCY, NONE, OWNER, READ, READ_WRITE, patients_visible_to, resolve_access
from core.testing import BaseTestCase
from medical_records.models import MedicalRecord


class PolicyTests(BaseTestCase):
    def setUp(self):
        self.pu, self.p = self.make_patient('pol_p')
        self.other, self.p2 = self.make_patient('pol_o')

    def level(self, user, patient=None):
        return resolve_access(user, patient or self.p).level

    def test_owner_and_other_patient(self):
        self.assertEqual(self.level(self.pu), OWNER)
        self.assertEqual(self.level(self.other), NONE)

    def test_doctor_has_no_access_by_default(self):
        doc, _ = self.make_doctor()
        self.assertEqual(self.level(doc), NONE)

    def test_doctor_levels_follow_consent_scope(self):
        doc, prof = self.make_doctor()
        grant = self.consent(self.p, prof, AccessGrant.Scope.VIEW); self.assertEqual(self.level(doc), READ)
        grant.activate(AccessGrant.Scope.VIEW_ADD, 30); self.assertEqual(self.level(doc), READ_WRITE)
        self.assertEqual(self.level(doc, self.p2), NONE)  # consent is per patient

    def test_pending_denied_revoked_expired_grants_give_nothing(self):
        doc, prof = self.make_doctor()
        grant = AccessGrant.objects.create(patient=self.p, doctor=prof)
        self.assertEqual(self.level(doc), NONE)
        grant.deny(); self.assertEqual(self.level(doc), NONE)
        grant.activate(AccessGrant.Scope.VIEW, 30); grant.revoke(); self.assertEqual(self.level(doc), NONE)
        grant.activate(AccessGrant.Scope.VIEW, 30)
        AccessGrant.objects.filter(pk=grant.pk).update(expires_at=grant.decided_at)
        self.assertEqual(self.level(doc), NONE)

    def test_emergency_doctor_only_gets_emergency_level(self):
        doc, _ = self.make_doctor(emergency=True)
        self.assertEqual(self.level(doc), EMERGENCY)

    def test_admins_and_anonymous_and_unapproved_get_nothing(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertEqual(self.level(self.make_hospital_admin()), NONE)
        self.assertEqual(self.level(self.make_sysadmin()), NONE)
        self.assertEqual(self.level(AnonymousUser()), NONE)
        doc, prof = self.make_doctor(); self.consent(self.p, prof)
        doc.status = 'SUSPENDED'; doc.save()
        self.assertEqual(self.level(doc), NONE)

    def test_patients_visible_to(self):
        doc, prof = self.make_doctor(); self.consent(self.p, prof)
        self.assertEqual(list(patients_visible_to(doc)), [self.p])
        self.assertEqual(list(patients_visible_to(self.pu)), [self.p])
        self.assertEqual(patients_visible_to(self.make_sysadmin()).count(), 0)


class ConsentFlowTests(BaseTestCase):
    def setUp(self):
        self.pu, self.p = self.make_patient('cf_p', first='Asha', last='Rao')
        self.ou, self.op = self.make_patient('cf_o')
        self.du, self.d = self.make_doctor('cf_doc')

    def detail(self): return reverse('doctors:patient_detail', args=[self.p.medical_id])

    def test_doctor_cannot_open_patient_without_consent(self):
        self.login(self.du)
        r = self.client.get(self.detail())
        self.assertEqual(r.status_code, 403)
        self.assertNotContains(r, 'Asha', status_code=403)
        self.assertTrue(RecordAccessLog.objects.filter(patient=self.p, accessed_by=self.du, action='ACCESS_DENIED').exists())

    def test_patient_grants_then_doctor_can_view_and_it_is_logged(self):
        self.login(self.pu)
        r = self.client.post(reverse('consents:grant'), {'doctor': self.d.pk, 'duration_days': 30, 'scope': 'VIEW'})
        self.assertEqual(r.status_code, 302)
        self.login(self.du)
        r = self.client.get(self.detail())
        self.assertContains(r, 'Asha')
        self.assertTrue(RecordAccessLog.objects.filter(patient=self.p, accessed_by=self.du, action='VIEW_PROFILE').exists())

    def test_doctor_request_then_patient_approve_flow(self):
        self.login(self.du)
        self.client.post(reverse('consents:request_access'), {'medical_id': self.p.medical_id.lower(), 'note': 'follow-up'})
        grant = AccessGrant.objects.get(patient=self.p, doctor=self.d)
        self.assertEqual((grant.status, grant.initiated_by_doctor), ('PENDING', True))
        self.assertEqual(self.client.get(self.detail()).status_code, 403)  # still no access while pending
        self.login(self.pu)
        self.assertContains(self.client.get(reverse('consents:privacy_center')), 'follow-up')
        self.client.post(reverse('consents:approve', args=[grant.id]), {'duration_days': 7, 'scope': 'VIEW'})
        grant.refresh_from_db(); self.assertEqual(grant.status, 'ACTIVE')
        self.login(self.du); self.assertEqual(self.client.get(self.detail()).status_code, 200)

    def test_patient_can_deny_and_doctor_gets_cooldown(self):
        self.login(self.du)
        self.client.post(reverse('consents:request_access'), {'medical_id': self.p.medical_id})
        grant = AccessGrant.objects.get()
        self.login(self.pu); self.client.post(reverse('consents:deny', args=[grant.id]))
        grant.refresh_from_db(); self.assertEqual(grant.status, 'DENIED')
        self.login(self.du)
        r = self.client.post(reverse('consents:request_access'), {'medical_id': self.p.medical_id}, follow=True)
        self.assertContains(r, 'declined a recent request')
        grant.refresh_from_db(); self.assertEqual(grant.status, 'DENIED')

    def test_revoke_removes_access_immediately(self):
        grant = self.consent(self.p, self.d)
        self.login(self.pu); self.client.post(reverse('consents:revoke', args=[grant.id]))
        self.login(self.du); self.assertEqual(self.client.get(self.detail()).status_code, 403)

    def test_other_patient_cannot_approve_deny_or_revoke_someone_elses_grant(self):
        pending = AccessGrant.objects.create(patient=self.p, doctor=self.d)
        active_doc, active_prof = self.make_doctor(); active = self.consent(self.p, active_prof)
        self.login(self.ou)
        self.assertEqual(self.client.post(reverse('consents:approve', args=[pending.id]), {'duration_days': 7, 'scope': 'VIEW_ADD'}).status_code, 404)
        self.assertEqual(self.client.post(reverse('consents:deny', args=[pending.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse('consents:revoke', args=[active.id])).status_code, 404)
        pending.refresh_from_db(); active.refresh_from_db()
        self.assertEqual((pending.status, active.status), ('PENDING', 'ACTIVE'))

    def test_doctor_cannot_use_patient_consent_endpoints(self):
        grant = AccessGrant.objects.create(patient=self.p, doctor=self.d)
        self.login(self.du)
        for name in ('consents:approve', 'consents:deny', 'consents:revoke'):
            self.assertEqual(self.client.post(reverse(name, args=[grant.id]), {'duration_days': 7, 'scope': 'VIEW'}).status_code, 403)
        self.assertEqual(self.client.post(reverse('consents:grant'), {'doctor': self.d.pk, 'duration_days': 7, 'scope': 'VIEW'}).status_code, 403)
        grant.refresh_from_db(); self.assertEqual(grant.status, 'PENDING')

    def test_consent_actions_reject_get(self):
        grant = AccessGrant.objects.create(patient=self.p, doctor=self.d); self.login(self.pu)
        self.assertEqual(self.client.get(reverse('consents:revoke', args=[grant.id])).status_code, 405)

    def test_invalid_medical_id_request(self):
        self.login(self.du)
        r = self.client.post(reverse('consents:request_access'), {'medical_id': 'MED-NOPE0000'}, follow=True)
        self.assertContains(r, 'No patient found'); self.assertFalse(AccessGrant.objects.exists())

    def test_open_redirect_in_request_access_is_ignored(self):
        self.login(self.du)
        r = self.client.post(reverse('consents:request_access'), {'medical_id': self.p.medical_id, 'next_url': 'https://evil.example/'})
        self.assertNotIn('evil.example', r['Location'])

    def test_search_shows_masked_name_only(self):
        self.login(self.du)
        r = self.client.get(reverse('doctors:search_patient'), {'q': self.p.medical_id})
        self.assertContains(r, 'Asha R.'); self.assertNotContains(r, 'Asha Rao')

    def test_search_is_rate_limited(self):
        self.login(self.du)
        for _ in range(30): self.client.get(reverse('doctors:search_patient'), {'q': 'MED-AAAAAAAA'})
        self.assertContains(self.client.get(reverse('doctors:search_patient'), {'q': 'MED-AAAAAAAA'}), 'Too many searches')

    def test_my_patients_lists_only_consented_patients(self):
        self.consent(self.p, self.d); self.login(self.du)
        r = self.client.get(reverse('doctors:my_patients'))
        self.assertContains(r, self.p.medical_id); self.assertNotContains(r, self.op.medical_id)


class ConsultationNoteTests(BaseTestCase):
    def setUp(self):
        self.pu, self.p = self.make_patient('cn_p')
        self.du, self.d = self.make_doctor('cn_doc')
        self.url = reverse('doctors:create_record', args=[self.p.medical_id])
        self.data = {'consultation_date': '2025-02-01T10:30', 'symptoms': 'cough', 'diagnosis': 'cold',
                     'treatment_details': 'rest', 'follow_up_notes': '', 'discharge_summary': '', 'status': 'ACTIVE',
                     'medication_name': ['Paracetamol', ''], 'dosage': ['500mg', ''], 'frequency': ['2x', ''], 'duration': ['3d', '']}

    def test_no_consent_no_note(self):
        self.login(self.du)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 403)
        self.assertEqual(MedicalRecord.objects.count(), 0)

    def test_view_only_consent_cannot_add_notes(self):
        self.consent(self.p, self.d, AccessGrant.Scope.VIEW); self.login(self.du)
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.post(self.url, self.data)
        self.assertEqual(MedicalRecord.objects.count(), 0)

    def test_add_notes_consent_creates_record_with_prescription_and_log(self):
        self.consent(self.p, self.d, AccessGrant.Scope.VIEW_ADD); self.login(self.du)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 302)
        rec = MedicalRecord.objects.get()
        self.assertEqual((rec.patient, rec.doctor, rec.diagnosis), (self.p, self.d, 'cold'))
        self.assertEqual(rec.prescriptions.get().medication_name, 'Paracetamol')
        self.assertTrue(RecordAccessLog.objects.filter(action='ADD_RECORD', accessed_by=self.du).exists())
        self.login(self.pu); self.assertContains(self.client.get(reverse('patients:my_records')), 'cold')

    def test_invalid_date_is_a_form_error_not_a_server_error(self):
        self.consent(self.p, self.d, AccessGrant.Scope.VIEW_ADD); self.login(self.du)
        r = self.client.post(self.url, dict(self.data, consultation_date='garbage'))
        self.assertEqual(r.status_code, 200); self.assertEqual(MedicalRecord.objects.count(), 0)

    def test_patient_cannot_use_create_record(self):
        self.login(self.pu); self.assertEqual(self.client.post(self.url, self.data).status_code, 403)


class AccessLogVisibilityTests(BaseTestCase):
    def test_patient_sees_only_own_access_history(self):
        pu, p = self.make_patient('al_p'); ou, o = self.make_patient('al_o')
        du, d = self.make_doctor('al_doc', emergency=True)
        self.consent(p, d); self.login(du)
        self.client.get(reverse('doctors:patient_detail', args=[p.medical_id]))
        self.client.get(reverse('doctors:patient_detail', args=[o.medical_id]))  # denied (emergency-only)
        self.login(pu); self.assertContains(self.client.get(reverse('consents:privacy_center')), 'Viewed patient records')
        self.login(ou); r = self.client.get(reverse('consents:privacy_center'))
        self.assertNotContains(r, 'Viewed patient records'); self.assertContains(r, 'Access denied')
