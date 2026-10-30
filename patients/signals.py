from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import PatientProfile


@receiver(post_save, sender=PatientProfile)
def create_qr_for_new_patient(sender, instance, created, **kwargs):
    if created:
        from qr_management.services import generate_qr_for_patient
        generate_qr_for_patient(instance)
