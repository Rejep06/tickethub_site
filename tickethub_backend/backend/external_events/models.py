from django.db import models
from core.models import Record


class ExternalEvent(Record):
    """One upstream event; existing local Event remains one occurrence/date."""
    provider = models.CharField(max_length=20, default='portalbilet', editable=False)
    external_event_id = models.CharField(max_length=30, editable=False)
    event_source_id = models.CharField(max_length=30, editable=False)
    external_place_id = models.CharField(max_length=30, editable=False)
    external_layout_id = models.CharField(max_length=30, blank=True, editable=False)
    url = models.URLField(max_length=600)
    title = models.CharField(max_length=250)
    venue = models.ForeignKey('venues.Venue', on_delete=models.PROTECT, null=True, blank=True)
    status = models.CharField(max_length=12, default='NEW', choices=[
        ('NEW', 'New'), ('RUNNING', 'Running'), ('COMPLETED', 'Completed'),
        ('PARTIAL', 'Partial'), ('FAILED', 'Failed'),
    ])
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_metadata_sync_at = models.DateTimeField(null=True, blank=True)
    diagnostics = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['provider', 'external_event_id'], name='external_event_source_unique')]
        ordering = ['-updated_at']

    def __str__(self):
        return self.title


class ExternalDate(Record):
    external_event = models.ForeignKey(ExternalEvent, on_delete=models.PROTECT, related_name='dates')
    external_date_id = models.CharField(max_length=30, editable=False)
    event = models.OneToOneField('events.Event', on_delete=models.PROTECT, related_name='external_date')
    source_active = models.BooleanField(default=True)
    source_start_at = models.DateTimeField(null=True, blank=True)
    last_local_version = models.PositiveIntegerField(default=1)
    last_seen_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['external_event', 'external_date_id'], name='external_date_source_unique')]


class ExternalSeatInventory(Record):
    """Read-only PortalBilet availability for one local physical Seat and event date.

    enabled_for_sale is a LOCAL manager decision. Provider sync never changes it.
    This row is not a TicketUnit and does not promise that PortalBilet reserved the seat.
    """
    external_date = models.ForeignKey(ExternalDate, on_delete=models.CASCADE, related_name='seat_inventory')
    seat = models.ForeignKey('venues.Seat', on_delete=models.PROTECT, related_name='external_inventory')
    external_ticket_id = models.CharField(max_length=100, blank=True, default='')
    source_price_minor = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, default='RUB')
    source_code = models.CharField(max_length=50, blank=True, default='')
    source_available = models.BooleanField(default=True)
    enabled_for_sale = models.BooleanField(default=False)
    last_seen_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['external_date', 'seat'], name='external_date_seat_unique')]
        indexes = [models.Index(fields=['external_date', 'source_available'], name='external_seat_avail_idx')]

    def __str__(self):
        return f'{self.external_date.external_date_id}: {self.seat}'


class ExternalStandingInventory(Record):
    """Standing/general-admission/add-on inventory; never converted to fake Seat rows."""
    external_date = models.ForeignKey(ExternalDate, on_delete=models.CASCADE, related_name='standing_inventory')
    external_key = models.CharField(max_length=64, editable=False)
    name = models.CharField(max_length=200)
    external_ticket_id = models.CharField(max_length=100, blank=True, default='')
    source_price_minor = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, default='RUB')
    source_code = models.CharField(max_length=50, blank=True, default='')
    available_count = models.PositiveIntegerField(default=0)
    source_available = models.BooleanField(default=True)
    enabled_for_sale = models.BooleanField(default=False)
    last_seen_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['external_date', 'external_key'], name='external_standing_key_unique')]
        indexes = [models.Index(fields=['external_date', 'source_available'], name='external_stand_avail_idx')]

    def __str__(self):
        return f'{self.external_date.external_date_id}: {self.name}'


class ExternalSnapshot(Record):
    """Latest bounded, redacted response per resource; staff-only, never public API."""
    external_event = models.ForeignKey(ExternalEvent, on_delete=models.CASCADE, related_name='snapshots')
    resource = models.CharField(max_length=90)
    url = models.URLField(max_length=1000)
    sha256 = models.CharField(max_length=64)
    byte_count = models.PositiveIntegerField()
    structure = models.JSONField(default=dict)
    payload = models.JSONField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['external_event', 'resource'], name='external_snapshot_resource_unique')]
