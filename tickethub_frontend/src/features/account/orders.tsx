'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { useLang, useT } from '@/i18n/use-t';
import { useApi, useTask } from '@/lib/hooks';
import { api } from '@/lib/api/client';
import type { Order, PaginatedOrder, CreateCaseInput, Case } from '@/lib/api/generated';
import { PriceSummary } from '@/features/checkout/promo-code';
import { auditTime, eventTime } from '@/lib/datetime';
import { localized, text } from '@/lib/safe';
import { parseRubles } from '@/lib/money';
import { Alert, Button, Card, Checkbox, Currency, EmptyState, ErrorState, Field, Input, Modal, PageHeader, Pagination, Select, Skeleton, StatusBadge, Textarea } from '@/components/ui';
export function OrderCard({ order }: {
    order: Order;
}) {
    const lang = useLang(), t = useT();
    return <Card>
  <div className="split">
    <strong>{t('orderNumber', { number: order.number })}</strong>
    <Currency value={order.total_minor}/>
  </div>
  <h3>{localized(order.event_snapshot, 'title', lang)}</h3>
  <p>{eventTime(text(order.event_snapshot.start_at), text(order.event_snapshot.timezone), lang)}</p>
  <div className="badges">
    <StatusBadge status={order.order_state}/>
    <StatusBadge status={order.payment_state}/>
    <StatusBadge status={order.delivery_state}/>
  </div>
  <Link className="text-link" href={`/${lang}/account/orders/${order.id}`}>{t('details')} →</Link>
    </Card>;
}
export function OrderList({ compact = false }: {
    compact?: boolean;
}) {
    const t = useT(), lang = useLang(), params = useSearchParams(), router = useRouter();
    const page = compact ? 1 : Math.max(1, Number(params.get('page')) || 1);
    const data = useApi<PaginatedOrder>(`orders/?page=${page}&page_size=${compact ? 3 : 24}`);
    return <div className="stack">{!compact && <PageHeader title={t('myOrders')}/>} {data.isPending ? <Skeleton /> : data.error ? <ErrorState error={data.error} retry={() => void data.refetch()}/> : !data.data?.results.length ? <EmptyState title={t('noOrders')}><Link href={`/${lang}/events`} className="btn btn-primary">{t('browse')}</Link></EmptyState> : <>{data.data.results.map(order => <OrderCard key={order.id} order={order}/>)}{!compact && <Pagination count={data.data.count} page={page} onChange={p => router.push(`?page=${p}`)}/>}</>}</div>;
}
export function OrderDetails({ id }: {
    id: string;
}) {
    const data = useApi<Order>(`orders/${id}/`, true, 30000), t = useT(), lang = useLang(), params = useSearchParams();
    const [caseOpen, setCaseOpen] = useState(false);
    if (data.isPending)
        return <Skeleton />;
    if (data.error)
        return <ErrorState error={data.error} retry={() => void data.refetch()}/>;
    const order = data.data;
    if (!order)
        return null;
    return <div className="stack">
  <PageHeader title={t('orderNumber', { number: order.number })} description={auditTime(order.created_at, lang)}><Button variant="secondary" onClick={() => void data.refetch()}>{t('refresh')}</Button></PageHeader>
  {params.get('success') === '1' && <Alert tone="good">
    <strong>{t('orderSuccess')}</strong>
    <p>{t('orderSuccessText')}</p>
  </Alert>}
  <div className="order-grid">
    <div className="stack">
      <Card>
        <h2>{localized(order.event_snapshot, 'title', lang)}</h2>
        <p>{localized(order.event_snapshot, 'venue', lang)}</p>
        <p>{eventTime(text(order.event_snapshot.start_at), text(order.event_snapshot.timezone), lang)}</p>
        <div className="badges">
          <StatusBadge status={order.order_state}/>
          <StatusBadge status={order.payment_state}/>
          <StatusBadge status={order.delivery_state}/>
        </div>
        <div className="ticket-items">{order.items.map(item => <div className="ticket-item" key={item.id}>
            <div>
              <strong>{localized(item, 'name', lang)}</strong>
              <p>{item.sector} / {item.row} / {item.seat_number}</p>
              {!item.is_active && <span>{t('inactiveTicket')}</span>}
            </div>
            <Currency value={item.sale_price_minor}/>
          </div>)}</div>
        <PriceSummary subtotal={order.subtotal_minor} discount={order.discount_minor} total={order.total_minor} code={order.promo_code}/>
      </Card>
      <Card>
        <h2>{t('deliveryState')}</h2>
        <p>{t('deliveryProgress', { sent: order.sent_count, total: order.items.filter(i => i.is_active).length })}</p>
        <p>{t(order.delivery_state === 'SENT' ? 'deliverySent' : 'deliveryPending', { email: order.customer_email })}</p>
        <p>{t('deliveryDue')}: {order.delivery_due_at ? auditTime(order.delivery_due_at, lang) : t('deliveryToBeAgreed')}</p>
        <small>{t('noDownload')}</small>
      </Card>
      <Card>
        <h2>{t('timeline')}</h2>
        <ol className="timeline">{order.history.map(item => <li key={item.id}>
            <strong>{item.public_message}</strong>
            <small>{auditTime(item.created_at, lang)}</small>
          </li>)}</ol>
      </Card>
    </div>
    <div className="stack">
      <Card>
        <h2>{t('contactsTitle')}</h2>
        <p>{order.customer_name}</p>
        <p className="break-word">{order.customer_email}</p>
        <p>{order.customer_phone}</p>
        <p>{order.customer_comment}</p>
        {order.event_snapshot.fan_id_required === true && <><h3>{t('fanId')}</h3><StatusBadge status={order.fan_id_help_state}/></>}
      </Card>
      <Card>
        <h2>{t('paymentState')}</h2>
        <p>{t('received')}: <Currency value={order.payment.received_minor}/></p>
        <p>{t('refunded')}: <Currency value={order.payment.refunded_minor}/></p>
        <small>{t('managerPayment')}</small>
      </Card>
      <Card>
        <h2>{t('refundRules')}</h2>
        <p className="preserve-lines">{localized(order.event_snapshot, 'refund_policy', lang)}</p>
        <Button variant="secondary" onClick={() => setCaseOpen(true)}>{t('problem')}</Button>
      </Card>
    </div>
  </div>
  <h2>{t('cases')}</h2>
  {order.cases.length ? order.cases.map(item => <Card key={item.id}>
    <div className="badges">
      <StatusBadge status={item.kind}/>
      <StatusBadge status={item.status}/>
    </div>
    <p>{item.reason}</p>
    <p>{item.public_response}</p>
    {item.approved_minor !== null && <Currency value={item.approved_minor}/>}
  </Card>) : <EmptyState />}
  <CaseForm order={order} open={caseOpen} close={() => setCaseOpen(false)}/>
    </div>;
}
function CaseForm({ order, open, close }: {
    order: Order;
    open: boolean;
    close: () => void;
}) {
    const t = useT(), lang = useLang(), client = useQueryClient(), task = useTask();
    const [kind, setKind] = useState<NonNullable<CreateCaseInput['kind']>>('REFUND_REQUEST'), [reason, setReason] = useState(''), [amount, setAmount] = useState(''), [items, setItems] = useState<string[]>([]);
    return <Modal title={t('openCase')} open={open} onClose={close} busy={task.busy}><form className="stack" onSubmit={e => {
        e.preventDefault();
        void task.run(async () => {
            await api<Case>(`orders/${order.id}/cases/`, { method: 'POST', body: { kind, item_ids: items.length ? items : undefined, reason, requested_minor: amount ? parseRubles(amount) : null } satisfies CreateCaseInput });
            await client.invalidateQueries({ queryKey: ['api'] });
            close();
        });
    }}>
    <Field label={t('caseType')}><Select value={kind} onChange={e => setKind(e.target.value as typeof kind)}>{['REFUND_REQUEST', 'CANCEL_REQUEST', 'DELIVERY_ISSUE', 'OTHER'].map(k => <option key={k} value={k}>{t('state_' + k)}</option>)}</Select></Field>
    <small>{t('caseAllItemsHint')}</small>
    {order.items.filter(i => i.is_active).map(i => <Checkbox key={i.id} checked={items.includes(i.id)} onChange={e => setItems(e.target.checked ? [...items, i.id] : items.filter(id => id !== i.id))}>{localized(i, 'name', lang)} {i.sector}/{i.row}/{i.seat_number}</Checkbox>)}
    <Field label={t('reason')}><Textarea required value={reason} maxLength={2000} onChange={e => setReason(e.target.value)}/></Field>
    <Field label={t('requestedAmount')}><Input inputMode="decimal" value={amount} onChange={e => setAmount(e.target.value)}/></Field>
    {task.error ? <ErrorState error={task.error}/> : null}
    <Button type="submit" busy={task.busy}>{t('openCase')}</Button>
  </form></Modal>;
}
