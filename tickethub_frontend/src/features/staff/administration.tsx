'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useApi, useTask } from '@/lib/hooks';
import { api } from '@/lib/api/client';
import type { PaginatedProfile, Settings, PaginatedEmail, Email, PaginatedStaffPrivacy, StaffPrivacy } from '@/lib/api/generated';
import { auditTime } from '@/lib/datetime';
import { Alert, Button, Card, ConfirmDialog, EmptyState, ErrorState, Field, Input, Modal, PageHeader, Pagination, Select, Skeleton, StatusBadge, Textarea } from '@/components/ui';
import { AdminOnly } from './resource-page';
export function Customers() {
    const params = useSearchParams(), customer = params.get('customer');
    const [search, setSearch] = useState(''), [query, setQuery] = useState(''), [page, setPage] = useState(1);
    const data = useApi<PaginatedProfile>(`staff/customers/?q=${encodeURIComponent(query)}&page=${page}`);
    return <div className="stack">
  <PageHeader title="Клиенты" description="Поиск контактов доступен только сотрудникам. Персональные данные не сохраняются в URL."/>
  {customer && <Card>
    <p>Клиент: {customer}</p>
    <Link className="btn btn-primary" href={`/ru/staff/orders?user=${encodeURIComponent(customer)}`}>Заказы клиента</Link>
  </Card>}
  <Card><form className="input-group" onSubmit={e => {
        e.preventDefault();
        setQuery(search);
        setPage(1);
    }}>
      <Field label="Поиск по email"><Input value={search} onChange={e => setSearch(e.target.value)} maxLength={200}/></Field>
      <Button>Найти</Button>
    </form></Card>
  {data.isPending ? <Skeleton /> : data.error ? <ErrorState error={data.error} retry={() => void data.refetch()}/> : data.data?.results.length ? <><div className="table-wrap"><table>
      <thead><tr>
          <th>Имя</th>
          <th>Email</th>
          <th>Телефон</th>
          <th>Язык</th>
          <th />
        </tr></thead>
      <tbody>{data.data.results.map(c => <tr key={c.id}>
          <td>{c.name}</td>
          <td>{c.email}</td>
          <td>{c.phone}</td>
          <td>{c.locale}</td>
          <td><Link href={`/ru/staff/orders?user=${c.id}`} className="text-link">Заказы →</Link></td>
        </tr>)}</tbody>
    </table></div><Pagination count={data.data.count} page={page} onChange={setPage}/></> : <EmptyState title="Клиентов по запросу нет"/>}
  <small>Итоги расходов клиента и отдельная история его заявок не предоставляются этим API.</small>
    </div>;
}
export function StaffSettings() {
    return <AdminOnly><SettingsContent /></AdminOnly>;
}
function SettingsContent() {
    const data = useApi<Settings>('staff/settings/');
    if (data.isPending)
        return <Skeleton />;
    if (data.error)
        return <ErrorState error={data.error} retry={() => void data.refetch()}/>;
    return <div className="stack">
  <PageHeader title="Настройки и готовность" description="Текущее состояние из backend environment. Веб-интерфейс не изменяет серверную конфигурацию."/>
  <Alert>Параметры меняются в окружении Django и применяются при перезапуске. Онлайн-оплата и скачивание файлов в этом бэкенде не реализованы.</Alert>
  <Card><dl className="settings-list">{Object.entries(data.data ?? {}).map(([key, value]) => <div key={key}>
        <dt>{key}</dt>
        <dd>{typeof value === 'boolean' ? value ? 'Включено' : 'Выключено' : value === null ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd>
      </div>)}</dl></Card>
    </div>;
}
export function Notifications() {
    const [page, setPage] = useState(1), [selected, setSelected] = useState<Email | null>(null);
    const data = useApi<PaginatedEmail>(`staff/notifications/?page=${page}`), task = useTask();
    return <div className="stack">
  <PageHeader title="Почтовые уведомления" description="Состояния отправки backend email. Повтор может доставить клиенту ещё одно письмо."/>
  {data.isPending ? <Skeleton /> : data.error ? <ErrorState error={data.error} retry={() => void data.refetch()}/> : data.data?.results.length ? <><div className="table-wrap"><table>
      <thead><tr>
          <th>Получатель</th>
          <th>Тема</th>
          <th>Статус</th>
          <th>Попытки</th>
          <th>Создано</th>
          <th />
        </tr></thead>
      <tbody>{data.data.results.map(mail => <tr key={mail.id}>
          <td>{mail.recipient}</td>
          <td>
            {mail.subject}
            <small>{mail.error_code}</small>
          </td>
          <td><StatusBadge status={mail.status}/></td>
          <td>{mail.attempts}</td>
          <td>{auditTime(mail.created_at)}</td>
          <td>{['FAILED', 'PENDING'].includes(mail.status) && <Button variant="secondary" onClick={() => setSelected(mail)}>Повторить</Button>}</td>
        </tr>)}</tbody>
    </table></div><Pagination count={data.data.count} page={page} onChange={setPage}/></> : <EmptyState />}
  <ConfirmDialog open={!!selected} onClose={() => setSelected(null)} title="Повторить отправку письма?" busy={task.busy} onConfirm={() => void task.run(async () => {
        if (!selected)
            return;
        await api(`staff/notifications/${selected.id}/retry/`, { method: 'POST', body: {} });
        await data.refetch();
        setSelected(null);
    })}>
    <p>{selected?.subject} → {selected?.recipient}</p>
    {task.error ? <ErrorState error={task.error}/> : null}
  </ConfirmDialog>
    </div>;
}
export function StaffPrivacy() {
    return <AdminOnly><PrivacyContent /></AdminOnly>;
}
function PrivacyContent() {
    const [page, setPage] = useState(1), [selected, setSelected] = useState<StaffPrivacy | null>(null);
    const data = useApi<PaginatedStaffPrivacy>(`staff/privacy-requests/?page=${page}`);
    return <div className="stack">
  <PageHeader title="Запросы по персональным данным" description="Изменение статуса не экспортирует и не удаляет данные автоматически."/>
  {data.isPending ? <Skeleton /> : data.error ? <ErrorState error={data.error} retry={() => void data.refetch()}/> : data.data?.results.length ? <><div className="table-wrap"><table>
      <thead><tr>
          <th>Пользователь</th>
          <th>Тип</th>
          <th>Комментарий</th>
          <th>Статус</th>
          <th />
        </tr></thead>
      <tbody>{data.data.results.map(r => <tr key={r.id}>
          <td>{r.user}</td>
          <td>{r.kind}</td>
          <td>{r.comment}</td>
          <td><StatusBadge status={r.status}/></td>
          <td><Button variant="secondary" onClick={() => setSelected(r)}>Ответить</Button></td>
        </tr>)}</tbody>
    </table></div><Pagination count={data.data.count} page={page} onChange={setPage}/></> : <EmptyState />}
  {selected && <PrivacyRespond request={selected} close={() => setSelected(null)} refresh={() => data.refetch()}/>}
    </div>;
}
function PrivacyRespond({ request, close, refresh }: {
    request: StaffPrivacy;
    close: () => void;
    refresh: () => Promise<unknown>;
}) {
    const [status, setStatus] = useState(request.status), [response, setResponse] = useState(request.response);
    const task = useTask();
    return <Modal open onClose={close} title="Ответ по запросу данных" busy={task.busy}><form className="stack" onSubmit={e => {
        e.preventDefault();
        void task.run(async () => {
            await api(`staff/privacy-requests/${request.id}/respond/`, { method: 'POST', body: { status, response } });
            await refresh();
            close();
        });
    }}>
    <p>{request.comment}</p>
    <Field label="Статус"><Select value={status} onChange={e => setStatus(e.target.value as typeof status)}>
        <option value="NEW">Новый</option>
        <option value="IN_PROGRESS">В работе</option>
        <option value="CLOSED">Закрыт</option>
      </Select></Field>
    <Field label="Ответ"><Textarea required value={response} onChange={e => setResponse(e.target.value)}/></Field>
    {task.error ? <ErrorState error={task.error}/> : null}
    <Button type="submit" busy={task.busy}>Сохранить ответ</Button>
  </form></Modal>;
}
