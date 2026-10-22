'use client';
import { apiUrl } from '@/lib/api/url';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useApi } from '@/lib/hooks';
import type { Dashboard, Cashflow, Funnel, PaginatedStaffRequest } from '@/lib/api/generated';
import { auditTime } from '@/lib/datetime';
import { Alert, Button, Card, Currency, EmptyState, ErrorState, Field, Input, PageHeader, Skeleton, Tabs } from '@/components/ui';
import { ReferencePicker } from './fields';
const stepNames: Record<string, string> = { EVENT_VIEW: 'Просмотр события', TICKETS_VIEW: 'Просмотр билетов', TICKET_SELECTED: 'Выбор билета', CHECKOUT_STARTED: 'Начало оформления', ORDER_CREATED: 'Заказ создан', ORDER_IN_PROGRESS: 'В работе', ORDER_CONFIRMED: 'Подтверждён', PAYMENT_RECEIVED: 'Оплата получена', ORDER_PAID: 'Оплачен', TICKET_SENT: 'Билеты отправлены', ORDER_COMPLETED: 'Завершён', REQUEST_CREATED: 'Заявка создана', REQUEST_IN_PROGRESS: 'Заявка в работе', REQUEST_PROCESSING_STARTED: 'Заявка в работе', ORDER_PROCESSING_STARTED: 'Заказ в работе', QUOTE_SENT: 'Предложение отправлено', REQUEST_CONVERTED: 'Заявка в заказ' };
function defaultRange() {
    const end = new Date();
    end.setUTCHours(0, 0, 0, 0);
    end.setUTCDate(end.getUTCDate() + 1);
    const start = new Date(end);
    start.setUTCDate(start.getUTCDate() - 30);
    return { from: start.toISOString().slice(0, 10), to: end.toISOString().slice(0, 10) };
}
export function StaffAnalytics({ dashboard = false }: {
    dashboard?: boolean;
}) {
    const params = useSearchParams(), router = useRouter(), defaults = defaultRange();
    const [tab, setTab] = useState('sales');
    const from = params.get('from')?.slice(0, 10) ?? defaults.from, to = params.get('to')?.slice(0, 10) ?? defaults.to;
    const [start, setStart] = useState(from), [end, setEnd] = useState(to), [event, setEvent] = useState(params.get('event') ?? ''), [category, setCategory] = useState(params.get('category') ?? '');
    useEffect(() => {
        setStart(from);
        setEnd(to);
        setEvent(params.get('event') ?? '');
        setCategory(params.get('category') ?? '');
    }, [from, to, params]);
    const query = new URLSearchParams({ from: from + 'T00:00:00Z', to: to + 'T00:00:00Z' });
    for (const k of ['event', 'category'])
        if (params.get(k))
            query.set(k, params.get(k)!);
    const sales = useApi<Dashboard>(`${dashboard ? 'staff/dashboard/summary/' : 'staff/analytics/sales/'}?${query}`);
    const cash = useApi<Cashflow>('staff/analytics/cashflow/?' + query, !dashboard && tab === 'cash');
    const funnel = useApi<Funnel>('staff/analytics/funnel/?' + query, !dashboard && tab === 'funnel');
    const requests = useApi<PaginatedStaffRequest>('staff/ticket-requests/?status=NEW&page_size=1', dashboard);
    function apply(s = start, e = end) {
        const q = new URLSearchParams({ from: s + 'T00:00:00Z', to: e + 'T00:00:00Z' });
        if (event)
            q.set('event', event);
        if (category)
            q.set('category', category);
        router.push('?' + q);
    }
    function preset(days: number) {
        const e = new Date();
        e.setUTCHours(0, 0, 0, 0);
        e.setUTCDate(e.getUTCDate() + 1);
        const s = new Date(e);
        s.setUTCDate(s.getUTCDate() - days);
        setStart(s.toISOString().slice(0, 10));
        setEnd(e.toISOString().slice(0, 10));
        apply(s.toISOString().slice(0, 10), e.toISOString().slice(0, 10));
    }
    return <div className="stack"><PageHeader title={dashboard ? 'Обзор работы' : 'Аналитика'} description="Агрегаты бэкенда на полной отфильтрованной выборке. Период — UTC."><a className="btn btn-secondary" href={apiUrl('staff/analytics/export/?' + query, 'ru')} download>Скачать CSV продаж</a></PageHeader><Card><form className="stack" onSubmit={e => {
        e.preventDefault();
        apply();
    }}>
      <div className="actions">
        <Button type="button" variant="ghost" onClick={() => preset(1)}>Сегодня</Button>
        <Button type="button" variant="ghost" onClick={() => preset(7)}>7 дней</Button>
        <Button type="button" variant="ghost" onClick={() => preset(30)}>30 дней</Button>
      </div>
      <div className="form-grid">
        <Field label="С даты (UTC)"><Input required type="date" value={start} onChange={e => setStart(e.target.value)}/></Field>
        <Field label="До даты, не включая (UTC)"><Input required type="date" min={start} value={end} onChange={e => setEnd(e.target.value)}/></Field>
        <Field label="Мероприятие"><ReferencePicker path="staff/events/" value={event} onChange={setEvent}/></Field>
        <Field label="Категория"><ReferencePicker path="staff/categories/" value={category} onChange={setCategory}/></Field>
      </div>
      <Button type="submit" disabled={start >= end}>Применить период</Button>
    </form></Card>{!dashboard && <Tabs value={tab} onChange={setTab} options={[{ value: 'sales', label: 'Продажи' }, { value: 'cash', label: 'Движение денег' }, { value: 'funnel', label: 'Воронки' }]}/>} {(dashboard || tab === 'sales') && (sales.isPending ? <Skeleton rows={5}/> : sales.error ? <ErrorState error={sales.error} retry={() => void sales.refetch()}/> : sales.data && <Sales data={sales.data}/>)}{!dashboard && tab === 'cash' && (cash.isPending ? <Skeleton /> : cash.error ? <ErrorState error={cash.error} retry={() => void cash.refetch()}/> : cash.data && <><Alert>Движение денег и продажи используют разные даты и разные когорты. Чистое движение денег не является прибылью.</Alert><div className="metric-grid">{[['received_minor', 'Поступления'], ['customer_refunds_minor', 'Возвраты клиентам'], ['direct_expenses_minor', 'Прямые расходы'], ['supplier_refunds_minor', 'Возвраты поставщиков'], ['net_cashflow_minor', 'Чистое движение']].map(([key, label]) => <Card key={key}>
      <small>{label}</small>
      <h2><Currency value={cash.data?.[key as keyof Cashflow] as number | undefined}/></h2>
    </Card>)}</div></>)}{!dashboard && tab === 'funnel' && (funnel.isPending ? <Skeleton /> : funnel.error ? <ErrorState error={funnel.error} retry={() => void funnel.refetch()}/> : funnel.data && <><Alert>{funnel.data.note ?? 'Клиентские и бизнес-события считаются отдельно.'}</Alert>{(['web', 'orders', 'requests'] as const).map(kind => <Card key={kind}>
    <h2>{({ web: 'Веб-события', orders: 'Заказы', requests: 'Заявки' })[kind]}</h2>
    {!funnel.data?.[kind]?.length ? <EmptyState /> : <div className="table-wrap"><table>
        <thead><tr>
            <th>Шаг</th>
            <th>Количество</th>
            <th>От прошлого шага</th>
            <th>От первого шага</th>
          </tr></thead>
        <tbody>{funnel.data[kind]?.map((step, i) => <tr key={step.step ?? i}>
            <td>{stepNames[step.step ?? ''] ?? step.step}</td>
            <td>{step.count ?? '—'}</td>
            <td>{percentage(step.conversion_from_previous)}</td>
            <td>{percentage(step.overall_conversion)}</td>
          </tr>)}</tbody>
      </table></div>}
  </Card>)}</>)}{dashboard && sales.data?.work_queue && <><h2>Требует внимания</h2><div className="metric-grid">
    {[['new_orders', 'Новые заказы'], ['review_overdue', 'Просрочена проверка'], ['delivery_pending', 'Ожидают отправки'], ['delivery_overdue', 'Просрочена отправка']].map(([key, label]) => <Card key={key}>
      <small>{label}</small>
      <h2>{sales.data?.work_queue?.[key as keyof NonNullable<Dashboard['work_queue']>] ?? '—'}</h2>
      <Link href={'/ru/staff/orders' + (key === 'new_orders' ? '?state=NEW' : '')} className="text-link">Открыть заказы →</Link>
    </Card>)}
    <Card>
      <small>Новые заявки</small>
      <h2>{requests.data?.count ?? '—'}</h2>
      <Link href="/ru/staff/requests?status=NEW" className="text-link">Открыть заявки →</Link>
    </Card>
  </div><small>Для просрочек API возвращает счётчики, но отдельного фильтра очереди нет. Ссылка открывает список заказов.</small></>}</div>;
}
function Sales({ data }: {
    data: Dashboard;
}) {
    const m = data.successful_sales;
    return <div className="stack">
  <small>Обновлено: {auditTime(data.generated_at)}</small>
  <div className="metric-grid">
    {[['Заказы созданы', data.orders_created], ['Успешные заказы', m?.orders_count], ['Проданные билеты', m?.tickets_count], ['Отменённые', data.cancelled_orders]].map(([label, value]) => <Card key={String(label)}>
      <small>{label}</small>
      <h2>{value ?? '—'}</h2>
    </Card>)}
    <Card>
      <small>Оборот</small>
      <h2><Currency value={m?.turnover_minor}/></h2>
    </Card>
    <Card>
      <small>Подтверждённые закупки</small>
      <h2><Currency value={m?.purchase_cost_minor}/></h2>
    </Card>
    <Card>
      <small>Маржинальный результат</small>
      <h2><Currency value={m?.profit_complete ? m.profit_minor : null}/></h2>
      <small>До налогов и общих расходов</small>
    </Card>
    <Card>
      <small>Средний чек</small>
      <h2><Currency value={m?.average_check_minor}/></h2>
    </Card>
    <Card>
      <small>Возвраты</small>
      <h2><Currency value={m?.refunded_minor}/></h2>
    </Card>
  </div>
  {m?.profit_complete === false && <Alert>Расчёт прибыли неполный: не указана себестоимость {m.unknown_cost_count ?? 'части'} билетов. Неизвестная стоимость не считается нулевой.</Alert>}
  <Series title="Оборот по дням" rows={(data.by_day ?? []).map(d => ({ label: d.date ?? '', value: d.turnover_minor ?? 0 }))} money/>
  <Series title="Заказы по дням" rows={(data.by_day ?? []).map(d => ({ label: d.date ?? '', value: d.orders_count ?? 0 }))}/>
  <Card>
    <h2>Продажи по событиям</h2>
    {!data.by_event?.length ? <EmptyState title="Нет данных за период"/> : <div className="table-wrap"><table>
        <thead><tr>
            <th>Событие</th>
            <th>Заказы</th>
            <th>Билеты</th>
            <th>Оборот</th>
            <th>Возвраты</th>
            <th>Закупки</th>
            <th>Результат</th>
          </tr></thead>
        <tbody>{data.by_event.map(row => <tr key={row.event_id}>
            <td><Link href={`/ru/staff/events/${row.event_id}`} className="text-link">{row.title_ru}</Link></td>
            <td>{row.orders_count}</td>
            <td>{row.tickets_count}</td>
            <td><Currency value={row.turnover_minor}/></td>
            <td><Currency value={row.refunded_minor}/></td>
            <td><Currency value={row.purchase_cost_minor}/></td>
            <td>
              <Currency value={row.profit_complete ? row.profit_minor : null}/>
              {row.profit_complete === false && <small>Неполная закупка</small>}
            </td>
          </tr>)}</tbody>
      </table></div>}
  </Card>
    </div>;
}
function Series({ title, rows, money = false }: {
    title: string;
    rows: {
        label: string;
        value: number;
    }[];
    money?: boolean;
}) {
    const max = Math.max(1, ...rows.map(r => Math.abs(r.value)));
    return <Card>
  <h2>{title}</h2>
  {rows.length ? <div className="bar-chart" role="list" aria-label={title}>{rows.map((r, i) => <div className="bar-row" key={r.label + i} role="listitem">
      <span>{r.label}</span>
      <div className="bar-track"><div className={r.value < 0 ? 'bar negative' : 'bar'} style={{ width: `${Math.abs(r.value) / max * 100}%` }}/></div>
      <strong>{money ? <Currency value={r.value}/> : r.value}</strong>
    </div>)}</div> : <EmptyState title="Нет данных за период"/>}
    </Card>;
}
function percentage(value: number | null | undefined) {
    return typeof value === 'number' ? new Intl.NumberFormat('ru-RU', { style: 'percent', maximumFractionDigits: 1 }).format(value) : '—';
}
