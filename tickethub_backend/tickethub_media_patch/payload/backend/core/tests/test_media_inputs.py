import tempfile
from unittest.mock import patch
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase
from core.serializers import ImageUploadSerializer
from core.adminbase import ImageAdminForm, VersionedAdminForm
from core.validation import clean_image
from events.models import Event
from venues.models import SeatingPlan
from tests.factories import event_fixture, manager, buyer

SVG=b'<svg xmlns="http://www.w3.org/2000/svg" width="20000" height="15000"><path d="M0 0 L100 100" stroke="red"/></svg>'


def upload():
    return SimpleUploadedFile('background.svg',SVG,content_type='image/svg+xml')


class ImageSerializerTests(SimpleTestCase):
    def test_svg_file_is_accepted(self):
        serializer=ImageUploadSerializer(data={'image':upload(),'rights_source':'Own design','rights_confirmed':True})
        self.assertTrue(serializer.is_valid(),serializer.errors)
        self.assertTrue(serializer.validated_data['image'].name.endswith('.svg'))
        serializer.validated_data['image'].close()

    def test_two_inputs_are_rejected_before_download(self):
        with patch('core.validation.image_from_url') as get:
            serializer=ImageUploadSerializer(data={'image':upload(),'image_url':'https://cdn.pbilet.com/x.svg',
                'rights_source':'Own','rights_confirmed':True})
            self.assertFalse(serializer.is_valid())
            get.assert_not_called()

    def test_missing_source_rejected(self):
        serializer=ImageUploadSerializer(data={'rights_source':'Own','rights_confirmed':True})
        self.assertFalse(serializer.is_valid())

    def test_denied_rights_do_not_download(self):
        with patch('core.validation.image_from_url') as get:
            serializer=ImageUploadSerializer(data={'image_url':'https://cdn.pbilet.com/x.svg','rights_source':'Own','rights_confirmed':False})
            self.assertFalse(serializer.is_valid());get.assert_not_called()

    def test_url_uses_same_file_result(self):
        with patch('core.validation.image_from_url',return_value=clean_image(upload())):
            serializer=ImageUploadSerializer(data={'image_url':'https://cdn.pbilet.com/x.svg','rights_source':'Own','rights_confirmed':True})
            self.assertTrue(serializer.is_valid(),serializer.errors)
            self.assertNotIn('image_url',serializer.validated_data)
            serializer.validated_data['image'].close()

    def test_non_media_admin_form_has_no_image_inputs(self):
        self.assertNotIn('image',VersionedAdminForm.base_fields)
        self.assertNotIn('image_url',VersionedAdminForm.base_fields)


class MediaAPITests(APITestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings_override=override_settings(MEDIA_ROOT=self.directory.name)
        self.settings_override.enable();self.addCleanup(self.settings_override.disable)
        self.event=event_fixture(is_published=False)
        self.plan=SeatingPlan.objects.create(venue=self.event.venue,name='SVG plan')
        self.actor=manager()
        self.client.force_login(self.actor,backend='users.backends.StaffPasswordBackend')

    def test_event_accepts_svg_upload(self):
        response=self.client.post(f'/api/v1/staff/events/{self.event.pk}/image/',{
            'image':upload(),'rights_source':'Own','rights_confirmed':True,'expected_version':self.event.version},format='multipart')
        self.assertEqual(response.status_code,200,response.data)
        self.event.refresh_from_db();self.assertTrue(self.event.image.name.endswith('.svg'))

    def test_plan_accepts_url_json(self):
        with patch('core.validation.image_from_url',return_value=clean_image(upload())) as download:
            response=self.client.post(f'/api/v1/staff/plans/{self.plan.pk}/image/',{
                'image_url':'https://cdn.pbilet.com/x.svg','rights_source':'Own','rights_confirmed':True,
                'expected_version':self.plan.version},format='json')
        self.assertEqual(response.status_code,200,response.data)
        download.assert_called_once()
        self.plan.refresh_from_db();self.assertTrue(self.plan.image.name.endswith('.svg'))

    def test_customer_cannot_trigger_download(self):
        self.client.force_login(buyer(),backend='users.backends.CustomerOTPBackend')
        with patch('core.validation.image_from_url') as download:
            result=self.client.post(f'/api/v1/staff/events/{self.event.pk}/image/',{
                'image_url':'https://cdn.pbilet.com/x.svg','rights_source':'Own','rights_confirmed':True,
                'expected_version':1},format='json')
        self.assertEqual(result.status_code,403);download.assert_not_called()

    def test_admin_url_input_is_converted_to_local_file(self):
        Form=forms.modelform_factory(Event,form=ImageAdminForm,
            fields=['image','image_url','image_rights_source','image_rights_confirmed'])
        with patch('core.adminbase.image_from_url',return_value=clean_image(upload())):
            form=Form(instance=self.event,data={'image_url':'https://cdn.pbilet.com/x.svg',
                'image_rights_source':'Own','image_rights_confirmed':True})
            self.assertTrue(form.is_valid(),form.errors)
            self.assertNotIn('image_url',form.cleaned_data)
            form.cleaned_data['image'].close()

    def test_unknown_schema_point_does_not_imply_image_rights(self):
        self.assertFalse(self.plan.rights_confirmed)
