from django.urls import path
from . import views

app_name = 'administration'

urlpatterns = [
    path('hospitals/pending/', views.pending_hospitals, name='pending_hospitals'),
    path('hospitals/<uuid:hospital_id>/approve/', views.approve_hospital, name='approve_hospital'),
    path('hospitals/<uuid:hospital_id>/reject/', views.reject_hospital, name='reject_hospital'),
    path('doctors/pending/', views.pending_doctors, name='pending_doctors'),
    path('doctors/<uuid:user_id>/approve/', views.approve_doctor, name='approve_doctor'),
    path('doctors/<uuid:user_id>/reject/', views.reject_doctor, name='reject_doctor'),
    path('patients/', views.manage_patients, name='manage_patients'),
    path('hospitals/', views.manage_hospitals, name='manage_hospitals'),
    path('doctors/', views.manage_doctors, name='manage_doctors'),
    path('users/<uuid:user_id>/toggle-suspend/', views.toggle_suspend, name='toggle_suspend'),
    path('audit-logs/', views.audit_logs, name='audit_logs'),
    path('analytics/', views.analytics, name='analytics'),
]
