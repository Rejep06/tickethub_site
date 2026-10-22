import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Record(models.Model):
    """Only shared identity/timestamps; no hidden business behaviour."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ContentPage(Record):
    slug = models.SlugField()
    version = models.PositiveIntegerField(default=1)
    title_ru = models.CharField(max_length=200)
    title_en = models.CharField(max_length=200)
    body_ru = models.TextField()
    body_en = models.TextField()
    is_published = models.BooleanField(default=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['slug', 'version'], name='content_slug_version_unique'),
            models.UniqueConstraint(fields=['slug'], condition=Q(is_published=True), name='content_one_published'),
        ]

    def clean(self):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk, published_at__isnull=False).first()
            if old and any(getattr(old, field) != getattr(self, field) for field in
                           ['slug', 'version', 'title_ru', 'title_en', 'body_ru', 'body_en']):
                raise ValidationError('Опубликованный текст неизменяем. Создайте новую версию.')

    def __str__(self):
        return f'{self.slug} v{self.version}'


class ConsentRecord(Record):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    page = models.ForeignKey(ContentPage, on_delete=models.PROTECT)
    source = models.CharField(max_length=20)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'page', 'source'], name='consent_unique')]


class PrivacyRequest(Record):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=12, choices=[('ACCESS', 'Access'), ('CORRECT', 'Correct'), ('DELETE', 'Delete')])
    comment = models.TextField(blank=True, max_length=2000)
    status = models.CharField(max_length=12, default='NEW', choices=[('NEW', 'New'), ('IN_PROGRESS', 'In progress'), ('CLOSED', 'Closed')])
    response = models.TextField(blank=True)


class EmailLog(Record):
    """Business emails only, never OTP. Synchronous send + explicit retry."""
    recipient = models.EmailField()
    subject = models.CharField(max_length=250)
    body = models.TextField()
    status = models.CharField(max_length=8, default='PENDING', choices=[('PENDING', 'Pending'), ('SENDING', 'Sending'), ('SENT', 'Sent'), ('FAILED', 'Failed')])
    attempts = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    error_code = models.CharField(max_length=40, blank=True)


class IdempotencyRecord(Record):
    """Checkout requests only; orders/money carry their own key on their row."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    hold = models.ForeignKey('tickets.CheckoutHold', on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'key'], name='hold_idempotency_key_unique')]
