from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import ContentPage
from .errors import require


@transaction.atomic
def save_page(instance, data):
    if instance:
        page = ContentPage.objects.select_for_update().get(pk=instance.pk)
        require(page.published_at is None, 'CONTENT_IMMUTABLE', 'Создайте новую версию документа.')
    else:
        page = ContentPage()
    for key, value in data.items():
        setattr(page, key, value)
    page.full_clean()
    page.save()
    return page


@transaction.atomic
def publish_page(page_id, actor):
    initial = get_object_or_404(ContentPage, pk=page_id)
    pages = list(ContentPage.objects.select_for_update().filter(slug=initial.slug).order_by('id'))
    page = next(p for p in pages if p.pk == initial.pk)
    require(page.published_at is None or page.is_published, 'CONTENT_IMMUTABLE', 'Повторно публиковать старую версию нельзя.')
    if page.is_published:
        return page
    for old in pages:
        if old.is_published:
            old.is_published = False
            old.save(update_fields=['is_published', 'updated_at'])
    page.is_published = True
    page.approved_by = actor
    page.published_at = timezone.now()
    page.full_clean()
    page.save()
    return page
