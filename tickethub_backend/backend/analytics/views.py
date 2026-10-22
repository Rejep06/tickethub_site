import csv
import uuid
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from core.api import payload
from core.errors import require
from core.permissions import IsStaff
from events.services import public_events
from users.services import rate_limit, client_ip
from .models import FunnelEvent
from .serializers import ClientEventSerializer, ReportFilterSerializer
from . import services


@method_decorator(csrf_protect, name='dispatch')
class ClientEvent(APIView):
    permission_classes = [AllowAny]
    serializer_class = ClientEventSerializer

    def post(self, request):
        require(settings.CLIENT_ANALYTICS_ENABLED, 'ANALYTICS_DISABLED', 'Веб-аналитика отключена.', status=403)
        data = payload(ClientEventSerializer, request)
        event = get_object_or_404(public_events(), pk=data['event_id'])
        key = request.session.get('analytics_id')
        if not key:
            key = uuid.uuid4().hex
            request.session['analytics_id'] = key
        rate_limit('analytics', key, client_ip(request), 300, 3000)
        row, created = FunnelEvent.objects.get_or_create(pk=data['client_event_id'], defaults={
            'event': event, 'event_type': data['event_type'], 'session_key': key, 'source': 'CLIENT',
            'user': request.user if request.user.is_authenticated else None})
        require(row.source == 'CLIENT' and row.event_id == event.id and row.event_type == data['event_type'] and row.session_key == key,
                'IDEMPOTENCY_CONFLICT', 'Идентификатор события уже использован.')
        return Response({'id': row.id}, status=201 if created else 200)


def filters(request):
    p = request.query_params
    data = {key: p[key] for key in ['event', 'category'] if key in p}
    if 'from' in p:
        data['date_from'] = p['from']
    if 'to' in p:
        data['date_to'] = p['to']
    serializer = ReportFilterSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    data = dict(serializer.validated_data)
    if 'date_from' in data:
        data['from'] = data.pop('date_from')
    if 'date_to' in data:
        data['to'] = data.pop('date_to')
    return data


class Dashboard(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        return Response(services.dashboard(filters(request)))


class Cashflow(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        return Response(services.cashflow(filters(request)))


class Funnel(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        return Response(services.funnel(filters(request)))


class Export(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        rows = services.dashboard(filters(request))['by_event']
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="tickethub-sales.csv"'
        response.write('\ufeff')
        writer = csv.writer(response)
        fields = ['event_id', 'title_ru', 'orders_count', 'tickets_count', 'turnover_minor', 'refunded_minor',
                  'purchase_cost_minor', 'unknown_cost_count', 'profit_minor', 'profit_complete']
        writer.writerow(fields)
        for row in rows:
            values = []
            for key in fields:
                value = row[key]
                # CSV opened in a spreadsheet must not execute a title as a formula.
                if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
                    value = "'" + value
                values.append(value)
            writer.writerow(values)
        return response
