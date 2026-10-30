from django.urls import path

from . import views

app_name = 'medical_records'

urlpatterns = [
    path('documents/', views.document_list, name='document_list'),
    path('documents/upload/', views.document_upload, name='document_upload'),
    path('documents/<uuid:pk>/edit/', views.document_edit, name='document_edit'),
    path('documents/<uuid:pk>/delete/', views.document_delete, name='document_delete'),
    path('files/<str:kind>/<str:pk>/', views.file_download, name='file'),
]
