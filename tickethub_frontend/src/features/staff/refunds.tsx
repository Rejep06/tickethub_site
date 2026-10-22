'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { useApi, useTask } from '@/lib/hooks';
import { api } from '@/lib/api/client';
import { staffApi } from '@/lib/api/endpoints';
import type { PaginatedStaffCase, StaffCase, MoneyOperationInput } from '@/lib/api/generated';
import { auditTime, fromLocalInput, toLocalInput } from '@/lib/datetime';
import { parseRubles } from '@/lib/money';
import { useToast } from '@/components/ui/toast';
import { Alert, Button, Card, Currency, EmptyState, ErrorState, Field, Input, Modal, PageHeader, Pagination, Select, Skeleton, StatusBadge, Textarea } from '@/components/ui';
import { MoneyFields } from './order-detail';
export function RefundList() {
    const params = useSearchParams(), router = useRouter(), page = Math.max(1, Number(params.get('page')) || 1), status = params.get('status') ?? '';
    const query = new URLSearchParams({ page: String(page) });
    if (status)
        query.set('status', status);
    const data = useApi<PaginatedStaffCase>('staff/refunds/?' + query);
    return <div className="stack">
  <PageHeader title="Обращения и возвраты" description="Одобрение обращения не означает возврат денег."/>
  <Field label="Статус"><Select value={status} onChange={e => router.push(e.target.value ? '?status=' + e.target.value : '/ru/staff/refunds')}>
      <option value="">Все</option>
      {['NEW', 'IN_PROGRESS', 'NEED_INFO', 'APPROVED', 'REJECTED', 'CLOSED'].map(s => <option key={s}>{s}</option>)}
    </Select></Field>
  {data.isPending ? <Skeleton /> : data.error ? <ErrorState error={data.error} retry={() => void data.refetch()}/> : data.data?.results.length ? <><div className="table-wrap"><table>
      <thead><tr>
          <th>Создано</th>
          <th>Тип</th>
          <th>Причина</th>
          <th>Запрошено</th>
          <th>Одобрено</th>
          <th>Статус</th>
          <th />
        </tr></thead>
      <tbody>{data.data.results.map(c => <tr key={c.id}>
          <td>{auditTime(c.created_at)}</td>
          <td><StatusBadge status={c.kind}/></td>
          <td>{c.reason}</td>
          <td><Currency value={c.requested_minor}/></td>
          <td><Currency value={c.approved_minor}/></td>
          <td><StatusBadge status={c.status}/></td>
          <td><Link className="text-link" href={`/ru/staff/refunds/${c.id}`}>Открыть →</Link></td>
        </tr>)}</tbody>
    </table></div><Pagination count={data.data.count} page={page} onChange={p => {
        query.set('page', String(p));
        router.push('?' + query);
    }}/></> : <EmptyState title="Обращений нет"/>}
    </div>;
}
export function RefundDetail({ id }: {
    id: string;
}) {
    const data = useApi<StaffCase>(`staff/refunds/${id}/`);
    const [action, setAction] = useState<{
        kind: string;
        item: StaffCase;
    } | null>(null);
    if (data.isPending)
        return <Skeleton />;
    if (data.error)
        return <ErrorState error={data.error} retry={() => void data.refetch()}/>;
    const item = data.data;
    if (!item)
        return null;
    const pending = ['NEW', 'IN_PROGRESS', 'NEED_INFO'].includes(item.status);
    return <div className="stack">
  <PageHeader title="Обращение клиента" description={`${id} · версия ${item.version}`}><Button variant="secondary" onClick={() => void data.refetch()}>Обновить</Button></PageHeader>
  <Card>
    <div className="badges">
      <StatusBadge status={item.kind}/>
      <StatusBadge status={item.status}/>
    </div>
    <h2>{item.reason}</h2>
    <p>Запрошено: <Currency value={item.requested_minor}/></p>
    <p>Одобрено: <Currency value={item.approved_minor}/></p>
    <p>Создано: {auditTime(item.created_at)}</p>
    <p>Решение: {auditTime(item.decided_at)}</p>
    <p>Ответ клиенту: {item.public_response}</p>
    <p>Внутренние заметки: {item.internal_notes}</p>
    <p>Позиций в обращении: {item.items.length}</p>
    <Link className="text-link" href={`/ru/staff/orders/${item.order}`}>Открыть заказ, состав и финансовую историю →</Link>
  </Card>
  <div className="actions">
    {pending && <>{item.kind === 'REFUND_REQUEST' && <Button onClick={() => setAction({ kind: 'approve', item: structuredClone(item) })}>Одобрить сумму</Button>}<Button variant="danger" onClick={() => setAction({ kind: 'reject', item: structuredClone(item) })}>Отклонить</Button>{(['IN_PROGRESS', 'NEED_INFO', 'CLOSED'] as const).map(k => <Button key={k} variant="secondary" onClick={() => setAction({ kind: k, item: structuredClone(item) })}>{({ IN_PROGRESS: 'В работе', NEED_INFO: 'Запросить уточнение', CLOSED: 'Закрыть' })[k]}</Button>)}</>}
    {item.status === 'APPROVED' && <Button onClick={() => setAction({ kind: 'settle', item: structuredClone(item) })}>Зафиксировать фактический возврат</Button>}
  </div>
  {item.status === 'APPROVED' && <Alert>Решение одобрено. Для учёта возврата нужна отдельная запись по фактически возвращенным деньгам. Остаток решения проверяется сервером.</Alert>}
  {action && <RefundAction key={action.kind} item={action.item} kind={action.kind} close={() => setAction(null)}/>}
    </div>;
}
function RefundAction({ item, kind, close }: {
    item: StaffCase;
    kind: string;
    close: () => void;
}) {
    const task = useTask(), client = useQueryClient(), notify = useToast();
    const [step, setStep] = useState(1), [amount, setAmount] = useState(''), [method, setMethod] = useState<MoneyOperationInput['method']>('BANK_TRANSFER'), [date, setDate] = useState(() => toLocalInput(new Date().toISOString())), [reference, setReference] = useState(''), [notes, setNotes] = useState(''), [response, setResponse] = useState('');
    const title = kind === 'settle' ? 'Фактический возврат денег' : kind === 'approve' ? 'Одобрить сумму возврата' : kind === 'reject' ? 'Отклонить обращение' : 'Изменить состояние обращения';
    return <Modal open onClose={close} title={title} busy={task.busy}><form className="stack" onSubmit={e => {
        e.preventDefault();
        void task.run(async () => {
            if (step === 1) {
                if (['settle', 'approve'].includes(kind) && parseRubles(amount) <= 0)
                    throw new Error('INVALID_MONEY');
                setStep(2);
                return;
            }
            if (kind === 'settle') {
                await staffApi.refund(item.id, { expected_version: item.order_version, amount_minor: parseRubles(amount), occurred_at: fromLocalInput(date), method, reference, notes });
            }
            else {
                const action = ['approve', 'reject'].includes(kind) ? kind : 'decision';
                const body: Record<string, unknown> = { expected_version: item.version, public_response: response, internal_notes: notes };
                if (kind === 'approve')
                    body.amount_minor = parseRubles(amount);
                if (action === 'decision')
                    body.decision = kind;
                await api(`staff/refunds/${item.id}/${action}/`, { method: 'POST', body });
            }
            await client.invalidateQueries({ queryKey: ['api'] });
            notify('Обращение обновлено');
            close();
        });
    }}>
    {step === 1 ? <>{kind === 'settle' ? <><Alert>Эта форма не перечисляет деньги. Укажите только уже выполненный возврат, сверив остаток по финансовой истории заказа.</Alert><MoneyFields {...{ amount, setAmount, method, setMethod, date, setDate, reference, setReference, notes, setNotes }}/></> : <>{kind === 'approve' && <Field label="Одобряемая сумма, ₽"><Input required inputMode="decimal" value={amount} onChange={e => setAmount(e.target.value)}/></Field>}<Field label="Ответ клиенту"><Textarea required maxLength={2000} value={response} onChange={e => setResponse(e.target.value)}/></Field><Field label="Внутренние заметки"><Textarea value={notes} maxLength={2000} onChange={e => setNotes(e.target.value)}/></Field></>}</> : <><Alert>{kind === 'approve' ? 'Вы одобряете сумму, но не фиксируете возврат денег.' : kind === 'settle' ? 'Подтвердите фактически возвращённую сумму.' : 'Подтвердите изменение обращения.'}</Alert>{['approve', 'settle'].includes(kind) && <h2><Currency value={parseRubles(amount)}/></h2>}<p>{response}</p>{kind === 'settle' && <p>{method} · {reference} · {date}</p>}<Button variant="secondary" type="button" onClick={() => setStep(1)} disabled={task.busy}>Изменить</Button></>}
    {task.error ? <ErrorState error={task.error}/> : null}
    <Button type="submit" busy={task.busy} variant={step === 2 ? 'danger' : 'primary'}>{step === 1 ? 'Проверить' : 'Подтвердить'}</Button>
  </form></Modal>;
}
