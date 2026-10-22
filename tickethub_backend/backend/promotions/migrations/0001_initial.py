import uuid
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
from django.db.models import F, Q


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('events', '0004_category_images_publication'),
        ('orders', '0003_manager_checkout_discounts'),
    ]
    operations = [
        migrations.CreateModel(name='PromoCode', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('code', models.CharField(max_length=40, unique=True)),
            ('description', models.CharField(blank=True, max_length=300)),
            ('kind', models.CharField(choices=[('PERCENT', 'Процент'), ('FIXED', 'Сумма в копейках')], max_length=7)),
            ('value', models.PositiveBigIntegerField(validators=[MinValueValidator(1), MaxValueValidator(9000000000000)])),
            ('minimum_total_minor', models.PositiveBigIntegerField(default=0, validators=[MaxValueValidator(9000000000000)])),
            ('maximum_discount_minor', models.PositiveBigIntegerField(blank=True, null=True, validators=[MinValueValidator(1), MaxValueValidator(9000000000000)])),
            ('starts_at', models.DateTimeField(blank=True, null=True)),
            ('ends_at', models.DateTimeField(blank=True, null=True)),
            ('is_active', models.BooleanField(default=True)),
            ('usage_limit', models.PositiveIntegerField(blank=True, null=True, validators=[MinValueValidator(1)])),
            ('per_user_limit', models.PositiveIntegerField(blank=True, default=1, null=True, validators=[MinValueValidator(1)])),
            ('version', models.PositiveIntegerField(default=1)),
            ('event', models.ForeignKey(blank=True, null=True, on_delete=models.PROTECT, related_name='promo_codes', to='events.event')),
        ], options={'ordering': ['-created_at', 'id']}),
        migrations.CreateModel(name='PromoRedemption', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('code', models.CharField(max_length=40)),
            ('discount_minor', models.PositiveBigIntegerField()),
            ('promo_version', models.PositiveIntegerField()),
            ('order', models.OneToOneField(on_delete=models.PROTECT, related_name='promo_redemption', to='orders.order')),
            ('promo', models.ForeignKey(on_delete=models.PROTECT, related_name='redemptions', to='promotions.promocode')),
            ('user', models.ForeignKey(on_delete=models.PROTECT, related_name='promo_redemptions', to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.AddConstraint(model_name='promocode', constraint=models.CheckConstraint(condition=Q(value__gt=0), name='promo_positive_value')),
        migrations.AddConstraint(model_name='promocode', constraint=models.CheckConstraint(condition=Q(kind='FIXED') | Q(kind='PERCENT', value__lte=99), name='promo_valid_percent')),
        migrations.AddConstraint(model_name='promocode', constraint=models.CheckConstraint(condition=Q(starts_at__isnull=True) | Q(ends_at__isnull=True) | Q(ends_at__gt=F('starts_at')), name='promo_valid_period')),
        migrations.AddIndex(model_name='promoredemption', index=models.Index(fields=['promo', 'user'], name='promo_use_customer_idx')),
    ]
