from django.urls import path
from . import views
urlpatterns = [
    path('analytics/events/', views.ClientEvent.as_view(), name='analytics-events'),
    path('staff/dashboard/summary/', views.Dashboard.as_view(), name='staff-dashboard'),
    path('staff/analytics/sales/', views.Dashboard.as_view(), name='analytics-sales'),
    path('staff/analytics/cashflow/', views.Cashflow.as_view(), name='analytics-cashflow'),
    path('staff/analytics/funnel/', views.Funnel.as_view(), name='analytics-funnel'),
    path('staff/analytics/export/', views.Export.as_view(), name='analytics-export'),
]
