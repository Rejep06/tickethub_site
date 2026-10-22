from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from core.models import Record


class Supplier(Record):
    name = models.CharField(max_length=200)
    contact = models.CharField(max_length=500, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class TicketOffer(Record):
    event = models.ForeignKey('events.Event', on_delete=models.PROTECT, related_name='offers')
    name_ru = models.CharField(max_length=200)
    name_en = models.CharField(max_length=200)
    description_ru = models.TextField(blank=True)
    description_en = models.TextField(blank=True)
    sale_price_minor = models.PositiveBigIntegerField(null=True, blank=True)
    kind = models.CharField(max_length=8, choices=[('SEAT', 'Seat'), ('CATEGORY', 'Category'), ('STANDING', 'Standing')])
    mode = models.CharField(max_length=9, default='AVAILABLE', choices=[('AVAILABLE', 'Available'), ('REQUEST', 'Request')])
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    def clean(self):
        if self.mode == 'AVAILABLE' and not self.sale_price_minor:
            raise ValidationError({'sale_price_minor': 'Нужна положительная цена в копейках.'})
        if self.event_id and bool(self.event.seating_plan_id) != (self.kind == 'SEAT'):
            raise ValidationError({'kind': 'При наличии схемы выбирают места; без схемы — категорию.'})
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).first()
            if old and self.units.exists() and (old.event_id != self.event_id or old.kind != self.kind):
                raise ValidationError('Событие и тип используемого предложения неизменяемы.')

    def __str__(self):
        return self.name_ru


class CheckoutHold(Record):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='holds')
    event = models.ForeignKey('events.Event', on_delete=models.PROTECT, related_name='holds')
    quote = models.ForeignKey('ticket_requests.Quote', on_delete=models.PROTECT, null=True, blank=True, related_name='holds')
    expires_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=9, default='ACTIVE', choices=[('ACTIVE', 'Active'), ('CONVERTED', 'Converted'), ('EXPIRED', 'Expired'), ('RELEASED', 'Released')])
    selection = models.JSONField(default=dict)
    total_minor = models.PositiveBigIntegerField()
    event_version = models.PositiveIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'event'], condition=Q(status='ACTIVE'), name='hold_one_active_user_event')]
        indexes = [models.Index(fields=['status', 'expires_at'], name='hold_cleanup_idx')]


class TicketUnit(Record):
    event = models.ForeignKey('events.Event', on_delete=models.PROTECT, related_name='units')
    offer = models.ForeignKey(TicketOffer, on_delete=models.PROTECT, related_name='units')
    seat = models.ForeignKey('venues.Seat', on_delete=models.PROTECT, null=True, blank=True, related_name='units')
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, null=True, blank=True)
    purchase_price_minor = models.PositiveBigIntegerField(null=True, blank=True)
    supplier_reference = models.CharField(max_length=200, blank=True, default='')
    stock_basis = models.CharField(max_length=20, default='OWNED', choices=[('OWNED', 'Owned'), ('EXCLUSIVE_ALLOCATION', 'Exclusive allocation')])
    allocation_until = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=13, default='AVAILABLE', choices=[('AVAILABLE', 'Available'), ('CHECKOUT_HELD', 'Checkout held'), ('ORDER_HELD', 'Order held'), ('SOLD', 'Sold'), ('BLOCKED', 'Blocked')])
    current_hold = models.ForeignKey(CheckoutHold, on_delete=models.PROTECT, null=True, blank=True, related_name='current_units')
    internal_notes = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['event', 'seat'], condition=Q(seat__isnull=False), name='unit_event_seat_unique'),
            models.UniqueConstraint(fields=['event', 'supplier', 'supplier_reference'], condition=~Q(supplier_reference='') & Q(supplier__isnull=False), name='unit_supplier_reference_unique'),
            models.CheckConstraint(condition=(Q(status='CHECKOUT_HELD', current_hold__isnull=False) | (~Q(status='CHECKOUT_HELD') & Q(current_hold__isnull=True))), name='unit_hold_matches_state'),
        ]
        indexes = [models.Index(fields=['event', 'status'], name='unit_availability_idx')]

    def clean(self):
        if self.offer_id and self.event_id != self.offer.event_id:
            raise ValidationError({'offer': 'Предложение относится к другому событию.'})
        if self.offer_id and (self.offer.kind == 'SEAT') != bool(self.seat_id):
            raise ValidationError({'seat': 'Нумерованный билет требует место; категория — без места.'})
        if self.seat_id and not self.seat.labels_known:
            raise ValidationError({'seat': 'Место без подтверждённых сектора, ряда и номера нельзя продавать.'})
        if self.seat_id and self.seat.plan_id != self.event.seating_plan_id:
            raise ValidationError({'seat': 'Место не принадлежит схеме события.'})
        if self.stock_basis == 'EXCLUSIVE_ALLOCATION' and not self.allocation_until:
            raise ValidationError({'allocation_until': 'Укажите срок эксклюзивного закрепления.'})
        if self.supplier_reference and not self.supplier_id:
            raise ValidationError({'supplier': 'Для идентификатора поставщика укажите поставщика.'})

    def __str__(self):
        return f'{self.offer} / {self.seat or str(self.id)[:8]} [{self.status}]'


class CheckoutHoldItem(Record):
    hold = models.ForeignKey(CheckoutHold, on_delete=models.PROTECT, related_name='items')
    ticket_unit = models.ForeignKey(TicketUnit, on_delete=models.PROTECT, related_name='hold_items')
    name_ru = models.CharField(max_length=200)
    name_en = models.CharField(max_length=200)
    sector = models.CharField(max_length=50, blank=True)
    row = models.CharField(max_length=30, blank=True)
    seat_number = models.CharField(max_length=30, blank=True)
    sale_price_minor = models.PositiveBigIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['hold', 'ticket_unit'], name='hold_unit_unique')]
