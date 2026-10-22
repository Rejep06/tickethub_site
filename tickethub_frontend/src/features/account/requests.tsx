'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { useT, useLang } from '@/i18n/use-t';
import { useApi, useTask } from '@/lib/hooks';
import { checkoutApi, requestApi } from '@/lib/api/endpoints';
import type { PaginatedRequest, Request as TicketRequest, Quote } from '@/lib/api/generated';
import { auditTime, eventTime } from '@/lib/datetime';
import { localized } from '@/lib/safe';
import { Alert, Button, Card, ConfirmDialog, Currency, EmptyState, ErrorState, PageHeader, Pagination, Skeleton, StatusBadge } from '@/components/ui';
export function RequestList({ compact = false }: {
    compact?: boolean;
}) {
    const t = useT(), lang = useLang(), params = useSearchParams(), router = useRouter(), page = compact ? 1 : Math.max(1, Number(params.get('page')) || 1);
    const data = useApi<PaginatedRequest>(`ticket-requests/?page=${page}&page_size=${compact ? 3 : 24}`);
    return <div className="stack">{!compact && <PageHeader title={t('requests')}/>} {data.isPending ? <Skeleton /> : data.error ? <ErrorState error={data.error} retry={() => void data.refetch()}/> : !data.data?.results.length ? <EmptyState title={t('noRequests')}><Link href={`/${lang}/request`} className="btn btn-primary">{t('requestSubmit')}</Link></EmptyState> : <>{data.data.results.map(item => <Card key={item.id}>
    <div className="split">
      <h3>{t('requestNumber', { number: item.number })}</h3>
      <StatusBadge status={item.status}/>
    </div>
    <p>{item.custom_event_name || t('requestTickets')} · {item.city}</p>
    <p>{t('ticketsCount', { count: item.quantity })}</p>
    <Link href={`/${lang}/account/requests/${item.id}`} className="text-link">{t('details')} →</Link>
  </Card>)}{!compact && <Pagination count={data.data.count} page={page} onChange={p => router.push(`?page=${p}`)}/>}</>}</div>;
}
export function RequestDetails({ id }: {
    id: string;
}) {
    const t = useT(), lang = useLang(), params = useSearchParams(), task = useTask(), data = useApi<TicketRequest>(`ticket-requests/${id}/`, true, 30000);
    const [confirm, setConfirm] = useState(false);
    if (data.isPending)
        return <Skeleton />;
    if (data.error)
        return <ErrorState error={data.error} retry={() => void data.refetch()}/>;
    if (!data.data)
        return null;
    const request = data.data;
    return <div className="stack">
  <PageHeader title={t('requestNumber', { number: request.number })} description={auditTime(request.created_at, lang)}/>
  {params.get('success') === '1' && <Alert tone="good">
    <strong>{t('requestSent')}</strong>
    <p>{t('requestSentText')}</p>
  </Alert>}
  <Card>
    <StatusBadge status={request.status}/>
    <h2>{request.custom_event_name || (request.quotes[0] ? localized(request.quotes[0].event, 'title', lang) : t('requestTickets'))}</h2>
    <p>{request.city} · {request.desired_date}</p>
    <p>{t('ticketsCount', { count: request.quantity })} · <Currency value={request.budget_minor}/></p>
    <p>{request.preferences}</p>
    {request.together_required && <p>{t('together')}</p>}
    <p>{request.comment}</p>
    <p>{request.public_response}</p>
    {['NEW', 'IN_PROGRESS', 'OFFERED'].includes(request.status) && <Button variant="secondary" onClick={() => setConfirm(true)}>{t('cancelRequest')}</Button>}
  </Card>
  <h2>{t('quote')}</h2>
  {request.quotes.length ? request.quotes.map(quote => <QuoteCard key={quote.id} quote={quote} requestId={id}/>) : <EmptyState title={t('noQuote')}/>}
  <ConfirmDialog open={confirm} onClose={() => setConfirm(false)} title={t('cancelRequest')} danger busy={task.busy} onConfirm={() => void task.run(async () => {
        await requestApi.cancel(id, request.version);
        await data.refetch();
        setConfirm(false);
    })}>{task.error ? <ErrorState error={task.error}/> : null}</ConfirmDialog>
    </div>;
}
function QuoteCard({ quote, requestId }: {
    quote: Quote;
    requestId: string;
}) {
    const t = useT(), lang = useLang(), router = useRouter(), client = useQueryClient(), task = useTask();
    const [confirm, setConfirm] = useState(false);
    const active = quote.status === 'SENT' && Date.parse(quote.expires_at) > Date.now();
    return <Card><div className="stack">
    <div className="split">
      <h3>{localized(quote.event, 'title', lang)}</h3>
      <StatusBadge status={quote.status}/>
    </div>
    <p>{eventTime(quote.event.start_at, quote.event.venue.timezone, lang)}</p>
    {quote.items.map(item => <div className="ticket-item" key={item.id}>
      <span>{localized(item, 'name', lang)} {item.sector} / {item.row} / {item.seat_number}</span>
      <Currency value={item.price_minor}/>
    </div>)}
    <h3>{t('total')}: <Currency value={quote.total_minor}/></h3>
    <p>{quote.public_comment}</p>
    <p>{t('quoteExpires')}: {auditTime(quote.expires_at, lang)}</p>
    <Alert>{t('quoteNote')}</Alert>
    {active ? <Button busy={task.busy} onClick={() => setConfirm(true)}>{t('quoteAccept')}</Button> : quote.status === 'SENT' && <Alert>{t('quoteExpired')}</Alert>}
    <ConfirmDialog open={confirm} onClose={() => setConfirm(false)} title={t('quoteAccept')} busy={task.busy} onConfirm={() => void task.run(async () => {
        const hold = await checkoutApi.quote(quote.id, quote.total_minor);
        client.setQueryData(['api', lang, `checkout/holds/${hold.id}/`], hold);
        router.push(`/${lang}/checkout?hold=${hold.id}&request=${requestId}`);
    })}>
      <p>{t('quoteNote')}</p>
      <h3><Currency value={quote.total_minor}/></h3>
      {task.error ? <ErrorState error={task.error}/> : null}
    </ConfirmDialog>
  </div></Card>;
}
