from django.urls import path
from rest_framework.routers import SimpleRouter
from .views import ApiInfoView
from . import public_api as views
router = SimpleRouter()
router.register('staff/content', views.StaffPageViewSet, basename='staff-content')
router.register('staff/notifications', views.StaffEmailViewSet, basename='staff-notifications')
router.register('staff/privacy-requests', views.StaffPrivacyViewSet, basename='staff-privacy')
urlpatterns = [
    path('', ApiInfoView.as_view(), name='api-info'),
    path('public/config/', views.PublicConfig.as_view(), name='public-config'),
    path('content/<slug:slug>/', views.PublicPage.as_view(), name='content-page'),
    path('legal/<slug:slug>/', views.PublicPage.as_view(), name='legal-page'),
    path('privacy/requests/', views.PrivacyList.as_view(), name='privacy-requests'),
    path('staff/settings/', views.StaffSettings.as_view(), name='staff-settings'),
] + router.urls
