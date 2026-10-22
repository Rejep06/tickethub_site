from django.db import migrations, models
from django.db.models import F
import re


def moderate_existing(apps, schema_editor):
    Category = apps.get_model('events', 'Category')
    Event = apps.get_model('events', 'Event')
    placeholder_ids = list(Category.objects.filter(slug='external-review').values_list('pk', flat=True))
    Category.objects.filter(pk__in=placeholder_ids).update(is_placeholder=True, is_active=False,
        name_ru='Без категории (черновики импорта)', name_en='Unclassified imported drafts')
    token = re.compile(r'\{\{?\s*[\w][\w .:-]{0,80}\s*\}?\}', re.UNICODE)
    sales = re.compile(r'(?:купить|бронирован|заказ|buy|book)[^\n]{0,120}(?:portalbilet|порталбилет)|(?:portalbilet|порталбилет)[^\n]{0,120}(?:купить|бронирован|заказ|buy|book)', re.I)
    # Intentional one-way moderation: rollback never republishes unchecked content.
    for event in Event.objects.filter(is_published=True).only('pk', 'category_id', 'title_ru', 'title_en', 'description_ru', 'description_en').iterator():
        invalid = event.category_id in placeholder_ids or any(
            token.search(getattr(event, field) or '') or sales.search(getattr(event, field) or '')
            for field in ('title_ru', 'title_en', 'description_ru', 'description_en'))
        if invalid:
            Event.objects.filter(pk=event.pk).update(is_published=False, version=F('version') + 1)


class Migration(migrations.Migration):
    dependencies = [('events', '0003_alter_event_fan_id_required')]
    operations = [
        migrations.AddField(model_name='category', name='is_placeholder', field=models.BooleanField(default=False, editable=False)),
        migrations.AddField(model_name='category', name='image', field=models.ImageField(blank=True, upload_to='categories/')),
        migrations.AddField(model_name='category', name='image_rights_source', field=models.CharField(blank=True, max_length=500)),
        migrations.AddField(model_name='category', name='image_rights_confirmed', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='category', name='version', field=models.PositiveIntegerField(default=1)),
        migrations.RunPython(moderate_existing, migrations.RunPython.noop),
    ]
