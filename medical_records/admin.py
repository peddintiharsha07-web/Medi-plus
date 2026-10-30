from django.contrib import admin
from .models import MedicalRecord, Prescription, LabReport, MedicalAttachment


class PrescriptionInline(admin.TabularInline):
    model = Prescription
    extra = 0


class LabReportInline(admin.TabularInline):
    model = LabReport
    extra = 0


class AttachmentInline(admin.TabularInline):
    model = MedicalAttachment
    extra = 0


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'patient', 'doctor', 'hospital', 'consultation_date', 'status')
    list_filter = ('status', 'hospital')
    search_fields = ('patient__medical_id',)
    inlines = [PrescriptionInline, LabReportInline, AttachmentInline]


from .models import PatientDocument  # noqa: E402


@admin.register(PatientDocument)
class PatientDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'patient', 'category', 'record_date', 'shared_with_doctors', 'uploaded_at')
    list_filter = ('category', 'shared_with_doctors')
    search_fields = ('title', 'patient__medical_id')
    readonly_fields = ('original_filename', 'content_type', 'file_size', 'uploaded_by')
