from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import ThrottledTokenObtainPairView

from users.views_api import UserViewSet, AuditLogViewSet
from patients.views_api import PatientProfileViewSet, AllergyViewSet, VaccinationViewSet
from doctors.views_api import DoctorProfileViewSet
from hospitals.views_api import (HospitalViewSet, DepartmentViewSet,
                                  HospitalStaffViewSet, RecordShareRequestViewSet)
from medical_records.views_api import (MedicalRecordViewSet, PrescriptionViewSet, LabReportViewSet,
                                        MedicalAttachmentViewSet, PatientDocumentViewSet)
from appointments.views_api import AppointmentViewSet
from emergency.views_api import EmergencyAccessLogViewSet
from qr_management.views_api import PatientQRCodeViewSet, qr_emergency, qr_resolve
from dashboard.views_api import dashboard_stats

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'audit-logs', AuditLogViewSet, basename='auditlog')
router.register(r'patients', PatientProfileViewSet, basename='patientprofile')
router.register(r'allergies', AllergyViewSet, basename='allergy')
router.register(r'vaccinations', VaccinationViewSet, basename='vaccination')
router.register(r'doctors', DoctorProfileViewSet, basename='doctorprofile')
router.register(r'hospitals', HospitalViewSet, basename='hospital')
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'hospital-staff', HospitalStaffViewSet, basename='hospitalstaff')
router.register(r'share-requests', RecordShareRequestViewSet, basename='sharerequest')
router.register(r'medical-records', MedicalRecordViewSet, basename='medicalrecord')
router.register(r'prescriptions', PrescriptionViewSet, basename='prescription')
router.register(r'lab-reports', LabReportViewSet, basename='labreport')
router.register(r'documents', PatientDocumentViewSet, basename='patientdocument')
router.register(r'attachments', MedicalAttachmentViewSet, basename='attachment')
router.register(r'appointments', AppointmentViewSet, basename='appointment')
router.register(r'emergency-logs', EmergencyAccessLogViewSet, basename='emergencylog')
router.register(r'qr-codes', PatientQRCodeViewSet, basename='qrcode')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/token/', ThrottledTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('qr/<uuid:token>/', qr_resolve, name='qr_resolve'),
    path('qr/<uuid:token>/emergency/', qr_emergency, name='qr_emergency'),
    path('dashboard/stats/', dashboard_stats, name='dashboard_stats'),
]
