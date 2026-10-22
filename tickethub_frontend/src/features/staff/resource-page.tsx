'use client';
import { useEffect, useState, type ReactNode } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { useApi, useTask } from '@/lib/hooks';
import { api } from '@/lib/api/client';
import { ImagePicker, ImageUpload } from './image-upload';
import { imageRequestBody, validateImageSelection, IMAGE_UPLOAD_TIMEOUT_MS, type ImageSelection } from '@/lib/image-upload';
import { auditTime, fromLocalInput, toLocalInput } from '@/lib/datetime';
import { parseRubles, rubInput } from '@/lib/money';
import { text, mediaPath } from '@/lib/safe';
import { useStaffAccess } from '@/features/auth/session';
import { UnsavedGuard } from '@/components/ui/unsaved-guard';
import { useToast } from '@/components/ui/toast';
import { Alert, Button, Card, Checkbox, ConfirmDialog, Currency, EmptyState, ErrorState, Field, Input, PageHeader, Pagination, Skeleton, StatusBadge, Textarea } from '@/components/ui';
import { resources, columnNames, type Resource } from './resources';
import { StaffFields, type StaffPage, type StaffRow, rowLabel } from './fields';
export function AdminOnly({ children }: {
    children: ReactNode;
}) {
    const { admin, isAdmin } = useStaffAccess();
    if (admin.isPending)
        return <Skeleton />;
    return isAdmin ? <>{children}</> : <Alert tone="bad">Раздел доступен только администратору.</Alert>;
}
export function DataCell({ name, value }: {
    name: string;
    value: unknown;
}) {
    if (name === 'image') {
        const src = mediaPath(typeof value === 'string' ? value : null);
        return src ? <Image className="staff-cover-thumb" src={src} alt="Обложка" width={96} height={60} unoptimized /> : <span className="staff-cover-empty">Нет обложки</span>;
    }
    if (name.endsWith('_minor'))
        return <Currency value={typeof value === 'number' ? value : null}/>;
    if (typeof value === 'boolean')
        return <span>{value ? 'Да' : 'Нет'}</span>;
    if (name.endsWith('_at'))
        return <span>{auditTime(text(value))}</span>;
    if (['status', 'kind', 'mode', 'stock_basis', 'staff_role', 'order_state', 'payment_state', 'delivery_state'].includes(name))
        return <StatusBadge status={text(value)}/>;
    return <span className={name === 'id' || name === 'offer' ? 'mono small' : ''}>{value === null ? '—' : typeof value === 'string' || typeof value === 'number' ? String(value) : '—'}</span>;
}
export function ResourceList({ name }: {
    name: string;
}) {
    const resource = resources[name];
    if (!resource)
        return <Alert tone="bad">Раздел не найден</Alert>;
    const content = <ResourceListInner name={name} resource={resource}/>;
    return resource.admin ? <AdminOnly>{content}</AdminOnly> : content;
}
function ResourceListInner({ name, resource }: {
    name: string;
    resource: Resource;
}) {
    const params = useSearchParams(), router = useRouter(), path = usePathname();
    const [filters, setFilters] = useState<Record<string, unknown>>(() => Object.fromEntries(params));
    const page = Math.max(1, Number(params.get('page')) || 1);
    useEffect(() => {
        setFilters(Object.fromEntries(params));
    }, [params]);
    const query = new URLSearchParams();
    query.set('page', String(page));
    for (const field of resource.filters ?? []) {
        const v = params.get(field.name);
        if (v)
            query.set(field.name, v);
    }
    const data = useApi<StaffPage>(resource.endpoint + '?' + query);
    return <div className="stack">
  <PageHeader title={resource.title} description={data.data ? `Записей: ${data.data.count}` : undefined}><Link className="btn btn-primary" href={`/ru/staff/${name}/new`}>Создать</Link></PageHeader>
  {resource.filters?.length && <Card><form className="stack" onSubmit={e => {
        e.preventDefault();
        const q = new URLSearchParams();
        for (const [k, v] of Object.entries(filters))
            if (v)
                q.set(k, String(v));
        router.push(path + '?' + q);
    }}>
      <StaffFields fields={resource.filters} values={filters} setValue={(key, value) => setFilters({ ...filters, [key]: value })}/>
      <div className="actions">
        <Button type="submit">Применить</Button>
        <Button type="button" variant="ghost" onClick={() => {
        setFilters({});
        router.push(path);
    }}>Сбросить</Button>
      </div>
    </form></Card>}
  {data.isFetching && !data.isPending && <small>Обновляем данные…</small>}
  {data.isPending ? <Skeleton /> : data.error ? <ErrorState error={data.error} retry={() => void data.refetch()}/> : data.data?.results.length ? <><div className="table-wrap"><table>
      <thead><tr>
          {resource.columns.map(c => <th key={c}>{columnNames[c] ?? c}</th>)}
          <th>Действия</th>
        </tr></thead>
      <tbody>{data.data.results.map(row => <tr key={row.id}>
          {resource.columns.map(c => <td key={c}><DataCell name={c} value={row[c]}/></td>)}
          <td><Link className="text-link" href={`/ru/staff/${name}/${row.id}`}>Открыть →</Link></td>
        </tr>)}</tbody>
    </table></div><Pagination count={data.data.count} page={page} onChange={p => {
        const q = new URLSearchParams(params);
        q.set('page', String(p));
        router.push(path + '?' + q);
    }}/></> : <EmptyState title="Записей пока нет"/>}
    </div>;
}
export function ResourceEditor({ name, id }: {
    name: string;
    id: string;
}) {
    const resource = resources[name];
    if (!resource)
        return <Alert tone="bad">Раздел не найден</Alert>;
    const content = <ResourceEditorLoader name={name} id={id} resource={resource}/>;
    return resource.admin ? <AdminOnly>{content}</AdminOnly> : content;
}
function ResourceEditorLoader({ name, id, resource }: {
    name: string;
    id: string;
    resource: Resource;
}) {
    const isNew = id === 'new';
    const data = useApi<StaffRow>(resource.endpoint + id + '/', !isNew);
    const [revision, setRevision] = useState(0);
    const [contentDirty, setContentDirty] = useState(false), [imageBusy, setImageBusy] = useState(false);
    if (!isNew && data.isPending)
        return <Skeleton />;
    if (!isNew && data.error)
        return <ErrorState error={data.error} retry={() => void data.refetch()}/>;
    return <div className="stack">
  <Link href={`/ru/staff/${name}`} className="text-link">← {resource.title}</Link>
  <PageHeader title={isNew ? `Создать: ${resource.title}` : rowLabel(data.data!)}>{!isNew && name === 'seating-plans' && <Link className="btn btn-primary" href={`/ru/staff/seating-plans/${id}/editor`}>Открыть редактор мест</Link>}</PageHeader>
  {!isNew && resource.image && data.data && (name !== 'seating-plans' || data.data.status === 'DRAFT') && <ImageUpload endpoint={resource.endpoint + id + '/image/'} version={Number(data.data.version)} image={text(data.data.image)} source={text(data.data[name === 'events' ? 'image_rights_source' : 'rights_source'])} kind={name === 'events' ? 'event' : 'plan'} disabled={contentDirty} onBusyChange={setImageBusy} onSaved={async () => { await data.refetch(); }} />}
  <EntityForm key={`${id}.${revision}`} resource={resource} name={name} initial={data.data} disabled={imageBusy} onDirtyChange={setContentDirty} onSaved={async () => {
        await data.refetch();
        setRevision(v => v + 1);
    }}/>
  {!isNew && data.data && <EntityActions name={name} row={data.data} resource={resource} disabled={contentDirty || imageBusy}/>}
    </div>;
}
function EntityForm({ initial, resource, name, onSaved, onDirtyChange, disabled = false }: {
    initial?: StaffRow;
    resource: Resource;
    name: string;
    onSaved: () => Promise<void>;
    onDirtyChange: (dirty: boolean) => void;
    disabled?: boolean;
}) {
    const task = useTask(), router = useRouter(), notify = useToast(), client = useQueryClient();
    const [values, setValues] = useState<Record<string, unknown>>(() => Object.fromEntries(resource.fields.map(field => {
        let value = initial?.[field.name] ?? field.default ?? (field.type === 'boolean' ? false : '');
        if (field.type === 'money')
            value = rubInput(typeof value === 'number' ? value : null);
        if (field.type === 'datetime')
            value = toLocalInput(typeof value === 'string' ? value : null);
        return [field.name, value];
    })));
    const [expectedVersion, setExpectedVersion] = useState(initial?.version);
    const [cover, setCover] = useState<ImageSelection | null>(null);
    const [createdRecord, setCreatedRecord] = useState<StaffRow | null>(null);
    const readOnly = name === 'seating-plans' && !!initial && initial.status !== 'DRAFT' || name === 'content' && !!initial?.published_at;
    const [dirty, setDirty] = useState(false);
    useEffect(() => { onDirtyChange(dirty); }, [dirty, onDirtyChange]);
    useEffect(() => { if (!dirty) setExpectedVersion(initial?.version); }, [initial?.version, dirty]);
    // A dirty form keeps the version it was based on; pristine forms may refresh.
    return <Card>
  <UnsavedGuard dirty={dirty}/>
  <form className="stack" onSubmit={e => {
        e.preventDefault();
        if (disabled) return;
        void task.run(async () => {
            // Validate the selected cover BEFORE creating an event; do not create
            // a duplicate event when only the second (image) request fails.
            if (cover) { await validateImageSelection(cover, 1); }
            const body: Record<string, unknown> = {};
            for (const field of resource.fields) {
                if (field.createOnly && initial)
                    continue;
                let value = values[field.name];
                if (field.type === 'password' && !value)
                    continue;
                if (value === '' || value === undefined) {
                    if (field.nullable)
                        body[field.name] = null;
                    else if (field.type !== 'number' && !field.required)
                        body[field.name] = '';
                    else if (field.required)
                        body[field.name] = value;
                    continue;
                }
                if (field.type === 'money')
                    value = parseRubles(String(value));
                if (field.type === 'number')
                    value = Number(value);
                if (field.type === 'datetime')
                    value = fromLocalInput(String(value));
                if (field.name === 'fan_id_required')
                    value = value === true || value === 'true';
                body[field.name] = value;
            }
            if (initial && resource.versioned)
                body.expected_version = expectedVersion;
            const result = createdRecord ?? await api<StaffRow>(resource.endpoint + (initial ? initial.id + '/' : ''), { method: initial ? 'PATCH' : 'POST', body });
            if (!initial) setCreatedRecord(result);
            if (!initial && name === 'events' && cover) {
                await api<StaffRow>(`${resource.endpoint}${result.id}/image/`, { method: 'POST', body: imageRequestBody(cover, Number(result.version)), timeoutMs: IMAGE_UPLOAD_TIMEOUT_MS });
                setCover(null);
            }
            setDirty(false);
            notify('Сохранено');
            await client.invalidateQueries({ queryKey: ['api'] });
            if (!initial)
                router.replace(`/ru/staff/${name}/${result.id}`);
            else
                await onSaved();
        });
    }}>
    {readOnly && <Alert>Опубликованная версия доступна только для чтения. Создайте новую версию.</Alert>}
    {!initial && name === 'events' && <section className="stack new-event-cover"><h2>Обложка мероприятия</h2><ImagePicker value={cover} onChange={value => { setCover(value); setDirty(true); task.setError(null); }} disabled={task.busy} error={task.error} /><small>Можно добавить сейчас или после создания мероприятия.</small></section>}
    {createdRecord && name === 'events' && task.error && <Alert>Мероприятие уже создано. Не удалось завершить загрузку обложки; повторная попытка не создаст второе мероприятие. <Link className="text-link" href={`/ru/staff/events/${createdRecord.id}#event-cover`}>Открыть сохранённую карточку →</Link></Alert>}
    <StaffFields fields={resource.fields} values={values} setValue={(key, value) => {
        setValues({ ...values, [key]: value });
        setDirty(true);
    }} error={task.error} isNew={!initial} disabled={disabled || !!readOnly || task.busy || !!createdRecord}/>
    {dirty && <small>Есть несохранённые изменения. Сохраните их перед переходом на другую страницу.</small>}
    {task.error ? <ErrorState error={task.error}/> : null}
    {!readOnly && <Button busy={task.busy} disabled={disabled} type="submit">{createdRecord ? cover ? 'Повторить загрузку обложки' : name === 'events' ? 'Открыть сохранённое мероприятие' : 'Открыть сохранённую запись' : !initial && name === 'events' ? cover ? 'Создать мероприятие с обложкой' : 'Создать мероприятие' : 'Сохранить'}</Button>}
  </form>
    </Card>;
}
function EntityActions({ name, row, resource, disabled = false }: {
    name: string;
    row: StaffRow;
    resource: Resource;
    disabled?: boolean;
}) {
    const task = useTask(), client = useQueryClient(), router = useRouter(), notify = useToast();
    const [action, setAction] = useState(''), [reason, setReason] = useState(''), [valid, setValid] = useState(false), [until, setUntil] = useState('');
    async function perform() {
        const body: Record<string, unknown> = action === 'clone-version' || name === 'content' ? {} : { expected_version: row.version };
        if (['block', 'unblock', 'renew-allocation'].includes(action)) {
            body.reason = reason;
            body.confirmed_valid = valid;
        }
        if (action === 'renew-allocation')
            body.allocation_until = fromLocalInput(until);
        const result = await api<StaffRow>(`${resource.endpoint}${row.id}/${action}/`, { method: 'POST', body });
        await client.invalidateQueries({ queryKey: ['api'] });
        notify('Действие выполнено');
        setAction('');
        if (action === 'clone-version')
            router.push(`/ru/staff/seating-plans/${result.id}/editor`);
    }
    return <><Card>
  <h2>Действия</h2>
  <fieldset className="actions" disabled={disabled}>
    {name === 'events' && <Button variant="secondary" onClick={() => setAction(row.is_published ? 'unpublish' : 'publish')}>{row.is_published ? 'Снять с публикации' : 'Опубликовать'}</Button>}
    {name === 'events' && row.visibility === 'PUBLIC' && row.is_published === true && <Link className="btn btn-ghost" href={`/ru/events/${text(row.slug)}`} target="_blank">Клиентская страница ↗</Link>}
    {name === 'seating-plans' && <><Button variant="secondary" onClick={() => setAction('clone-version')}>Клонировать версию</Button>{row.status === 'DRAFT' && <Button onClick={() => setAction('publish')}>Опубликовать схему</Button>}</>}
    {name === 'content' && !row.published_at && row.is_published !== true && <Button onClick={() => setAction('publish')}>Опубликовать документ</Button>}
    {name === 'tickets' && <>{['AVAILABLE', 'BLOCKED'].includes(text(row.status)) && <Button variant="secondary" onClick={() => setAction(row.status === 'BLOCKED' ? 'unblock' : 'block')}>{row.status === 'BLOCKED' ? 'Разблокировать' : 'Заблокировать'}</Button>}{row.stock_basis === 'EXCLUSIVE_ALLOCATION' && <Button variant="secondary" onClick={() => setAction('renew-allocation')}>Продлить закрепление</Button>}</>}
  </fieldset>
  <small>Статусы меняются только серверными действиями. Сохранение формы не заменяет публикацию или продажу.</small>
    </Card><ConfirmDialog open={!!action} title={`Подтвердить: ${action}`} onClose={() => setAction('')} onConfirm={() => void task.run(perform)} busy={task.busy} danger={['block', 'unpublish'].includes(action)}>
  <p>{rowLabel(row)}</p>
  {['block', 'unblock', 'renew-allocation'].includes(action) && <div className="stack">
    <Field label="Причина"><Textarea required value={reason} onChange={e => setReason(e.target.value)}/></Field>
    <Checkbox checked={valid} onChange={e => setValid(e.target.checked)}>Подтверждаю действительность билета / закрепления</Checkbox>
    {action === 'renew-allocation' && <Field label="Закрепление до (время этого устройства)"><Input required type="datetime-local" value={until} onChange={e => setUntil(e.target.value)}/></Field>}
  </div>}
  {task.error ? <ErrorState error={task.error}/> : null}
    </ConfirmDialog></>;
}
