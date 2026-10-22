from django.urls import path
from rest_framework.routers import SimpleRouter
from . import views
router = SimpleRouter()
router.register('staff/ticket-requests', views.StaffRequestViewSet, basename='staff-ticket-requests')
router.register('staff/quotes', views.StaffQuoteViewSet, basename='staff-quotes')
urlpatterns = [
    path('ticket-requests/', views.RequestList.as_view(), name='ticket-requests'),
    path('ticket-requests/<uuid:pk>/', views.RequestDetail.as_view(), name='ticket-request-detail'),
    path('ticket-requests/<uuid:pk>/cancel/', views.RequestCancel.as_view(), name='ticket-request-cancel'),
    path('quotes/<uuid:pk>/start-checkout/', views.QuoteCheckout.as_view(), name='quote-checkout'),
] + router.urls
