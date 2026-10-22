import queue
import threading
import uuid
from django.db import connection, connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from tests.factories import buyer, stock
from tickets.models import CheckoutHold, TicketUnit


class PostgreSQLReservationConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def test_two_connections_compete_for_last_seat(self):
        self.assertEqual(connection.vendor, 'postgresql', 'This test must run on PostgreSQL, not SQLite.')
        event, offer, units, selection = stock(1, seated=True)
        users = [buyer(), buyer()]
        barrier = threading.Barrier(3)
        results = queue.Queue()
        def worker(user):
            connections.close_all()
            try:
                client = APIClient()
                client.force_login(user, backend='users.backends.CustomerOTPBackend')
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_backend_pid()')
                    pid = cursor.fetchone()[0]
                barrier.wait(timeout=15)
                response = client.post('/api/v1/checkout/holds/',
                    {'event_id': str(event.id), 'selection': {'mode': 'SEATS', 'seat_ids': [str(units[0].seat_id)]},
                     'expected_total_minor': offer.sale_price_minor}, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
                results.put((response.status_code, response.json(), pid))
            except Exception as exc:
                results.put(('ERROR', repr(exc), None))
            finally:
                connections.close_all()
        threads = [threading.Thread(target=worker, args=(user,), daemon=True) for user in users]
        for thread in threads:
            thread.start()
        barrier.wait(timeout=15)
        for thread in threads:
            thread.join(timeout=25)
            self.assertFalse(thread.is_alive(), 'Database deadlock or stuck request')
        rows = [results.get(timeout=3) for _ in threads]
        self.assertEqual(sorted(str(row[0]) for row in rows), ['201', '409'], rows)
        self.assertEqual(len({row[2] for row in rows}), 2, 'Connections must be independent')
        conflict = next(row for row in rows if row[0] == 409)
        self.assertEqual(conflict[1]['code'], 'SEAT_UNAVAILABLE')
        self.assertEqual(CheckoutHold.objects.filter(status='ACTIVE').count(), 1)
        self.assertEqual(TicketUnit.objects.filter(status='CHECKOUT_HELD').count(), 1)
