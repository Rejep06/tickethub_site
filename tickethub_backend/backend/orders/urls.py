from django.urls import path
from rest_framework.routers import SimpleRouter
from . import views
router = SimpleRouter()
router.register('staff/orders', views.StaffOrderViewSet, basename='staff-orders')
urlpatterns = [
    path('staff/order-items/<uuid:pk>/cost/', views.ItemCostUpdate.as_view(), name='item-cost'),
    path('orders/', views.OrderList.as_view(), name='orders'),
    path('orders/<uuid:pk>/', views.OrderDetail.as_view(), name='order-detail'),
    path('orders/<uuid:pk>/cases/', views.OrderCases.as_view(), name='order-cases'),
    path('cases/<uuid:pk>/', views.CaseDetail.as_view(), name='case-detail'),
    path('staff/deliveries/<uuid:pk>/void/', views.DeliveryVoid.as_view(), name='delivery-void'),
] + router.urls
