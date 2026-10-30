from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, AuditLog


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'status', 'is_active')
    list_filter = ('role', 'status', 'is_active')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Role & Status', {'fields': ('role', 'status', 'phone_number', 'profile_picture',
                                       'preferred_language', 'date_of_birth', 'address')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Role', {'fields': ('role', 'email')}),
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'actor', 'action_type', 'target_object', 'ip_address')
    list_filter = ('action_type',)
    search_fields = ('description', 'target_object')
    readonly_fields = [f.name for f in AuditLog._meta.fields]
