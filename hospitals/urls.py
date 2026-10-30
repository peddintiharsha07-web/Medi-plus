from django.urls import path
from . import views

app_name = 'hospitals'

urlpatterns = [
    path('complete-profile/', views.complete_profile, name='complete_profile'),
    path('departments/', views.manage_departments, name='manage_departments'),
    path('doctors/', views.manage_doctors, name='manage_doctors'),
    path('staff/', views.manage_staff, name='manage_staff'),
    path('appointments/', views.manage_appointments, name='manage_appointments'),
    path('share-requests/', views.share_requests, name='share_requests'),
    path('request-access/', views.request_record_access, name='request_record_access'),
]
