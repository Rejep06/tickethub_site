'use client';
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Plus, Tag } from 'lucide-react';
import { useApi, useTask } from '@/lib/hooks';
import { api } from '@/lib/api/client';
import { useStaffAccess } from '@/features/auth/session';
import type { PaginatedPromoCode, PromoCode, PromoCodeInput } from '@/lib/api/generated';
import { auditTime, toLocalInput, fromLocalInput } from '@/lib/datetime';
import { formatMoney, parseRubles, rubInput } from '@/lib/money';
import { normalizedPromoCode, validPromoCode } from '@/lib/promotions';
import { Alert, Badge, Button, Card, Checkbox, EmptyState, ErrorState, Field, FieldErrors, Input, Modal, PageHeader, Pagination, Select, Skeleton, Textarea } from '@/components/ui';
import { ReferencePicker } from './fields';

export function StaffPromoCodes() {
    const { isAdmin } = useStaffAccess();
    const [search, setSearch] = useState(''), [query, setQuery] = useState(''), [page, setPage] = useState(1);
    const [editing, setEditing] = useState<PromoCode | 'new' | null>(null);
    const result = useApi<PaginatedPromoCode>(`staff/promo-codes/?page=${page}&q=${encodeURIComponent(query)}`);
    return <div className="stack">
        <PageHeader title="Промокоды" description="Скидка рассчитывается при оформлении и сохраняется в заказе. Онлайн-оплата не требуется.">
            {isAdmin && <Button onClick={() => setEditing('new')}><Plus size={18}/>Создать промокод</Button>}
        </PageHeader>
        <Card><form className="actions" onSubmit={e => { e.preventDefault(); setPage(1); setQuery(search); }}>
            <Field label="Поиск по коду"><Input maxLength={40} value={search} onChange={e => setSearch(e.target.value)} placeholder="Например, MATCH10"/></Field>
            <Button variant="secondary" type="submit">Найти</Button>
            <Button type="button" variant="ghost" onClick={() => void result.refetch()}>Обновить</Button>
        </form></Card>
        {!isAdmin && <Alert>Менеджеры могут просматривать условия. Создание и изменение доступны администратору.</Alert>}
        {result.isPending ? <Skeleton/> : result.error ? <ErrorState error={result.error} retry={() => void result.refetch()}/> : result.data?.results.length ? <>
            <div className="table-wrap"><table><thead><tr><th>Промокод</th><th>Скидка</th><th>Период</th><th>Ограничения</th><th>Использован</th><th/></tr></thead>
                <tbody>{result.data.results.map(promo => <tr key={promo.id}>
                    <td><strong>{promo.code}</strong><small>{promo.description}</small><Badge tone={promo.is_active ? 'good' : 'neutral'}>{promo.is_active ? 'Включён' : 'Отключён'}</Badge></td>
                    <td>{promo.kind === 'PERCENT' ? `${promo.value}%` : formatMoney(promo.value)}<small>Заказ от {formatMoney(promo.minimum_total_minor)}</small>{promo.maximum_discount_minor !== null && <small>Не более {formatMoney(promo.maximum_discount_minor)}</small>}</td>
                    <td><small>С {promo.starts_at ? auditTime(promo.starts_at) : 'момента создания'}</small><small>До {promo.ends_at ? auditTime(promo.ends_at) : 'отключения'}</small></td>
                    <td>{promo.event ? 'На одно мероприятие' : 'На все мероприятия'}<small>На клиента: {promo.per_user_limit ?? 'без лимита'}</small></td>
                    <td>{promo.usage_count ?? 0} / {promo.usage_limit ?? 'без лимита'}</td>
                    <td>{isAdmin && <Button variant="secondary" onClick={() => setEditing(promo)}>Изменить</Button>}</td>
                </tr>)}</tbody></table></div>
            <Pagination count={result.data.count} page={page} onChange={setPage}/>
        </> : <EmptyState title="Промокодов пока нет"><p>Создайте код со скидкой в процентах или рублях.</p></EmptyState>}
        <Card className="stack-sm"><h3><Tag size={18}/> Как учитываются применения</h3><p>Одно применение — один созданный заказ. Проверка промокода и резерв мест лимит не расходуют. Повторная отправка того же заказа не списывает применение второй раз.</p><p>Отмена или возврат не восстанавливают лимит. С персональными предложениями менеджера промокоды не суммируются. Скидка 100% и полностью бесплатные заказы не поддерживаются.</p></Card>
        {editing !== null && <PromoForm key={typeof editing === 'string' ? 'new' : `${editing.id}.${editing.version}`} initial={editing === 'new' ? null : editing} close={() => setEditing(null)}/>}
    </div>;
}

function nullableLimit(value: string): number | null {
    if (!value.trim()) return null;
    if (!/^\d+$/.test(value) || !Number.isSafeInteger(Number(value)) || Number(value) < 1 || Number(value) > 2147483647) throw new Error('PROMO_LIMIT_INPUT');
    return Number(value);
}
function PromoForm({ initial, close }: { initial: PromoCode | null; close: () => void }) {
    const client = useQueryClient(), task = useTask();
    const [code, setCode] = useState(initial?.code ?? ''), [description, setDescription] = useState(initial?.description ?? '');
    const [kind, setKind] = useState<'PERCENT' | 'FIXED'>(initial?.kind ?? 'PERCENT');
    const [value, setValue] = useState(initial ? initial.kind === 'PERCENT' ? String(initial.value) : rubInput(initial.value) : '');
    const [minimum, setMinimum] = useState(rubInput(initial?.minimum_total_minor ?? 0)), [maximum, setMaximum] = useState(rubInput(initial?.maximum_discount_minor));
    const [starts, setStarts] = useState(toLocalInput(initial?.starts_at)), [ends, setEnds] = useState(toLocalInput(initial?.ends_at));
    const [limit, setLimit] = useState(initial?.usage_limit == null ? '' : String(initial.usage_limit));
    const [perUser, setPerUser] = useState(initial ? initial.per_user_limit == null ? '' : String(initial.per_user_limit) : '1');
    const [event, setEvent] = useState(initial?.event ?? ''), [active, setActive] = useState(initial?.is_active ?? true);
    async function save() {
        if (!validPromoCode(code)) throw new Error('PROMO_INVALID');
        const amount = kind === 'PERCENT' ? Number(value) : parseRubles(value);
        if (!Number.isSafeInteger(amount) || amount < 1 || (kind === 'PERCENT' && amount > 99)) throw new Error('PROMO_VALUE_INPUT');
        const body: PromoCodeInput = {
            code: normalizedPromoCode(code), description, kind, value: amount,
            minimum_total_minor: parseRubles(minimum || '0'), maximum_discount_minor: maximum.trim() ? parseRubles(maximum) : null,
            starts_at: starts ? fromLocalInput(starts) : null, ends_at: ends ? fromLocalInput(ends) : null,
            usage_limit: nullableLimit(limit), per_user_limit: nullableLimit(perUser), event: event || null, is_active: active,
            ...(initial ? { expected_version: initial.version } : {})
        };
        await api<PromoCode>(initial ? `staff/promo-codes/${initial.id}/` : 'staff/promo-codes/', { method: initial ? 'PATCH' : 'POST', body });
        await client.invalidateQueries({ queryKey: ['api'] });
        close();
    }
    return <Modal open onClose={close} title={initial ? `Промокод ${initial.code}` : 'Новый промокод'} busy={task.busy}>
        <form className="stack" onSubmit={e => { e.preventDefault(); void task.run(save); }}>
            <fieldset disabled={task.busy} className="promo-form-fields form-grid">
                <div><Field label="Код" hint="3–40 символов: латинские буквы, цифры, дефис, подчёркивание."><Input required readOnly={!!initial} maxLength={40} value={code} onChange={e => setCode(e.target.value)} autoCapitalize="characters"/></Field><FieldErrors error={task.error} name="code"/></div>
                <Field label="Тип скидки"><Select value={kind} onChange={e => { setKind(e.target.value as 'PERCENT' | 'FIXED'); setValue(''); }}><option value="PERCENT">Процент</option><option value="FIXED">Сумма в рублях</option></Select></Field>
                <div><Field label={kind === 'PERCENT' ? 'Скидка, % (1–99)' : 'Скидка, ₽'}><Input required inputMode={kind === 'PERCENT' ? 'numeric' : 'decimal'} value={value} onChange={e => setValue(e.target.value)}/></Field><FieldErrors error={task.error} name="value"/></div>
                <Field label="Минимальная сумма заказа, ₽"><Input inputMode="decimal" value={minimum} onChange={e => setMinimum(e.target.value)}/></Field>
                <Field label="Максимальная скидка, ₽" hint="Пусто — без дополнительного ограничения."><Input inputMode="decimal" value={maximum} onChange={e => setMaximum(e.target.value)}/></Field>
                <Field label="Общий лимит применений" hint="Пусто — без лимита."><Input type="number" min="1" step="1" value={limit} onChange={e => setLimit(e.target.value)}/></Field>
                <Field label="Лимит на клиента" hint="Пусто — без лимита. По умолчанию одно применение."><Input type="number" min="1" step="1" value={perUser} onChange={e => setPerUser(e.target.value)}/></Field>
                <Field label="Действует с" hint="В часовом поясе этого устройства; пусто — сразу."><Input type="datetime-local" value={starts} onChange={e => setStarts(e.target.value)}/></Field>
                <Field label="Действует до" hint="Пусто — до отключения."><Input type="datetime-local" value={ends} onChange={e => setEnds(e.target.value)}/></Field>
                <div className="field-wide"><Field label="Мероприятие" hint="Пусто — на все мероприятия."><ReferencePicker path="staff/events/" value={event} onChange={setEvent}/></Field><FieldErrors error={task.error} name="event"/></div>
                <div className="field-wide"><Field label="Внутреннее описание"><Textarea maxLength={300} value={description} onChange={e => setDescription(e.target.value)}/></Field></div>
                <Checkbox checked={active} onChange={e => setActive(e.target.checked)}>Промокод включён</Checkbox>
            </fieldset>
            {initial && <Alert>Новые условия действуют для следующих оформлений. Суммы уже созданных заказов не изменятся. Для отключения снимите флажок выше.</Alert>}
            {task.error ? <ErrorState error={task.error}/> : null}
            <div className="actions"><Button type="submit" busy={task.busy}>Сохранить</Button><Button type="button" variant="ghost" disabled={task.busy} onClick={close}>Закрыть</Button></div>
        </form>
    </Modal>;
}
