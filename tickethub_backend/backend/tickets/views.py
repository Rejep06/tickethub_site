from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, serializers
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from core.api import payload, idempotency_key
from core.serializers import VersionActionSerializer
from core.staff import CatalogViewSet
from events.services import public_events, check_orderable
from core.errors import BusinessError
from venues.serializers import SeatSerializer
from .models import Supplier, TicketOffer, TicketUnit, CheckoutHold
from .serializers import (SupplierSerializer, OfferSerializer, StaffOfferSerializer, StaffUnitSerializer,
                          PreviewSerializer, CreateHoldSerializer, HoldSerializer)
from . import services


class EventOffers(APIView):
    permission_classes = [AllowAny]

    def get(self, request, event_id):
        event = get_object_or_404(public_events(), pk=event_id)
        return Response(OfferSerializer(event.offers.filter(is_active=True).order_by('sale_price_minor', 'id'), many=True).data)


class SeatMap(APIView):
    permission_classes = [AllowAny]

    def get(self, request, event_id):
        event = get_object_or_404(public_events(), pk=event_id)
        if not event.seating_plan_id:
            return Response({'event_id': event.id, 'plan': None, 'seats': []})
        plan = event.seating_plan
        image = request.build_absolute_uri(plan.image.url) if plan.image else None
        return Response({'event_id': event.id, 'plan': {
                          'id': plan.id, 'version': plan.version, 'name': plan.name, 'image': image,
                          'external_background_url': plan.external_background_url or None,
                          'width': plan.external_width, 'height': plan.external_height,
                          'geometry_points': plan.external_geometry, 'sectors': plan.external_sectors,
                         }, 'seats': SeatSerializer(plan.seats.all(), many=True).data})


class Availability(APIView):
    permission_classes = [AllowAny]

    def get(self, request, event_id):
        event = get_object_or_404(public_events(), pk=event_id)
        now = timezone.now()
        orderable, code, message = True, None, None
        try:
            check_orderable(event, now)
        except BusinessError as exc:
            orderable, code, message = False, exc.business_code, str(exc.detail)
        units = list(services.available_units(event, now).select_related('seat', 'offer').order_by('id'))
        offers = {}
        seats = []
        for unit in units:
            key = str(unit.offer_id)
            if key not in offers:
                offers[key] = {'offer_id': unit.offer_id, 'available_count': 0, 'sale_price_minor': unit.offer.sale_price_minor}
            offers[key]['available_count'] += 1
            if unit.seat_id:
                seats.append({'seat_id': unit.seat_id, 'offer_id': unit.offer_id, 'sale_price_minor': unit.offer.sale_price_minor})
        return Response({'event_id': event.id, 'event_version': event.version, 'server_now': now,
                         'orderable': orderable, 'reason_code': code, 'reason_message': message, 'offers': list(offers.values()), 'available_seats': seats})


class CheckoutPreview(APIView):
    permission_classes = [AllowAny]
    serializer_class = PreviewSerializer

    def post(self, request):
        return Response(services.preview(**payload(PreviewSerializer, request)))


class CreateHold(APIView):
    serializer_class = CreateHoldSerializer

    def post(self, request):
        from users.services import rate_limit, client_ip
        rate_limit('checkout-hold', request.user.email, client_ip(request), 60, 300)
        hold = services.create_hold(request.user, **payload(CreateHoldSerializer, request), idempotency_key=idempotency_key(request))
        return Response(HoldSerializer(hold).data, status=201)


class HoldDetail(generics.RetrieveAPIView):
    serializer_class = HoldSerializer

    def get_queryset(self):
        return CheckoutHold.objects.filter(user=self.request.user).prefetch_related('items__ticket_unit')


class HoldRelease(APIView):
    def post(self, request, pk):
        from core.serializers import StrictSerializer
        payload(StrictSerializer, request)
        return Response(HoldSerializer(services.release_hold(request.user, pk)).data)


class StaffSupplierViewSet(CatalogViewSet):
    queryset = Supplier.objects.order_by('name', 'id')
    serializer_class = SupplierSerializer


class StaffOfferViewSet(CatalogViewSet):
    queryset = TicketOffer.objects.select_related('event').order_by('-created_at', 'id')
    serializer_class = StaffOfferSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if 'event' in self.request.query_params:
            queryset = queryset.filter(event_id=serializers.UUIDField().run_validation(self.request.query_params['event']))
        return queryset


class UnitBlockSerializer(VersionActionSerializer):
    confirmed_valid = serializers.BooleanField(required=False, default=False)


class RenewAllocationSerializer(VersionActionSerializer):
    allocation_until = serializers.DateTimeField()
    reason = serializers.CharField(max_length=2000)
    confirmed_valid = serializers.BooleanField()


class StaffUnitViewSet(CatalogViewSet):
    queryset = TicketUnit.objects.select_related('event', 'offer', 'seat', 'supplier').order_by('-created_at', 'id')
    serializer_class = StaffUnitSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        for key in ['event', 'offer', 'supplier']:
            if key in self.request.query_params:
                queryset = queryset.filter(**{key + '_id': serializers.UUIDField().run_validation(self.request.query_params[key])})
        if 'status' in self.request.query_params:
            queryset = queryset.filter(status=serializers.ChoiceField(choices=['AVAILABLE', 'CHECKOUT_HELD', 'ORDER_HELD', 'SOLD', 'BLOCKED']).run_validation(self.request.query_params['status']))
        return queryset

    @action(detail=True, methods=['post'])
    def block(self, request, pk=None):
        obj = services.set_unit_blocked(self.get_object().pk, blocked=True, **payload(UnitBlockSerializer, request))
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['post'])
    def unblock(self, request, pk=None):
        obj = services.set_unit_blocked(self.get_object().pk, blocked=False, **payload(UnitBlockSerializer, request))
        return Response(self.get_serializer(obj).data)


    @action(detail=True, methods=['post'], url_path='renew-allocation')
    def renew_allocation(self, request, pk=None):
        obj = services.renew_supplier_allocation(self.get_object().pk, request.user,
                                                **payload(RenewAllocationSerializer, request))
        return Response(self.get_serializer(obj).data)
