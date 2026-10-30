from django.contrib import admin

from .models import AccessGrant, RecordAccessLog


@admin.register(AccessGrant)
class AccessGrantAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'status', 'scope', 'expires_at', 'created_at')
    list_filter = ('status', 'scope')
    search_fields = ('patient__medical_id', 'doctor__user__username')


@admin.register(RecordAccessLog)
class RecordAccessLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'patient', 'accessed_by', 'accessor_role', 'access_level', 'action')
    list_filter = ('action', 'access_level')
    search_fields = ('patient__medical_id', 'accessed_by__username')
    readonly_fields = [f.name for f in RecordAccessLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
