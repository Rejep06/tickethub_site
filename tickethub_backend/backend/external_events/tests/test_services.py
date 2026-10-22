"""Local ORM/service fixtures only; these are NOT claimed to be PortalBilet JSON.

Provider payload integration tests require a real capture and are not fabricated.
"""
from datetime import timedelta
from threading import Event as ThreadEvent, Thread
from unittest.mock import patch
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APITestCase
from core.errors import BusinessError
from events.models import Event
from venues.models import Venue
from tickets.models import TicketUnit
from external_events.models import ExternalEvent, ExternalDate
from external_events.services import apply_metadata, source_lock
from tests.factories import manager, buyer


class LocalImportTests(TestCase):
    def setUp(self):
        self.actor=manager(role='ADMIN')
        self.source=ExternalEvent.objects.create(external_event_id='90001',event_source_id='90002',
            external_place_id='90003',external_layout_id='90004',url='https://portalbilet.ru/test-city/test-event',title='Internal test')
        self.metadata={'title':'Внутренний тест','description':'Локальная проверка','place_name':'Тестовая площадка',
                       'address':'Тестовый адрес','city':'Тестовый город','place_metadata':{'country':'RU'}}
        self.date=timezone.now()+timedelta(days=20)

    def apply(self,ids=('90101',),authoritative=True):
        # Date parsing is isolated here: this tests our database contract, not an unobserved API shape.
        with patch('external_events.services.parse_date',return_value=self.date):
            return apply_metadata(self.source,self.metadata,[{'id':i} for i in ids],authoritative,self.actor,[])

    def test_same_source_twice_no_duplicate(self):
        self.apply();self.apply()
        self.assertEqual(Event.objects.count(),1)
        self.assertEqual(Venue.objects.count(),1)
        self.assertEqual(ExternalDate.objects.count(),1)

    def test_different_dates_use_existing_event_model(self):
        self.apply(('90101','90102'))
        self.assertEqual(Event.objects.count(),2)
        self.assertEqual(Venue.objects.count(),1)
        self.assertEqual(self.source.dates.count(),2)

    def test_no_ticketunit_created(self):
        self.apply()
        self.assertEqual(TicketUnit.objects.count(),0)
        self.assertFalse(Event.objects.get().is_published)

    def test_metadata_sync_preserves_local_title(self):
        self.apply()
        event=Event.objects.get()
        event.title_ru='Название менеджера';event.version+=1;event.save()
        self.metadata['title']='Новое название источника'
        self.apply()
        event.refresh_from_db()
        self.assertEqual(event.title_ru,'Название менеджера')

    def test_source_date_disappeared_not_deleted(self):
        self.apply(('90101','90102'))
        self.apply(('90101',))
        self.assertEqual(Event.objects.count(),2)
        self.assertFalse(self.source.dates.get(external_date_id='90102').source_active)

    def test_fallback_does_not_disable_dates(self):
        self.apply(('90101','90102'))
        self.apply(('90101',),authoritative=False)
        self.assertTrue(self.source.dates.get(external_date_id='90102').source_active)

    def test_unknown_timezone_keeps_tba_draft(self):
        with patch('external_events.services.parse_date',return_value=None):
            warnings=[]
            apply_metadata(self.source,self.metadata,[{'id':'90101'}],True,self.actor,warnings)
        event=Event.objects.get()
        self.assertIsNone(event.start_at)
        self.assertTrue(event.date_tba)
        self.assertTrue(any(w['code']=='DATE_REQUIRES_REVIEW' for w in warnings))


class ImportPermissionTests(APITestCase):
    def test_customer_cannot_import(self):
        self.client.force_login(buyer(),backend='users.backends.CustomerOTPBackend')
        response=self.client.post('/api/v1/staff/external-events/import/',{'url':'https://portalbilet.ru/test/test'},format='json')
        self.assertEqual(response.status_code,403)

    def test_manager_cannot_import(self):
        self.client.force_login(manager(),backend='users.backends.StaffPasswordBackend')
        response=self.client.post('/api/v1/staff/external-events/import/',{'url':'https://portalbilet.ru/test/test'},format='json')
        self.assertEqual(response.status_code,403)

    def test_admin_rejects_unsafe_url_without_request(self):
        self.client.force_login(manager(role='ADMIN'),backend='users.backends.StaffPasswordBackend')
        with patch('external_events.http.JSONClient.get_json') as fetch:
            response=self.client.post('/api/v1/staff/external-events/import/',{'url':'https://localhost/private'},format='json')
        self.assertEqual(response.status_code,400)
        fetch.assert_not_called()

    def test_live_provider_sale_not_exposed(self):
        self.client.force_login(manager(role='ADMIN'),backend='users.backends.StaffPasswordBackend')
        response=self.client.post('/api/v1/staff/external-events/import/',
            {'url':'https://portalbilet.ru/test/test','mode':'LIVE_PROVIDER_SALE'},format='json')
        self.assertEqual(response.status_code,400)

    def test_admin_import_page(self):
        self.client.force_login(manager(role='ADMIN'),backend='users.backends.StaffPasswordBackend')
        response=self.client.get('/ops/external_events/externalevent/import-url/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'pb-url')


class ImportConcurrencyTests(TransactionTestCase):
    def test_only_one_connection_can_sync_a_source(self):
        self.assertEqual(connection.vendor,'postgresql','This is a PostgreSQL test, not a SQLite substitute.')
        entered,release,second_finished=ThreadEvent(),ThreadEvent(),ThreadEvent()
        results=[]
        def first():
            close_old_connections()
            try:
                with source_lock('concurrency-test'):
                    results.append('first acquired');entered.set();release.wait(10)
            except Exception as exc:results.append(repr(exc));entered.set()
            finally:connection.close()
        def second():
            close_old_connections()
            try:
                entered.wait(10)
                with source_lock('concurrency-test'):results.append('second acquired')
            except BusinessError as exc:results.append(exc.business_code)
            except Exception as exc:results.append(repr(exc))
            finally:connection.close();second_finished.set()
        threads=[Thread(target=first),Thread(target=second)]
        for thread in threads:thread.start()
        second_finished.wait(10);release.set()
        for thread in threads:thread.join(timeout=10)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertCountEqual(results,['first acquired','IMPORT_IN_PROGRESS'])


class VerifiedInventoryDatabaseTests(TestCase):
    def setUp(self):
        import json
        from pathlib import Path
        self.actor = manager(role='ADMIN')
        self.source = ExternalEvent.objects.create(
            external_event_id='114696', event_source_id='10679', external_place_id='56', external_layout_id='3513',
            url='https://portalbilet.ru/sochi/match-khk-sochi-spartak-kontinentalnaia-khokkeinaia-liga-2', title='Сочи - Спартак')
        self.metadata = {'title':'Сочи - Спартак','description':'Импорт','place_name':'Дворец спорта «Большой»',
                         'address':'Россия, Краснодарский край, Сочи, Олимпийский парк','city':'Сочи',
                         'country_name':'Россия','place_metadata':{}}
        self.when = timezone.now() + timedelta(days=20)
        path = Path(__file__).with_name('fixtures') / 'portalbilet_verified_sample.json'
        self.fixture = json.loads(path.read_text(encoding='utf-8'))
        with patch('external_events.services.parse_date', return_value=self.when):
            apply_metadata(self.source, self.metadata, [{'id':'402328'}], True, self.actor, [])
        self.source.refresh_from_db()

    def test_verified_payload_creates_plan_seats_and_external_inventory_not_ticketunit(self):
        from external_events.normalization import normalize_layout, normalize_assigned_tickets
        from external_events.services import apply_layout, apply_assigned_inventory
        from external_events.models import ExternalSeatInventory
        from venues.models import SeatingPlan, Seat
        layout = normalize_layout(self.fixture['layout'], expected_layout_id='3513')
        decoded = normalize_assigned_tickets(self.fixture['tickets'], event_date_id='402328', layout=layout)
        warnings=[]
        plan, created, attached = apply_layout(self.source, layout, decoded['sectors'], self.actor, warnings)
        binding=self.source.dates.get(external_date_id='402328')
        counts=apply_assigned_inventory(binding, plan, decoded, warnings)
        self.assertTrue(created)
        self.assertEqual(attached, 1)
        self.assertEqual(counts['seats_created'], 0)  # All points were created by apply_layout().
        self.assertEqual(counts['seats_updated'], 5)
        self.assertEqual(Seat.objects.filter(plan=plan).count(), len(layout['points']))
        self.assertEqual(Seat.objects.filter(plan=plan, sector='', row='', number='').count(), len(layout['points']) - 5)
        self.assertEqual(ExternalSeatInventory.objects.filter(external_date=binding).count(), 5)
        self.assertEqual(TicketUnit.objects.count(), 0)
        binding.event.refresh_from_db()
        self.assertEqual(binding.event.seating_plan_id, plan.id)
        self.assertFalse(binding.event.is_published)

    def test_provider_sync_preserves_local_enabled_for_sale(self):
        from external_events.normalization import normalize_layout, normalize_assigned_tickets
        from external_events.services import apply_layout, apply_assigned_inventory
        from external_events.models import ExternalSeatInventory
        layout=normalize_layout(self.fixture['layout'],expected_layout_id='3513')
        decoded=normalize_assigned_tickets(self.fixture['tickets'],event_date_id='402328',layout=layout)
        plan,_,_=apply_layout(self.source,layout,decoded['sectors'],self.actor,[])
        binding=self.source.dates.get(external_date_id='402328')
        apply_assigned_inventory(binding,plan,decoded,[])
        target = decoded['seats'][0]
        item=ExternalSeatInventory.objects.get(external_date=binding, seat__sector=target['sector'],
                                               seat__row=target['row'], seat__number=target['number'])
        item.enabled_for_sale=True;item.save(update_fields=['enabled_for_sale','updated_at'])
        decoded['seats'][0]['source_price_minor'] += 10000
        apply_assigned_inventory(binding,plan,decoded,[])
        item.refresh_from_db()
        self.assertTrue(item.enabled_for_sale)
        self.assertEqual(item.source_price_minor,140000)
