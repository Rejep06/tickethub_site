from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from core.models import Record
from .calculations import MAX_MONEY, normalize_code


class PromoCode(Record):
    code = models.CharField(max_length=40, unique=True)
    description = models.CharField(max_length=300, blank=True)
    kind = models.CharField(max_length=7, choices=[('PERCENT', 'Процент'), ('FIXED', 'Сумма в копейках')])
    value = models.PositiveBigIntegerField(validators=[MinValueValidator(1), MaxValueValidator(MAX_MONEY)])
    minimum_total_minor = models.PositiveBigIntegerField(default=0, validators=[MaxValueValidator(MAX_MONEY)])
    maximum_discount_minor = models.PositiveBigIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(MAX_MONEY)])
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    per_user_limit = models.PositiveIntegerField(default=1, null=True, blank=True, validators=[MinValueValidator(1)])
    # Empty = all events. A quote has individually agreed prices and cannot be stacked.
    event = models.ForeignKey('events.Event', on_delete=models.PROTECT, null=True, blank=True, related_name='promo_codes')
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['-created_at', 'id']
        constraints = [
            models.CheckConstraint(condition=Q(value__gt=0), name='promo_positive_value'),
            models.CheckConstraint(condition=Q(kind='FIXED') | Q(kind='PERCENT', value__lte=99), name='promo_valid_percent'),
            models.CheckConstraint(condition=Q(starts_at__isnull=True) | Q(ends_at__isnull=True) | Q(ends_at__gt=F('starts_at')), name='promo_valid_period'),
        ]

    def clean(self):
        errors = {}
        try:
            self.code = normalize_code(self.code)
        except ValueError:
            errors['code'] = 'От 3 до 40 символов: латинские буквы, цифры, дефис или подчёркивание.'
        if self.kind == 'PERCENT' and (not isinstance(self.value, int) or isinstance(self.value, bool) or not 1 <= self.value <= 99):
            errors['value'] = 'Процент скидки: от 1 до 99.'
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            errors['ends_at'] = 'Окончание должно быть позже начала.'
        if self.pk and not self._state.adding:
            old = type(self).objects.filter(pk=self.pk).only('code').first()
            if old and old.code != self.code:
                errors['code'] = 'Код нельзя переименовать. Отключите его и создайте новый.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.code


class PromoRedemption(Record):
    """Immutable use receipt. Cancellation/refund does not recycle a code's quota."""
    promo = models.ForeignKey(PromoCode, on_delete=models.PROTECT, related_name='redemptions')
    order = models.OneToOneField('orders.Order', on_delete=models.PROTECT, related_name='promo_redemption')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='promo_redemptions')
    code = models.CharField(max_length=40)
    discount_minor = models.PositiveBigIntegerField()
    promo_version = models.PositiveIntegerField()

    class Meta:
        indexes = [models.Index(fields=['promo', 'user'], name='promo_use_customer_idx')]
