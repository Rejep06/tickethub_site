from django.urls import path
from rest_framework.routers import SimpleRouter
from . import views
router = SimpleRouter()
router.register('staff/refunds', views.StaffCaseViewSet, basename='staff-refunds')
urlpatterns = [path('staff/financial-entries/<uuid:pk>/reverse/', views.FinancialReverse.as_view(), name='financial-reverse')] + router.urls
