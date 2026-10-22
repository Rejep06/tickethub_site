import io
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from PIL import Image
from rest_framework.test import APITestCase
from core.errors import BusinessError
from core.validation import clean_image
from events.models import Event
from events.services import check_orderable, save_event
from tests.factories import event_fixture, stock, buyer, manager, assert_no_private_fields


class CatalogTests(APITestCase):
    def setUp(self):
        self.event, self.offer, self.units, self.selection = stock(2, seated=True)

    def test_anonymous_catalog_and_details(self):
        self.assertEqual(self.client.get('/api/v1/events/').status_code, 200)
        response = self.client.get(f'/api/v1/events/{self.event.slug}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['title_en'], 'Test event')

    def test_unpublished_event_is_not_public(self):
        Event.objects.filter(pk=self.event.id).update(is_published=False)
        self.assertEqual(self.client.get(f'/api/v1/events/{self.event.slug}/').status_code, 404)

    def test_unlisted_event_is_not_public(self):
        Event.objects.filter(pk=self.event.id).update(visibility='UNLISTED')
        self.assertEqual(self.client.get(f'/api/v1/events/{self.event.slug}/').status_code, 404)

    def test_customer_catalog_does_not_leak_internal_data(self):
        for suffix in ['offers', 'availability', 'seat-map']:
            response = self.client.get(f'/api/v1/events/{self.event.id}/{suffix}/')
            self.assertEqual(response.status_code, 200)
            assert_no_private_fields(self, response.data)
            self.assertNotIn('Private supplier', str(response.data))

    def test_category_without_scheme_has_empty_map(self):
        event, _, _, _ = stock(1)
        self.assertEqual(self.client.get(f'/api/v1/events/{event.id}/seat-map/').data['seats'], [])

    def test_optional_metadata_does_not_block_manager_intake(self):
        self.event.fan_id_required = None
        check_orderable(self.event, timezone.now())

    def test_manager_can_create_unnumbered_unit(self):
        event, offer, _, _ = stock(1)
        self.client.force_login(manager(), backend='users.backends.StaffPasswordBackend')
        response = self.client.post('/api/v1/staff/units/', {'event': str(event.id), 'offer': str(offer.id)}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(response.data['seat'])

    def test_customer_cannot_change_catalog(self):
        self.client.force_login(buyer(), backend='users.backends.CustomerOTPBackend')
        self.assertEqual(self.client.post('/api/v1/staff/events/', {}, format='json').status_code, 403)

    def test_fan_id_document_field_rejected(self):
        self.client.force_login(manager(), backend='users.backends.StaffPasswordBackend')
        response = self.client.patch(f'/api/v1/staff/events/{self.event.id}/',
            {'expected_version': self.event.version, 'passport_number': 'not-accepted'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_event_change_releases_checkout_not_order(self):
        from tickets.services import create_hold
        user = buyer()
        hold = create_hold(user, self.event.id, self.selection, 200000)
        save_event(self.event, {'expected_version': self.event.version, 'status': 'POSTPONED'}, manager())
        hold.refresh_from_db()
        self.assertEqual(hold.status, 'RELEASED')


class ImageTests(TestCase):
    def test_valid_image_is_reencoded(self):
        image = io.BytesIO()
        Image.new('RGB', (12, 10)).save(image, 'PNG')
        result = clean_image(SimpleUploadedFile('input.png', image.getvalue(), content_type='image/png'))
        self.assertTrue(result.name.endswith('.jpg'))
        self.assertEqual(Image.open(result).size, (12, 10))

    def test_non_image_is_rejected(self):
        with self.assertRaises(ValidationError):
            clean_image(SimpleUploadedFile('bad.jpg', b'not-an-image', content_type='image/jpeg'))

    def test_svg_is_rejected(self):
        with self.assertRaises(ValidationError):
            clean_image(SimpleUploadedFile('image.svg', b'<svg></svg>', content_type='image/svg+xml'))
