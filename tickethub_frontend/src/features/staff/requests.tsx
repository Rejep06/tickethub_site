'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { useApi, useTask } from '@/lib/hooks';
import { api } from '@/lib/api/client';
import type { PaginatedStaffRequest, StaffRequest, StaffQuote, CreateQuoteInput, PaginatedStaffUnit, StaffUnit } from '@/lib/api/generated';
import { auditTime, fromLocalInput, toLocalInput } from '@/lib/datetime';
import { parseRubles } from '@/lib/money';
import { useToast } from '@/components/ui/toast';
import { Alert, Button, Card, Checkbox, ConfirmDialog, Currency, EmptyState, ErrorState, Field, Input, Modal, PageHeader, Pagination, Select, Skeleton, StatusBadge, Textarea } from '@/components/ui';
import { ReferencePicker, StaffFields } from './fields';
export function StaffRequestList() {
    const router = useRouter(), params = useSearchParams(), page = Math.max(1, Number(params.get('page')) || 1), status = params.get('status') ?? '', manager = params.get('manager') ?? '';
    const [managerInput, setManager] = useState(manager);
    useEffect(() => setManager(manager), [manager]);
    const query = new URLSearchParams({ page: String(page) });
    if (status)
        query.set('status', status);
    if (manager)
        query.set('manager', manager);
    const data = useApi<PaginatedStaffRequest>('staff/ticket-requests/?' + query);
    function update(k: string, v: string) {
        const q = new URLSearchParams(params);
        if (v) q.set(k, v);
        else q.delete(k);
        q.delete('page');
        router.push('?' + q);
    }
    return <div className="stack">
  <PageHeader title="Заявки на подбор"/>
  <Card><div className="form-grid">
      <Field label="Статус"><Select value={status} onChange={e => update('status', e.target.value)}>
          <option value="">Все</option>
          {['NEW', 'IN_PROGRESS', 'OFFERED', 'CONVERTED', 'CANCELLED', 'REJECTED'].map(s => <option key={s} value={s}>{s}</option>)}
        </Select></Field>
      <form className="input-group" onSubmit={e => {
        e.preventDefault();
        update('manager', managerInput);
    }}>
        <Field label="Менеджер (UUID)"><Input value={managerInput} onChange={e => setManager(e.target.value)}/></Field>
        <Button variant="secondary">Применить</Button>
      </form>
    </div></Card>
  {data.isPending ? <Skeleton /> : data.error ? <ErrorState error={data.error} retry={() => void data.refetch()}/> : data.data?.results.length ? <><div className="table-wrap"><table>
      <thead><tr>
          <th>Заявка</th>
          <th>Клиент</th>
          <th>Событие / пожелания</th>
          <th>Количество</th>
          <th>Бюджет</th>
          <th>Статус</th>
        </tr></thead>
      <tbody>{data.data.results.map(r => <tr key={r.id}>
          <td>
            <Link className="text-link" href={`/ru/staff/requests/${r.id}`}>{r.number}</Link>
            <small>{auditTime(r.created_at)}</small>
          </td>
          <td>
            {r.customer_name}
            <small>{r.customer_email}</small>
          </td>
          <td>
            {r.custom_event_name || r.quotes[0]?.event.title_ru || 'Мероприятие из каталога'}
            <small>{r.preferences}</small>
          </td>
          <td>
            {r.quantity}
            {r.together_required && <small>Места рядом</small>}
          </td>
          <td><Currency value={r.budget_minor}/></td>
          <td><StatusBadge status={r.status}/></td>
        </tr>)}</tbody>
    </table></div><Pagination count={data.data.count} page={page} onChange={p => {
        query.set('page', String(p));
        router.push('?' + query);
    }}/></> : <EmptyState title="Заявок нет"/>}
    </div>;
}
export function StaffRequestDetail({ id }: {
    id: string;
}) {
    const data = useApi<StaffRequest>(`staff/ticket-requests/${id}/`), task = useTask(), client = useQueryClient(), notify = useToast();
    const [edit, setEdit] = useState<StaffRequest | null>(null), [quoteRequest, setQuoteRequest] = useState<StaffRequest | null>(null), [quoteAction, setQuoteAction] = useState<{
        kind: 'send' | 'withdraw';
        quote: StaffQuote;
    } | null>(null);
    if (data.isPending)
        return <Skeleton />;
    if (data.error)
        return <ErrorState error={data.error} retry={() => void data.refetch()}/>;
    const request = data.data;
    if (!request)
        return null;
    return <div className="stack"><Link href="/ru/staff/requests" className="text-link">← Заявки</Link><PageHeader title={`Заявка ${request.number}`} description={`${auditTime(request.created_at)} · версия ${request.version}`}><Button variant="secondary" onClick={() => void data.refetch()}>Обновить</Button></PageHeader><div className="actions">
    <StatusBadge status={request.status}/>
    {request.status === 'NEW' && <Button busy={task.busy} onClick={() => void task.run(async () => {
        await api(`staff/ticket-requests/${id}/start/`, { method: 'POST', body: { expected_version: request.version } });
        await client.invalidateQueries({ queryKey: ['api'] });
        notify('Заявка взята в работу');
    })}>Взять в работу</Button>}
    {!['CANCELLED', 'REJECTED', 'CONVERTED'].includes(request.status) && <><Button variant="secondary" onClick={() => setEdit(structuredClone(request))}>Ответ / назначение</Button><Button onClick={() => setQuoteRequest(structuredClone(request))}>Создать предложение</Button></>}
  </div>{task.error ? <ErrorState error={task.error}/> : null}<div className="order-grid">
    <Card>
      <h2>{request.custom_event_name || 'Подбор на мероприятие из каталога'}</h2>
      {request.event && <Link href={`/ru/staff/events/${request.event}`} className="text-link">Открыть мероприятие →</Link>}
      <p>{request.city} · {request.desired_date}</p>
      <p>{request.quantity} бил. · общий бюджет <Currency value={request.budget_minor}/></p>
      {request.together_required && <Alert>Клиент просит места рядом. Подтверждайте соседство только после проверки.</Alert>}
      <p>{request.preferences}</p>
      <p>{request.comment}</p>
      <h3>Ответ клиенту</h3>
      <p>{request.public_response}</p>
      <h3>Внутренние заметки</h3>
      <p>{request.internal_notes}</p>
    </Card>
    <Card>
      <h2>Клиент</h2>
      <p>{request.customer_name}</p>
      <p className="break-word">{request.customer_email}</p>
      <p>{request.customer_phone}</p>
      <small>Ответственный: {request.manager ?? 'не назначен'}</small>
    </Card>
  </div><h2>Предложения</h2>{request.quotes.map(q => <Card key={q.id}>
    <div className="split">
      <h3>Версия предложения {q.version} · {q.event.title_ru}</h3>
      <StatusBadge status={q.status}/>
    </div>
    <p>До {auditTime(q.expires_at)}</p>
    <div className="ticket-items">{q.items.map(i => <div key={i.id} className="ticket-item">
        <span>{i.name_ru} {i.sector}/{i.row}/{i.seat_number}</span>
        <Currency value={i.price_minor}/>
      </div>)}</div>
    <h3><Currency value={q.total_minor}/></h3>
    <p>{q.public_comment}</p>
    <div className="actions">
      {q.status === 'DRAFT' && <Button onClick={() => setQuoteAction({ kind: 'send', quote: structuredClone(q) })}>Отправить клиенту</Button>}
      {['SENT', 'DRAFT'].includes(q.status) && <Button variant="secondary" onClick={() => setQuoteAction({ kind: 'withdraw', quote: structuredClone(q) })}>Отозвать</Button>}
    </div>
  </Card>)}{edit && <RequestEdit request={edit} close={() => setEdit(null)}/>} {quoteRequest && <QuoteBuilder request={quoteRequest} close={() => setQuoteRequest(null)}/>}<ConfirmDialog title={quoteAction?.kind === 'send' ? 'Отправить предложение клиенту?' : 'Отозвать предложение?'} open={!!quoteAction} onClose={() => setQuoteAction(null)} busy={task.busy} onConfirm={() => void task.run(async () => {
        if (!quoteAction)
            return;
        await api(`staff/quotes/${quoteAction.quote.id}/${quoteAction.kind}/`, { method: 'POST', body: { expected_version: quoteAction.quote.request_version } });
        await client.invalidateQueries({ queryKey: ['api'] });
        setQuoteAction(null);
        notify('Предложение обновлено');
    })}>
    <p>Перед отправкой проверьте состав и сумму. Предложение не закрепляет билеты.</p>
    <Currency value={quoteAction?.quote.total_minor}/>
    {task.error ? <ErrorState error={task.error}/> : null}
  </ConfirmDialog></div>;
}
function RequestEdit({ request, close }: {
    request: StaffRequest;
    close: () => void;
}) {
    const task = useTask(), client = useQueryClient();
    const [values, setValues] = useState<Record<string, unknown>>({ manager_id: request.manager ?? '', event_id: request.event ?? '', internal_notes: request.internal_notes, public_response: request.public_response, status: '' });
    const [confirm, setConfirm] = useState(false);
    return <Modal open onClose={close} title="Ответ / назначение" busy={task.busy}><form className="stack" onSubmit={e => {
        e.preventDefault();
        if (!confirm) {
            setConfirm(true);
            return;
        }
        void task.run(async () => {
            const body: Record<string, unknown> = { expected_version: request.version };
            for (const [k, v] of Object.entries(values)) {
                if (k === 'event_id' && v === (request.event ?? ''))
                    continue;
                if (v || ['internal_notes', 'public_response'].includes(k))
                    body[k] = v;
            }
            await api(`staff/ticket-requests/${request.id}/update-status/`, { method: 'POST', body });
            await client.invalidateQueries({ queryKey: ['api'] });
            close();
        });
    }}>
    <StaffFields values={values} disabled={confirm} setValue={(k, v) => setValues({ ...values, [k]: v })} fields={[{ name: 'manager_id', label: 'Менеджер (UUID)' }, { name: 'event_id', label: 'Событие', type: 'reference', lookup: 'staff/events/' }, { name: 'public_response', label: 'Ответ клиенту', type: 'textarea' }, { name: 'internal_notes', label: 'Внутренние заметки', type: 'textarea' }, { name: 'status', label: 'Изменить статус', type: 'select', options: ['IN_PROGRESS', 'CANCELLED', 'REJECTED'] }]}/>
    {confirm && <><Alert>Подтвердите изменение заявки. При отклонении сообщите клиенту причину.</Alert><Button type="button" variant="secondary" onClick={() => setConfirm(false)}>Изменить</Button></>}
    {task.error ? <ErrorState error={task.error}/> : null}
    <Button type="submit" busy={task.busy}>{confirm ? 'Подтвердить' : 'Проверить'}</Button>
  </form></Modal>;
}
function QuoteBuilder({ request, close }: {
    request: StaffRequest;
    close: () => void;
}) {
    const [event, setEvent] = useState(request.event ?? ''), [page, setPage] = useState(1), [chosen, setChosen] = useState<Record<string, {
        unit: StaffUnit;
        price: string;
    }>>({}), [expires, setExpires] = useState(() => toLocalInput(new Date(Date.now() + 24 * 3600000).toISOString())), [comment, setComment] = useState(''), [together, setTogether] = useState(false), [preview, setPreview] = useState(false);
    const task = useTask(), client = useQueryClient(), notify = useToast();
    const units = useApi<PaginatedStaffUnit>(`staff/units/?event=${event}&status=AVAILABLE&page=${page}`, !!event);
    const total = Object.values(chosen).reduce((sum, i) => {
        try {
            return sum + parseRubles(i.price);
        }
        catch {
            return sum;
        }
    }, 0);
    async function submit() {
        const body: CreateQuoteInput = { expected_version: request.version, event_id: event, expires_at: fromLocalInput(expires), public_comment: comment, together_confirmed: together, items: Object.values(chosen).map(i => ({ ticket_unit_id: i.unit.id, price_minor: parseRubles(i.price) })) };
        await api<StaffQuote>(`staff/ticket-requests/${request.id}/quotes/`, { method: 'POST', body });
        await client.invalidateQueries({ queryKey: ['api'] });
        notify('Черновик предложения создан. Следующий шаг — отправить клиенту.');
        close();
    }
    return <Modal open onClose={close} title="Новое предложение" busy={task.busy}><form className="stack" onSubmit={e => {
        e.preventDefault();
        void task.run(async () => {
            if (!preview) {
                for (const c of Object.values(chosen))
                    if (parseRubles(c.price) <= 0)
                        throw new Error('INVALID_MONEY');
                setPreview(true);
            }
            else
                await submit();
        });
    }}>
    {!preview ? <><Field label="Мероприятие"><ReferencePicker required path="staff/events/" value={event} onChange={id => {
        setEvent(id);
        setChosen({});
        setPage(1);
    }}/></Field><Alert>Показаны units со статусом AVAILABLE. Просроченное закрепление исключено из выбора. Сервер повторно проверит билеты при сохранении и оформлении.</Alert>{event && (units.isPending ? <Skeleton /> : units.error ? <ErrorState error={units.error} retry={() => void units.refetch()}/> : <><div className="lookup-list">{units.data?.results.map(unit => {
        const expired = unit.stock_basis === 'EXCLUSIVE_ALLOCATION' && (!unit.allocation_until || Date.parse(unit.allocation_until) <= Date.now());
        return <Checkbox key={unit.id} disabled={expired} checked={!!chosen[unit.id]} onChange={e => {
            const next = { ...chosen };
            if (e.target.checked)
                next[unit.id] = { unit, price: '' };
            else
                delete next[unit.id];
            setChosen(next);
        }}>
        {unit.id}
        <small>Предложение: {unit.offer} · место: {unit.seat ?? 'категория'}{expired ? ' · закрепление истекло' : ''}</small>
      </Checkbox>;
    })}</div>{units.data && <Pagination count={units.data.count} page={page} onChange={setPage}/>}</>)}{Object.entries(chosen).map(([id, item]) => <Field label={`Цена продажи, ₽ · ${id}`} key={id}><Input required inputMode="decimal" value={item.price} onChange={e => setChosen({ ...chosen, [id]: { ...item, price: e.target.value } })}/></Field>)}<Field label="Действует до (время устройства)"><Input required type="datetime-local" value={expires} onChange={e => setExpires(e.target.value)}/></Field><Field label="Условия / сообщение клиенту"><Textarea value={comment} maxLength={2000} onChange={e => setComment(e.target.value)}/></Field><Checkbox checked={together} onChange={e => setTogether(e.target.checked)}>Подтверждаю соседство выбранных мест</Checkbox></> : <><Alert>Предпросмотр суммы и условий. Закупки и поставщики не попадут в клиентское предложение. После сохранения будет доступен точный состав из серверных снимков.</Alert><p>{Object.keys(chosen).length} бил. · до {expires}</p><p>{comment}</p>{together && <p>Соседство подтверждено менеджером</p>}<Button variant="secondary" type="button" onClick={() => setPreview(false)}>Изменить</Button></>}
    <h3>Итого: <Currency value={total}/></h3>
    {task.error ? <ErrorState error={task.error}/> : null}
    <Button type="submit" busy={task.busy} disabled={!event || !Object.keys(chosen).length || Object.keys(chosen).length > 100}>{preview ? 'Создать черновик' : 'Предпросмотр'}</Button>
  </form></Modal>;
}
