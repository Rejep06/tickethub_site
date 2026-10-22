from django.conf import settings
from django.db import models
from django.db.models import Q
from core.models import Record
from core.identifiers import order_number


class Order(Record):
    number = models.CharField(max_length=25, unique=True, default=order_number, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    event = models.ForeignKey('events.Event', on_delete=models.PROTECT, related_name='orders')
    hold = models.OneToOneField('tickets.CheckoutHold', on_delete=models.PROTECT, related_name='order')
    quote = models.OneToOneField('ticket_requests.Quote', on_delete=models.PROTECT, null=True, blank=True, related_name='order')
    ticket_request = models.ForeignKey('ticket_requests.TicketRequest', on_delete=models.PROTECT, null=True, blank=True, related_name='orders')
    origin = models.CharField(max_length=12, choices=[('SITE_DIRECT', 'Site direct'), ('SITE_REQUEST', 'Site request')])
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='managed_orders')
    order_state = models.CharField(max_length=11, default='NEW', choices=[('NEW', 'New'), ('IN_PROGRESS', 'In progress'), ('CONFIRMED', 'Confirmed'), ('COMPLETED', 'Completed'), ('REJECTED', 'Rejected'), ('CANCELLED', 'Cancelled')])
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=16)
    customer_email = models.EmailField()
    customer_comment = models.TextField(blank=True, max_length=2000)
    fan_id_answer = models.CharField(max_length=12, blank=True, choices=[('HAS_FAN_ID', 'Has Fan ID'), ('NEEDS_HELP', 'Needs help'), ('NOT_SURE', 'Not sure')])
    fan_id_help_state = models.CharField(max_length=12, default='NOT_NEEDED', choices=[('NOT_NEEDED', 'Not needed'), ('REQUESTED', 'Requested'), ('IN_PROGRESS', 'In progress'), ('INSTRUCTED', 'Instructed')])
    subtotal_minor = models.PositiveBigIntegerField(default=0)
    discount_minor = models.PositiveBigIntegerField(default=0)
    promo_code = models.CharField(max_length=40, blank=True, default='')
    total_minor = models.PositiveBigIntegerField()
    event_snapshot = models.JSONField(default=dict)
    accepted_document_versions = models.JSONField(default=dict)
    review_due_at = models.DateTimeField()
    settlement_due_at = models.DateTimeField(null=True, blank=True)
    delivery_due_at = models.DateTimeField(null=True, blank=True)
    first_contact_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    first_paid_at = models.DateTimeField(null=True, blank=True)
    internal_notes = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    idempotency_key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    analytics_session_key = models.CharField(max_length=64, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'idempotency_key'], name='order_idempotency_unique'),
            models.UniqueConstraint(fields=['user', 'event'], condition=Q(order_state__in=['NEW', 'IN_PROGRESS']), name='order_one_unprocessed'),
            models.CheckConstraint(condition=Q(total_minor__gt=0), name='order_positive_total'),
            models.CheckConstraint(condition=Q(subtotal_minor=models.F('total_minor') + models.F('discount_minor')), name='order_discount_matches_total'),
        ]
        indexes = [
            models.Index(fields=['user', 'created_at'], name='order_customer_idx'),
            models.Index(fields=['order_state', 'created_at'], name='order_queue_idx'),
            models.Index(fields=['delivery_due_at'], name='order_delivery_due_idx'),
        ]

    def __str__(self):
        return self.number


class OrderItem(Record):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='items')
    ticket_unit = models.ForeignKey('tickets.TicketUnit', on_delete=models.PROTECT, related_name='order_items')
    name_ru = models.CharField(max_length=200)
    name_en = models.CharField(max_length=200)
    sector = models.CharField(max_length=50, blank=True)
    row = models.CharField(max_length=30, blank=True)
    seat_number = models.CharField(max_length=30, blank=True)
    original_price_minor = models.PositiveBigIntegerField(default=0)
    discount_minor = models.PositiveBigIntegerField(default=0)
    sale_price_minor = models.PositiveBigIntegerField()
    purchase_price_minor = models.PositiveBigIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['order', 'ticket_unit'], name='order_unit_unique'),
            models.CheckConstraint(condition=Q(original_price_minor=models.F('sale_price_minor') + models.F('discount_minor')), name='order_item_discount_matches'),
            models.UniqueConstraint(fields=['ticket_unit'], condition=Q(is_active=True), name='unit_one_active_order_item'),
        ]


class CustomerCase(Record):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='cases')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=14, default='REFUND_REQUEST', choices=[('REFUND_REQUEST', 'Refund'), ('CANCEL_REQUEST', 'Cancel'), ('DELIVERY_ISSUE', 'Delivery issue'), ('OTHER', 'Other')])
    items = models.ManyToManyField(OrderItem, related_name='cases')
    reason = models.TextField(max_length=2000)
    requested_minor = models.PositiveBigIntegerField(null=True, blank=True)
    approved_minor = models.PositiveBigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=11, default='NEW', choices=[('NEW', 'New'), ('IN_PROGRESS', 'In progress'), ('NEED_INFO', 'Need info'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected'), ('CLOSED', 'Closed')])
    public_response = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='case_decisions')
    decided_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)


class DeliveryRecord(Record):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='deliveries')
    items = models.ManyToManyField(OrderItem, related_name='deliveries')
    recipient_email = models.EmailField()
    sent_at = models.DateTimeField()
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    note = models.TextField(blank=True)
    message_id = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=6, default='SENT', choices=[('SENT', 'Sent'), ('VOIDED', 'Voided')])
    void_reason = models.TextField(blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    idempotency_key = models.UUIDField()
    request_hash = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['order', 'idempotency_key'], name='delivery_idempotency_unique')]


class OrderHistory(Record):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='history')
    event_type = models.CharField(max_length=40)
    public_message = models.CharField(max_length=500)
    internal_note = models.TextField(blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        ordering = ['created_at', 'id']
