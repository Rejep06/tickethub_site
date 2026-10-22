from django.urls import path
from rest_framework.routers import SimpleRouter
from .views import PromoPreview, StaffPromoCodeViewSet

router = SimpleRouter()
router.register('staff/promo-codes', StaffPromoCodeViewSet, basename='staff-promo-codes')
urlpatterns = [path('checkout/promo/', PromoPreview.as_view(), name='promo-preview')] + router.urls
