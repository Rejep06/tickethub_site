from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from core.errors import BusinessError
from venues.models import SeatingPlan, Seat
from venues.services import save_seat, publish_plan, clone_plan, create_row
from tests.factories import event_fixture, stock


class PlanTests(TestCase):
    def setUp(self):
        self.event = event_fixture()
        self.plan = SeatingPlan.objects.create(venue=self.event.venue, name='Plan', image='plans/test.png',
                                               rights_confirmed=True, rights_source='Fixture')

    def test_row_coordinates_are_normalized(self):
        seats = create_row(self.plan.id, 'A', '1', ['1', '2', '3'], Decimal('0.1'), Decimal('0.2'),
                           Decimal('0.9'), Decimal('0.2'), 'A1')
        self.assertEqual(seats[1].x, Decimal('0.5'))
        self.assertEqual(seats[2].adjacency_position, 2)

    def test_published_plan_seats_cannot_be_edited(self):
        seat = save_seat(None, {'plan': self.plan, 'sector': 'A', 'row': '1', 'number': '1', 'x': Decimal('0.5'), 'y': Decimal('0.5')})
        self.plan.refresh_from_db()
        publish_plan(self.plan.id, self.plan.version)
        with self.assertRaises(BusinessError):
            save_seat(seat, {'number': '2'})

    def test_clone_is_separate_editable_version(self):
        save_seat(None, {'plan': self.plan, 'sector': 'A', 'row': '1', 'number': '1', 'x': Decimal('0.5'), 'y': Decimal('0.5')})
        copied = clone_plan(self.plan.id)
        self.assertNotEqual(copied.id, self.plan.id)
        self.assertEqual(copied.status, 'DRAFT')
        self.assertEqual(copied.seats.count(), 1)

    def test_seat_coordinate_database_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Seat.objects.create(plan=self.plan, sector='A', row='1', number='1', x=2, y=0)

    def test_event_seat_database_unique_constraint(self):
        from tickets.models import TicketUnit
        event, offer, units, _ = stock(1, seated=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            TicketUnit.objects.create(event=event, offer=offer, seat=units[0].seat)

    def test_same_number_can_exist_in_different_events(self):
        from tickets.models import TicketUnit
        from tickets.models import TicketOffer
        event, offer, units, _ = stock(1, seated=True)
        other = event_fixture(venue=event.venue, seating_plan=event.seating_plan)
        other_offer = TicketOffer.objects.create(event=other, name_ru='Билет', name_en='Ticket', kind='SEAT', sale_price_minor=1000)
        unit = TicketUnit.objects.create(event=other, offer=other_offer, seat=units[0].seat)
        self.assertIsNotNone(unit.id)
