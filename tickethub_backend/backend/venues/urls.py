from django.urls import path
from rest_framework.routers import SimpleRouter
from . import views
router = SimpleRouter()
router.register('staff/venues', views.StaffVenueViewSet, basename='staff-venues')
router.register('staff/plans', views.StaffPlanViewSet, basename='staff-plans')
router.register('staff/seats', views.StaffSeatViewSet, basename='staff-seats')
urlpatterns = [path('venues/', views.VenueList.as_view(), name='venues')] + router.urls
