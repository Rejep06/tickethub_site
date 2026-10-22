'use client';
import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { Save, Undo2, Redo2, Copy, Download, Plus, Rows3, Upload, Trash2, ZoomIn, ZoomOut, Maximize, RefreshCw } from 'lucide-react';
import { useApi, useTask } from '@/lib/hooks';
import { ApiError } from '@/lib/api/client';
import { editorApi, type EditorSnapshot, type EditorSeatInput } from '@/lib/api/editor';
import { mediaPath } from '@/lib/safe';
import { assertBatch, changeCount, clearAffectedAdjacency, coordinate, draftChanges, newSeatDrafts, normalizeSeat, planChanges, seatDrafts, seatIssues, seatsCsv, transformSeats, validateSeats, type DraftSeat, type Transform } from '@/lib/seat-editor';
import { useToast } from '@/components/ui/toast';
import { UnsavedGuard } from '@/components/ui/unsaved-guard';
import { Alert, Badge, Button, Card, Checkbox, ConfirmDialog, EmptyState, ErrorState, Field, Input, Modal, PageHeader, Pagination, Select, Skeleton, StatusBadge, Tabs } from '@/components/ui';
import { ImageUpload } from './image-upload';
import { EditorCanvas, type CanvasTool } from './seat-editor-canvas';
import { SeatBatchDialog } from './seat-editor-batch';
interface History { past: DraftSeat[][]; current: DraftSeat[]; future: DraftSeat[][] }
function download(contents: string, name: string, type: string) {
    const url = URL.createObjectURL(new Blob([contents], { type }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = name;
    document.body.append(anchor); anchor.click(); anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function SeatEditor({ id }: { id: string }) {
    const snapshot = useApi<EditorSnapshot>(`staff/plans/${id}/preview/`);
    if (snapshot.isPending) return <Skeleton />;
    if (snapshot.error && !snapshot.data) return <ErrorState error={snapshot.error} retry={() => void snapshot.refetch()} />;
    if (!snapshot.data) return null;
    return <SeatWorkspace key={id} initial={snapshot.data} remoteVersion={snapshot.data.plan.version} />;
}
function SeatWorkspace({ initial, remoteVersion }: { initial: EditorSnapshot; remoteVersion: number }) {
    const [baseline, setBaseline] = useState(initial), [original, setOriginal] = useState(() => seatDrafts(initial.seats));
    const [history, setHistory] = useState<History>(() => ({ past: [], current: original, future: [] }));
    const [selected, setSelected] = useState(new Set<string>()), [tool, setTool] = useState<CanvasTool>('select'), [zoom, setZoom] = useState(1), [aspect, setAspect] = useState(1.6);
    const [sector, setSector] = useState(''), [row, setRow] = useState(''), [page, setPage] = useState(1), [batch, setBatch] = useState<'block' | 'csv' | null>(null);
    const [action, setAction] = useState<'reload' | 'delete' | 'publish' | 'clone' | null>(null), [point, setPoint] = useState<{ x: number; y: number } | null>(null);
    const [imageBusy, setImageBusy] = useState(false), [onlyProblems, setOnlyProblems] = useState(false);
    const [localError, setLocalError] = useState<unknown>(null), [conflict, setConflict] = useState(false), [pendingReload, setPendingReload] = useState<'saved' | 'unknown' | null>(null);
    const task = useTask(), notify = useToast(), client = useQueryClient(), router = useRouter();
    const plan = baseline.plan, seats = history.current;
    const changes = useMemo(() => draftChanges(original, seats, plan.version), [original, seats, plan.version]);
    const count = changeCount(changes), dirty = count > 0;
    const issues = useMemo(() => seatIssues(seats), [seats]);
    const issuesByKey = useMemo(() => new Map(issues.map(issue => [issue.key, issue])), [issues]);
    const newer = remoteVersion > plan.version;
    const canEdit = plan.status === 'DRAFT' && !task.busy && !imageBusy && !pendingReload && !conflict && !newer;
    const chosen = useMemo(() => seats.filter(seat => selected.has(seat.key)), [seats, selected]);
    const sectors = useMemo(() => [...new Set(seats.map(seat => seat.sector).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ru', { numeric: true })), [seats]);
    const rows = useMemo(() => [...new Set(seats.filter(seat => !sector || seat.sector === sector).map(seat => seat.row).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ru', { numeric: true })), [seats, sector]);
    const visible = useMemo(() => seats.filter(seat => (!sector || seat.sector === sector) && (!row || seat.row === row) && (!onlyProblems || issuesByKey.has(seat.key))), [seats, sector, row, onlyProblems, issuesByKey]);
    const displayPage = Math.min(page, Math.max(1, Math.ceil(visible.length / 24)));
    function reset(snapshot: EditorSnapshot) {
        const next = seatDrafts(snapshot.seats);
        setBaseline(snapshot); setOriginal(next); setHistory({ past: [], current: next, future: [] });
        setSelected(new Set()); setOnlyProblems(false); setConflict(false); setPendingReload(null); setLocalError(null); task.setError(null);
    }
    async function reload() {
        const next = await editorApi.snapshot(plan.id);
        reset(next);
        await client.invalidateQueries({ queryKey: ['api'] });
    }
    function commit(next: DraftSeat[]) {
        if (!canEdit) return;
        // Existing imported records can be incomplete. Validate only actual mutations,
        // otherwise an unrelated bad row prevents repairing the first bad seat.
        const normalized = clearAffectedAdjacency(seats, next);
        const diff = planChanges(original, normalized, plan.version);
        if (changeCount(diff) > 2000) throw new Error('BATCH_LIMIT');
        setHistory(current => ({ past: [...current.past, current.current].slice(-20), current: normalized, future: [] }));
        setLocalError(null);
    }
    function edit(operation: () => void) { try { operation(); } catch (error) { setLocalError(error); } }
    function transform(keys: Set<string>, operation: Transform) { edit(() => commit(transformSeats(seats, keys, { aspect, ...operation }))); }
    function undo() { if (!canEdit || !history.past.length) return; setHistory(current => ({ past: current.past.slice(0, -1), current: current.past.at(-1)!, future: [current.current, ...current.future] })); setLocalError(null); }
    function redo() { if (!canEdit || !history.future.length) return; setHistory(current => ({ past: [...current.past, current.current].slice(-20), current: current.future[0], future: current.future.slice(1) })); setLocalError(null); }
    async function save() {
        if (!dirty || !canEdit || conflict || newer) return;
        const payload = planChanges(original, seats, plan.version); assertBatch(payload);
        let response;
        try { response = await editorApi.save(plan.id, payload); }
        catch (error) {
            if (error instanceof ApiError && error.code === 'VERSION_CONFLICT') setConflict(true);
            if (error instanceof ApiError && (error.status === 0 || error.status >= 500 || ['PLAN_IMMUTABLE', 'PLAN_IN_USE'].includes(error.code))) setPendingReload('unknown');
            throw error;
        }
        // The write succeeded. Never resend it if the subsequent refresh fails.
        setPendingReload('saved');
        notify(`Сохранено: добавлено ${response.created}, изменено ${response.updated}, удалено ${response.deleted}`);
        await reload();
    }
    async function perform() {
        if (action === 'reload') await reload();
        if (action === 'delete') { commit(seats.filter(seat => !selected.has(seat.key))); setSelected(new Set()); }
        if (action === 'publish') {
            validateSeats(seats);
            const published = await editorApi.publish(plan.id, plan.version);
            reset({ plan: published, seats: baseline.seats });
            await client.invalidateQueries({ queryKey: ['api'] });
            notify('Схема опубликована');
        }
        if (action === 'clone') {
            const copy = await editorApi.clone(plan.id);
            await client.invalidateQueries({ queryKey: ['api'] });
            router.push(`/ru/staff/seating-plans/${copy.id}/editor`);
        }
        setAction(null);
    }
    return <div className="stack seat-workspace">
        <UnsavedGuard dirty={dirty} />
        <Link href={`/ru/staff/seating-plans/${plan.id}`} className="text-link">← Свойства схемы</Link>
        <PageHeader title={plan.name} description={`Версия ${plan.version} · ${seats.length} мест · ${chosen.length} выбрано`}>
            <StatusBadge status={plan.status} />
            {plan.status === 'DRAFT' && <Button busy={task.busy} disabled={!dirty || conflict || newer || imageBusy || !!pendingReload} onClick={() => void task.run(save)}><Save size={18} />Сохранить изменения</Button>}
            <Button variant="secondary" disabled={dirty || task.busy || imageBusy || !!pendingReload} onClick={() => setAction('clone')}><Copy size={17} />Создать копию</Button>
        </PageHeader>
        {plan.status !== 'DRAFT' && <Alert>Схема доступна только для просмотра. Для изменения мест создайте копию.</Alert>}
        {(conflict || newer) && <Alert tone="bad">Схема изменилась на сервере. Ваши правки остались на холсте, но сохранение поверх чужих изменений заблокировано. Скачайте черновик и загрузите актуальную версию.</Alert>}
        {pendingReload && <Alert>{pendingReload === 'saved' ? 'Изменения сохранены, но актуальную схему пока не удалось получить. Загрузите её снова — повторное сохранение не отправляется.' : 'Результат операции требует проверки. Прежде чем продолжать, загрузите актуальную схему с сервера.'}</Alert>}
        {(conflict || newer || pendingReload) && <div className="actions"><Button variant="secondary" disabled={task.busy || imageBusy} onClick={() => setAction('reload')}>Загрузить актуальную схему</Button><Button variant="ghost" onClick={() => download(JSON.stringify({ plan_id: plan.id, expected_version: plan.version, saved: false, seats }, null, 2), `plan-${plan.id}-draft.json`, 'application/json')}>Скачать черновик JSON</Button></div>}
        {issues.length > 0 && <Alert>
            <div className="stack seat-data-warning">
                <strong>Проверьте данные мест: {issues.length}</strong>
                <p>Схема открыта. У части мест не заполнены поля, превышены ограничения или есть повторы. Ничего не удалено и не перенумеровано: выберите место в списке и исправьте его свойства.</p>
                <Button type="button" variant="secondary" onClick={() => {
                    setOnlyProblems(true); setSector(''); setRow(''); setPage(1);
                    setSelected(new Set([issues[0].key]));
                    requestAnimationFrame(() => document.getElementById('plan-seat-list')?.scrollIntoView({ block: 'start', behavior: 'smooth' }));
                }}>Показать места с ошибками</Button>
                <details><summary>Что нужно исправить</summary><div className="stack small">
                    {issues.slice(0, 8).map(issue => {
                        const seat = seats.find(item => item.key === issue.key)!;
                        return <p key={issue.key}><strong>{seat.sector || 'Без сектора'} · ряд {seat.row || '—'} · место {seat.number || '—'}:</strong> {issue.messages.join(' ')}</p>;
                    })}
                    {issues.length > 8 && <p>Остальные места доступны по фильтру «Только с ошибками» в списке.</p>}
                </div></details>
            </div>
        </Alert>}
        {task.error ? <ErrorState error={task.error} /> : null}{localError ? <ErrorState error={localError} /> : null}
        <div className="plan-editor-layout">
            <div className="stack">
                <Card className="plan-stage">
                    <div className="plan-toolbar"><Tabs value={tool} onChange={value => setTool(value as CanvasTool)} options={[{ value: 'select', label: 'Выбрать / двигать' }, { value: 'box', label: 'Рамка' }, { value: 'pan', label: 'Рука' }, ...(canEdit ? [{ value: 'add', label: 'Место' }] : [])]} /><div className="actions"><Button variant="ghost" aria-label="Отменить изменение" disabled={!canEdit || !history.past.length} onClick={undo}><Undo2 size={18} /></Button><Button variant="ghost" aria-label="Повторить изменение" disabled={!canEdit || !history.future.length} onClick={redo}><Redo2 size={18} /></Button></div></div>
                    <div className="plan-toolbar"><div className="actions"><Button variant="secondary" disabled={!canEdit} onClick={() => setBatch('block')}><Rows3 size={18} />Блок рядов</Button><Button variant="ghost" disabled={!canEdit} onClick={() => setBatch('csv')}><Upload size={17} />Импорт CSV</Button></div><div className="actions"><Button variant="ghost" aria-label="Отдалить" disabled={zoom <= 1} onClick={() => setZoom(Math.max(1, zoom - .5))}><ZoomOut size={17} /></Button><span className="mono small">{Math.round(zoom * 100)}%</span><Button variant="ghost" aria-label="Приблизить" disabled={zoom >= 6} onClick={() => setZoom(Math.min(6, zoom + .5))}><ZoomIn size={17} /></Button><Button variant="ghost" aria-label="Показать целиком" onClick={() => setZoom(1)}><Maximize size={17} /></Button></div></div>
                    <EditorCanvas seats={visible} selected={selected} onSelect={setSelected} onMove={(keys, dx, dy) => transform(keys, { dx, dy })} onAdd={setPoint} image={mediaPath(plan.image)} tool={tool} zoom={zoom} setZoom={setZoom} editable={canEdit} onAspect={setAspect} />
                    <div className="plan-statusbar"><span><i className="legend-dot" />Место <i className="legend-dot legend-selected" />Выбрано</span><span>Alt + перетаскивание — холст · Ctrl + колесо — масштаб</span></div>
                </Card>
                <Card className="stack" id="plan-seat-list"><div className="split"><h2>Список мест</h2><Button variant="ghost" disabled={!seats.length} onClick={() => download(seatsCsv(chosen.length ? chosen : seats), `plan-${plan.id}-${chosen.length ? 'selection' : 'all'}.csv`, 'text/csv;charset=utf-8')}><Download size={17} />Экспорт CSV</Button></div>
                    <div className="grid-2"><Field label="Сектор"><Select value={sector} onChange={event => { setSector(event.target.value); setRow(''); setPage(1); }}><option value="">Все секторы</option>{sectors.map(value => <option key={value}>{value}</option>)}</Select></Field><Field label="Ряд"><Select value={row} onChange={event => { setRow(event.target.value); setPage(1); }}><option value="">Все ряды</option>{rows.map(value => <option key={value}>{value}</option>)}</Select></Field></div>
                    <Checkbox checked={onlyProblems} onChange={event => { setOnlyProblems(event.target.checked); setPage(1); }}>Только с ошибками ({issues.length})</Checkbox>
                    <div className="actions"><Button variant="secondary" disabled={!visible.length} onClick={() => setSelected(new Set(visible.map(seat => seat.key)))}>Выбрать все видимые ({visible.length})</Button><Button variant="ghost" onClick={() => setSelected(new Set())}>Снять выделение</Button><small>Выбрано: {chosen.length}</small></div>
                    {visible.length ? <div className="table-wrap"><table><thead><tr><th>Выбор</th><th>Сектор</th><th>Ряд</th><th>Место</th><th>X / Y, %</th><th>Состояние</th></tr></thead><tbody>{visible.slice((displayPage - 1) * 24, displayPage * 24).map(seat => <tr key={seat.key} className={selected.has(seat.key) ? 'selected-row' : ''}><td><Checkbox aria-label={`Выбрать ${seat.sector}, ряд ${seat.row}, место ${seat.number}`} checked={selected.has(seat.key)} onChange={event => { const keys = new Set(selected); if (event.target.checked) keys.add(seat.key); else keys.delete(seat.key); setSelected(keys); }}><span className="sr-only">Выбрать</span></Checkbox></td><td>{seat.sector || <span className="muted">Не указан</span>}</td><td>{seat.row || <span className="muted">Не указан</span>}</td><td><Button variant="ghost" onClick={() => setSelected(new Set([seat.key]))}>{seat.number || 'Не указан'}</Button></td><td className="mono small">{coordinateLabel(seat.x)} / {coordinateLabel(seat.y)}</td><td>{issuesByKey.has(seat.key) ? <Badge tone="warn">Проверьте данные</Badge> : !seat.id ? <Badge tone="accent">Новое</Badge> : 'На схеме'}</td></tr>)}</tbody></table></div> : <EmptyState title="Здесь пока нет мест" />}
                    <Pagination count={visible.length} page={displayPage} onChange={setPage} />
                </Card>
                {plan.status === 'DRAFT' && <ImageUpload endpoint={`staff/plans/${plan.id}/image/`} version={plan.version} image={plan.image} source={plan.rights_source} kind="plan" disabled={dirty || task.busy || !!pendingReload || newer || conflict} onBusyChange={setImageBusy} onSaved={reload} />}
            </div>
            <aside className="stack plan-inspector">
                <Card className="stack"><span className="eyebrow">ИНСТРУМЕНТЫ</span><h2>{chosen.length === 1 ? 'Свойства места' : 'Выделение'}</h2>
                    {chosen.length === 1 && issuesByKey.has(chosen[0].key) && <Alert>{issuesByKey.get(chosen[0].key)!.messages.map((message, index) => <p key={index}>{message}</p>)}</Alert>}
                    {chosen.length === 1 ? <SeatProperties key={JSON.stringify(chosen[0])} seat={chosen[0]} disabled={!canEdit} onApply={value => { commit(seats.map(seat => seat.key === chosen[0].key ? { ...seat, ...normalizeSeat(value) } : seat)); }} /> : <p className="muted">{chosen.length ? `Выбрано ${chosen.length} мест. Можно перемещать, поворачивать и менять их нумерацию.` : 'Выберите место на холсте или в списке. Shift добавляет места к выделению.'}</p>}
                    {!chosen.length && canEdit && <Button variant="secondary" onClick={() => setPoint({ x: .5, y: .5 })}><Plus size={17} />Добавить место</Button>}
                </Card>
                {chosen.length > 0 && <SelectionTools disabled={!canEdit} chosen={chosen} onTransform={operation => transform(selected, operation)} onRename={(values, start) => {
                    const counters = new Map<string, number>();
                    const ordered = [...chosen].sort((a, b) => a.sector.localeCompare(b.sector, 'ru', { numeric: true }) || a.row.localeCompare(b.row, 'ru', { numeric: true }) || Number(a.x) - Number(b.x));
                    const changed = new Map(ordered.map(seat => {
                        const next = { ...seat, ...(values.sector ? { sector: values.sector } : {}), ...(values.row ? { row: values.row } : {}) };
                        if (start !== null) { const group = JSON.stringify([next.sector, next.row]); const n = counters.get(group) ?? start; counters.set(group, n + 1); next.number = String(n); }
                        return [seat.key, next];
                    }));
                    commit(seats.map(seat => changed.get(seat.key) ?? seat));
                }} onDelete={() => setAction('delete')} />}
                <Card className="stack"><h3>Готовность схемы</h3><p>{dirty ? `${count} изменений ещё не сохранено.` : 'Локальных изменений нет.'}</p><p className="muted small">Фоновая картинка необязательна. Опубликуйте схему и привяжите её к мероприятию до добавления билетов.</p><Button variant="secondary" disabled={plan.status !== 'DRAFT' || dirty || issues.length > 0 || !seats.length || task.busy || imageBusy || conflict || newer || !!pendingReload} onClick={() => setAction('publish')}>Опубликовать схему</Button><Button variant="ghost" disabled={task.busy || imageBusy} onClick={() => setAction('reload')}><RefreshCw size={16} />Обновить с сервера</Button><small>Разметка мест не создаёт билеты и не меняет наличие.</small></Card>
            </aside>
        </div>
        {dirty && <div className="editor-savebar"><div><strong>Изменения на холсте</strong><small>+{changes.create.length} новых · {changes.update.length} изменено · −{changes.delete.length} удалено · лимит 2000</small></div><Button busy={task.busy} disabled={conflict || newer || imageBusy || !!pendingReload} onClick={() => void task.run(save)}><Save size={18} />Сохранить изменения</Button></div>}
        {batch && <SeatBatchDialog id={plan.id} kind={batch} onClose={() => setBatch(null)} onApply={items => { const drafts = newSeatDrafts(items); commit([...seats, ...drafts]); setSelected(new Set(drafts.map(seat => seat.key))); }} />}
        {point && <Modal open title="Добавить место" onClose={() => setPoint(null)}><SeatProperties seat={{ sector: sector || 'A', row: row || '1', number: '1', x: coordinate(point.x), y: coordinate(point.y), adjacency_group: '', adjacency_position: null }} disabled={!canEdit} onApply={value => { const [added] = newSeatDrafts([value]); commit([...seats, added]); setSelected(new Set([added.key])); setPoint(null); }} /></Modal>}
        <ConfirmDialog open={!!action} title={action === 'reload' ? 'Загрузить схему с сервера?' : action === 'delete' ? `Убрать ${chosen.length} мест с холста?` : action === 'clone' ? 'Создать новую версию схемы?' : 'Опубликовать схему?'} danger={action === 'delete' || action === 'reload' && dirty} busy={task.busy} onClose={() => setAction(null)} onConfirm={() => {
            // Local deletion must not be blocked by useTask setting busy=true.
            if (action === 'delete') { edit(() => { commit(seats.filter(seat => !selected.has(seat.key))); setSelected(new Set()); setAction(null); }); }
            else void task.run(perform);
        }}>
            <p>{action === 'reload' ? dirty ? 'Несохранённые изменения будут заменены серверной версией. Для резервной копии сначала скачайте черновик JSON или CSV.' : 'Будут получены текущие места и версия схемы.' : action === 'delete' ? 'Удаление вступит в силу после сохранения изменений. До этого его можно отменить.' : action === 'clone' ? 'Создастся отдельный редактируемый черновик с текущими сохранёнными местами.' : 'После публикации геометрию этой версии нельзя будет менять. Для дальнейших изменений потребуется копия.'}</p>
            {task.error ? <ErrorState error={task.error} /> : null}
        </ConfirmDialog>
    </div>;
}
function coordinateLabel(value: string): string {
    return value.trim() && Number.isFinite(Number(value)) ? (Number(value) * 100).toFixed(2) : '—';
}
function percentInput(value: string | number): string {
    return String(value).trim() && Number.isFinite(Number(value)) ? String(Number(value) * 100) : String(value);
}
function SeatProperties({ seat, disabled, onApply }: { seat: EditorSeatInput; disabled: boolean; onApply: (seat: EditorSeatInput) => void }) {
    const [values, setValues] = useState({ sector: seat.sector, row: seat.row, number: seat.number, x: percentInput(seat.x), y: percentInput(seat.y), adjacency_group: seat.adjacency_group ?? '', adjacency_position: seat.adjacency_position == null ? '' : String(seat.adjacency_position) });
    const task = useTask();
    return <form className="stack" onSubmit={event => { event.preventDefault(); void task.run(async () => {
        if (!values.x.trim() || !values.y.trim()) throw new Error('INVALID_GEOMETRY');
        onApply({ sector: values.sector, row: values.row, number: values.number, x: coordinate(Number(values.x) / 100), y: coordinate(Number(values.y) / 100), adjacency_group: values.adjacency_group, adjacency_position: values.adjacency_position.trim() ? Number(values.adjacency_position) : null });
    }); }}><fieldset className="stack" disabled={disabled}>
        {(['sector', 'row', 'number'] as const).map(key => <Field key={key} label={{ sector: 'Сектор', row: 'Ряд', number: 'Место' }[key]}><Input required maxLength={key === 'sector' ? 50 : 30} value={values[key]} onChange={event => setValues(current => ({ ...current, [key]: event.target.value }))} /></Field>)}
        <div className="grid-2">{(['x', 'y'] as const).map(key => <Field key={key} label={`${key.toUpperCase()}, %`}><Input required type="number" min={0} max={100} step="any" value={values[key]} onChange={event => setValues(current => ({ ...current, [key]: event.target.value }))} /></Field>)}</div>
        <details><summary>Группа соседства</summary><div className="stack"><Field label="Название группы"><Input maxLength={80} value={values.adjacency_group} onChange={event => setValues(current => ({ ...current, adjacency_group: event.target.value }))} /></Field><Field label="Позиция в группе"><Input type="number" min={0} max={1000000} step={1} value={values.adjacency_position} onChange={event => setValues(current => ({ ...current, adjacency_position: event.target.value }))} /></Field><small>Геометрические изменения сбрасывают затронутые группы соседства.</small></div></details>
        {!disabled && <Button type="submit" variant="secondary" busy={task.busy}>Применить на холсте</Button>}
    </fieldset>{task.error ? <ErrorState error={task.error} /> : null}</form>;
}
function SelectionTools({ disabled, chosen, onTransform, onRename, onDelete }: { disabled: boolean; chosen: DraftSeat[]; onTransform: (transform: Transform) => void; onRename: (values: { sector: string; row: string }, start: number | null) => void; onDelete: () => void }) {
    const [dx, setDx] = useState('0'), [dy, setDy] = useState('0'), [angle, setAngle] = useState('15'), [sector, setSector] = useState(''), [row, setRow] = useState(''), [start, setStart] = useState('');
    const task = useTask();
    return <Card className="stack"><h3>Операции с выделением</h3><fieldset className="stack" disabled={disabled}>
        <div className="grid-2"><Field label="Сдвиг X, %"><Input type="number" step="any" value={dx} onChange={event => setDx(event.target.value)} /></Field><Field label="Сдвиг Y, %"><Input type="number" step="any" value={dy} onChange={event => setDy(event.target.value)} /></Field></div><Button variant="secondary" onClick={() => onTransform({ dx: Number(dx) / 100, dy: Number(dy) / 100 })}>Переместить</Button>
        <Field label="Поворот, °"><Input type="number" step="any" value={angle} onChange={event => setAngle(event.target.value)} /></Field><Button variant="secondary" onClick={() => onTransform({ angle: Number(angle) })}>Повернуть</Button><div className="actions"><Button variant="ghost" onClick={() => onTransform({ flipX: true })}>Отразить ↔</Button><Button variant="ghost" onClick={() => onTransform({ flipY: true })}>Отразить ↕</Button></div>
        <details><summary>Переименовать / перенумеровать</summary><div className="stack"><Field label="Новый сектор (пусто — оставить)"><Input maxLength={50} value={sector} onChange={event => setSector(event.target.value)} /></Field><Field label="Новый ряд (пусто — оставить)"><Input maxLength={30} value={row} onChange={event => setRow(event.target.value)} /></Field><Field label="Первый номер (пусто — оставить)" hint="Нумерация слева направо, отдельно в каждом ряду."><Input type="number" min={1} step={1} value={start} onChange={event => setStart(event.target.value)} /></Field><Button variant="secondary" onClick={() => void task.run(async () => { const value = start.trim() ? Number(start) : null; if (value !== null && (!Number.isInteger(value) || value < 1)) throw new Error('INVALID_SEAT_LABEL'); onRename({ sector: sector.trim(), row: row.trim() }, value); })}>Применить к {chosen.length} местам</Button></div></details>
        <Button variant="danger" onClick={onDelete}><Trash2 size={17} />Убрать выделенные</Button>
    </fieldset>{task.error ? <ErrorState error={task.error} /> : null}</Card>;
}
