'use client';
import { useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useQueryClient } from '@tanstack/react-query';
import { useApi, useTask } from '@/lib/hooks';
import { useConfig, useSession } from '@/features/auth/session';
import { authApi, checkoutApi } from '@/lib/api/endpoints';
import { api, ApiError } from '@/lib/api/client';
import { readPendingHold, reserveRecoverably } from '@/lib/pending-hold';
import { acceptedDocuments } from '@/lib/consents';
import { PromoCodeField, PriceSummary } from './promo-code';
import { orderPromoFields, promoMatchesHold, type PromoSelection } from '@/lib/promotions';
import { loadDraft, type SelectionDraft } from '@/lib/drafts';
import type { Availability, Event, Hold, HoldItem, PreviewResult, QuoteEvent, Request as TicketRequest } from '@/lib/api/generated';
import { countdown, eventTime, remainingSeconds } from '@/lib/datetime';
import { localized } from '@/lib/safe';
import { useT, useLang } from '@/i18n/use-t';
import { Alert, Button, Card, Checkbox, Currency, ErrorState, Field, FieldErrors, Input, Modal, PageHeader, Select, Skeleton, Textarea } from '@/components/ui';
export function ContactFields({ name, phone, email, setName, setPhone, error }: {
    name: string;
    phone: string;
    email: string;
    setName: (s: string) => void;
    setPhone: (s: string) => void;
    error?: unknown;
}) {
    const t = useT();
    return <div className="form-grid">
  <Field label={t('name')}><Input required autoComplete="name" value={name} onChange={e => setName(e.target.value)} maxLength={100}/></Field>
  <Field label={t('phone')}><Input required type="tel" autoComplete="tel" pattern="\+[1-9][0-9]{7,14}" value={phone} onChange={e => setPhone(e.target.value)} placeholder="+993…"/></Field>
  <Field label={t('email')}><Input type="email" value={email} readOnly autoComplete="email"/></Field>
  <small>{t('contactHint')}</small>
  <FieldErrors error={error} name="name"/>
  <FieldErrors error={error} name="phone"/>
    </div>;
}
export function LegalConsent({ accepted, onChange }: {
    accepted: Record<string, number>;
    onChange: (v: Record<string, number>) => void;
}) {
    const cfg = useConfig(), t = useT(), lang = useLang();
    return <div className="stack">{Object.entries(cfg?.legal_versions ?? {}).map(([slug, version]) => <Checkbox key={slug} required checked={accepted[slug] === version} onChange={e => onChange({ ...accepted, [slug]: e.target.checked ? version : 0 })}><span>{t('acceptDocument', { document: slug, version })} <Link href={`/${lang}/legal/${encodeURIComponent(slug)}`} target="_blank" rel="noreferrer">↗</Link></span></Checkbox>)}</div>;
}
export function TicketItems({ items }: {
    items: HoldItem[];
}) {
    const lang = useLang(), t = useT();
    return <div className="ticket-items">{items.map((item, i) => <div className="ticket-item" key={item.id ?? i}>
    <div>
      <strong>{localized(item, 'name', lang)}</strong>
      {item.sector && <p>{t('sector')} {item.sector} · {t('row')} {item.row} · {t('seat')} {item.seat_number}</p>}
    </div>
    <Currency value={item.sale_price_minor}/>
  </div>)}</div>;
}
export function HoldClock({ hold, onExpire }: {
    hold: Hold;
    onExpire: () => void;
}) {
    const t = useT();
    const [left, setLeft] = useState<number | null>(null);
    const fired = useRef(false);
    const expiry = useRef(onExpire);
    useEffect(() => {
        expiry.current = onExpire;
    }, [onExpire]);
    useEffect(() => {
        const received = performance.now();
        fired.current = false;
        const tick = () => {
            const s = remainingSeconds(hold.expires_at, hold.server_now, received, performance.now());
            setLeft(s);
            if (s === 0 && !fired.current) {
                fired.current = true;
                expiry.current();
            }
        };
        tick();
        const id = setInterval(tick, 250);
        return () => clearInterval(id);
    }, [hold.expires_at, hold.server_now]);
    return <div className="hold-clock">
  <span>{t('holdRemaining')}</span>
  <strong role="timer" aria-live="off">{left === null ? '—' : countdown(left)}</strong>
    </div>;
}
export function Checkout() {
    const t = useT(), lang = useLang(), router = useRouter(), params = useSearchParams(), client = useQueryClient(), session = useSession(), cfg = useConfig(), task = useTask();
    const [draft, setDraft] = useState<SelectionDraft | null>(null);
    const [ready, setReady] = useState(false);
    const [name, setName] = useState(''), [phone, setPhone] = useState(''), [comment, setComment] = useState(''), [fan, setFan] = useState<'HAS_FAN_ID' | 'NEEDS_HELP' | 'NOT_SURE'>('NOT_SURE');
    const [accepted, setAccepted] = useState<Record<string, number>>({});
    const [promo, setPromo] = useState<PromoSelection>({ code: '', quote: null });
    const [preview, setPreview] = useState<PreviewResult | null>(null);
    const [expired, setExpired] = useState(false), [expiryOpen, setExpiryOpen] = useState(false), [release, setRelease] = useState(false);
    const holdId = params.get('hold') ?? '', slug = holdId ? (params.get('event') ?? '') : (draft?.slug ?? params.get('event') ?? ''), requestId = params.get('request') ?? '';
    const [pending, setPending] = useState<ReturnType<typeof readPendingHold>>(null);
    useEffect(() => {
        setDraft(loadDraft());
        setPending(readPendingHold(sessionStorage));
        setReady(true);
    }, []);
    useEffect(() => {
        if (session.data) {
            setName(session.data.name);
            setPhone(session.data.phone);
        }
    }, [session.data]);
    const event = useApi<Event>(`events/${encodeURIComponent(slug)}/`, !!slug);
    const request = useApi<TicketRequest>(`ticket-requests/${requestId}/`, !!requestId);
    const hold = useApi<Hold>(`checkout/holds/${holdId}/`, !!holdId, 30000);
    const info: Event | QuoteEvent | undefined = event.data ?? request.data?.quotes.find(q => q.id === hold.data?.quote)?.event;
    const mismatch = !!info && ((!!hold.data && hold.data.event !== info.id) || (!holdId && !!draft && draft.eventId !== info.id));
    const promoPending = !!promo.code.trim() && (!hold.data || !promo.quote || !promoMatchesHold(promo.quote, hold.data, promo.code));
    const stale = expired || mismatch || !!hold.data && hold.data.status !== 'ACTIVE';
    useEffect(() => {
        setExpired(false);
        setExpiryOpen(false);
        setPromo({ code: '', quote: null });
    }, [holdId]);
    useEffect(() => {
        if (hold.data?.status === 'CONVERTED' && hold.data.order_id)
            router.replace(`/${lang}/account/orders/${hold.data.order_id}?success=1`);
    }, [hold.data?.status, hold.data?.order_id, router, lang]);
    useEffect(() => {
        if (hold.data?.status === 'EXPIRED') {
            setExpired(true);
            setExpiryOpen(true);
            sessionStorage.removeItem('th.selection');
        }
    }, [hold.data?.status]);
    async function prepare() {
        if (!draft || mismatch || pending)
            return;
        await authApi.update({ name, phone, locale: lang });
        await client.invalidateQueries({ queryKey: ['session'] });
        setPreview(await checkoutApi.preview({ event_id: draft.eventId, selection: draft.selection }));
    }
    async function reserve() {
        const body = pending ?? (draft && preview?.total_minor !== undefined ? { event_id: draft.eventId, selection: draft.selection, expected_total_minor: preview.total_minor, expected_offer_versions: preview.offer_versions } : null);
        if (!body || mismatch)
            return;
        try {
            const result = await reserveRecoverably(body);
            client.setQueryData(['api', lang, `checkout/holds/${result.id}/`], result);
            setPending(null);
            setPreview(null);
            const query = new URLSearchParams(params);
            query.set('hold', result.id);
            if (draft)
                query.set('event', draft.slug);
            router.replace(`/${lang}/checkout?${query}`);
        }
        catch (error) {
            setPending(readPendingHold(sessionStorage));
            if (error instanceof ApiError && error.status === 409 && !['PENDING_ATTEMPT', 'IDEMPOTENCY_CONFLICT'].includes(error.code)) {
                setPreview(null);
                await client.invalidateQueries({ queryKey: ['api'] });
                try {
                    const path = `events/${body.event_id}/availability/`;
                    client.setQueryData(['api', lang, path], await api<Availability>(path));
                }
                catch {
                }
            }
            throw error;
        }
    }
    async function submit() {
        if (!hold.data || !info || stale || promoPending)
            return;
        await authApi.update({ name, phone, locale: lang });
        let result;
        try {
            result = await checkoutApi.order({ hold_id: hold.data.id, fan_id_answer: fan, comment,
                accepted_documents: acceptedDocuments(cfg?.legal_versions ?? {}, accepted), ...orderPromoFields(hold.data, promo) });
        } catch (error) {
            // Never silently fall back to the undiscounted total after a promo fails.
            if (error instanceof ApiError && error.code.startsWith('PROMO_')) setPromo(previous => ({ ...previous, quote: null }));
            void hold.refetch(); // a timed-out response may still have created the order
            throw error;
        }
        sessionStorage.removeItem('th.selection');
        await client.invalidateQueries({ queryKey: ['api'] });
        router.replace(`/${lang}/account/orders/${result.id}?success=1`);
    }
    if (!ready)
        return <Skeleton />;
    if (!holdId && !draft && !pending)
        return <div className="narrow stack">
  <Alert>{t('noDraft')}</Alert>
  <Link className="btn btn-primary" href={`/${lang}/events`}>{t('browse')}</Link>
        </div>;
    const eventLink = info ? `/${lang}/events/${info.slug}` : `/${lang}/events`;
    return <div className="container section">
  <PageHeader title={t('checkout')} description={t('managerPayment')}/>
  <div className="checkout-grid">
    <div className="stack">
      {mismatch && <Alert tone="bad">{t('selectionMismatch')}</Alert>}
      {!holdId && pending && <Card>
        <Alert>{t('pendingHold')}</Alert>
        <Button disabled={mismatch} busy={task.busy} onClick={() => void task.run(reserve)}>{t('recoverHold')}</Button>
      </Card>}
      <Card><form className="stack" onSubmit={e => {
        e.preventDefault();
        void task.run(holdId ? submit : prepare);
    }}>
          <h2>{t('contactsTitle')}</h2>
          <ContactFields name={name} phone={phone} email={session.data?.email ?? ''} setName={setName} setPhone={setPhone} error={task.error}/>
          <Field label={t('comment')} hint={t('commentHint')}><Textarea value={comment} onChange={e => setComment(e.target.value)} maxLength={1000}/></Field>
          {info?.fan_id_required && <><Alert>{t('fanIdRequired')}</Alert><Field label={t('fanId')}><Select value={fan} onChange={e => setFan(e.target.value as typeof fan)}>
              <option value="NOT_SURE">{t('notSure')}</option>
              <option value="HAS_FAN_ID">{t('hasFanId')}</option>
              <option value="NEEDS_HELP">{t('needHelp')}</option>
            </Select></Field></>}
          <LegalConsent accepted={accepted} onChange={setAccepted}/>
          {task.error ? <ErrorState error={task.error}/> : null}
          {!cfg?.order_intake_enabled && <Alert>{t('formsDisabled')}</Alert>}
          {holdId && promoPending && <Alert>{t('promoApplyRequired')}</Alert>}
          <Button type="submit" busy={task.busy} disabled={!cfg?.order_intake_enabled || mismatch || !holdId && !!pending || !!holdId && (!hold.data || !info || stale || promoPending)}>{t(holdId ? 'placeOrder' : 'createHold')}</Button>
        </form></Card>
    </div>
    <div className="stack">{info && <Card>
        <h2>{localized(info, 'title', lang)}</h2>
        <p>{eventTime(info.start_at, info.venue.timezone, lang)}</p>
        <p>{localized(info.venue, 'name', lang)}</p>
      </Card>}{event.error && !requestId && <ErrorState error={event.error} retry={() => void event.refetch()}/>} {holdId && <Card>{hold.isPending ? <Skeleton /> : hold.error ? <ErrorState error={hold.error} retry={() => void hold.refetch()}/> : hold.data && <div className="stack">
          <h2>{t('holdTitle')}</h2>
          {hold.data.status === 'ACTIVE' ? <HoldClock hold={hold.data} onExpire={() => {
        setExpired(true);
        setExpiryOpen(true);
        sessionStorage.removeItem('th.selection');
        void hold.refetch();
    }}/> : <Alert>{t(hold.data.status === 'CONVERTED' ? 'holdConverted' : 'holdExpiredText')}</Alert>}
          <TicketItems items={hold.data.items}/>
          {!hold.data.quote && hold.data.status === 'ACTIVE' && cfg?.promo_codes_enabled !== false && <PromoCodeField key={hold.data.id} hold={hold.data} value={promo} onChange={setPromo} disabled={stale || task.busy}/>}
          {hold.data.quote && <small>{t('promoQuoteHint')}</small>}
          <PriceSummary subtotal={hold.data.total_minor} discount={!promoPending ? promo.quote?.discount_minor : 0}
              total={!promoPending && promo.quote ? promo.quote.total_minor : hold.data.total_minor} code={promo.quote?.code}/>
          <small>{t('managerCheckoutNote')}</small>
          {hold.data.status === 'ACTIVE' && !expired && <Button variant="secondary" onClick={() => setRelease(true)}>{t('releaseHold')}</Button>}
          {hold.data.status === 'CONVERTED' && <Link href={`/${lang}/account/orders`}>{t('myOrders')}</Link>}
        </div>}</Card>}{!holdId && <Alert>{t('availabilityNote')}</Alert>}</div>
  </div>
  <Modal open={!!preview} onClose={() => setPreview(null)} title={t('confirmPrice')} busy={task.busy}><div className="stack">
      {preview?.items?.map((item, i) => <div key={i} className="ticket-item">
        <span>{localized(item, 'name', lang)} {item.sector} {item.row} {item.seat_number}</span>
        <Currency value={item.sale_price_minor}/>
      </div>)}
      <h3>{t('total')}: <Currency value={preview?.total_minor}/></h3>
      <Alert>{t('availabilityNote')}</Alert>
      {task.error ? <ErrorState error={task.error}/> : null}
      <Button busy={task.busy} onClick={() => void task.run(reserve)}>{t('confirmPrice')}</Button>
    </div></Modal>
  <Modal open={expiryOpen} onClose={() => setExpiryOpen(false)} title={t('holdExpired')}>
    <p>{t('holdExpiredText')}</p>
    <Link className="btn btn-primary" href={eventLink} onClick={() => sessionStorage.removeItem('th.selection')}>{t('selectAgain')}</Link>
  </Modal>
  <Modal open={release} onClose={() => setRelease(false)} title={t('releaseQuestion')} busy={task.busy}><div className="stack">
      {task.error ? <ErrorState error={task.error}/> : null}
      <Button variant="danger" busy={task.busy} onClick={() => void task.run(async () => {
        await checkoutApi.release(holdId);
        sessionStorage.removeItem('th.selection');
        router.replace(eventLink);
    })}>{t('releaseHold')}</Button>
    </div></Modal>
    </div>;
}
