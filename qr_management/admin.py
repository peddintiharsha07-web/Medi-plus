from django.contrib import admin
from .models import PatientQRCode


@admin.register(PatientQRCode)
class PatientQRCodeAdmin(admin.ModelAdmin):
    list_display = ('patient', 'token', 'is_active', 'created_at')
