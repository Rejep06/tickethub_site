from django.shortcuts import get_object_or_404
from rest_framework import generics, viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from core.api import payload, idempotency_key
from core.permissions import IsStaff
from core.serializers import VersionActionSerializer
from .models import Order, CustomerCase
from .serializers import (OrderSerializer, CreateOrderSerializer, CreateCaseSerializer, CaseSerializer,
    StaffOrderSerializer, CancelOrderSerializer, ContactSerializer, OrderOperationsSerializer,
    RecordDeliverySerializer, DeliverySerializer)
from . import services


def order_queryset():
    return Order.objects.select_related('event', 'user', 'manager').prefetch_related(
        'items', 'history', 'cases__items', 'financial_entries', 'deliveries__items').order_by('-created_at', 'id')


class OrderList(generics.ListCreateAPIView):
    serializer_class = OrderSerializer

    def get_queryset(self):
        return order_queryset().filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        from users.services import rate_limit, client_ip
        rate_limit('order-create', request.user.email, client_ip(request), 30, 150, 600)
        order, created = services.create_order_from_hold(request.user, payload(CreateOrderSerializer, request),
                                  idempotency_key(request), request.session.get('analytics_id', ''))
        return Response(OrderSerializer(order).data, status=201 if created else 200)


class OrderDetail(generics.RetrieveAPIView):
    serializer_class = OrderSerializer

    def get_queryset(self):
        return order_queryset().filter(user=self.request.user)


class OrderCases(APIView):
    def post(self, request, pk):
        case, created = services.create_refund_request(request.user, pk, payload(CreateCaseSerializer, request))
        return Response(CaseSerializer(case).data, status=201 if created else 200)


class CaseDetail(generics.RetrieveAPIView):
    serializer_class = CaseSerializer

    def get_queryset(self):
        return CustomerCase.objects.filter(user=self.request.user).prefetch_related('items')


class StaffOrderViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsStaff]
    serializer_class = StaffOrderSerializer

    def get_queryset(self):
        queryset = order_queryset()
        p = self.request.query_params
        for field in ['event', 'manager', 'user']:
            if field in p:
                queryset = queryset.filter(**{field + '_id': serializers.UUIDField().run_validation(p[field])})
        if 'state' in p:
            state = serializers.ChoiceField(choices=['NEW', 'IN_PROGRESS', 'CONFIRMED', 'COMPLETED', 'REJECTED', 'CANCELLED']).run_validation(p['state'])
            queryset = queryset.filter(order_state=state)
        if 'q' in p:
            queryset = queryset.filter(number__icontains=p['q'][:100])
        if 'from' in p:
            queryset = queryset.filter(created_at__gte=serializers.DateTimeField().run_validation(p['from']))
        if 'to' in p:
            queryset = queryset.filter(created_at__lt=serializers.DateTimeField().run_validation(p['to']))
        return queryset

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        data = payload(VersionActionSerializer, request)
        return Response(self.get_serializer(services.start_processing_order(self.get_object().pk, request.user, data['expected_version'])).data)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        data = payload(VersionActionSerializer, request)
        return Response(self.get_serializer(services.confirm_order(self.get_object().pk, request.user, data['expected_version'])).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        obj = services.cancel_order(self.get_object().pk, request.user, **payload(CancelOrderSerializer, request))
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        obj = services.reject_order(self.get_object().pk, request.user, **payload(CancelOrderSerializer, request))
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        data = payload(VersionActionSerializer, request)
        return Response(self.get_serializer(services.complete_order(self.get_object().pk, request.user, data['expected_version'])).data)

    @action(detail=True, methods=['post'])
    def contact(self, request, pk=None):
        obj = services.record_contact(self.get_object().pk, request.user, **payload(ContactSerializer, request))
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['post'])
    def operations(self, request, pk=None):
        obj = services.update_order_operations(self.get_object().pk, request.user, payload(OrderOperationsSerializer, request))
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['get', 'post'], url_path='financial-entries')
    def financial_entries(self, request, pk=None):
        from payments.serializers import RecordPaymentSerializer, FinancialEntrySerializer
        from payments.services import record_payment
        order = self.get_object()
        if request.method == 'GET':
            return Response(FinancialEntrySerializer(order.financial_entries.all(), many=True).data)
        entry, created = record_payment(order.id, request.user, payload(RecordPaymentSerializer, request), idempotency_key(request))
        return Response(FinancialEntrySerializer(entry).data, status=201 if created else 200)

    @action(detail=True, methods=['get', 'post'])
    def deliveries(self, request, pk=None):
        order = self.get_object()
        if request.method == 'GET':
            return Response(DeliverySerializer(order.deliveries.all(), many=True).data)
        record, created = services.record_delivery(order.id, request.user, payload(RecordDeliverySerializer, request), idempotency_key(request))
        return Response(DeliverySerializer(record).data, status=201 if created else 200)


class DeliveryVoid(APIView):
    permission_classes = [IsStaff]

    def post(self, request, pk):
        record = services.void_delivery(pk, request.user, **payload(VersionActionSerializer, request))
        return Response(DeliverySerializer(record).data)


class ItemCostUpdate(APIView):
    permission_classes = [IsStaff]

    def post(self, request, pk):
        from .serializers import UpdateItemCostSerializer
        order = services.update_item_cost(pk, request.user, **payload(UpdateItemCostSerializer, request))
        return Response(StaffOrderSerializer(order).data)
