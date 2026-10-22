from django.contrib.auth import login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import generics, mixins, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from core.permissions import IsAdmin, IsStaff
from core.serializers import StrictSerializer
from .models import User
from .serializers import RequestCodeSerializer, VerifyCodeSerializer, StaffLoginSerializer, ProfileSerializer, StaffUserSerializer
from . import services


@method_decorator(csrf_protect, name='dispatch')
class RequestCodeView(APIView):
    permission_classes = [AllowAny]
    serializer_class = RequestCodeSerializer

    def post(self, request):
        data = self.serializer_class(data=request.data)
        data.is_valid(raise_exception=True)
        services.request_code(ip=services.client_ip(request), **data.validated_data)
        return Response({'detail': 'Код отправлен.', 'expires_in': 600, 'resend_after': 60})


@method_decorator(csrf_protect, name='dispatch')
class VerifyCodeView(APIView):
    permission_classes = [AllowAny]
    serializer_class = VerifyCodeSerializer

    def post(self, request):
        data = self.serializer_class(data=request.data)
        data.is_valid(raise_exception=True)
        user = services.verify_login(ip=services.client_ip(request), **data.validated_data)
        login(request, user, backend='users.backends.CustomerOTPBackend')
        request.session.set_expiry(30 * 24 * 60 * 60)
        return Response(ProfileSerializer(user).data)


@method_decorator(csrf_protect, name='dispatch')
class StaffLoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = StaffLoginSerializer

    def post(self, request):
        data = self.serializer_class(data=request.data)
        data.is_valid(raise_exception=True)
        user = services.authenticate_staff(request, **data.validated_data)
        login(request, user, backend='users.backends.StaffPasswordBackend')
        request.session.set_expiry(8 * 60 * 60)
        return Response({'id': user.id, 'email': user.email, 'staff_role': user.staff_role})


@method_decorator(csrf_protect, name='dispatch')
class LogoutView(APIView):
    serializer_class = StrictSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        logout(request)
        return Response(status=204)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        return self.request.user


class StaffUserViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                       mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = StaffUserSerializer
    queryset = User.objects.filter(staff_role__in=['ADMIN', 'MANAGER']).order_by('email')
    http_method_names = ['get', 'post', 'patch', 'head', 'options']


class CustomerListView(generics.ListAPIView):
    permission_classes = [IsStaff]
    serializer_class = ProfileSerializer

    def get_queryset(self):
        qs = User.objects.filter(staff_role='').order_by('email')
        q = self.request.query_params.get('q', '').strip()[:100]
        return qs.filter(email__icontains=q) if q else qs


class StartEmailChangeView(APIView):
    def post(self, request):
        from core.api import payload
        from .serializers import StartEmailChangeSerializer
        services.start_email_change(request, **payload(StartEmailChangeSerializer, request))
        return Response({'detail': 'Коды отправлены на старый и новый адрес.', 'expires_in': 600})


class ConfirmEmailChangeView(APIView):
    def post(self, request):
        from core.api import payload
        from .serializers import ConfirmEmailChangeSerializer
        user = services.confirm_email_change(request, **payload(ConfirmEmailChangeSerializer, request))
        return Response(ProfileSerializer(user).data)
