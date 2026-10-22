from django.conf import settings
from django.db import models
from django.db.models import Q
from core.models import Record


class FunnelEvent(Record):
    session_key = models.CharField(max_length=64, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    event = models.ForeignKey('events.Event', on_delete=models.PROTECT, null=True, blank=True)
    order = models.ForeignKey('orders.Order', on_delete=models.PROTECT, null=True, blank=True, related_name='funnel_events')
    ticket_request = models.ForeignKey('ticket_requests.TicketRequest', on_delete=models.PROTECT, null=True, blank=True, related_name='funnel_events')
    event_type = models.CharField(max_length=32)
    source = models.CharField(max_length=6, choices=[('CLIENT', 'Client'), ('SERVER', 'Server')])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['order', 'event_type'], condition=Q(order__isnull=False, source='SERVER'), name='funnel_order_step_unique'),
            models.UniqueConstraint(fields=['ticket_request', 'event_type'], condition=Q(ticket_request__isnull=False, order__isnull=True, source='SERVER'), name='funnel_request_step_unique'),
        ]
        indexes = [models.Index(fields=['event_type', 'created_at'], name='funnel_period_idx')]
