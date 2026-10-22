"""Regression tests use the full coordinates file from the user's PortalBilet capture."""
import json
from pathlib import Path
from django.test import TestCase
from django.db import transaction
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from core.errors import BusinessError
from events.models import Event
from tickets.models import TicketUnit, TicketOffer
from venues.models import Seat, SeatingPlan
from venues.services import clone_plan
from venues.editor_services import edit_seats
from venues.import_geometry import materialize_geometry, point_key
from external_events.normalization import normalize_layout, normalize_assigned_tickets
from external_events.services import apply_layout, apply_assigned_inventory


class FullGeometryTests(TestCase):
    def setUp(self):
        from .test_services import VerifiedInventoryDatabaseTests
        VerifiedInventoryDatabaseTests.setUp(self)
        path=Path(__file__).with_name('fixtures')/'full_coordinates.json'
        self.layout=normalize_layout(json.loads(path.read_text()),expected_layout_id='3513')
        # Five labelled tickets are real samples; coordinates contains all 12,075 points.
        self.decoded=normalize_assigned_tickets(self.fixture['tickets'], event_date_id='402328',
            layout=normalize_layout(self.fixture['layout'],expected_layout_id='3513'))
        self.plan,_,_=apply_layout(self.source,self.layout,[],self.actor,[])
        self.binding=self.source.dates.get(external_date_id='402328')

    def test_all_points_exist_before_any_ticket_request(self):
        self.assertEqual(self.plan.seats.count(),12075)
        self.assertEqual(self.plan.seats.filter(sector='',row='',number='').count(),12075)
        self.assertFalse(TicketUnit.objects.exists())
        self.assertFalse(self.binding.seat_inventory.exists())

    def test_labels_enrich_same_seat_ids(self):
        target=self.decoded['seats'][0]
        seat=self.plan.seats.get(external_point_key=point_key(target['x'],target['y']))
        old_id=seat.pk
        apply_assigned_inventory(self.binding,self.plan,self.decoded,[])
        seat.refresh_from_db()
        self.assertEqual(seat.pk,old_id)
        self.assertEqual((seat.sector,seat.row,seat.number),(target['sector'],target['row'],target['number']))
        self.assertEqual(self.plan.seats.count(),12075)
        self.assertEqual(self.plan.seats.filter(sector='',row='',number='').count(),12070)

    def test_second_geometry_sync_does_not_duplicate(self):
        ids=set(self.plan.seats.values_list('id',flat=True))
        apply_layout(self.source,self.layout,[],self.actor,[])
        self.assertEqual(set(self.plan.seats.values_list('id',flat=True)),ids)

    def test_disappeared_ticket_does_not_delete_physical_seat_or_selection(self):
        apply_assigned_inventory(self.binding,self.plan,self.decoded,[])
        target=self.decoded['seats'][0]
        item=self.binding.seat_inventory.get(seat__external_point_key=point_key(target['x'],target['y']))
        item.enabled_for_sale=True
        item.save(update_fields=['enabled_for_sale'])
        apply_assigned_inventory(self.binding,self.plan,{'seats':[],'sectors':[]},[])
        item.refresh_from_db()
        self.assertFalse(item.source_available)
        self.assertTrue(item.enabled_for_sale)
        self.assertTrue(item.seat.labels_known)
        self.assertEqual(self.plan.seats.count(),12075)

    def test_conflicting_label_does_not_reassign_point(self):
        apply_assigned_inventory(self.binding,self.plan,self.decoded,[])
        target=self.decoded['seats'][0]
        changed={**target,'number':'DIFFERENT'}
        warnings=[]
        apply_assigned_inventory(self.binding,self.plan,{'seats':[changed]},warnings)
        self.assertTrue(any(w['code']=='SEAT_IDENTITY_CONFLICT' for w in warnings))
        self.assertFalse(self.plan.seats.filter(number='DIFFERENT').exists())

    def test_unknown_point_cannot_be_sold(self):
        event=self.binding.event;event.refresh_from_db()
        offer=TicketOffer.objects.create(event=event,name_ru='A',name_en='A',kind='SEAT',sale_price_minor=10000)
        seat=self.plan.seats.first()
        with self.assertRaises(ValidationError):
            TicketUnit(event=event,offer=offer,seat=seat).full_clean()

    def test_public_map_contains_unknown_places_but_no_sellable_stock(self):
        from events.models import Category

        event = self.binding.event

        Event.objects.filter(pk=event.pk).update(
            is_published=True,
            fan_id_required=False
        )

        SeatingPlan.objects.filter(
            pk=self.plan.pk
        ).update(status='PUBLISHED')

        client = APIClient()
        url = f'/api/v1/events/{event.pk}/seat-map/'

        # Импортированное событие со служебной категорией
        # не должно отображаться публично.
        self.assertEqual(client.get(url).status_code, 404)

        # Назначаем настоящую активную категорию.
        category = Category.objects.create(
            slug='test-hockey-public-map',
            name_ru='Хоккей',
            name_en='Hockey',
            kind='SPORT',
            is_active=True,
        )

        Event.objects.filter(pk=event.pk).update(
            category=category
        )

        result = client.get(url)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.data['seats']), 12075)

        self.assertFalse(
            any(s['labels_known'] for s in result.data['seats'])
        )

        self.assertEqual(
            client.get(
                f'/api/v1/events/{event.pk}/availability/'
            ).data['available_seats'],
            []
        )
    
    def test_backfill_links_legacy_seat_without_replacing_its_id(self):
        other=SeatingPlan.objects.create(venue=self.plan.venue,name='Legacy',external_geometry=[[.1,.2]])
        existing=Seat.objects.create(plan=other,sector='A',row='1',number='2',x='.1',y='.2')
        with transaction.atomic():
            locked=SeatingPlan.objects.select_for_update().get(pk=other.pk)
            self.assertEqual(materialize_geometry(locked),0)
        existing.refresh_from_db()
        self.assertEqual(existing.external_point_key,point_key(.1,.2))
        self.assertEqual(other.seats.count(),1)

    def test_batch_edits_do_not_treat_empty_labels_as_duplicates(self):
        self.plan.refresh_from_db()
        result=edit_seats(self.plan.pk,expected_version=self.plan.version,create=[{
            'sector':'Manual','row':'1','number':'1','x':'.5','y':'.5'}])
        self.assertEqual(result['created'],1)
        self.assertEqual(self.plan.seats.count(),12076)

    def test_source_coordinates_are_protected_from_manual_edits(self):
        self.plan.refresh_from_db()
        seat=self.plan.seats.first()
        with self.assertRaises(BusinessError):
            edit_seats(self.plan.pk,expected_version=self.plan.version,delete=[str(seat.pk)])

    def test_cloning_preserves_all_points_and_detaches_labelled_seats(self):
        apply_assigned_inventory(self.binding,self.plan,self.decoded,[])
        copy=clone_plan(self.plan.pk)
        self.assertEqual(copy.seats.count(),12075)
        self.assertEqual(copy.external_provider,'')
        self.assertEqual(copy.seats.filter(external_point_key='').count(),5)

    def test_published_label_enrichment_does_not_move_coordinates(self):
        SeatingPlan.objects.filter(pk=self.plan.pk).update(status='PUBLISHED')
        target=self.decoded['seats'][0]
        old=self.plan.seats.get(external_point_key=point_key(target['x'],target['y']))
        apply_assigned_inventory(self.binding,self.plan,self.decoded,[])
        new=Seat.objects.get(pk=old.pk)
        self.assertTrue(new.labels_known)
        self.assertEqual((new.x,new.y),(old.x,old.y))
