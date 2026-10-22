from django.urls import path
from rest_framework.routers import SimpleRouter
from . import views

router = SimpleRouter()
router.register('staff/events', views.StaffEventViewSet, basename='staff-events')
router.register('staff/categories', views.StaffCategoryViewSet, basename='staff-categories')
router.register('staff/participants', views.StaffParticipantViewSet, basename='staff-participants')
urlpatterns = [
    path('categories/', views.CategoryList.as_view(), name='categories'),
    path('participants/', views.ParticipantList.as_view(), name='participants'),
    path('events/', views.EventList.as_view(), name='events'),
    path('events/<slug:slug>/', views.EventDetail.as_view(), name='event-detail'),
] + router.urls
