"""Real executable tests of production pure functions; no Django or database substitute."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

def load(relative, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

money = load('backend/payments/calculations.py', 'tickethub_money')
funnel = load('backend/analytics/calculations.py', 'tickethub_funnel')

class MoneyTests(unittest.TestCase):
    def test_positive_payment(self):
        self.assertEqual(money.ledger_totals([{'kind': 'PAYMENT', 'amount_minor': 123}])['PAYMENT'], 123)
    def test_reversal_preserves_signed_total(self):
        rows = [{'kind': 'PAYMENT', 'amount_minor': 100}, {'kind': 'PAYMENT', 'amount_minor': 100, 'direction': 'REVERSAL'}]
        self.assertEqual(money.ledger_totals(rows)['PAYMENT'], 0)
    def test_expense_does_not_increase_payment(self):
        totals = money.ledger_totals([{'kind': 'DIRECT_EXPENSE', 'amount_minor': 50}])
        self.assertEqual(totals['PAYMENT'], 0)
        self.assertEqual(totals['DIRECT_EXPENSE'], 50)
    def test_negative_amount_is_rejected(self):
        with self.assertRaises(ValueError): money.ledger_totals([{'kind': 'PAYMENT', 'amount_minor': -1}])
    def test_zero_amount_is_rejected(self):
        with self.assertRaises(ValueError): money.ledger_totals([{'kind': 'PAYMENT', 'amount_minor': 0}])
    def test_float_and_bool_amounts_are_rejected(self):
        for value in [1.5, True, '100']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                money.ledger_totals([{'kind': 'PAYMENT', 'amount_minor': value}])
    def test_invalid_kind_is_rejected(self):
        with self.assertRaises(ValueError): money.ledger_totals([{'kind': 'FAKE', 'amount_minor': 100}])
    def test_unpaid(self): self.assertEqual(money.payment_state(100, 0, 0), 'UNPAID')
    def test_partial(self): self.assertEqual(money.payment_state(100, 30, 0), 'PARTIAL')
    def test_paid(self): self.assertEqual(money.payment_state(100, 100, 0), 'PAID')
    def test_partial_refund(self): self.assertEqual(money.payment_state(100, 100, 20), 'PARTIALLY_REFUNDED')
    def test_full_refund(self): self.assertEqual(money.payment_state(100, 100, 100), 'REFUNDED')
    def test_refund_cannot_exceed_payment(self):
        with self.assertRaises(ValueError): money.payment_state(100, 20, 21)
    def test_empty_delivery_is_not_complete(self): self.assertEqual(money.delivery_summary([], [])['state'], 'NOT_SENT')
    def test_partial_delivery_uses_unique_items(self):
        result = money.delivery_summary([1,2,3,4], [1,2,1,2])
        self.assertEqual(result, {'state': 'PARTIALLY_SENT', 'sent_count': 2, 'active_count': 4})
    def test_delivery_foreign_items_do_not_count(self): self.assertEqual(money.delivery_summary([1,2], [7,8])['sent_count'], 0)
    def test_full_delivery(self): self.assertEqual(money.delivery_summary([1,2], [1,2])['state'], 'SENT')
    def test_unknown_cost_does_not_inflate_profit(self):
        result = money.profit_summary(10000, 1000, [3000,None], 100)
        self.assertIsNone(result['profit_minor'])
        self.assertFalse(result['profit_complete'])
        self.assertEqual(result['unknown_cost_count'], 1)
    def test_known_cost_and_supplier_refund(self):
        result = money.profit_summary(10000, 1000, [3000, 2000], 500, 1000)
        self.assertEqual(result['profit_minor'], 4500)
        self.assertTrue(result['profit_complete'])
    def test_zero_cost_is_known_not_unknown(self): self.assertTrue(money.profit_summary(100, 0, [0])['profit_complete'])

class FunnelTests(unittest.TestCase):
    def test_empty_funnel_has_null_conversion(self): self.assertIsNone(funnel.milestone_funnel([], ['A'])[0]['overall_conversion'])
    def test_milestones_must_have_prefix(self):
        result = funnel.milestone_funnel([{'A','B','C'}, {'A'}, {'B','C'}], ['A','B','C'])
        self.assertEqual([r['count'] for r in result], [2,1,1])
        self.assertEqual(result[1]['conversion_from_previous'], 0.5)
    def test_payment_can_precede_confirmation(self):
        result = funnel.milestone_funnel([{'CREATED','PAID','CONFIRMED'}], ['CREATED','CONFIRMED','PAID'])
        self.assertEqual([r['count'] for r in result], [1,1,1])
    def test_web_funnel_requires_chronological_order(self):
        result = funnel.chronological_funnel([['B','A'], ['A','B']], ['A','B'])
        self.assertEqual([r['count'] for r in result], [2,1])
    def test_duplicates_do_not_inflate_web_funnel(self):
        result = funnel.chronological_funnel([['A','A','B','B','C']], ['A','B','C'])
        self.assertEqual([r['count'] for r in result], [1,1,1])
    def test_increasing_funnel_is_rejected(self):
        with self.assertRaises(ValueError): funnel.funnel_rows([1,2], ['A','B'])
    def test_negative_counts_rejected(self):
        with self.assertRaises(ValueError): funnel.funnel_rows([-1], ['A'])
    def test_mismatched_steps_rejected(self):
        with self.assertRaises(ValueError): funnel.funnel_rows([1], ['A','B'])
