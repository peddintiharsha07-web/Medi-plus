from django.urls import path
from . import views

app_name = 'patients'

urlpatterns = [
    path('records/', views.my_records, name='my_records'),
    path('records/<uuid:record_id>/', views.record_detail, name='record_detail'),
    path('qr-card/', views.my_qr_card, name='my_qr_card'),
    path('qr-card/image.png', views.qr_image, name='qr_image'),
    path('qr-card/download/', views.qr_download, name='qr_download'),
    path('qr-card/rotate/', views.qr_rotate, name='qr_rotate'),
    path('qr-card/revoke/', views.qr_revoke, name='qr_revoke'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('allergies/add/', views.allergy_add, name='allergy_add'),
    path('allergies/<int:allergy_id>/delete/', views.allergy_delete, name='allergy_delete'),
    path('appointments/book/', views.book_appointment, name='book_appointment'),
    path('appointments/', views.my_appointments, name='my_appointments'),
    path('appointments/<uuid:appointment_id>/cancel/', views.cancel_appointment, name='cancel_appointment'),
]
