from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw
from events.models import Category, Event
from venues.models import Venue
from venues.models import SeatingPlan, Seat
from venues.services import publish_plan
from tickets.models import Supplier, TicketOffer, TicketUnit


class Command(BaseCommand):
    help = 'Безопасные demo-события для local/test. Не создаёт пользователей или заказов.'

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG and not settings.ALLOW_DEMO_DATA:
            raise CommandError('Demo data is disabled in this environment.')
        category, _ = Category.objects.get_or_create(slug='demo-football', defaults={
            'name_ru': 'Демо: футбол', 'name_en': 'Demo football', 'kind': 'SPORT'})
        venue, _ = Venue.objects.get_or_create(name_ru='Демо-площадка Tickethub', defaults={
            'name_en': 'Tickethub demo venue', 'country': 'RU', 'city': 'Демо-город', 'city_en': 'Demo city',
            'address': 'Тестовый адрес, не место проведения', 'address_en': 'Test address, not a real venue', 'timezone': 'Europe/Moscow'})
        plan, _ = SeatingPlan.objects.get_or_create(venue=venue, name='Демонстрационная схема', defaults={
            'rights_source': 'Generated locally by seed_demo', 'rights_confirmed': True})
        if plan.status == 'DRAFT':
            if not plan.image:
                image = Image.new('RGB', (1000, 600), 'white')
                draw = ImageDraw.Draw(image)
                draw.rectangle((50, 50, 950, 350), outline='black', width=3)
                output = BytesIO()
                image.save(output, 'PNG')
                plan.image.save('demo-plan.png', ContentFile(output.getvalue()), save=True)
            for index in range(1, 9):
                Seat.objects.get_or_create(plan=plan, sector='A', row='1', number=str(index), defaults={
                    'x': Decimal(index) / Decimal(10), 'y': Decimal('0.8'),
                    'adjacency_group': 'A-1', 'adjacency_position': index})
            plan = publish_plan(plan.id, plan.version)
        supplier, _ = Supplier.objects.get_or_create(name='DEMO — не реальный поставщик', defaults={
            'contact': 'demo@example.invalid', 'notes': 'For local development only'})
        for slug, title, scheme in [('demo-seats', 'Демо: матч с выбором места', plan),
                                     ('demo-category', 'Демо: билеты по категории', None)]:
            start = timezone.now() + timedelta(days=14)
            event, _ = Event.objects.get_or_create(slug=slug, defaults={
                'title_ru': title, 'title_en': slug.replace('-', ' ').title(),
                'description_ru': 'Только демонстрационные данные. Это не настоящее мероприятие.',
                'description_en': 'Development fixture, not a real event.', 'category': category, 'venue': venue,
                'seating_plan': scheme, 'start_at': start, 'sale_deadline': start - timedelta(hours=2),
                'fan_id_required': False, 'refund_policy_ru': 'DEMO: условия для тестов, не юридический документ.',
                'refund_policy_en': 'DEMO: test conditions, not a legal document.',
                'refund_policy_approved': True, 'is_published': True})
            offer, _ = TicketOffer.objects.get_or_create(event=event, name_ru='Демо-категория', defaults={
                'name_en': 'Demo category', 'kind': 'SEAT' if scheme else 'CATEGORY', 'sale_price_minor': 100000})
            seats = list(plan.seats.all()) if scheme else [None] * 5
            for index, seat in enumerate(seats, 1):
                reference = f'{slug}-{index}'
                TicketUnit.objects.get_or_create(event=event, supplier=supplier, supplier_reference=reference, defaults={
                    'offer': offer, 'seat': seat, 'purchase_price_minor': 60000, 'stock_basis': 'OWNED'})
            self.stdout.write(f'{event.slug}: event_id={event.id}, offer_id={offer.id}')
        self.stdout.write('Demo seed completed. Existing inventory and prices were not reset. No staff account was created.')
