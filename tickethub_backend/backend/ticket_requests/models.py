from django.conf import settings
from django.db import models
from django.db.models import Q
from core.models import Record
from core.identifiers import request_number


class TicketRequest(Record):
    number = models.CharField(max_length=25, unique=True, default=request_number, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='ticket_requests')
    event = models.ForeignKey('events.Event', on_delete=models.PROTECT, null=True, blank=True)
    custom_event_name = models.CharField(max_length=250, blank=True)
    city = models.CharField(max_length=100, blank=True)
    desired_date = models.DateField(null=True, blank=True)
    quantity = models.PositiveSmallIntegerField()
    preferences = models.CharField(max_length=500, blank=True)
    together_required = models.BooleanField(default=False)
    budget_minor = models.PositiveBigIntegerField(null=True, blank=True)
    comment = models.TextField(blank=True, max_length=2000)
    status = models.CharField(max_length=11, default='NEW', choices=[('NEW', 'New'), ('IN_PROGRESS', 'In progress'), ('OFFERED', 'Offered'), ('CONVERTED', 'Converted'), ('CANCELLED', 'Cancelled'), ('REJECTED', 'Rejected')])
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='managed_requests')
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=16)
    customer_email = models.EmailField()
    internal_notes = models.TextField(blank=True)
    public_response = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    idempotency_key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    analytics_session_key = models.CharField(max_length=64, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'idempotency_key'], name='request_idempotency_unique'),
            models.CheckConstraint(condition=Q(quantity__gte=1, quantity__lte=100), name='request_quantity_valid'),
            models.CheckConstraint(condition=Q(event__isnull=False) | ~Q(custom_event_name='') | ~Q(comment=''), name='request_event_or_description'),
        ]
        indexes = [models.Index(fields=['status', 'created_at'], name='request_queue_idx')]

    def __str__(self):
        return self.number


class Quote(Record):
    ticket_request = models.ForeignKey(TicketRequest, on_delete=models.PROTECT, related_name='quotes')
    event = models.ForeignKey('events.Event', on_delete=models.PROTECT, related_name='quotes')
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=9, default='DRAFT', choices=[('DRAFT', 'Draft'), ('SENT', 'Sent'), ('ACCEPTED', 'Accepted'), ('EXPIRED', 'Expired'), ('WITHDRAWN', 'Withdrawn')])
    expires_at = models.DateTimeField()
    total_minor = models.PositiveBigIntegerField()
    public_comment = models.TextField(blank=True, max_length=2000)
    sent_at = models.DateTimeField(null=True, blank=True)
    together_confirmed = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['ticket_request', 'version'], name='quote_version_unique')]


class QuoteItem(Record):
    quote = models.ForeignKey(Quote, on_delete=models.PROTECT, related_name='items')
    ticket_unit = models.ForeignKey('tickets.TicketUnit', on_delete=models.PROTECT)
    price_minor = models.PositiveBigIntegerField()
    name_ru = models.CharField(max_length=200)
    name_en = models.CharField(max_length=200)
    sector = models.CharField(max_length=50, blank=True)
    row = models.CharField(max_length=30, blank=True)
    seat_number = models.CharField(max_length=30, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['quote', 'ticket_unit'], name='quote_unit_unique'),
            models.CheckConstraint(condition=Q(price_minor__gt=0), name='quote_positive_price'),
        ]
