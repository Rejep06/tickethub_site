from django.urls import path
from rest_framework.routers import SimpleRouter
from . import views
router = SimpleRouter()
router.register('staff/suppliers', views.StaffSupplierViewSet, basename='staff-suppliers')
router.register('staff/offers', views.StaffOfferViewSet, basename='staff-offers')
router.register('staff/units', views.StaffUnitViewSet, basename='staff-units')
urlpatterns = [
    path('events/<uuid:event_id>/offers/', views.EventOffers.as_view(), name='event-offers'),
    path('events/<uuid:event_id>/seat-map/', views.SeatMap.as_view(), name='event-seat-map'),
    path('events/<uuid:event_id>/availability/', views.Availability.as_view(), name='event-availability'),
    path('checkout/preview/', views.CheckoutPreview.as_view(), name='checkout-preview'),
    path('checkout/holds/', views.CreateHold.as_view(), name='hold-create'),
    path('checkout/holds/<uuid:pk>/', views.HoldDetail.as_view(), name='hold-detail'),
    path('checkout/holds/<uuid:pk>/release/', views.HoldRelease.as_view(), name='hold-release'),
] + router.urls
