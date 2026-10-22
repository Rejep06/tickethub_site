'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useQueryClient } from '@tanstack/react-query';
import { useApi, useTask } from '@/lib/hooks';
import { api } from '@/lib/api/client';
import { staffApi } from '@/lib/api/endpoints';
import { idempotentPost } from '@/lib/api/attempts';
import type { StaffOrder, RecordPaymentInput, RecordDeliveryInput, MoneyOperationInput } from '@/lib/api/generated';
import { PriceSummary } from '@/features/checkout/promo-code';
import { auditTime, eventTime, fromLocalInput, toLocalInput } from '@/lib/datetime';
import { localized, text } from '@/lib/safe';
import { parseRubles, rubInput } from '@/lib/money';
import { orderActions, deliveryProgress } from '@/lib/order-actions';
import { useToast } from '@/components/ui/toast';
import { Alert, Button, Card, Checkbox, Currency, ErrorState, Field, Input, Modal, PageHeader, Select, Skeleton, StatusBadge, Textarea } from '@/components/ui';
import { StaffFields } from './fields';
const labels: Record<string, string> = { start: 'Взять в работу', confirm: 'Подтвердить заказ', contact: 'Отметить контакт', operations: 'Рабочие параметры', payment: 'Записать деньги', delivery: 'Отметить отправку', cancel: 'Отменить заказ', reject: 'Отклонить заказ', complete: 'Завершить заказ', cost: 'Изменить себестоимость', reverse: 'Сторнировать запись', void: 'Аннулировать отправку' };
type Action = {
    kind: string;
    order: StaffOrder;
    target?: string;
};
export function StaffOrderDetail({ id }: {
    id: string;
}) {
    const data = useApi<StaffOrder>(`staff/orders/${id}/`), notify = useToast(), copyTask = useTask();
    const [action, setAction] = useState<Action | null>(null);
    if (data.isPending)
        return <Skeleton />;
    if (data.error)
        return <ErrorState error={data.error} retry={() => void data.refetch()}/>;
    const order = data.data;
    if (!order)
        return null;
    const allowed = orderActions(order);
    const act = (kind: string, target?: string) => setAction({ kind, order: structuredClone(order), target });
    return <div className="stack">
  <Link href="/ru/staff/orders" className="text-link">← Заказы</Link>
  <PageHeader title={`Заказ ${order.number}`} description={`Версия ${order.version} · ${auditTime(order.created_at)}`}><Button variant="secondary" onClick={() => void data.refetch()}>Обновить</Button></PageHeader>
  <div className="badges">
    <StatusBadge status={order.order_state}/>
    <StatusBadge status={order.payment_state}/>
    <StatusBadge status={order.delivery_state}/>
  </div>
  <div className="actions">{allowed.map(kind => <Button key={kind} variant={['cancel', 'reject'].includes(kind) ? 'danger' : kind === 'start' ? 'primary' : 'secondary'} onClick={() => act(kind)}>{labels[kind]}</Button>)}</div>
  <div className="order-grid">
    <div className="stack">
      <Card>
        <h2>{localized(order.event_snapshot, 'title', 'ru')}</h2>
        <p>{eventTime(text(order.event_snapshot.start_at), text(order.event_snapshot.timezone))}</p>
        <p>{localized(order.event_snapshot, 'venue', 'ru')}</p>
        <Link href={`/ru/staff/events/${order.event}`} className="text-link">Карточка события →</Link>
        <div className="table-wrap"><table>
            <thead><tr>
                <th>Билет</th>
                <th>Продажа</th>
                <th>Закупка</th>
                <th>Состояние</th>
                <th>Действие</th>
              </tr></thead>
            <tbody>{order.items.map(item => <tr key={item.id}>
                <td>
                  {item.name_ru}
                  <small>{item.sector} / {item.row} / {item.seat_number}</small>
                  <Link href={`/ru/staff/tickets/${item.ticket_unit}`} className="text-link">Остаток →</Link>
                </td>
                <td><Currency value={item.sale_price_minor}/></td>
                <td><Currency value={item.purchase_price_minor}/></td>
                <td>{item.is_active ? 'Активен' : 'Неактивен'}</td>
                <td><Button variant="ghost" onClick={() => act('cost', item.id)}>Стоимость</Button></td>
              </tr>)}</tbody>
          </table></div>
        {order.items.some(i => i.purchase_price_minor === null) && <Alert>Себестоимость части билетов неизвестна. Точную прибыль по этим данным показать нельзя.</Alert>}
      </Card>
      <Card>
        <h2>Финансы</h2>
        <PriceSummary subtotal={order.subtotal_minor} discount={order.discount_minor} total={order.total_minor} code={order.promo_code}/>
        <div className="metric-grid">
          <div>
            <small>Сумма заказа</small>
            <h3><Currency value={order.total_minor}/></h3>
          </div>
          <div>
            <small>Получено</small>
            <h3><Currency value={order.payment.received_minor}/></h3>
          </div>
          <div>
            <small>Возвращено</small>
            <h3><Currency value={order.payment.refunded_minor}/></h3>
          </div>
          <div>
            <small>Получено за вычетом возвратов</small>
            <h3><Currency value={order.payment.net_received_minor}/></h3>
          </div>
        </div>
        {order.financial_entries.map(entry => <div className="ticket-item" key={entry.id}>
          <div>
            <StatusBadge status={entry.kind}/>
            <p>
              {entry.direction === 'REVERSAL' ? 'Сторно · ' : ''}
              {auditTime(entry.occurred_at)}
            </p>
            <small>{entry.method} · {entry.reference}</small>
            <p>{entry.notes}</p>
          </div>
          <div>
            <Currency value={entry.amount_minor}/>
            {entry.direction === 'NORMAL' && !order.financial_entries.some(e => e.reversal_of === entry.id) && <Button variant="ghost" onClick={() => act('reverse', entry.id)}>Сторнировать</Button>}
          </div>
        </div>)}
      </Card>
      <Card>
        <h2>Отправка</h2>
        <h3>{deliveryProgress(order.sent_count, order.items.filter(i => i.is_active).length)}</h3>
        <p>Срок: {order.delivery_due_at ? auditTime(order.delivery_due_at) : 'нужно согласовать с клиентом'}</p>
        <small>Здесь отмечается фактическая ручная отправка. Нажатие кнопки не отправляет файл.</small>
        {order.deliveries.map(record => <div className="ticket-item" key={record.id}>
          <div>
            <StatusBadge status={record.status}/>
            <p>{record.items.length} бил. → {record.recipient_email}</p>
            <small>{auditTime(record.sent_at)}</small>
            <p>{record.note}</p>
            {record.message_id && <small>ID письма: {record.message_id}</small>}
          </div>
          {record.status === 'SENT' && <Button variant="ghost" onClick={() => act('void', record.id)}>Исправить отметку</Button>}
        </div>)}
      </Card>
      <Card>
        <h2>История</h2>
        <ol className="timeline">{order.history.map(h => <li key={h.id}>
            <strong>{h.public_message || h.event_type}</strong>
            {h.internal_note && <p>{h.internal_note}</p>}
            <small>{auditTime(h.created_at)}</small>
          </li>)}</ol>
      </Card>
    </div>
    <div className="stack">
      <Card>
        <h2>Клиент</h2>
        <h3>{order.customer_name}</h3>
        <p className="break-word">{order.customer_email}</p>
        <p>{order.customer_phone}</p>
        <div className="actions">
          <Button variant="ghost" onClick={() => void copyTask.run(async () => {
        await navigator.clipboard.writeText(order.customer_email);
        notify('Email скопирован');
    })}>Копировать email</Button>
          <Button variant="ghost" onClick={() => void copyTask.run(async () => {
        await navigator.clipboard.writeText(order.customer_phone);
        notify('Телефон скопирован');
    })}>Копировать телефон</Button>
        </div>
        {copyTask.error ? <ErrorState error={copyTask.error}/> : null}
        <p>{order.customer_comment}</p>
        <Link href={`/ru/staff/orders?user=${order.user}`} className="text-link">Другие заказы клиента →</Link>
      </Card>
      <Card>
        <h2>Обработка</h2>
        <p>Ответственный: {order.manager ?? 'не назначен'}</p>
        <p>Проверить до: {auditTime(order.review_due_at)}</p>
        <p>Расчёты до: {auditTime(order.settlement_due_at)}</p>
        <p>Первый контакт: {auditTime(order.first_contact_at)}</p>
        <StatusBadge status={order.fan_id_help_state}/>
        <p className="preserve-lines">{order.internal_notes}</p>
      </Card>
      <Card>
        <h2>Обращения</h2>
        {order.cases.map(c => <div className="stack" key={c.id}>
          <StatusBadge status={c.status}/>
          <p>{c.reason}</p>
          <Link href={`/ru/staff/refunds/${c.id}`} className="text-link">Открыть обращение →</Link>
        </div>)}
      </Card>
    </div>
  </div>
  {action && <OrderActionModal key={action.kind + '.' + action.order.version + '.' + action.target} action={action} close={() => setAction(null)}/>}
    </div>;
}
export function MoneyFields({ amount, setAmount, method, setMethod, date, setDate, reference, setReference, notes, setNotes }: {
    amount: string;
    setAmount: (s: string) => void;
    method: MoneyOperationInput['method'];
    setMethod: (s: MoneyOperationInput['method']) => void;
    date: string;
    setDate: (s: string) => void;
    reference: string;
    setReference: (s: string) => void;
    notes: string;
    setNotes: (s: string) => void;
}) {
    return <div className="stack">
  <div className="form-grid">
    <Field label="Сумма, ₽"><Input required inputMode="decimal" value={amount} onChange={e => setAmount(e.target.value)}/></Field>
    <Field label="Способ расчёта"><Select required value={method} onChange={e => setMethod(e.target.value as typeof method)}>{(['BANK_CARD', 'SBP', 'BANK_TRANSFER', 'CASH', 'OTHER'] as const).map(m => <option key={m} value={m}>{({ BANK_CARD: 'Карта', SBP: 'СБП', BANK_TRANSFER: 'Банковский перевод', CASH: 'Наличные', OTHER: 'Другой' })[m]}</option>)}</Select></Field>
    <Field label="Фактическая дата / время" hint="В часовом поясе этого устройства."><Input required type="datetime-local" value={date} onChange={e => setDate(e.target.value)}/></Field>
    <Field label="Номер / подтверждение операции"><Input required value={reference} onChange={e => setReference(e.target.value)} maxLength={200}/></Field>
  </div>
  <Field label="Комментарий"><Textarea value={notes} onChange={e => setNotes(e.target.value)} maxLength={2000}/></Field>
    </div>;
}
export function OrderActionModal({ action, close }: {
    action: Action;
    close: () => void;
}) {
    const { kind, order, target } = action, task = useTask(), notify = useToast(), client = useQueryClient();
    const [step, setStep] = useState(1), [amount, setAmount] = useState(kind === 'cost' ? rubInput(order.items.find(i => i.id === target)?.purchase_price_minor) : kind === 'payment' ? rubInput(order.total_minor - (order.payment.received_minor ?? 0)) : ''), [method, setMethod] = useState<MoneyOperationInput['method']>('BANK_TRANSFER'), [date, setDate] = useState(() => toLocalInput(new Date().toISOString())), [reference, setReference] = useState(''), [note, setNote] = useState(''), [checked, setChecked] = useState(false), [paymentKind, setPaymentKind] = useState<RecordPaymentInput['kind']>(['CANCELLED', 'REJECTED'].includes(order.order_state) ? 'DIRECT_EXPENSE' : 'PAYMENT'), [items, setItems] = useState<string[]>([]), [email, setEmail] = useState(order.customer_email), [messageId, setMessageId] = useState('');
    const [operations, setOperations] = useState<Record<string, unknown>>({ manager_id: order.manager ?? '', internal_notes: order.internal_notes, review_due_at: toLocalInput(order.review_due_at), settlement_due_at: toLocalInput(order.settlement_due_at), delivery_due_at: toLocalInput(order.delivery_due_at), fan_id_help_state: order.fan_id_help_state });
    const financial = ['payment', 'cost', 'reverse'].includes(kind);
    const entry = order.financial_entries.find(e => e.id === target);
    const reasonRequired = ['cancel', 'reject', 'cost', 'reverse', 'void'].includes(kind);
    async function perform() {
        const base = { expected_version: order.version };
        if (kind === 'payment') {
            const body: RecordPaymentInput = { ...base, kind: paymentKind, amount_minor: parseRubles(amount), method, occurred_at: fromLocalInput(date), reference, notes: note };
            await staffApi.payment(order.id, body);
        }
        else if (kind === 'delivery') {
            const body: RecordDeliveryInput = { ...base, item_ids: items, recipient_email: email, sent_at: fromLocalInput(date), note, message_id: messageId };
            await staffApi.delivery(order.id, body);
        }
        else if (kind === 'cost') {
            await api<StaffOrder>(`staff/order-items/${target}/cost/`, { method: 'POST', body: { ...base, purchase_price_minor: parseRubles(amount), reason: note, zero_confirmed: checked } });
        }
        else if (kind === 'reverse') {
            await idempotentPost(`staff/financial-entries/${target}/reverse/`, { ...base, reason: note, occurred_at: fromLocalInput(date) }, 'reverse.' + target);
        }
        else if (kind === 'void') {
            await api(`staff/deliveries/${target}/void/`, { method: 'POST', body: { ...base, reason: note } });
        }
        else {
            let body: Record<string, unknown> = base;
            if (kind === 'cancel' || kind === 'reject')
                body = { ...base, reason: note, no_pending_settlements: checked };
            if (kind === 'contact')
                body = { ...base, note };
            if (kind === 'operations') {
                body = { ...base, internal_notes: operations.internal_notes, fan_id_help_state: operations.fan_id_help_state };
                if (operations.manager_id)
                    body.manager_id = operations.manager_id;
                for (const k of ['review_due_at', 'delivery_due_at'])
                    body[k] = fromLocalInput(text(operations[k]));
                body.settlement_due_at = operations.settlement_due_at ? fromLocalInput(text(operations.settlement_due_at)) : null;
            }
            await api<StaffOrder>(`staff/orders/${order.id}/${kind}/`, { method: 'POST', body });
        }
        await client.invalidateQueries({ queryKey: ['api'] });
        notify(labels[kind] + ': выполнено');
        close();
    }
    return <Modal open title={labels[kind]} onClose={close} busy={task.busy}><form className="stack" onSubmit={e => {
        e.preventDefault();
        if (step === 1) {
            try {
                if (kind === 'payment' && parseRubles(amount) <= 0)
                    throw new Error('INVALID_MONEY');
                if (kind === 'cost' && (parseRubles(amount) < 0 || parseRubles(amount) === 0 && !checked))
                    throw new Error('ZERO_COST_CONFIRMATION');
                task.setError(null);
                setStep(2);
            }
            catch (error) {
                task.setError(error);
            }
            return;
        }
        void task.run(perform);
    }}>
    <p>Заказ {order.number} · версия {order.version}</p>
    {step === 1 ? <>{kind === 'payment' && <><Alert>Записывайте только фактически полученные или выплаченные деньги. Эта форма не выполняет банковский перевод.</Alert><Field label="Вид записи"><Select value={paymentKind} onChange={e => setPaymentKind(e.target.value as typeof paymentKind)}>
        {!['CANCELLED', 'REJECTED'].includes(order.order_state) && <option value="PAYMENT">Полученная оплата</option>}
        <option value="DIRECT_EXPENSE">Прямой расход</option>
        <option value="SUPPLIER_REFUND">Возврат от поставщика</option>
      </Select></Field><MoneyFields {...{ amount, setAmount, method, setMethod, date, setDate, reference, setReference, notes: note, setNotes: setNote }}/></>}{kind === 'delivery' && <><Alert>Сначала отправьте билеты вручную. Выберите только действительно отправленные позиции.</Alert>{order.items.filter(i => i.is_active).map(i => <Checkbox key={i.id} checked={items.includes(i.id)} onChange={e => setItems(e.target.checked ? [...items, i.id] : items.filter(id => id !== i.id))}>{i.name_ru} · {i.sector}/{i.row}/{i.seat_number}</Checkbox>)}<Field label="Email получателя"><Input required type="email" value={email} onChange={e => setEmail(e.target.value)}/></Field><Field label="Когда отправлено (время устройства)"><Input required type="datetime-local" value={date} onChange={e => setDate(e.target.value)}/></Field><Field label="ID письма (необязательно)"><Input value={messageId} onChange={e => setMessageId(e.target.value)}/></Field><Field label="Комментарий"><Textarea value={note} onChange={e => setNote(e.target.value)}/></Field></>}{kind === 'cost' && <Field label="Подтверждённая закупка, ₽"><Input required inputMode="decimal" value={amount} onChange={e => setAmount(e.target.value)}/></Field>}{kind === 'reverse' && <><Alert>Сторно исправляет учётную запись. Не используйте его вместо фактического возврата клиенту.</Alert><Currency value={entry?.amount_minor}/><Field label="Фактическое время исправления"><Input required type="datetime-local" value={date} onChange={e => setDate(e.target.value)}/></Field></>}{(reasonRequired || kind === 'contact') && <Field label={reasonRequired ? 'Обязательная причина' : 'Заметка'}><Textarea required={reasonRequired} value={note} onChange={e => setNote(e.target.value)} maxLength={2000}/></Field>}{['cost', 'cancel', 'reject'].includes(kind) && <Checkbox checked={checked} onChange={e => setChecked(e.target.checked)}>{kind === 'cost' ? 'Подтверждаю нулевую себестоимость (если указано 0 ₽)' : 'Подтверждаю отсутствие незавершённых внешних расчётов'}</Checkbox>}{kind === 'operations' && <StaffFields values={operations} setValue={(k, v) => setOperations({ ...operations, [k]: v })} fields={[{ name: 'manager_id', label: 'Менеджер (UUID)' }, { name: 'internal_notes', label: 'Внутренние заметки', type: 'textarea' }, { name: 'review_due_at', label: 'Проверить до', type: 'datetime', required: true }, { name: 'settlement_due_at', label: 'Расчёты до', type: 'datetime' }, { name: 'delivery_due_at', label: 'Выдать до', type: 'datetime', required: true }, { name: 'fan_id_help_state', label: 'Помощь Fan ID', type: 'select', options: ['NOT_NEEDED', 'REQUESTED', 'IN_PROGRESS', 'INSTRUCTED'] }]}/>}</> : <><Alert>{financial ? 'Проверьте сумму и реквизиты перед записью.' : 'Проверьте действие: изменения будут сохранены на сервере.'}</Alert>{['payment', 'cost'].includes(kind) && <h2><Currency value={safeMinor(amount)}/></h2>}{kind === 'payment' && <p>{paymentKind} · {method} · {reference} · {date}</p>}{kind === 'delivery' && <p>Отмечаем {items.length} бил. → {email} · {date}</p>}{kind === 'reverse' && <Currency value={entry?.amount_minor}/>}<p>{note}</p><Button type="button" variant="secondary" disabled={task.busy} onClick={() => setStep(1)}>Изменить данные</Button></>}
    {task.error ? <ErrorState error={task.error}/> : null}
    <Button type="submit" busy={task.busy} disabled={kind === 'delivery' && !items.length} variant={['cancel', 'reject', 'reverse', 'void'].includes(kind) ? 'danger' : 'primary'}>{step === 1 ? 'Проверить действие' : 'Подтвердить'}</Button>
    <small>При сетевой ошибке повторите с теми же полями. Не меняйте сумму до проверки истории.</small>
  </form></Modal>;
}
function safeMinor(value: string) {
    try {
        return parseRubles(value);
    }
    catch {
        return null;
    }
}
