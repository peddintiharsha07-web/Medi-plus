from django.apps import AppConfig


class MedicalRecordsConfig(AppConfig):
    name = 'medical_records'

    def ready(self):
        from . import signals  # noqa: F401
