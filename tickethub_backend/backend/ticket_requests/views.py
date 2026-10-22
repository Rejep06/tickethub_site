from rest_framework import generics, viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from core.api import payload, idempotency_key
from core.permissions import IsStaff
from core.serializers import VersionActionSerializer
from tickets.serializers import HoldSerializer
from .models import TicketRequest, Quote
from .serializers import (CreateRequestSerializer, RequestSerializer, StaffRequestSerializer,
                         RequestActionSerializer, CreateQuoteSerializer, QuoteCheckoutSerializer, StaffQuoteSerializer)
from . import services


def request_queryset():
    return TicketRequest.objects.select_related('user', 'event').prefetch_related(
        'quotes__items', 'quotes__event__venue', 'quotes__event__category', 'quotes__event__participants').order_by('-created_at', 'id')


class RequestList(generics.ListCreateAPIView):
    serializer_class = RequestSerializer

    def get_queryset(self):
        return request_queryset().filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        from users.services import rate_limit, client_ip
        rate_limit('ticket-request', request.user.email, client_ip(request), 20, 100)
        obj, created = services.create_ticket_request(request.user, payload(CreateRequestSerializer, request),
                                      idempotency_key(request), request.session.get('analytics_id', ''))
        return Response(self.get_serializer(obj).data, status=201 if created else 200)


class RequestDetail(generics.RetrieveAPIView):
    serializer_class = RequestSerializer

    def get_queryset(self):
        return request_queryset().filter(user=self.request.user)


class RequestCancel(APIView):
    def post(self, request, pk):
        data = payload(VersionActionSerializer, request)
        obj = services.change_request(pk, request.user, {'expected_version': data['expected_version'], 'status': 'CANCELLED'}, customer=True)
        return Response(RequestSerializer(obj).data)


class QuoteCheckout(APIView):
    def post(self, request, pk):
        hold = services.start_quote_checkout(request.user, pk, **payload(QuoteCheckoutSerializer, request), idempotency_key=idempotency_key(request))
        return Response(HoldSerializer(hold).data, status=201)


class StaffRequestViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsStaff]
    serializer_class = StaffRequestSerializer

    def get_queryset(self):
        queryset = request_queryset()
        if 'status' in self.request.query_params:
            value = serializers.ChoiceField(choices=['NEW', 'IN_PROGRESS', 'OFFERED', 'CONVERTED', 'CANCELLED', 'REJECTED']).run_validation(self.request.query_params['status'])
            queryset = queryset.filter(status=value)
        if 'manager' in self.request.query_params:
            queryset = queryset.filter(manager_id=serializers.UUIDField().run_validation(self.request.query_params['manager']))
        return queryset

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        obj = services.change_request(self.get_object().pk, request.user, payload(RequestActionSerializer, request))
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        data = payload(VersionActionSerializer, request)
        obj = services.change_request(self.get_object().pk, request.user, {'expected_version': data['expected_version'], 'status': 'IN_PROGRESS'})
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['post'], url_path='update-status')
    def update_status(self, request, pk=None):
        obj = services.change_request(self.get_object().pk, request.user, payload(RequestActionSerializer, request))
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['post'])
    def quotes(self, request, pk=None):
        quote = services.create_quote(self.get_object().pk, request.user, payload(CreateQuoteSerializer, request))
        return Response(StaffQuoteSerializer(quote, context=self.get_serializer_context()).data, status=201)


class StaffQuoteViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsStaff]
    serializer_class = StaffQuoteSerializer
    queryset = Quote.objects.select_related('ticket_request', 'event__venue', 'event__category').prefetch_related('items', 'event__participants').order_by('-created_at', 'id')

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        data = payload(VersionActionSerializer, request)
        quote = services.send_quote(self.get_object().pk, request.user, data['expected_version'])
        return Response(self.get_serializer(quote).data)

    @action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        data = payload(VersionActionSerializer, request)
        quote = services.withdraw_quote(self.get_object().pk, request.user, data['expected_version'])
        return Response(self.get_serializer(quote).data)
