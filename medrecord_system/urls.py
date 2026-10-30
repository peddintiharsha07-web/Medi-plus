from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('accounts/', include('users.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('patients/', include('patients.urls')),
    path('doctors/', include('doctors.urls')),
    path('hospitals/', include('hospitals.urls')),
    path('emergency/', include('emergency.urls')),
    path('administration/', include('administration.urls')),
    path('medical-records/', include('medical_records.urls')),
    path('consents/', include('consents.urls')),
    path('q/', include('qr_management.urls')),
    path('api/', include('api.urls')),
]

# NOTE: MEDIA_URL is deliberately NOT served: medical files are private and only
# reachable through the permission-checked download views / API actions.
handler403 = 'django.views.defaults.permission_denied'
