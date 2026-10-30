from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from users.models import User
from patients.models import PatientProfile, Allergy
from doctors.models import DoctorProfile
from hospitals.models import Hospital, Department
from medical_records.models import MedicalRecord, Prescription
from appointments.models import Appointment
from consents.models import AccessGrant


class Command(BaseCommand):
    help = "Seed demo data for MedGrid"

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                            help='Allow seeding when DEBUG is off (never do this on a real production database).')

    def handle(self, *args, **options):
        if not settings.DEBUG and not options['force']:
            raise CommandError('Refusing to create demo accounts with a well-known password while DEBUG is off. '
                               'Use --force only on a throw-away database.')
        # Hospital admin + hospital
        h_admin, created = User.objects.get_or_create(
            username='cityhospital_admin',
            defaults=dict(email='admin@cityhospital.test', first_name='Rekha', last_name='Nair',
                          role='HOSPITAL_ADMIN', status='APPROVED', phone_number='9000000001'))
        if created:
            h_admin.set_password('Demo@12345')
            h_admin.save()

        hospital, _ = Hospital.objects.get_or_create(
            admin=h_admin,
            defaults=dict(name='City Central Hospital', registration_number='REG-CCH-001',
                          address='12 MG Road', city='Visakhapatnam', state='Andhra Pradesh',
                          phone='0891-2222222', email='contact@cityhospital.test', status='APPROVED'))

        dept, _ = Department.objects.get_or_create(hospital=hospital, name='Cardiology',
                                                     defaults={'description': 'Heart & vascular care'})

        # Doctor
        doc_user, created = User.objects.get_or_create(
            username='dr_arjun',
            defaults=dict(email='arjun@cityhospital.test', first_name='Arjun', last_name='Mehta',
                          role='DOCTOR', status='APPROVED', phone_number='9000000002'))
        if created:
            doc_user.set_password('Demo@12345')
            doc_user.save()

        doc_profile, _ = DoctorProfile.objects.get_or_create(
            user=doc_user,
            defaults=dict(hospital=hospital, department=dept, specialization='Cardiology',
                          license_number='LIC-ARJUN-001', years_of_experience=8,
                          consultation_fee=500, is_emergency_authorized=True))

        # Patient
        pat_user, created = User.objects.get_or_create(
            username='asha_rao',
            defaults=dict(email='asha@example.test', first_name='Asha', last_name='Rao',
                          role='PATIENT', status='APPROVED', phone_number='9000000003'))
        if created:
            pat_user.set_password('Demo@12345')
            pat_user.save()

        pat_profile, _ = PatientProfile.objects.get_or_create(
            user=pat_user,
            defaults=dict(gender='FEMALE', blood_group='O+', emergency_contact_name='Ravi Rao',
                          emergency_contact_phone='9000000099', chronic_diseases='Hypertension',
                          current_medications='Amlodipine 5mg', organ_donor=True))

        Allergy.objects.get_or_create(patient=pat_profile, allergen='Penicillin',
                                       defaults={'reaction': 'Rash', 'severity': 'MODERATE'})

        record, created = MedicalRecord.objects.get_or_create(
            patient=pat_profile, doctor=doc_profile, hospital=hospital,
            consultation_date=timezone.now(),
            defaults=dict(symptoms='Chest discomfort', diagnosis='Mild hypertension',
                          treatment_details='Prescribed antihypertensives, advised low-sodium diet',
                          follow_up_notes='Review in 2 weeks', status='ACTIVE'))
        if created:
            Prescription.objects.create(record=record, medication_name='Amlodipine', dosage='5mg',
                                         frequency='Once daily', duration='30 days')

        Appointment.objects.get_or_create(
            patient=pat_profile, doctor=doc_profile, hospital=hospital,
            appointment_date=timezone.now().date(), appointment_time='10:30',
            defaults={'reason': 'Follow-up', 'status': 'ACCEPTED'})

        # Asha has consented to Dr. Arjun (view + add notes, 30 days).
        grant, _ = AccessGrant.objects.get_or_create(patient=pat_profile, doctor=doc_profile)
        if grant.status != AccessGrant.Status.ACTIVE:
            grant.activate(AccessGrant.Scope.VIEW_ADD, 30)

        # A second patient who has NOT consented to anyone (to try the restricted / request flow).
        meera, created = User.objects.get_or_create(
            username='meera_iyer',
            defaults=dict(email='meera@example.test', first_name='Meera', last_name='Iyer',
                          role='PATIENT', status='APPROVED', phone_number='9000000004'))
        if created:
            meera.set_password('Demo@12345')
            meera.save()
        PatientProfile.objects.get_or_create(
            user=meera, defaults=dict(gender='FEMALE', blood_group='B+', emergency_contact_name='Anand Iyer',
                                      emergency_contact_phone='9000000098'))

        self.stdout.write(self.style.SUCCESS(
            'Seeded: hospital admin (cityhospital_admin), doctor (dr_arjun, emergency-authorized), '
            'patients asha_rao (has consented to dr_arjun) and meera_iyer (no consent) '
            '— all password Demo@12345'))
