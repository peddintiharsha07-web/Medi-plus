from django.contrib import admin
from .models import EmergencyAccessLog


@admin.register(EmergencyAccessLog)
class EmergencyAccessLogAdmin(admin.ModelAdmin):
    list_display = ('patient', 'accessed_by', 'accessed_at', 'patient_notified')
    readonly_fields = [f.name for f in EmergencyAccessLog._meta.fields]
