"""Requires Django and the isolated PostgreSQL test DB; not a production probe."""
import io
import tempfile
from unittest.mock import patch
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase, APIClient
from core.errors import BusinessError
from events.models import Category, Event
from events.services import save_event, save_category, public_events, public_categories
from tests.factories import event_fixture, manager, buyer


def png():
    stream=io.BytesIO(); Image.new('RGB',(16,10)).save(stream,'PNG')
    return SimpleUploadedFile('cover.png',stream.getvalue(),content_type='image/png')


class LaunchCatalogTests(APITestCase):
    def setUp(self):
        self.actor=manager()
        self.event=event_fixture(is_published=False)
        self.category=self.event.category
        self.client.force_login(self.actor,backend='users.backends.StaffPasswordBackend')
        self.media=tempfile.TemporaryDirectory()
        self.override=override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.media.cleanup); self.addCleanup(self.override.disable)

    def test_placeholder_publish_action_rejected(self):
        c=Category.objects.create(slug='external-review',name_ru='Черновики',name_en='Drafts',kind='OTHER',is_placeholder=True,is_active=False)
        Event.objects.filter(pk=self.event.pk).update(category=c)
        r=self.client.post(f'/api/v1/staff/events/{self.event.pk}/publish/',{'expected_version':1},format='json')
        self.assertEqual(r.status_code,400,r.data)
        self.event.refresh_from_db(); self.assertFalse(self.event.is_published)

    def test_unresolved_import_template_rejected(self):
        with self.assertRaises(ValidationError):
            save_event(self.event,{'expected_version':1,'is_published':True,'description_ru':'Купить {name} {city-in}'},self.actor)

    def test_clean_event_publishes(self):
        result=save_event(self.event,{'expected_version':1,'is_published':True},self.actor)
        self.assertTrue(result.is_published)

    def test_publication_readiness_in_staff(self):
        Event.objects.filter(pk=self.event.pk).update(description_en='{{name}}')
        r=self.client.get(f'/api/v1/staff/events/{self.event.pk}/')
        self.assertIn('description_en',r.data['publication_issues'])

    def test_model_admin_validation_is_not_only_frontend(self):
        self.event.is_published=True; self.event.description_en='Buy tickets at Portalbilet'
        with self.assertRaises(ValidationError): self.event.full_clean()

    def test_hidden_placeholder_never_leaks_in_public_results(self):
        c=Category.objects.create(slug='external-review',name_ru='Draft',name_en='Draft',kind='OTHER',is_active=True)
        Event.objects.filter(pk=self.event.pk).update(category=c,is_published=True)
        self.assertFalse(public_categories().filter(pk=c.pk).exists())
        self.assertFalse(public_events().filter(pk=self.event.pk).exists())

    def test_kind_filter_and_parent_category(self):
        child=Category.objects.create(slug='hockey',name_ru='Хоккей',name_en='Hockey',kind='SPORT',parent=self.category)
        Event.objects.filter(pk=self.event.pk).update(category=child,is_published=True)
        for suffix in ['kind=SPORT',f'category={self.category.pk}']:
            r=self.client.get('/api/v1/events/?'+suffix)
            self.assertIn(str(self.event.pk),[str(x['id']) for x in r.data['results']])
        self.assertEqual(self.client.get('/api/v1/events/?kind=CONCERT').data['count'],0)

    def test_dated_and_tba_public_events_are_both_in_default_catalog(self):
        Event.objects.filter(pk=self.event.pk).update(is_published=True)
        tba=event_fixture(start_at=None,date_tba=True,sale_deadline=None,status='POSTPONED')
        data=self.client.get('/api/v1/events/?page_size=6').data
        self.assertEqual({str(x['id']) for x in data['results']},{str(self.event.pk),str(tba.pk)})

    def test_category_upload_file_and_version(self):
        r=self.client.post(f'/api/v1/staff/categories/{self.category.pk}/image/',
            {'image':png(),'expected_version':1,'rights_source':'Own photo','rights_confirmed':True},format='multipart')
        self.assertEqual(r.status_code,200,r.data)
        self.assertEqual(r.data['version'],2); self.assertTrue(r.data['image'])

    @patch('core.validation.image_from_url')
    def test_category_upload_url_uses_shared_downloader(self,download):
        download.return_value=png()
        r=self.client.post(f'/api/v1/staff/categories/{self.category.pk}/image/',
            {'image_url':'https://images.example.com/photo.png','expected_version':1,'rights_source':'Licensed photo','rights_confirmed':True},format='json')
        self.assertEqual(r.status_code,200,r.data); download.assert_called_once()

    def test_no_rights_confirmation_rejected(self):
        r=self.client.post(f'/api/v1/staff/categories/{self.category.pk}/image/',
            {'image':png(),'expected_version':1,'rights_source':'Unknown','rights_confirmed':False},format='multipart')
        self.assertEqual(r.status_code,400)

    def test_category_stale_version_conflict(self):
        save_category(self.category,{'expected_version':1,'name_ru':'Хоккей'})
        with self.assertRaises(BusinessError): save_category(self.category,{'expected_version':1,'name_ru':'Старое имя'})

    def test_customer_cannot_upload_category_cover(self):
        self.client.force_login(buyer(),backend='users.backends.CustomerOTPBackend')
        r=self.client.post(f'/api/v1/staff/categories/{self.category.pk}/image/',{},format='json')
        self.assertEqual(r.status_code,403)

    def test_csrf_required_for_staff_upload(self):
        client=APIClient(enforce_csrf_checks=True)
        client.force_login(self.actor,backend='users.backends.StaffPasswordBackend')
        r=client.post(f'/api/v1/staff/categories/{self.category.pk}/image/',{},format='json')
        self.assertEqual(r.status_code,403)

    def test_cannot_disable_category_with_published_events(self):
        Event.objects.filter(pk=self.event.pk).update(is_published=True)
        with self.assertRaises(ValidationError): save_category(self.category,{'expected_version':1,'is_active':False})

    def test_parent_type_cannot_invalidate_child(self):
        Category.objects.create(slug='hockey',name_ru='Хоккей',name_en='Hockey',kind='SPORT',parent=self.category)
        with self.assertRaises(ValidationError): save_category(self.category,{'expected_version':1,'kind':'CONCERT'})
