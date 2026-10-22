from django.urls import path, include
from rest_framework.routers import SimpleRouter
from . import views

router = SimpleRouter()
router.register('staff/users/staff', views.StaffUserViewSet, basename='staff-users')
urlpatterns = [
    path('auth/otp/request/', views.RequestCodeView.as_view()),
    path('auth/otp/verify/', views.VerifyCodeView.as_view()),
    path('auth/staff/login/', views.StaffLoginView.as_view()),
    path('auth/logout/', views.LogoutView.as_view()),
    path('me/email-change/start/', views.StartEmailChangeView.as_view()),
    path('me/email-change/confirm/', views.ConfirmEmailChangeView.as_view()),
    path('me/', views.ProfileView.as_view()),
    path('staff/customers/', views.CustomerListView.as_view()),
    path('', include(router.urls)),
]
