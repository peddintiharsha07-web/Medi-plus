from django.contrib import admin
from .models import DoctorProfile


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'specialization', 'hospital', 'license_number', 'is_emergency_authorized')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'license_number')
    list_filter = ('hospital', 'specialization', 'is_emergency_authorized')
