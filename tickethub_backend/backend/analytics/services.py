from collections import defaultdict
from django.utils import timezone
from payments.calculations import profit_summary
from payments.selectors import money_summary, sent_summary
from .models import FunnelEvent
from .calculations import chronological_funnel, milestone_funnel

CLIENT_STEPS = ['EVENT_VIEW', 'TICKETS_VIEW', 'TICKET_SELECTED', 'CHECKOUT_STARTED']
ORDER_STEPS = ['ORDER_CREATED', 'ORDER_PROCESSING_STARTED', 'ORDER_CONFIRMED', 'PAYMENT_RECEIVED', 'TICKET_SENT', 'ORDER_COMPLETED']
REQUEST_STEPS = ['REQUEST_CREATED', 'REQUEST_PROCESSING_STARTED', 'QUOTE_SENT', 'ORDER_CREATED']


def record_order_event(order, event_type):
    if event_type not in ORDER_STEPS:
        raise ValueError('Unknown server order event')
    return FunnelEvent.objects.get_or_create(order=order, event_type=event_type, source='SERVER', defaults={
        'user': order.user, 'event': order.event, 'ticket_request': order.ticket_request,
        'session_key': order.analytics_session_key})[0]


def record_request_event(request, event_type):
    if event_type not in REQUEST_STEPS[:-1]:
        raise ValueError('Unknown server request event')
    return FunnelEvent.objects.get_or_create(ticket_request=request, order=None, event_type=event_type, source='SERVER', defaults={
        'user': request.user, 'event': request.event, 'session_key': request.analytics_session_key})[0]


def _filtered_orders(filters):
    from orders.models import Order
    queryset = Order.objects.filter(origin__in=['SITE_DIRECT', 'SITE_REQUEST']).select_related('event').prefetch_related(
        'items', 'financial_entries', 'deliveries__items')
    if filters.get('event'):
        queryset = queryset.filter(event_id=filters['event'])
    if filters.get('category'):
        queryset = queryset.filter(event__category_id=filters['category'])
    return queryset


def _inside(value, filters):
    return value is not None and (not filters.get('from') or value >= filters['from']) and (not filters.get('to') or value < filters['to'])


def _sales_metrics(orders):
    revenue = refunds = expenses = supplier_refunds = ticket_count = 0
    costs = []
    for order in orders:
        money = money_summary(order)
        revenue += order.total_minor
        refunds += money['refunded_minor']
        expenses += money['expense_minor']
        supplier_refunds += money['supplier_refund_minor']
        costs.extend(item.purchase_price_minor for item in order.items.all())
        ticket_count += sum(item.is_active for item in order.items.all())
    profit = profit_summary(revenue, refunds, costs, expenses, supplier_refunds)
    net = revenue - refunds
    return {'orders_count': len(orders), 'tickets_count': ticket_count, 'gross_turnover_minor': revenue,
            'turnover_minor': net, 'refunded_minor': refunds, 'direct_expenses_minor': expenses,
            'supplier_refunds_minor': supplier_refunds,
            'average_check_minor': (net + len(orders) // 2) // len(orders) if orders else None, **profit}


def dashboard(filters):
    orders = list(_filtered_orders(filters).order_by('created_at', 'id'))
    created = [order for order in orders if _inside(order.created_at, filters)]
    paid_cohort = [order for order in orders if _inside(order.first_paid_at, filters)
                   and money_summary(order)['received_minor'] == order.total_minor]
    successful = [order for order in paid_cohort if order.order_state not in ['CANCELLED', 'REJECTED']
                  and any(item.is_active for item in order.items.all())]
    by_event = defaultdict(list)
    by_day = defaultdict(list)
    from zoneinfo import ZoneInfo
    from django.conf import settings
    for order in successful:
        by_event[order.event_id].append(order)
        by_day[order.first_paid_at.astimezone(ZoneInfo(settings.REPORT_TIMEZONE)).date().isoformat()].append(order)
    now = timezone.now()
    pending_delivery = [order for order in orders if order.order_state == 'CONFIRMED'
                        and money_summary(order)['received_minor'] == order.total_minor and sent_summary(order)['state'] != 'SENT']
    return {'currency': 'RUB', 'generated_at': now,
            'orders_created': len(created), 'cancelled_orders': sum(o.order_state == 'CANCELLED' for o in created),
            'successful_sales': _sales_metrics(successful),
            'paid_cohort_including_cancelled': _sales_metrics(paid_cohort),
            'by_event': [{'event_id': event_id, 'title_ru': rows[0].event.title_ru, **_sales_metrics(rows)} for event_id, rows in by_event.items()],
            'by_day': [{'date': day, **_sales_metrics(rows)} for day, rows in sorted(by_day.items())],
            'work_queue': {'new_orders': sum(o.order_state == 'NEW' for o in orders),
                           'review_overdue': sum(o.order_state in ['NEW', 'IN_PROGRESS'] and o.review_due_at < now for o in orders),
                           'delivery_pending': len(pending_delivery),
                           'delivery_overdue': sum(bool(o.delivery_due_at and o.delivery_due_at < now) for o in pending_delivery)}}


def cashflow(filters):
    from payments.models import FinancialEntry
    queryset = FinancialEntry.objects.filter(order__origin__in=['SITE_DIRECT', 'SITE_REQUEST'])
    if filters.get('from'):
        queryset = queryset.filter(occurred_at__gte=filters['from'])
    if filters.get('to'):
        queryset = queryset.filter(occurred_at__lt=filters['to'])
    if filters.get('event'):
        queryset = queryset.filter(order__event_id=filters['event'])
    if filters.get('category'):
        queryset = queryset.filter(order__event__category_id=filters['category'])
    from payments.calculations import ledger_totals
    totals = ledger_totals(queryset.values('kind', 'amount_minor', 'direction'))
    return {'currency': 'RUB', 'received_minor': totals['PAYMENT'], 'customer_refunds_minor': totals['CUSTOMER_REFUND'],
            'direct_expenses_minor': totals['DIRECT_EXPENSE'], 'supplier_refunds_minor': totals['SUPPLIER_REFUND'],
            'net_cashflow_minor': totals['PAYMENT'] - totals['CUSTOMER_REFUND'] - totals['DIRECT_EXPENSE'] + totals['SUPPLIER_REFUND']}


def funnel(filters):
    queryset = FunnelEvent.objects.all()
    if filters.get('event'):
        queryset = queryset.filter(event_id=filters['event'])
    if filters.get('category'):
        queryset = queryset.filter(event__category_id=filters['category'])
    all_rows = list(queryset.order_by('created_at', 'id'))
    web, web_start, order_paths, order_start, request_paths, request_start = {}, {}, {}, {}, {}, {}
    for row in all_rows:
        if row.session_key and row.event_id and row.event_type in CLIENT_STEPS + ['ORDER_CREATED']:
            key = (row.session_key, row.event_id)
            web.setdefault(key, []).append(row.event_type)
            if row.event_type == 'EVENT_VIEW' and key not in web_start:
                web_start[key] = row.created_at
        if row.source == 'SERVER' and row.order_id:
            order_paths.setdefault(row.order_id, set()).add(row.event_type)
            if row.event_type == 'ORDER_CREATED':
                order_start[row.order_id] = row.created_at
        if row.source == 'SERVER' and row.ticket_request_id:
            request_paths.setdefault(row.ticket_request_id, set()).add(row.event_type)
            if row.event_type == 'REQUEST_CREATED':
                request_start[row.ticket_request_id] = row.created_at
    return {'cohort': 'first step in [from,to); later steps included through now',
            'web': chronological_funnel([path for key, path in web.items() if _inside(web_start.get(key), filters)], CLIENT_STEPS + ['ORDER_CREATED']),
            'orders': milestone_funnel([path for key, path in order_paths.items() if _inside(order_start.get(key), filters)], ORDER_STEPS),
            'requests': milestone_funnel([path for key, path in request_paths.items() if _inside(request_start.get(key), filters)], REQUEST_STEPS),
            'note': 'Web paths require consent. Operational paths include all website orders; corrections remain in historical milestones.'}
