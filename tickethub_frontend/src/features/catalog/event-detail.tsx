'use client';
import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { CalendarDays, MapPin, Ticket, ArrowRight, Trash2, Maximize } from 'lucide-react';
import type { Event as EventData, Offer, Availability, SeatMap, SelectionInput } from '@/lib/api/generated';
import { useApi } from '@/lib/hooks';
import { useConfig } from '@/features/auth/session';
import { useLang, useT } from '@/i18n/use-t';
import { localized, mediaPath } from '@/lib/safe';
import { eventTime } from '@/lib/datetime';
import { formatMoney } from '@/lib/money';
import { canCheckout, intakeMessage } from '@/lib/checkout-policy';
import { readPendingHold } from '@/lib/pending-hold';
import { saveDraft, loadDraft } from '@/lib/drafts';
import { SeatPicker } from '@/features/seat-map/seat-picker';
import { Alert, Badge, Button, Card, EmptyState, ErrorState, Input, Skeleton, StatusBadge, Modal } from '@/components/ui';
import { useEventAnalytics } from './analytics';
export function EventDetail({ event }: {
    event: EventData;
}) {
    const t = useT(), lang = useLang(), track = useEventAnalytics(event.id);
    const [portrait, setPortrait] = useState(false), [coverOpen, setCoverOpen] = useState(false);
    const [failedImage, setFailedImage] = useState<string | null>(null);
    const imageSource = mediaPath(event.image), image = imageSource === failedImage ? null : imageSource;
    useEffect(() => {
        track('EVENT_VIEW');
    }, [track]);
    return <div className="container section">
  <nav className="breadcrumb"><Link href={`/${lang}/events`}>{t('events')}</Link> / {localized(event, 'title', lang)}</nav>
  <section className="event-top">
    <div className="event-title">
      <Badge>{localized(event.category, 'name', lang)}</Badge>
      <h1>{localized(event, 'title', lang)}</h1>
      <div className="event-info">
        <div className="event-meta">
          <CalendarDays size={19}/>
          <div>
            {eventTime(event.start_at, event.venue.timezone, lang)}
            <br />
            <small>{t('localTime')} · {event.venue.timezone}</small>
          </div>
        </div>
        <div className="event-meta">
          <MapPin size={19}/>
          <span>{localized(event.venue, 'name', lang)}, {lang === 'en' ? (event.venue.city_en || event.venue.city) : event.venue.city}<br />{lang === 'en' ? (event.venue.address_en || event.venue.address) : event.venue.address}</span>
        </div>
        {event.status !== 'SCHEDULED' && <div><StatusBadge status={event.status}/></div>}
      </div>
    </div>
    <div className={`event-hero-image ${portrait ? 'is-poster' : ''}`}>{image ? <Image src={image} onError={() => setFailedImage(image)} onLoad={e => setPortrait(e.currentTarget.naturalWidth / e.currentTarget.naturalHeight < 1.2)} alt={localized(event, 'title', lang)} fill sizes="(max-width: 900px) 100vw, 50vw" priority unoptimized/> : <div className="cover-fallback"><Ticket size={90} strokeWidth={1}/></div>}</div>
    {image && <Button type="button" variant="ghost" className="view-cover-button" onClick={() => setCoverOpen(true)}><Maximize size={16}/>{t('openCover')}</Button>}
  </section>
  {event.fan_id_required && <div style={{ marginTop: 28 }}><Alert>
      <strong>{t('fanIdRequired')}</strong>
      <p>{localized(event, 'fan_id_description', lang) || t('fanIdHelp')}</p>
      <Link className="text-link" href={`/${lang}/request?event=${encodeURIComponent(event.slug)}&help=fan-id`}>{t('needHelp')}</Link>
    </Alert></div>}
  <section className="section" id="tickets">
    <h2 style={{ marginBottom: 26 }}>{t('chooseTickets')}</h2>
    <TicketSelection event={event}/>
  </section>
  <section className="grid-2 section event-description-grid">
    <Card className="stack">
      <h2>{t('description')}</h2>
      <p className="pre-line">{localized(event, 'description', lang)}</p>
      {event.participants.length > 0 && <div className="actions">{event.participants.map(p => <Badge key={p.id}>{localized(p, 'name', lang)}</Badge>)}</div>}
    </Card>
    <Card className="stack">
      <h2>{t('refundRules')}</h2>
      <p className="pre-line">{localized(event, 'refund_policy', lang) || t('refundClarify')}</p>
      <hr className="separator"/>
      <strong>{t('deliveryDue')}</strong>
      <p>{eventTime(event.delivery_due_at, event.venue.timezone, lang)}</p>
      <small>{t('managerPayment')}</small>
    </Card>
  </section>
    <Modal open={coverOpen} onClose={() => setCoverOpen(false)} title={localized(event, 'title', lang)}>{image && <div className="event-cover-large"><Image src={image} alt={localized(event, 'title', lang)} fill unoptimized sizes="90vw" style={{ objectFit: 'contain' }} /></div>}</Modal>
    </div>;
}
function TicketSelection({ event }: {
    event: EventData;
}) {
    const t = useT(), lang = useLang(), router = useRouter(), config = useConfig(), track = useEventAnalytics(event.id);
    const container = useRef<HTMLDivElement>(null);
    const [visible, setVisible] = useState(false);
    const offers = useApi<Offer[]>(`events/${event.id}/offers/`), map = useApi<SeatMap>(`events/${event.id}/seat-map/`), availability = useApi<Availability>(`events/${event.id}/availability/`, true, visible ? 10000 : undefined);
    const [seats, setSeats] = useState<string[]>([]), [offerId, setOfferId] = useState(''), [quantity, setQuantity] = useState(1), [notice, setNotice] = useState('');
    const [priceAck, setPriceAck] = useState<{
        key: string;
        sum: number;
    } | null>(null);
    const limit = config?.direct_order_limit ?? 10;
    useEffect(() => {
        const el = container.current;
        if (!el)
            return;
        const observer = new IntersectionObserver(([entry]) => {
            setVisible(entry.isIntersecting);
            if (entry.isIntersecting)
                track('TICKETS_VIEW');
        });
        observer.observe(el);
        return () => observer.disconnect();
    }, [track]);
    useEffect(() => {
        const draft = loadDraft();
        if (draft?.eventId === event.id) {
            if (draft.selection.mode === 'SEATS')
                setSeats(draft.selection.seat_ids ?? []);
            else {
                setOfferId(draft.selection.offer_id ?? '');
                setQuantity(draft.selection.quantity ?? 1);
            }
        }
    }, [event.id]);
    const choose = useCallback((id: string) => {
        setNotice('');
        if (seats.includes(id)) {
            setSeats(seats.filter(s => s !== id));
            return;
        }
        if (seats.length >= limit) {
            setNotice('seatLimit');
            return;
        }
        track('TICKET_SELECTED');
        setSeats([...seats, id]);
    }, [seats, limit, track]);
    const error = offers.error || map.error || availability.error;
    const current = availability.data;
    const availableSeats = current?.available_seats ?? [];
    const selectedOffer = offers.data?.find(o => o.id === offerId);
    const currentOffer = current?.offers?.find(o => o.offer_id === offerId);
    const numbered = !!event.seating_plan;
    const unavailable = seats.filter(id => !availableSeats.some(s => s.seat_id === id));
    const sum = numbered ? seats.reduce((s, id) => s + (availableSeats.find(x => x.seat_id === id)?.sale_price_minor ?? 0), 0) : (currentOffer?.sale_price_minor ?? selectedOffer?.sale_price_minor ?? 0) * quantity;
    const requestHref = `/${lang}/request?event=${encodeURIComponent(event.slug)}`;
    const canOrder = canCheckout(config, current);
    const intakeReason = intakeMessage(config, current);
    const chosen = numbered ? seats.length > 0 : !!selectedOffer;
    const adjacent = numbered && seats.length > 1 ? seats.map(id => map.data?.seats?.find(s => s.id === id)) : [];
    const positions = adjacent.map(s => s?.adjacency_position).filter((x): x is number => typeof x === 'number').sort((a, b) => a - b);
    const together = adjacent.length > 1 && adjacent.every(s => s?.adjacency_group && s.adjacency_group === adjacent[0]?.adjacency_group) && positions.length === adjacent.length && positions.every((p, i) => i === 0 || p === positions[i - 1] + 1);
    const selectionKey = numbered ? 'seats:' + seats.slice().sort().join(',') : `category:${offerId}:${quantity}`;
    const priceChanged = priceAck?.key === selectionKey && priceAck.sum !== sum;
    useEffect(() => {
        if (availability.isSuccess && chosen && !unavailable.length)
            setPriceAck(previous => previous?.key === selectionKey ? previous : { key: selectionKey, sum });
    }, [availability.isSuccess, chosen, unavailable.length, selectionKey, sum]);
    function proceed() {
        if (!canOrder || !chosen || priceChanged || unavailable.length > 0 || (!numbered && quantity > (currentOffer?.available_count ?? 0)))
            return;
        if (readPendingHold(sessionStorage)) {
            router.push(`/${lang}/checkout`);
            return;
        }
        const selection: SelectionInput = numbered ? { mode: 'SEATS', seat_ids: seats } : { mode: 'CATEGORY', offer_id: offerId, quantity };
        saveDraft({ eventId: event.id, slug: event.slug, selection, createdAt: Date.now() });
        track('CHECKOUT_STARTED');
        router.push(`/${lang}/checkout?event=${event.slug}`);
    }
    return <div ref={container}>{error ? <ErrorState error={error} retry={() => {
        void offers.refetch();
        void map.refetch();
        void availability.refetch();
    }}/> : offers.isPending || map.isPending || availability.isPending ? <Skeleton /> : <div className="buy-layout">
    <div className="stack">
      {!canOrder && <Alert>{t(intakeReason)}</Alert>}
      {numbered && map.data && current ? <SeatPicker map={map.data} availability={current} selected={seats} onChoose={choose}/> : <div className="stack">
        {offers.data?.map(offer => {
        const stock = current?.offers?.find(o => o.offer_id === offer.id);
        const active = offer.id === offerId;
        return <div className={`offer-card ${active ? 'active' : ''}`} key={offer.id}>
          <div>
            <h3>{localized(offer, 'name', lang)}</h3>
            <p>{localized(offer, 'description', lang)}</p>
            <div className="actions" style={{ marginTop: 10 }}>
              <StatusBadge status={offer.kind}/>
              <strong>{formatMoney(stock?.sale_price_minor ?? offer.sale_price_minor, lang)}</strong>
            </div>
          </div>
          {(stock?.available_count ?? 0) > 0 && canOrder ? <Button aria-pressed={active} variant={active ? 'primary' : 'secondary'} onClick={() => {
            setOfferId(offer.id);
            setQuantity(1);
            track('TICKET_SELECTED');
        }}>
            {active ? '✓ ' : ''}
            {t('chooseTickets')}
          </Button> : <Link className="btn btn-secondary" href={`${requestHref}&category=${encodeURIComponent(localized(offer, 'name', lang))}`}>{t('requestSubmit')}</Link>}
        </div>;
    })}
        {!offers.data?.length && <EmptyState title={t('checkOptions')}><Link className="btn btn-primary" href={requestHref}>{t('requestSubmit')}</Link></EmptyState>}
      </div>}
    </div>
    <Card id="selection-summary" className="selection-summary stack-sm">
      <h3>{t('selectedSeats')}</h3>
      {notice && <Alert>{t(notice, { count: limit })}</Alert>}
      {priceChanged && <Alert>
        <p>{t('priceChanged')}</p>
        <p>{t('previousPrice')}: {formatMoney(priceAck?.sum, lang)} → {t('currentPrice')}: {formatMoney(sum, lang)}</p>
        <Button variant="secondary" onClick={() => setPriceAck({ key: selectionKey, sum })}>{t('acceptNewPrice')}</Button>
      </Alert>}
      {unavailable.length > 0 && <Alert tone="bad">{t('seatConflict')}</Alert>}
      {numbered && seats.map(id => {
        const seat = map.data?.seats?.find(s => s.id === id);
        return <div className="selection-line" key={id}>
        <div>
          <strong>{t('sector')} {seat?.sector} · {t('row')} {seat?.row} · {t('seat')} {seat?.number}</strong>
          <p>{unavailable.includes(id) ? t('unavailableSeat') : formatMoney(availableSeats.find(s => s.seat_id === id)?.sale_price_minor, lang)}</p>
        </div>
        <Button variant="ghost" aria-label={t('remove')} onClick={() => choose(id)}><Trash2 size={16}/></Button>
      </div>;
    })}
      {!numbered && selectedOffer && <div className="stack-sm">
        <strong>{localized(selectedOffer, 'name', lang)}</strong>
        <div className="qty">
          <label htmlFor="quantity">{t('quantity')}</label>
          <Input id="quantity" type="number" min={1} max={Math.min(limit, currentOffer?.available_count ?? 0)} value={quantity} onChange={e => setQuantity(Math.max(1, Math.min(limit, Number(e.target.value) || 1)))}/>
        </div>
      </div>}
      {!chosen && <p className="muted">{t('nothingSelected')}</p>}
      {adjacent.length > 1 && !together && <Alert>{t('separateSeats')}</Alert>}
      <div className="selection-total">
        <span>{t('total')}</span>
        <span>{unavailable.length ? '—' : formatMoney(sum, lang)}</span>
      </div>
      {canOrder ? <Button disabled={!chosen || priceChanged || unavailable.length > 0 || (!numbered && quantity > (currentOffer?.available_count ?? 0))} onClick={proceed}>
        {t('continueCheckout')}
        <ArrowRight size={18}/>
      </Button> : <Link className="btn btn-primary" href={requestHref}>{t('requestSubmit')}</Link>}
      <small>{t('availabilityNote')}</small>
      <Link className="text-link" href={requestHref}>{t('requestTickets')}</Link>
    </Card>
  </div>}
  {chosen && canOrder && visible && !error && <div className="mobile-selection-rail"><div><small>{t('selectedCount', { count: numbered ? seats.length : quantity })}</small><strong>{unavailable.length ? '—' : formatMoney(sum, lang)}</strong></div><Button onClick={() => document.getElementById('selection-summary')?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'center' })}>{t('selectionSummary')}<ArrowRight size={17} /></Button></div>}
  </div>;
}
