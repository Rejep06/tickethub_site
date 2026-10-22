'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useApi } from '@/lib/hooks';
import type { PaginatedStaffOrder } from '@/lib/api/generated';
import { auditTime } from '@/lib/datetime';
import { localized } from '@/lib/safe';
import { Button, Card, Currency, EmptyState, ErrorState, PageHeader, Pagination, Skeleton, StatusBadge } from '@/components/ui';
import { StaffFields, type StaffField } from './fields';
const filters: StaffField[] = [{ name: 'q', label: 'Номер заказа' }, { name: 'state', label: 'Обработка', type: 'select', options: ['NEW', 'IN_PROGRESS', 'CONFIRMED', 'COMPLETED', 'REJECTED', 'CANCELLED'] }, { name: 'event', label: 'Мероприятие', type: 'reference', lookup: 'staff/events/' }, { name: 'manager', label: 'Менеджер (UUID)', hint: 'Список команды доступен администратору.' }, { name: 'from', label: 'Создан от (ISO 8601 с timezone)' }, { name: 'to', label: 'Создан до, не включая (ISO 8601)' }];
export function StaffOrderList() {
    const params = useSearchParams(), router = useRouter(), page = Math.max(1, Number(params.get('page')) || 1);
    const [values, setValues] = useState<Record<string, unknown>>(() => Object.fromEntries(params));
    useEffect(() => {
        setValues(Object.fromEntries(params));
    }, [params]);
    const query = new URLSearchParams();
    for (const k of ['q', 'state', 'event', 'manager', 'user', 'from', 'to'])
        if (params.get(k))
            query.set(k, params.get(k)!);
    query.set('page', String(page));
    const data = useApi<PaginatedStaffOrder>('staff/orders/?' + query, true, 15000);
    return <div className="stack">
  <PageHeader title="Заказы" description="Новые заказы с сайта попадают сюда автоматически. Список обновляется каждые 15 секунд."/>
  <Card><form className="stack" onSubmit={e => {
        e.preventDefault();
        const q = new URLSearchParams();
        for (const f of filters)
            if (values[f.name])
                q.set(f.name, String(values[f.name]));
        router.push('?' + q);
    }}>
      <StaffFields fields={filters} values={values} setValue={(k, v) => setValues({ ...values, [k]: v })}/>
      <div className="actions">
        <Button type="submit">Применить</Button>
        <Button type="button" variant="ghost" onClick={() => {
        setValues({});
        router.push('/ru/staff/orders');
    }}>Сбросить</Button>
      </div>
    </form></Card>
  {data.isFetching && !data.isPending && <small>Обновляем данные…</small>}
  {data.isPending ? <Skeleton /> : data.error ? <ErrorState error={data.error} retry={() => void data.refetch()}/> : data.data?.results.length ? <><div className="table-wrap"><table>
      <thead><tr>
          <th>Заказ / создан</th>
          <th>Клиент</th>
          <th>Событие</th>
          <th>Сумма</th>
          <th>Обработка</th>
          <th>Оплата</th>
          <th>Отправка</th>
          <th>Срок выдачи</th>
        </tr></thead>
      <tbody>{data.data.results.map(o => <tr key={o.id}>
          <td>
            <Link className="text-link" href={`/ru/staff/orders/${o.id}`}>{o.number}</Link>
            <small>{auditTime(o.created_at)}</small>
          </td>
          <td>
            {o.customer_name}
            <small>{o.customer_email}</small>
          </td>
          <td>
            {localized(o.event_snapshot, 'title', 'ru')}
            <small>{o.items.length} бил.</small>
          </td>
          <td><Currency value={o.total_minor}/></td>
          <td><StatusBadge status={o.order_state}/></td>
          <td><StatusBadge status={o.payment_state}/></td>
          <td>
            <StatusBadge status={o.delivery_state}/>
            <small>{o.sent_count}/{o.items.filter(i => i.is_active).length}</small>
          </td>
          <td>{auditTime(o.delivery_due_at)}</td>
        </tr>)}</tbody>
    </table></div><Pagination count={data.data.count} page={page} onChange={p => {
        query.set('page', String(p));
        router.push('?' + query);
    }}/></> : <EmptyState title="Заказов по этим условиям нет"/>}
    </div>;
}
