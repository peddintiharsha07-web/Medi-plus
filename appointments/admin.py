from django.contrib import admin
from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'hospital', 'appointment_date', 'appointment_time', 'status')
    list_filter = ('status', 'hospital')
    search_fields = ('patient__medical_id',)
