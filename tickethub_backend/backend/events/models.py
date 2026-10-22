from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db import models
from core.models import Record


class Category(Record):
    slug = models.SlugField(unique=True)
    name_ru = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    kind = models.CharField(max_length=7, choices=[('SPORT', 'Sport'), ('CONCERT', 'Concert'), ('OTHER', 'Other')])
    parent = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='children')
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    # The importer must never expose its service category to the public catalogue.
    is_placeholder = models.BooleanField(default=False, editable=False)
    image = models.ImageField(upload_to='categories/', blank=True)
    image_rights_source = models.CharField(max_length=500, blank=True)
    image_rights_confirmed = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['sort_order', 'name_ru', 'id']

    def clean(self):
        from .publication import is_placeholder_category
        if self.is_active and is_placeholder_category(self):
            raise ValidationError({'is_active': 'Служебную категорию нельзя включить в афишу. Создайте настоящую категорию и перенесите в неё мероприятия.'})
        if self.image and (not self.image_rights_confirmed or not self.image_rights_source.strip()):
            raise ValidationError({'image_rights_source': 'Укажите основание использования фотографии и подтвердите права.'})
        if self.pk and not self.is_active and type(self).objects.filter(pk=self.pk).exists():
            descendants = {self.pk}
            while True:
                found = set(type(self).objects.filter(parent_id__in=descendants).values_list('pk', flat=True)) - descendants
                if not found:
                    break
                descendants.update(found)
            if Event.objects.filter(category_id__in=descendants, is_published=True).exists():
                raise ValidationError({'is_active': 'Сначала снимите мероприятия этой категории и её подкатегорий с публикации или смените им категорию.'})
        if self.pk and type(self).objects.filter(parent_id=self.pk).exclude(kind=self.kind).exists():
            raise ValidationError({'kind': 'Тип должен совпадать с типом подкатегорий. Сначала измените структуру категорий.'})
        node, visited = self.parent, {self.pk}
        while node:
            if node.pk in visited:
                raise ValidationError({'parent': 'Цикл категорий запрещён.'})
            visited.add(node.pk)
            if self.is_active and (not node.is_active or is_placeholder_category(node)):
                raise ValidationError({'parent': 'У активной категории должен быть активный, не служебный родитель.'})
            if node.kind != self.kind:
                raise ValidationError({'parent': 'Тип родителя должен совпадать.'})
            node = node.parent

    def __str__(self):
        return self.name_ru


class Participant(Record):
    name_ru = models.CharField(max_length=200)
    name_en = models.CharField(max_length=200)
    kind = models.CharField(max_length=10, choices=[('TEAM', 'Team'), ('ARTIST', 'Artist'), ('OTHER', 'Other')])

    def __str__(self):
        return self.name_ru


class Event(Record):
    slug = models.SlugField(unique=True, max_length=200)
    title_ru = models.CharField(max_length=250)
    title_en = models.CharField(max_length=250)
    description_ru = models.TextField(blank=True)
    description_en = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='events')
    venue = models.ForeignKey('venues.Venue', on_delete=models.PROTECT, related_name='events')
    participants = models.ManyToManyField(Participant, blank=True, related_name='events')
    seating_plan = models.ForeignKey('venues.SeatingPlan', on_delete=models.PROTECT, null=True, blank=True, related_name='events')
    start_at = models.DateTimeField(null=True, blank=True, db_index=True)
    date_tba = models.BooleanField(default=False)
    sale_deadline = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, default='SCHEDULED', db_index=True, choices=[('SCHEDULED', 'Scheduled'), ('POSTPONED', 'Postponed'), ('CANCELLED', 'Cancelled'), ('FINISHED', 'Finished')])
    visibility = models.CharField(max_length=8, default='PUBLIC', choices=[('PUBLIC', 'Public'), ('UNLISTED', 'Unlisted')])
    is_published = models.BooleanField(default=False, db_index=True)
    image = models.ImageField(upload_to='events/', blank=True)
    image_rights_source = models.CharField(max_length=500, blank=True)
    image_rights_confirmed = models.BooleanField(default=False)
    # None = the requirement has not been checked. Publication validation is separate from intake.
    fan_id_required = models.BooleanField(null=True, blank=True, default=None)
    fan_id_description_ru = models.TextField(blank=True)
    fan_id_description_en = models.TextField(blank=True)
    refund_policy_ru = models.TextField(blank=True)
    refund_policy_en = models.TextField(blank=True)
    refund_policy_approved = models.BooleanField(default=False)
    late_delivery_due_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['start_at', 'id']
        indexes = [models.Index(fields=['is_published', 'status', 'start_at'], name='event_catalog_idx')]

    @property
    def delivery_due_at(self):
        return self.late_delivery_due_at or (self.start_at - timedelta(hours=24) if self.start_at else None)

    def clean(self):
        errors = {}
        if self.date_tba == bool(self.start_at):
            errors['start_at'] = 'Укажите дату либо включите «Дата уточняется».'
        if self.start_at and self.sale_deadline is None:
            self.sale_deadline = self.start_at - timedelta(hours=2)
        if self.start_at and self.sale_deadline and self.sale_deadline >= self.start_at:
            errors['sale_deadline'] = 'Продажи должны завершаться до начала мероприятия.'
        if self.late_delivery_due_at and (not self.start_at or self.late_delivery_due_at >= self.start_at):
            errors['late_delivery_due_at'] = 'Выдача должна быть до начала события.'
        if self.seating_plan_id:
            if self.seating_plan.venue_id != self.venue_id:
                errors['seating_plan'] = (
                    'Схема должна принадлежать площадке мероприятия.'
                )

            if self.is_published and self.seating_plan.status != 'PUBLISHED':
                errors['seating_plan'] = (
                    'Для опубликованного мероприятия нужна опубликованная схема.'
                )
        if self.is_published:
            from .publication import content_issues
            errors.update(content_issues(self))
        if self.is_published and (not self.description_ru or not self.description_en):
            errors['description_ru'] = 'Для публикации нужны описания RU/EN.'
        if self.is_published and self.fan_id_required is None:
            errors['fan_id_required'] = 'Перед публикацией укажите, требуется ли Fan ID.'
        if self.image and (not self.image_rights_confirmed or not self.image_rights_source):
            errors['image_rights_confirmed'] = 'Подтвердите основание использования изображения.'
        if self.refund_policy_approved and (not self.refund_policy_ru or not self.refund_policy_en):
            errors['refund_policy_ru'] = 'Нужны утверждённые условия RU/EN.'
        if self.fan_id_required and (not self.fan_id_description_ru or not self.fan_id_description_en):
            errors['fan_id_description_ru'] = 'Нужны инструкции Fan ID RU/EN.'
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).first()
            if old and (old.seating_plan_id != self.seating_plan_id or old.venue_id != self.venue_id):
                if self.holds.exists() or self.units.exists():
                    errors['seating_plan'] = 'Площадку/схему нельзя менять после создания запаса или резервов.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title_ru
