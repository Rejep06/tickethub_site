from .calculations import ledger_totals, payment_state, delivery_summary


def money_summary(order):
    totals = ledger_totals({'kind': e.kind, 'amount_minor': e.amount_minor, 'direction': e.direction}
                           for e in order.financial_entries.all())
    return {'state': payment_state(order.total_minor, totals['PAYMENT'], totals['CUSTOMER_REFUND']),
            'received_minor': totals['PAYMENT'], 'refunded_minor': totals['CUSTOMER_REFUND'],
            'net_received_minor': totals['PAYMENT'] - totals['CUSTOMER_REFUND'],
            'expense_minor': totals['DIRECT_EXPENSE'], 'supplier_refund_minor': totals['SUPPLIER_REFUND']}


def sent_summary(order):
    active = [item.id for item in order.items.all() if item.is_active]
    sent = []
    for delivery in order.deliveries.all():
        if delivery.status == 'SENT':
            sent.extend(item.id for item in delivery.items.all())
    return delivery_summary(active, sent)


def sent_item_ids(order, *, include_voided=False):
    records = order.deliveries.all()
    if not include_voided:
        records = records.filter(status='SENT')
    return set(records.values_list('items__id', flat=True)) - {None}
