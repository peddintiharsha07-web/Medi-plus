from django.urls import reverse

from core.testing import PASSWORD, BaseTestCase
from patients.models import PatientProfile
from qr_management.models import PatientQRCode
from users.models import AuditLog, User


class RegistrationLoginTests(BaseTestCase):
    def register(self, username='newpat'):
        return self.client.post(reverse('users:register_patient'), {
            'username': username, 'email': f'{username}@x.test', 'first_name': 'New', 'last_name': 'Pat',
            'phone_number': '9999999999', 'date_of_birth': '1990-01-01', 'address': 'x',
            'password1': PASSWORD, 'password2': PASSWORD})

    def test_patient_registration_creates_profile_unique_id_and_qr_and_logs_in(self):
        resp = self.register()
        self.assertRedirects(resp, reverse('dashboard:home'), fetch_redirect_response=False)
        user = User.objects.get(username='newpat')
        profile = PatientProfile.objects.get(user=user)
        self.assertRegex(profile.medical_id, r'^MED-[A-Z0-9]{8}$')
        self.assertTrue(PatientQRCode.objects.filter(patient=profile).exists())
        self.assertEqual(self.client.get(reverse('dashboard:home')).status_code, 200)

    def test_medical_ids_are_unique(self):
        self.register('a1'); self.register('a2')
        ids = list(PatientProfile.objects.values_list('medical_id', flat=True))
        self.assertEqual(len(ids), len(set(ids)))

    def test_duplicate_username_rejected(self):
        self.register()
        self.client.logout()
        self.register()
        self.assertEqual(User.objects.filter(username='newpat').count(), 1)

    def test_login_and_logout(self):
        user, _ = self.make_patient('loginpat')
        resp = self.client.post(reverse('users:login'), {'username': 'loginpat', 'password': PASSWORD})
        self.assertRedirects(resp, reverse('dashboard:home'), fetch_redirect_response=False)
        self.assertTrue(AuditLog.objects.filter(actor=user, action_type='LOGIN').exists())
        # logout needs POST: a GET (e.g. a malicious <img src>) must not log the user out
        self.assertEqual(self.client.get(reverse('users:logout')).status_code, 405)
        self.assertEqual(self.client.get(reverse('dashboard:home')).status_code, 200)
        self.client.post(reverse('users:logout'))
        self.assertEqual(self.client.get(reverse('dashboard:home')).status_code, 302)

    def test_wrong_password_rejected(self):
        self.make_patient('p')
        resp = self.client.post(reverse('users:login'), {'username': 'p', 'password': 'nope'})
        self.assertContains(resp, 'Invalid username or password')

    def test_protected_pages_require_login(self):
        for name in ['dashboard:home', 'patients:my_records', 'patients:my_qr_card', 'medical_records:document_list',
                     'consents:privacy_center', 'doctors:search_patient', 'doctors:my_patients']:
            resp = self.client.get(reverse(name))
            self.assertEqual(resp.status_code, 302, name)
            self.assertIn(reverse('users:login'), resp['Location'])

    def test_patient_cannot_open_doctor_pages_and_vice_versa(self):
        pat, _ = self.make_patient()
        doc, _ = self.make_doctor()
        self.login(pat)
        self.assertEqual(self.client.get(reverse('doctors:search_patient')).status_code, 403)
        self.login(doc)
        self.assertEqual(self.client.get(reverse('patients:my_records')).status_code, 403)

    def test_pending_doctor_cannot_login(self):
        self.make_doctor('pendingdoc', status='PENDING')
        resp = self.client.post(reverse('users:login'), {'username': 'pendingdoc', 'password': PASSWORD})
        self.assertContains(resp, 'pending approval')
        self.assertEqual(self.client.get(reverse('dashboard:home')).status_code, 302)

    def test_suspension_ends_an_active_session(self):
        doc, _ = self.make_doctor()
        self.login(doc)
        self.assertEqual(self.client.get(reverse('dashboard:home')).status_code, 200)
        User.objects.filter(pk=doc.pk).update(status='SUSPENDED')
        resp = self.client.get(reverse('dashboard:home'))
        self.assertRedirects(resp, reverse('users:login'), fetch_redirect_response=False)

    def test_next_redirect_is_honoured_but_only_for_local_urls(self):
        self.make_patient('nx')
        url = reverse('users:login') + '?next=/patients/records/'
        resp = self.client.post(url, {'username': 'nx', 'password': PASSWORD})
        self.assertEqual(resp['Location'], '/patients/records/')
        self.client.logout()
        resp = self.client.post(reverse('users:login') + '?next=https://evil.example/', {'username': 'nx', 'password': PASSWORD})
        self.assertEqual(resp['Location'], reverse('dashboard:home'))

    def test_login_is_throttled_after_repeated_failures(self):
        self.make_patient('victim')
        for _ in range(5):
            self.client.post(reverse('users:login'), {'username': 'victim', 'password': 'bad'})
        resp = self.client.post(reverse('users:login'), {'username': 'victim', 'password': PASSWORD})
        self.assertEqual(resp.status_code, 429)  # even the right password is refused during the lockout

    def test_password_change(self):
        user, _ = self.make_patient('pc')
        self.login(user)
        new = 'An0ther!Str0ng#Pass'
        resp = self.client.post(reverse('users:password_change'), {
            'old_password': PASSWORD, 'new_password1': new, 'new_password2': new})
        self.assertRedirects(resp, reverse('users:password_change_done'), fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertTrue(user.check_password(new))

    def test_patient_can_edit_own_profile_with_validation(self):
        user, profile = self.make_patient('ep')
        self.login(user)
        base = {'first_name': 'A', 'last_name': 'B', 'email': 'a@b.test', 'phone_number': '1', 'date_of_birth': '1990-01-01',
                'address': 'x', 'gender': 'FEMALE', 'blood_group': 'O+', 'height_cm': '170', 'weight_kg': '60'}
        self.assertEqual(self.client.post(reverse('patients:edit_profile'), base).status_code, 302)
        profile.refresh_from_db()
        self.assertEqual(profile.blood_group, 'O+')
        bad = dict(base, blood_group='ZZZ', height_cm='5')
        resp = self.client.post(reverse('patients:edit_profile'), bad)
        self.assertEqual(resp.status_code, 200)  # re-rendered with errors, nothing saved
        profile.refresh_from_db()
        self.assertEqual(profile.blood_group, 'O+')
