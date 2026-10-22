from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from core.api import payload, idempotency_key
from core.permissions import IsStaff
from orders.models import CustomerCase
from orders.serializers import StaffCaseSerializer
from .serializers import (FinancialEntrySerializer, MoneyOperationSerializer, ReverseEntrySerializer,
                         CaseDecisionSerializer, ApproveRefundSerializer, RejectRefundSerializer)
from . import services


class StaffCaseViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsStaff]
    queryset = CustomerCase.objects.select_related('order').prefetch_related('items').order_by('-created_at', 'id')
    serializer_class = StaffCaseSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if 'status' in self.request.query_params:
            from rest_framework import serializers
            value = serializers.ChoiceField(choices=['NEW', 'IN_PROGRESS', 'NEED_INFO', 'APPROVED', 'REJECTED', 'CLOSED']).run_validation(self.request.query_params['status'])
            queryset = queryset.filter(status=value)
        return queryset

    @action(detail=True, methods=['post'])
    def decision(self, request, pk=None):
        case = services.decide_case(self.get_object().pk, request.user, **payload(CaseDecisionSerializer, request))
        return Response(self.get_serializer(case).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        case = services.approve_refund(self.get_object().pk, request.user, **payload(ApproveRefundSerializer, request))
        return Response(self.get_serializer(case).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        case = services.decide_case(self.get_object().pk, request.user, decision='REJECTED', **payload(RejectRefundSerializer, request))
        return Response(self.get_serializer(case).data)

    @action(detail=True, methods=['post'])
    def settle(self, request, pk=None):
        entry, created = services.record_refund(self.get_object().pk, request.user, payload(MoneyOperationSerializer, request), idempotency_key(request))
        return Response(FinancialEntrySerializer(entry).data, status=201 if created else 200)


class FinancialReverse(APIView):
    permission_classes = [IsStaff]

    def post(self, request, pk):
        entry, created = services.reverse_entry(pk, request.user, payload(ReverseEntrySerializer, request), idempotency_key(request))
        return Response(FinancialEntrySerializer(entry).data, status=201 if created else 200)
