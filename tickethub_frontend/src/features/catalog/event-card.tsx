'use client';
import Link from 'next/link';
import { useState } from 'react';
import Image from 'next/image';
import { CalendarDays, MapPin, ArrowUpRight, CircleDot, Music2, Sparkles } from 'lucide-react';
import type { Event as EventData } from '@/lib/api/generated';
import { useT, useLang } from '@/i18n/use-t';
import { localized, mediaPath } from '@/lib/safe';
import { eventTime } from '@/lib/datetime';
import { formatMoney } from '@/lib/money';
import { Badge, StatusBadge } from '@/components/ui';
export function EventCard({ event }: { event: EventData }) {
    const t = useT(), lang = useLang();
    const [portrait, setPortrait] = useState(false);
    const [failedImage, setFailedImage] = useState<string | null>(null);
    const imageSource = mediaPath(event.image), image = imageSource === failedImage ? null : imageSource;
    const title = localized(event, 'title', lang), href = `/${lang}/events/${event.slug}`;
    const Icon = event.category.kind === 'SPORT' ? CircleDot : event.category.kind === 'CONCERT' ? Music2 : Sparkles;
    return <article className="event-card" data-kind={event.category.kind}>
        <Link href={href} className={`event-cover ${portrait ? 'is-poster' : ''}`} tabIndex={-1} aria-hidden="true">
            {image ? <Image src={image} alt="" onError={() => setFailedImage(image)} onLoad={e => setPortrait(e.currentTarget.naturalWidth / e.currentTarget.naturalHeight < 1.2)} fill sizes="(max-width: 640px) 100vw, (max-width: 1100px) 50vw, 33vw" unoptimized /> : <div className="cover-fallback"><span className="cover-orbit" /><Icon size={68} strokeWidth={1} /><span className="cover-word">LIVE</span></div>}
            <Badge>{localized(event.category, 'name', lang)}</Badge><span className="cover-arrow"><ArrowUpRight size={21} /></span>
        </Link>
        <div className="event-card-body"><div className="event-meta event-card-date"><CalendarDays size={15} aria-hidden="true" /><span>{eventTime(event.start_at, event.venue.timezone, lang)}</span></div>
            <h3 title={title}><Link href={href}>{title}</Link></h3>
            <div className="event-meta"><MapPin size={15} aria-hidden="true" /><span>{lang === 'en' ? (event.venue.city_en || event.venue.city) : event.venue.city} · {localized(event.venue, 'name', lang)}</span></div>
            {(event.fan_id_required || event.status !== 'SCHEDULED') && <div className="actions">{event.fan_id_required && <Badge tone="accent">Fan ID</Badge>}{event.status !== 'SCHEDULED' && <StatusBadge status={event.status} />}</div>}
            <div className="event-card-bottom"><strong>{event.price_from_minor != null ? t('fromPrice', { price: formatMoney(event.price_from_minor, lang) }) : t('onRequest')}</strong><Link href={href} className="event-card-cta" aria-label={`${t(event.orderable ? 'tickets' : 'requestTickets')}: ${title}`}><span>{t(event.orderable ? 'tickets' : 'selectionService')}</span><ArrowUpRight size={18} aria-hidden="true" /></Link></div>
        </div>
    </article>;
}
