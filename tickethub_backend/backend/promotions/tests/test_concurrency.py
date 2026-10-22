"""These tests require PostgreSQL row locks and two real DB connections."""
import queue
import threading
import uuid
from django.db import connection, connections
from django.test import TransactionTestCase
from core.errors import BusinessError
from tests.factories import buyer, stock
from tickets.services import create_hold
from orders.models import Order
from orders.services import create_order_from_hold
from promotions.models import PromoRedemption
from promotions.services import preview_promotion, save_promotion


class PromoConcurrencyTests(TransactionTestCase):
    def run_competition(self, *, same_user=False):
        self.assertEqual(connection.vendor, 'postgresql', 'SQLite cannot verify this test.')
        promo = save_promotion(None, {'code': 'LASTUSE', 'kind': 'PERCENT', 'value': 10,
                                     'usage_limit': None if same_user else 1, 'per_user_limit': 1})
        first = buyer()
        users = [first, first if same_user else buyer()]
        entries = []
        for user in users:
            # Distinct events ensure the promo lock, not an event lock, guards total quota.
            event, offer, _, selection = stock()
            hold = create_hold(user, event.pk, selection, offer.sale_price_minor)
            quote = preview_promotion(user, hold.pk, promo.code)
            entries.append((user, {'hold_id': hold.pk, 'promo_code': promo.code,
                'expected_promo_version': quote['promo_version'], 'expected_total_minor': quote['total_minor'],
                'expected_discount_minor': quote['discount_minor']}))
        barrier, results = threading.Barrier(3), queue.Queue()

        def worker(user, data):
            connections.close_all()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '10s'")
                    cursor.execute("SET statement_timeout = '20s'")
                    cursor.execute('SELECT pg_backend_pid()')
                    pid = cursor.fetchone()[0]
                barrier.wait(timeout=15)
                try:
                    order, created = create_order_from_hold(user, data, uuid.uuid4())
                    results.put(('OK', str(order.pk), pid))
                except BusinessError as exc:
                    results.put(('REJECTED', exc.business_code, pid))
            except Exception as exc:
                results.put(('ERROR', repr(exc), None))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=worker, args=entry, daemon=True) for entry in entries]
        for thread in threads:
            thread.start()
        barrier.wait(timeout=15)
        for thread in threads:
            thread.join(timeout=30)
            self.assertFalse(thread.is_alive(), 'Potential deadlock: checkout did not finish.')
        rows = [results.get(timeout=3) for _ in threads]
        self.assertEqual(sorted(row[0] for row in rows), ['OK', 'REJECTED'], rows)
        self.assertEqual(len({row[2] for row in rows}), 2)
        self.assertEqual(next(row[1] for row in rows if row[0] == 'REJECTED'), 'PROMO_USER_LIMIT' if same_user else 'PROMO_LIMIT')
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(PromoRedemption.objects.count(), 1)

    def test_last_global_use_is_consumed_once(self):
        self.run_competition()

    def test_one_account_cannot_race_its_limit_across_events(self):
        self.run_competition(same_user=True)
