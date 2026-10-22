import json
from copy import deepcopy
from pathlib import Path
from django.test import SimpleTestCase
from external_events.http import ProviderError
from external_events.normalization import (
    normalize_layout, normalize_assigned_tickets, normalize_standing_tickets,
)


FIXTURE = Path(__file__).with_name('fixtures') / 'portalbilet_verified_sample.json'


def fixture():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


class VerifiedPortalBiletPayloadTests(SimpleTestCase):
    def test_real_layout_and_ticket_coordinates_join(self):
        data = fixture()
        layout = normalize_layout(data['layout'], expected_layout_id='3513')
        tickets = normalize_assigned_tickets(
            data['tickets'], event_date_id=data['event_date_id'], layout=layout,
        )
        self.assertEqual(len(layout['points']), 409)
        self.assertEqual(len(tickets['seats']), 5)
        self.assertEqual(tickets['seats'][0]['sector'], 'Сектор 112')
        self.assertEqual(tickets['seats'][0]['row'], '5')
        self.assertEqual(tickets['seats'][0]['number'], '11')
        self.assertEqual(tickets['seats'][0]['source_price_minor'], 130000)
        self.assertEqual(tickets['seats'][0]['currency'], 'RUB')

    def test_ticket_coordinate_must_exist_in_layout(self):
        data = fixture()
        layout = normalize_layout(data['layout'], expected_layout_id='3513')
        broken = deepcopy(data['tickets'])
        broken['sectors'][0]['r'][0]['s'][0]['x'] = 1
        broken['sectors'][0]['r'][0]['s'][0]['y'] = 1
        with self.assertRaisesRegex(ProviderError, 'отсутствует в coordinates'):
            normalize_assigned_tickets(broken, event_date_id=data['event_date_id'], layout=layout)

    def test_provider_ticket_id_is_not_used_as_physical_seat_identity(self):
        data = fixture()
        layout = normalize_layout(data['layout'], expected_layout_id='3513')
        tickets = normalize_assigned_tickets(data['tickets'], event_date_id=data['event_date_id'], layout=layout)
        seat = tickets['seats'][0]
        self.assertTrue(seat['external_ticket_id'])
        self.assertEqual((seat['sector'], seat['row'], seat['number']), ('Сектор 112', '5', '11'))

    def test_standing_payload_remains_separate_inventory(self):
        data = fixture()
        rows = normalize_standing_tickets(data['standing'], event_date_id=data['standing_event_date_id'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['name'], 'Парковка')
        self.assertEqual(rows[0]['available_count'], 200)
        self.assertEqual(rows[0]['source_price_minor'], 50000)
