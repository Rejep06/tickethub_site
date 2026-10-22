"""Small pure functions: integer kopecks in, no ORM or floating-point money."""
KINDS = ('PAYMENT', 'CUSTOMER_REFUND', 'DIRECT_EXPENSE', 'SUPPLIER_REFUND')


def ledger_totals(entries):
    totals = dict.fromkeys(KINDS, 0)
    for entry in entries:
        kind = entry['kind']
        amount = entry['amount_minor']
        direction = entry.get('direction', 'NORMAL')
        if kind not in totals or direction not in ('NORMAL', 'REVERSAL'):
            raise ValueError('Unknown ledger entry')
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ValueError('Money must be positive integer kopecks')
        totals[kind] += amount if direction == 'NORMAL' else -amount
    return totals


def payment_state(total_minor, received_minor, refunded_minor):
    if total_minor <= 0 or received_minor < 0 or not 0 <= refunded_minor <= received_minor:
        raise ValueError('Invalid payment totals')
    if refunded_minor and refunded_minor == received_minor:
        return 'REFUNDED'
    if refunded_minor:
        return 'PARTIALLY_REFUNDED'
    if received_minor >= total_minor:
        return 'PAID'
    return 'PARTIAL' if received_minor else 'UNPAID'


def delivery_summary(active_item_ids, sent_item_ids):
    active = set(active_item_ids)
    sent = active & set(sent_item_ids)
    state = 'SENT' if active and sent == active else ('PARTIALLY_SENT' if sent else 'NOT_SENT')
    return {'state': state, 'sent_count': len(sent), 'active_count': len(active)}


def profit_summary(revenue_minor, refunded_minor, costs, expenses_minor=0, supplier_refunds_minor=0):
    costs = list(costs)
    unknown = sum(cost is None for cost in costs)
    known = sum(cost for cost in costs if cost is not None)
    result = revenue_minor - refunded_minor - known - expenses_minor + supplier_refunds_minor
    return {'purchase_cost_minor': known, 'unknown_cost_count': unknown,
            'profit_minor': None if unknown else result,
            'profit_complete': unknown == 0}
