"""Explicit PostgreSQL test fixtures, not production seeds or gateway mocks."""
import uuid
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from users.models import User
from venues.models import Venue, SeatingPlan, Seat
from events.models import Category, Event
from tickets.models import TicketOffer, TicketUnit, Supplier
from tickets.services import create_hold
from orders.services import create_order_from_hold, start_processing_order, confirm_order

PASSWORD = 'Local-test-password!2026!'


def buyer(email=None):
    return User.objects.create_user(email or f'buyer-{uuid.uuid4().hex}@example.com', name='Test customer',
                                    phone='+447911123456', email_verified_at=timezone.now())


def manager(email=None, role='MANAGER'):
    return User.objects.create_user(email or f'manager-{uuid.uuid4().hex}@example.com', password=PASSWORD, name='Manager', staff_role=role)


def event_fixture(**overrides):
    category, _ = Category.objects.get_or_create(slug='test-sport', defaults={'name_ru': 'Спорт', 'name_en': 'Sport', 'kind': 'SPORT'})
    venue = Venue.objects.create(name_ru='Площадка', name_en='Venue', country='GB', city='London', address='Test', timezone='Europe/London')
    start = timezone.now() + timedelta(days=14)
    data = {'slug': uuid.uuid4().hex, 'title_ru': 'Тестовое событие', 'title_en': 'Test event', 'description_ru': 'Fixture only',
            'description_en': 'Fixture only', 'category': category, 'venue': venue, 'start_at': start,
            'sale_deadline': start - timedelta(hours=2), 'fan_id_required': False, 'refund_policy_approved': True,
            'refund_policy_ru': 'Test fixture conditions', 'refund_policy_en': 'Test fixture conditions', 'is_published': True}
    data.update(overrides)
    return Event.objects.create(**data)


def stock(count=1, *, event=None, seated=False, cost=60000, price=100000):
    event = event or event_fixture()
    seats = [None] * count
    if seated:
        plan = SeatingPlan.objects.create(venue=event.venue, name='Plan', image='plans/test.png', rights_confirmed=True, rights_source='test fixture')
        seats = [Seat.objects.create(plan=plan, sector='A', row='1', number=str(i+1), x=Decimal('0.5'), y=Decimal('0.5'),
                                     adjacency_group='A1', adjacency_position=i) for i in range(count)]
        plan.status = 'PUBLISHED'
        plan.save()
        event.seating_plan = plan
        event.save()
    offer = TicketOffer.objects.create(event=event, name_ru='Билет', name_en='Ticket', kind='SEAT' if seated else 'CATEGORY', sale_price_minor=price)
    supplier = Supplier.objects.create(name='Private supplier', notes='Secret supplier notes')
    units = [TicketUnit.objects.create(event=event, offer=offer, seat=seat, supplier=supplier, purchase_price_minor=cost,
                                      internal_notes='Internal secret') for seat in seats]
    selection = {'mode': 'SEATS', 'seat_ids': [s.id for s in seats]} if seated else {'mode': 'CATEGORY', 'offer_id': offer.id, 'quantity': count}
    return event, offer, units, selection


def order_fixture(count=1, *, user=None, cost=60000, seated=False):
    user = user or buyer()
    event, offer, units, selection = stock(count, cost=cost, seated=seated)
    hold = create_hold(user, event.id, selection, count * offer.sale_price_minor)
    order, _ = create_order_from_hold(user, {'hold_id': hold.id, 'accepted_documents': {}}, uuid.uuid4())
    return order, units


def confirmed_order(count=1, *, actor=None, cost=60000):
    actor = actor or manager()
    order, units = order_fixture(count, cost=cost)
    order = start_processing_order(order.id, actor, order.version)
    order = confirm_order(order.id, actor, order.version)
    return order, units, actor


def payment_data(order, amount=None, kind='PAYMENT'):
    order.refresh_from_db()
    return {'expected_version': order.version, 'kind': kind, 'amount_minor': amount or order.total_minor,
            'occurred_at': timezone.now(), 'method': 'BANK_TRANSFER', 'reference': uuid.uuid4().hex}


def assert_no_private_fields(testcase, value):
    forbidden = {'purchase_price_minor', 'supplier', 'supplier_id', 'profit', 'profit_minor', 'internal_notes',
                 'internal_note', 'manager_notes', 'financial_entries', 'ticket_unit', 'request_hash'}
    if isinstance(value, dict):
        testcase.assertFalse(forbidden.intersection(value), forbidden.intersection(value))
        for item in value.values():
            assert_no_private_fields(testcase, item)
    elif isinstance(value, list):
        for item in value:
            assert_no_private_fields(testcase, item)
