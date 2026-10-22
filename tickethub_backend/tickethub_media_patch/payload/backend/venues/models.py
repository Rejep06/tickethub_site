from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from core.models import Record


class Venue(Record):
    name_ru = models.CharField(max_length=200)
    name_en = models.CharField(max_length=200)
    country = models.CharField(max_length=2, blank=True)
    city = models.CharField(max_length=100, blank=True)
    city_en = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=300, blank=True)
    address_en = models.CharField(max_length=300, blank=True)
    timezone = models.CharField(max_length=64, default='Europe/Moscow')

    external_provider = models.CharField(max_length=20, blank=True, default='', editable=False)
    external_place_id = models.CharField(max_length=30, blank=True, default='', editable=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['external_provider', 'external_place_id'],
            condition=~Q(external_provider='') & ~Q(external_place_id=''), name='venue_external_place_unique')]

    def clean(self):
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValidationError({'timezone': 'Укажите IANA timezone.'})
        self.country = self.country.upper()

    def __str__(self):
        return self.name_ru


class SeatingPlan(Record):
    venue = models.ForeignKey(Venue, on_delete=models.PROTECT, related_name='plans')
    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to='plans/', blank=True)
    rights_source = models.CharField(max_length=500, blank=True)
    rights_confirmed = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=10, default='DRAFT', choices=[('DRAFT', 'Draft'), ('PUBLISHED', 'Published'), ('ARCHIVED', 'Archived')])
    # Read-only geometry imported from a trusted external provider. Local image remains optional.
    external_provider = models.CharField(max_length=20, blank=True, default='', editable=False)
    external_layout_id = models.CharField(max_length=30, blank=True, default='', editable=False)
    external_background_url = models.URLField(max_length=1000, blank=True, default='', editable=False)
    external_width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    external_height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    external_geometry = models.JSONField(default=list, blank=True, editable=False)
    external_sectors = models.JSONField(default=list, blank=True, editable=False)
    external_synced_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['external_provider', 'external_layout_id'],
            condition=~Q(external_provider='') & ~Q(external_layout_id=''), name='plan_external_layout_unique')]

    def clean(self):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).first()
            if old and old.status != 'DRAFT' and any(getattr(self, f) != getattr(old, f) for f in
                                                    ['venue_id', 'name', 'image', 'rights_source', 'rights_confirmed']):
                raise ValidationError('Опубликованный план неизменяем. Клонируйте версию.')
        if self.image and not self.rights_confirmed:
            raise ValidationError({'rights_confirmed': 'Подтвердите право использования схемы.'})

    def __str__(self):
        return f'{self.name} ({self.status})'


class Seat(Record):
    plan = models.ForeignKey(SeatingPlan, on_delete=models.PROTECT, related_name='seats')
    sector = models.CharField(max_length=50, blank=True)
    row = models.CharField(max_length=30, blank=True)
    number = models.CharField(max_length=30, blank=True)
    external_point_key = models.CharField(max_length=64, blank=True, default='', editable=False)
    x = models.DecimalField(max_digits=7, decimal_places=6)
    y = models.DecimalField(max_digits=7, decimal_places=6)
    adjacency_group = models.CharField(max_length=80, blank=True)
    adjacency_position = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['sector', 'row', 'number', 'id']
        constraints = [
            models.UniqueConstraint(fields=['plan', 'sector', 'row', 'number'],
                condition=~Q(sector='') & ~Q(row='') & ~Q(number=''), name='seat_plan_position_unique'),
            models.UniqueConstraint(fields=['plan', 'external_point_key'],
                condition=~Q(external_point_key=''), name='seat_plan_external_point_unique'),
            models.CheckConstraint(condition=(
                (~Q(sector='') & ~Q(row='') & ~Q(number='')) |
                (Q(sector='', row='', number='') & ~Q(external_point_key=''))
            ), name='seat_labels_complete_or_unknown'),
            models.CheckConstraint(condition=Q(x__gte=0, x__lte=1, y__gte=0, y__lte=1), name='seat_coordinates_normalized'),
        ]

    @property
    def labels_known(self):
        return bool(self.sector and self.row and self.number)

    def clean(self):
        if not self.labels_known and not (
            self.external_point_key and not any([self.sector, self.row, self.number])
        ):
            raise ValidationError('Укажите сектор, ряд и номер. Неизвестная геометрия создаётся только импортом.')
        if self.plan_id and self.plan.status != 'DRAFT':
            raise ValidationError('Изменять места можно только в черновике схемы.')
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).first()
            if old and old.plan_id != self.plan_id:
                raise ValidationError('Перемещение места в другой план запрещено.')

    def __str__(self):
        if not self.labels_known:
            return f'Место без подписи · {self.x}, {self.y}'
        return f'{self.sector} / {self.row} / {self.number}' 
