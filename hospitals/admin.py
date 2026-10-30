from django.contrib import admin
from .models import Hospital, Department, HospitalStaff, RecordShareRequest


class DepartmentInline(admin.TabularInline):
    model = Department
    extra = 0


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ('name', 'registration_number', 'city', 'status', 'admin')
    list_filter = ('status', 'state')
    search_fields = ('name', 'registration_number')
    inlines = [DepartmentInline]


@admin.register(HospitalStaff)
class HospitalStaffAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'hospital', 'role_title', 'is_active')


@admin.register(RecordShareRequest)
class RecordShareRequestAdmin(admin.ModelAdmin):
    list_display = ('hospital', 'patient', 'status', 'requested_at')
    list_filter = ('status',)
