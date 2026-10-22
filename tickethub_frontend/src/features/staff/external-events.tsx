'use client';
import { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { ArrowUpRight, Download, Eye, Link2, RefreshCw, CalendarDays } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError } from '@/lib/api/client';
import { externalEventsApi, portalBiletUrl, type ImportPreview, type ImportReport, type ImportWarning, type ExternalPage, type ExternalSource } from '@/lib/api/external-events';
import { useApi, useTask } from '@/lib/hooks';
import { auditTime } from '@/lib/datetime';
import { Alert, Badge, Button, Card, ConfirmDialog, EmptyState, ErrorState, Field, Input, PageHeader, Pagination, Skeleton } from '@/components/ui';
import { AdminOnly } from './resource-page';

function SourceStatus({ status }: { status: string }) {
    const labels: Record<string, string> = { NEW: 'Новый источник', PREVIEW: 'Предпросмотр', RUNNING: 'Выполняется', PARTIAL: 'Нужна проверка', FAILED: 'Не завершён' };
    return <Badge tone={status === 'FAILED' ? 'bad' : status === 'PARTIAL' ? 'warn' : 'neutral'}>{labels[status] ?? status}</Badge>;
}
function Warnings({ warnings }: { warnings?: ImportWarning[] }) {
    if (!warnings?.length) return null;
    return <div className="import-warnings">{warnings.map((warning, index) => <div key={`${warning.code}-${index}`}><strong>{warning.code}</strong>{warning.resource && <span className="mono small"> · {warning.resource}</span>}<p>{warning.message}</p></div>)}</div>;
}
function Report({ report }: { report: Partial<ImportReport> }) {
    return <div className="stack">
        {report.status && <SourceStatus status={report.status} />}
        {report.created && <div className="import-metrics"><div><strong>{report.created.events.length}</strong><span>Новых дат</span></div><div><strong>{report.updated?.events.length ?? 0}</strong><span>Обновлено</span></div><div><strong>{report.created.venues}</strong><span>Новых площадок</span></div><div><strong>{report.created.ticket_units}</strong><span>Создано билетов</span></div></div>}
        {report.status === 'PARTIAL' && <Alert>Запрос обработан частично. Откройте созданные даты, проверьте данные и добавьте обложку. Этот импорт не создаёт схему мест и собственные билеты для продажи.</Alert>}
        {report.status === 'FAILED' && <Alert tone="bad">Импорт не завершён. Проверьте диагностику ниже; HTTP-ответ сам по себе не означает успешное создание события.</Alert>}
        <Warnings warnings={report.warnings} />
        {report.created && report.created.events.length > 0 && <div className="stack"><h3>Созданные мероприятия</h3>{report.created.events.map((id, index) => <Link className="text-link" key={id} href={`/ru/staff/events/${id}#event-cover`}>Дата {index + 1} — проверить и добавить обложку <ArrowUpRight size={16} /></Link>)}</div>}
        {report.resources && Object.keys(report.resources).length > 0 && <details className="diagnostic-panel"><summary>Диагностика ресурсов источника</summary><div className="table-wrap"><table><thead><tr><th>Ресурс</th><th>Состояние</th><th>Код / размер</th></tr></thead><tbody>{Object.entries(report.resources).map(([key, resource]) => <tr key={key}><td className="mono small">{key}</td><td>{resource.status}</td><td>{resource.code ?? (resource.bytes != null ? `${resource.bytes} байт` : '—')}</td></tr>)}</tbody></table></div></details>}
    </div>;
}
export function ExternalEventsPage() { return <AdminOnly><Importer /></AdminOnly>; }
function Importer() {
    const [url, setUrl] = useState(''), [preview, setPreview] = useState<ImportPreview | null>(null), [report, setReport] = useState<ImportReport | null>(null), [confirm, setConfirm] = useState(false), [uncertain, setUncertain] = useState(false);
    const previewTask = useTask(), importTask = useTask(), client = useQueryClient();
    const normalized = portalBiletUrl(url);
    const busy = previewTask.busy || importTask.busy;
    async function refreshSources() { await client.invalidateQueries({ queryKey: ['api'] }); }
    return <div className="stack">
        <PageHeader title="Импорт мероприятий" description="Ссылка PortalBilet → предпросмотр → черновики дат в Tickethub"><Badge tone="accent">Только администратор</Badge></PageHeader>
        <div className="import-layout"><Card className="stack">
            <div className="split"><h2>Добавить по ссылке</h2><Link2 size={25} /></div>
            <p className="muted">Вставьте ссылку на мероприятие. Идентификаторы источника, площадки и дат определяет сервер.</p>
            <form className="stack" onSubmit={event => {
                event.preventDefault();
                void previewTask.run(async () => {
                    if (!normalized) throw new ApiError(400, 'INVALID_PORTALBILET_URL', 'Нужна HTTPS-ссылка PortalBilet на мероприятие.');
                    setReport(null); setPreview(null);
                    setPreview(await externalEventsApi.preview(normalized));
                });
            }}>
                <Field label="Ссылка на мероприятие" hint="https://portalbilet.ru/город/мероприятие" error={url && !normalized ? 'Проверьте HTTPS-адрес и путь город/мероприятие.' : undefined}><Input type="url" required maxLength={600} value={url} disabled={busy || uncertain} placeholder="https://portalbilet.ru/…" onChange={event => { setUrl(event.target.value); setPreview(null); setReport(null); previewTask.setError(null); importTask.setError(null); }} /></Field>
                <Button type="submit" busy={previewTask.busy} disabled={busy || !normalized || uncertain}><Eye size={18} />Показать предпросмотр</Button>
            </form>
            {previewTask.error ? <ErrorState error={previewTask.error} /> : null}
            {busy && <p role="status">Получаем данные источника. Это может занять около минуты; не закрывайте страницу.</p>}
            <small>Предпросмотр ничего не сохраняет. Импорт работает в режиме IMPORT_ONLY: внешнее наличие не становится вашим запасом.</small>
        </Card><Card className="stack import-help"><span className="eyebrow">ПОСЛЕ ИМПОРТА</span><h2>Подготовьте событие к афише</h2><p>Проверьте категорию, дату и часовой пояс, описания и условия посещения. Загрузите свою обложку в карточке мероприятия.</p><p>При необходимости создайте схему в редакторе и добавьте собственные билеты через обычные предложения Tickethub.</p><Link href="/ru/staff/events" className="text-link">Открыть мероприятия <ArrowUpRight size={16} /></Link></Card></div>
        {preview && !report && <Card className="stack"><div className="split"><div><span className="eyebrow">ПРЕДПРОСМОТР ИСТОЧНИКА</span><h2>{preview.title}</h2><p>{[preview.venue.name, preview.venue.city, preview.venue.address].filter(Boolean).join(' · ')}</p></div><SourceStatus status={preview.status} /></div>
            <p>Распознано дат: <strong>{preview.dates.length}</strong>. Мест: <strong>{preview.seats_count ?? 'не определено'}</strong>. Зон без нумерации: <strong>{preview.standing_zones_count ?? 'не определено'}</strong>.</p>
            <div className="import-date-list">{preview.dates.map(date => <div key={date.external_date_id}><CalendarDays size={18} /><span>{sourceTime(date.start_at)}</span><small>ID даты: {date.external_date_id}</small></div>)}</div>
            <Warnings warnings={preview.warnings} />
            <Button disabled={busy || uncertain} onClick={() => setConfirm(true)}><Download size={18} />Импортировать черновики</Button>
        </Card>}
        {report && <Card className="stack"><h2>Результат импорта</h2><Report report={report} /><Link className="btn btn-secondary" href={`/ru/staff/external-events/${report.source_id}`}>Открыть источник и даты</Link></Card>}
        {importTask.error ? <ErrorState error={importTask.error} /> : null}
        {uncertain && <Alert>Связь прервалась до получения результата. Сервер мог сохранить черновики. Обновите список источников ниже и откройте нужный источник — повторный импорт автоматически не запускается.</Alert>}
        {uncertain && <div className="actions"><Button variant="secondary" onClick={() => void refreshSources()}>Обновить источники</Button><Button variant="ghost" onClick={() => { setUncertain(false); setPreview(null); importTask.setError(null); }}>Я проверил результат — вернуться к форме</Button></div>}
        <ExternalList />
        <ConfirmDialog open={confirm} title="Импортировать черновики дат?" busy={importTask.busy} onClose={() => setConfirm(false)} onConfirm={() => void importTask.run(async () => {
            if (!preview) return;
            try { setReport(await externalEventsApi.import(preview.url)); setPreview(null); }
            catch (error) { if (error instanceof ApiError && (error.status === 0 || error.status >= 500)) setUncertain(true); throw error; }
            finally { setConfirm(false); await refreshSources(); }
        })}><p>{preview?.title}</p><p>События будут непубличными. Места, обложка и билеты не создаются этим импортом.</p></ConfirmDialog>
    </div>;
}
function ExternalList() {
    const params = useSearchParams(), router = useRouter(), pathname = usePathname();
    const page = Math.max(1, Number(params.get('page')) || 1);
    const list = useApi<ExternalPage>(`staff/external-events/?page=${page}`);
    return <Card className="stack"><div className="split"><h2>Источники мероприятий</h2><Button variant="ghost" disabled={list.isFetching} onClick={() => void list.refetch()}><RefreshCw size={16} />Обновить</Button></div>
        {list.isPending ? <Skeleton /> : list.error ? <ErrorState error={list.error} retry={() => void list.refetch()} /> : list.data?.results.length ? <><div className="table-wrap"><table><thead><tr><th>Мероприятие</th><th>Статус</th><th>Даты</th><th>Последняя синхронизация</th><th>Действие</th></tr></thead><tbody>{list.data.results.map(source => <tr key={source.id}><td><strong>{source.title}</strong><br /><small>PortalBilet · {source.external_event_id}</small></td><td><SourceStatus status={source.status} /></td><td>{source.dates.length}</td><td>{auditTime(source.last_metadata_sync_at)}</td><td><Link className="text-link" href={`/ru/staff/external-events/${source.id}`}>Открыть →</Link></td></tr>)}</tbody></table></div><Pagination count={list.data.count} page={page} onChange={next => { const query = new URLSearchParams(params); query.set('page', String(next)); router.push(pathname + '?' + query); }} /></> : <EmptyState title="Пока нет импортированных источников" />}
    </Card>;
}
function sourceTime(value: string | null): string {
    if (!value) return 'Дата и время требуют проверки';
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return 'Дата требует проверки';
    return date.toLocaleString('ru-RU', { timeZone: 'UTC', dateStyle: 'medium', timeStyle: 'short' }) + ' UTC';
}
export function ExternalSourcePage({ id }: { id: string }) { return <AdminOnly><SourceDetail id={id} /></AdminOnly>; }
function SourceDetail({ id }: { id: string }) {
    const source = useApi<ExternalSource>(`staff/external-events/${id}/`), task = useTask();
    const [confirm, setConfirm] = useState(false), [report, setReport] = useState<ImportReport | null>(null), [uncertain, setUncertain] = useState(false);
    const client = useQueryClient();
    if (source.isPending) return <Skeleton />;
    if (source.error) return <ErrorState error={source.error} retry={() => void source.refetch()} />;
    if (!source.data) return null;
    const data = source.data, href = portalBiletUrl(data.url);
    return <div className="stack"><Link className="text-link" href="/ru/staff/external-events">← Импорт мероприятий</Link><PageHeader title={data.title} description="Локальные черновики и результат синхронизации источника"><SourceStatus status={data.status} /><Button disabled={task.busy || uncertain} onClick={() => setConfirm(true)}><RefreshCw size={18} />Синхронизировать</Button></PageHeader>
        <Card className="stack"><div className="split"><h2>Источник</h2>{href && <a className="text-link" href={href} target="_blank" rel="noopener noreferrer">Открыть PortalBilet <ArrowUpRight size={16} /></a>}</div><p>Последняя попытка: {auditTime(data.last_attempt_at)}. Метаданные: {auditTime(data.last_metadata_sync_at)}.</p>{data.venue && <Link className="text-link" href={`/ru/staff/venues/${data.venue}`}>Проверить площадку и часовой пояс →</Link>}<small>Ручные изменения событий сохраняются согласно правилам backend. Синхронизация не резервирует внешние билеты.</small></Card>
        {task.error ? <ErrorState error={task.error} /> : null}{uncertain && <Alert>Результат синхронизации пока неизвестен. Обновите источник перед новой попыткой.</Alert>}
        <Button variant="secondary" busy={source.isFetching} onClick={() => void task.run(async () => { const result = await source.refetch(); if (result.error) throw result.error; setReport(null); setUncertain(false); })}>Обновить состояние источника</Button>
        <Card className="stack"><h2>Даты и обложки</h2>{data.dates.length ? <div className="table-wrap"><table><thead><tr><th>Дата источника</th><th>Доступна у источника</th><th>Мероприятие Tickethub</th></tr></thead><tbody>{data.dates.map(date => <tr key={date.id}><td>{sourceTime(date.source_start_at)}<br /><small>ID даты: {date.external_date_id}</small></td><td>{date.source_active ? 'Да' : 'Больше не указана'}</td><td><Link className="text-link" href={`/ru/staff/events/${date.event}#event-cover`}>Проверить и добавить обложку →</Link></td></tr>)}</tbody></table></div> : <EmptyState title="Локальные даты ещё не созданы" />}</Card>
        <Card className="stack"><h2>Результат и диагностика</h2><Report report={report ?? data.diagnostics} /><details className="diagnostic-panel"><summary>JSON диагностики</summary><pre>{JSON.stringify(report ?? data.diagnostics, null, 2)}</pre></details></Card>
        <ConfirmDialog open={confirm} title="Повторить синхронизацию?" busy={task.busy} onClose={() => setConfirm(false)} onConfirm={() => void task.run(async () => {
            try { setReport(await externalEventsApi.sync(id)); }
            catch (error) { if (error instanceof ApiError && (error.status === 0 || error.status >= 500)) setUncertain(true); throw error; }
            finally { setConfirm(false); await client.invalidateQueries({ queryKey: ['api'] }); }
        })}><p>Будут повторно получены метаданные и диагностические снимки. Публикация и продажа билетов не включаются.</p></ConfirmDialog>
    </div>;
}
