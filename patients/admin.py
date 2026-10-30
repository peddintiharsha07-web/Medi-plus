from django.contrib import admin
from .models import PatientProfile, Allergy, Vaccination


class AllergyInline(admin.TabularInline):
    model = Allergy
    extra = 0


class VaccinationInline(admin.TabularInline):
    model = Vaccination
    extra = 0


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ('medical_id', 'user', 'gender', 'blood_group', 'organ_donor')
    search_fields = ('medical_id', 'user__username', 'user__first_name', 'user__last_name')
    inlines = [AllergyInline, VaccinationInline]
