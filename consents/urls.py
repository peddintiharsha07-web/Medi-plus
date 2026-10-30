from django.urls import path

from . import views

app_name = 'consents'

urlpatterns = [
    path('', views.privacy_center, name='privacy_center'),
    path('grant/', views.grant_access, name='grant'),
    path('<uuid:grant_id>/approve/', views.approve_request, name='approve'),
    path('<uuid:grant_id>/deny/', views.deny_request, name='deny'),
    path('<uuid:grant_id>/revoke/', views.revoke_grant, name='revoke'),
    path('request/', views.request_access, name='request_access'),
]
