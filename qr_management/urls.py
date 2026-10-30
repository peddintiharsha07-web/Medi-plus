from django.urls import path

from . import views

app_name = 'qr'

urlpatterns = [
    path('<uuid:token>/', views.scan, name='scan'),
]
