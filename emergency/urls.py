from django.urls import path
from . import views

app_name = 'emergency'

urlpatterns = [
    path('access/', views.emergency_access, name='access'),
    path('my-logs/', views.my_emergency_logs, name='my_logs'),
]
