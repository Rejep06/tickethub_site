from rest_framework.routers import SimpleRouter
from .views import ExternalEventViewSet

router = SimpleRouter()
router.register('staff/external-events', ExternalEventViewSet, basename='staff-external-events')
urlpatterns = router.urls
