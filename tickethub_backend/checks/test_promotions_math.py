"""Actual pure pricing/time policy tests; does not claim to exercise a database."""
import importlib.util
from pathlib import Path
import random
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
import unittest

BASE = Path(__file__).resolve().parents[1] / 'backend'
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, BASE / path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module
math = load('promo_math', 'promotions/calculations.py')
policy = load('checkout_policy', 'events/checkout_policy.py')

class PromoMathTests(unittest.TestCase):
    def test_normalize(self): self.assertEqual(math.normalize_code(' match10 '), 'MATCH10')
    def test_bad_codes(self):
        for value in [None,123,'XX','КОД10','two codes','ABC!','A'*41,'-CODE']:
            with self.subTest(value=value), self.assertRaises(ValueError): math.normalize_code(value)
    def test_percent(self): self.assertEqual(math.calculate_discount(250000,'PERCENT',10),25000)
    def test_fraction_rounds_once_down(self): self.assertEqual(math.calculate_discount(10009,'PERCENT',15),1501)
    def test_fixed(self): self.assertEqual(math.calculate_discount(250000,'FIXED',50000),50000)
    def test_cap(self): self.assertEqual(math.calculate_discount(1000000,'PERCENT',20,maximum=50000),50000)
    def test_minimum_inclusive(self): self.assertEqual(math.calculate_discount(200000,'PERCENT',10,minimum=200000),20000)
    def test_below_minimum(self):
        with self.assertRaisesRegex(ValueError,'PROMO_MINIMUM'): math.calculate_discount(199999,'PERCENT',10,minimum=200000)
    def test_free_orders_rejected(self):
        for kind,value in [('FIXED',10000),('FIXED',10001),('PERCENT',100)]:
            with self.subTest(kind=kind,value=value), self.assertRaises(ValueError): math.calculate_discount(10000,kind,value)
    def test_bool_fraction_negative_rejected(self):
        for subtotal in [True, 1.2, -1, 0, math.MAX_MONEY+1]:
            with self.subTest(subtotal=subtotal), self.assertRaises(ValueError): math.calculate_discount(subtotal,'PERCENT',10)
    def test_zero_percent_rounding_rejected(self):
        with self.assertRaisesRegex(ValueError,'PROMO_AMOUNT'): math.calculate_discount(1,'PERCENT',1)
    def test_allocation(self): self.assertEqual(math.allocate_discount([100,200,300],120),[20,40,60])
    def test_allocation_remainder_stable(self): self.assertEqual(math.allocate_discount([100,100,100],2),[1,1,0])
    def test_no_discount(self): self.assertEqual(math.allocate_discount([100,101],0),[0,0])
    def test_invalid_allocation(self):
        for prices,discount in [([],0),([0],0),([100],100),([1.5],0),([100],-1)]:
            with self.subTest(prices=prices), self.assertRaises(ValueError): math.allocate_discount(prices,discount)
    def test_5000_random_integer_allocations(self):
        rng=random.Random(20261021)
        for _ in range(5000):
            prices=[rng.randint(1,10000000) for _ in range(rng.randint(1,100))]
            discount=rng.randint(0,sum(prices)-1)
            parts=math.allocate_discount(prices,discount)
            self.assertEqual(sum(parts),discount)
            self.assertEqual(sum(p-d for p,d in zip(prices,parts)),sum(prices)-discount)
            self.assertTrue(all(0<=d<=p for p,d in zip(prices,parts)))

class ManualIntakeTimeTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,21,12,tzinfo=timezone.utc)
        self.event=SimpleNamespace(status='SCHEDULED',start_at=self.now+timedelta(days=10),sale_deadline=None,date_tba=False,delivery_due_at=None)
    def test_future_event_can_be_ordered(self): self.assertIsNone(policy.intake_time_error(self.event,self.now))
    def test_postponed_event_with_unknown_date(self):
        self.event.status='POSTPONED'; self.event.start_at=None; self.event.date_tba=True
        self.assertIsNone(policy.intake_time_error(self.event,self.now))
    def test_cancelled_and_finished(self):
        for status in ['CANCELLED','FINISHED']:
            self.event.status=status; self.assertEqual(policy.intake_time_error(self.event,self.now)[0],'EVENT_CLOSED')
    def test_started(self):
        self.event.start_at=self.now; self.assertEqual(policy.intake_time_error(self.event,self.now)[0],'EVENT_STARTED')
    def test_explicit_deadline_respected(self):
        self.event.sale_deadline=self.now; self.assertEqual(policy.intake_time_error(self.event,self.now)[0],'SALES_CLOSED')
    def test_normal_hold_ten_minutes(self): self.assertEqual(policy.hold_deadline(self.event,self.now,600),self.now+timedelta(minutes=10))
    def test_near_deadline_shorter_hold_not_blocked(self):
        self.event.sale_deadline=self.now+timedelta(seconds=30)
        self.assertEqual(policy.hold_deadline(self.event,self.now,600),self.event.sale_deadline)
    def test_hold_without_known_date(self):
        self.event.start_at=None; self.event.date_tba=True
        self.assertEqual(policy.hold_deadline(self.event,self.now,600),self.now+timedelta(minutes=10))
    def test_no_fake_delivery_promise(self):
        self.event.delivery_due_at=self.now-timedelta(hours=1)
        review,delivery=policy.order_deadlines(self.event,self.now)
        self.assertEqual(review,self.now+timedelta(hours=24)); self.assertIsNone(delivery)
    def test_agreed_delivery_preserved(self):
        self.event.delivery_due_at=self.now+timedelta(days=1)
        self.assertEqual(policy.order_deadlines(self.event,self.now)[1],self.event.delivery_due_at)

if __name__=='__main__': unittest.main(verbosity=2)
