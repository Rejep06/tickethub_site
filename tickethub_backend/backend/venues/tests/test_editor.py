from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from core.errors import BusinessError
from venues.models import SeatingPlan, Seat
from venues.services import publish_plan, clone_plan
from venues.editor_services import edit_seats
from tests.factories import event_fixture, manager, buyer, stock, PASSWORD


def seat(number='1', **changes):
    return {'sector': 'A', 'row': '1', 'number': number, 'x': '.2', 'y': '.3', **changes}


class EditorTests(TestCase):
    def setUp(self):
        self.event = event_fixture()
        self.plan = SeatingPlan.objects.create(venue=self.event.venue, name='Neutral')

    def test_create_batch(self):
        result = edit_seats(self.plan.pk, expected_version=1, create=[seat(), seat('2')])
        self.assertEqual(result['created'], 2)
        self.assertEqual(result['version'], 2)
        self.assertEqual(self.plan.seats.count(), 2)

    def test_bad_coordinate_rolls_back_entire_batch(self):
        with self.assertRaises(BusinessError):
            edit_seats(self.plan.pk, expected_version=1, create=[seat(), seat('2', x='2')])
        self.assertEqual(self.plan.seats.count(), 0)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.version, 1)

    def test_duplicate_labels_roll_back(self):
        with self.assertRaises(BusinessError):
            edit_seats(self.plan.pk, expected_version=1, create=[seat(), seat()])
        self.assertFalse(self.plan.seats.exists())

    def test_stale_version_rejected(self):
        edit_seats(self.plan.pk, expected_version=1, create=[seat()])
        with self.assertRaises(BusinessError) as error:
            edit_seats(self.plan.pk, expected_version=1, create=[seat('2')])
        self.assertEqual(error.exception.business_code, 'VERSION_CONFLICT')

    def test_swap_numbers(self):
        result = edit_seats(self.plan.pk, expected_version=1, create=[seat(), seat('2')])
        a,b=result['created_ids']
        edit_seats(self.plan.pk, expected_version=2, update=[{'id':a,'number':'2'},{'id':b,'number':'1'}])
        self.assertEqual(Seat.objects.get(pk=a).number,'2')
        self.assertEqual(Seat.objects.get(pk=b).number,'1')

    def test_delete_releases_label_for_new_seat(self):
        result=edit_seats(self.plan.pk, expected_version=1, create=[seat()])
        edit_seats(self.plan.pk, expected_version=2, delete=result['created_ids'], create=[seat()])
        self.assertEqual(self.plan.seats.count(),1)

    def test_no_cross_plan_update(self):
        other=SeatingPlan.objects.create(venue=self.event.venue,name='Other')
        outsider=Seat.objects.create(plan=other,**seat())
        with self.assertRaises(BusinessError):
            edit_seats(self.plan.pk,expected_version=1,update=[{'id':str(outsider.pk),'number':'2'}])
        outsider.refresh_from_db()
        self.assertEqual(outsider.number,'1')

    def test_no_published_plan_edit(self):
        edit_seats(self.plan.pk,expected_version=1,create=[seat()])
        publish_plan(self.plan.pk,2)
        with self.assertRaises(BusinessError):edit_seats(self.plan.pk,expected_version=3,create=[seat('2')])

    def test_publish_without_background(self):
        edit_seats(self.plan.pk,expected_version=1,create=[seat()])
        result=publish_plan(self.plan.pk,2)
        self.assertEqual(result.status,'PUBLISHED')
        self.assertFalse(result.image)

    def test_no_invented_image_rights(self):
        edit_seats(self.plan.pk,expected_version=1,create=[seat()])
        self.plan.image='plans/test.png'
        self.plan.save(update_fields=['image'])
        with self.assertRaises(BusinessError):publish_plan(self.plan.pk,2)

    def test_clone_keeps_original_unchanged(self):
        edit_seats(self.plan.pk,expected_version=1,create=[seat()])
        publish_plan(self.plan.pk,2)
        copy=clone_plan(self.plan.pk)
        edit_seats(copy.pk,expected_version=1,create=[seat('2')])
        self.assertEqual(self.plan.seats.count(),1)
        self.assertEqual(copy.seats.count(),2)

    def test_published_stock_not_deleted(self):
        event,offer,units,_=stock(1,seated=True)
        with self.assertRaises(BusinessError):
            edit_seats(event.seating_plan_id,expected_version=event.seating_plan.version,delete=[str(units[0].seat_id)])
        self.assertTrue(Seat.objects.filter(pk=units[0].seat_id).exists())


class EditorAPITests(APITestCase):
    def setUp(self):
        self.staff=manager()
        self.event=event_fixture()
        self.plan=SeatingPlan.objects.create(venue=self.event.venue,name='Editor test')
        self.path=f'/api/v1/staff/plans/{self.plan.pk}/'

    def test_customer_cannot_edit(self):
        self.client.force_login(buyer(),backend='users.backends.CustomerOTPBackend')
        response=self.client.post(self.path+'bulk-edit/',{'expected_version':1,'create':[seat()]},format='json')
        self.assertEqual(response.status_code,403)

    def test_staff_preview_does_not_write(self):
        self.client.force_login(self.staff,backend='users.backends.StaffPasswordBackend')
        response=self.client.post(self.path+'block-preview/',{'sector':'A','rows':2,'seats_per_row':3},format='json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['count'],6)
        self.assertFalse(self.plan.seats.exists())

    def test_staff_batch_endpoint(self):
        self.client.force_login(self.staff,backend='users.backends.StaffPasswordBackend')
        response=self.client.post(self.path+'bulk-edit/',{'expected_version':1,'create':[seat()]},format='json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.plan.seats.count(),1)

    def test_admin_editor_page(self):
        self.client.force_login(self.staff,backend='users.backends.StaffPasswordBackend')
        response=self.client.get(f'/ops/venues/seatingplan/{self.plan.pk}/editor/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'le-canvas')
