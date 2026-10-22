'use client';
import { useId, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { ArrowRight, ArrowUpRight, Search, MapPin, SlidersHorizontal, Sparkles, MessagesSquare, HeartHandshake, Ticket, CircleDot, Music2, Plus, Check, Headphones } from 'lucide-react';
import type { Event as EventData, Category } from '@/lib/api/generated';
import { EventCard } from './event-card';
import { Badge, EmptyState, ErrorState, Input, Select, Button } from '@/components/ui';
import { Logo } from '@/components/brand';
import { BrandMoment } from '@/components/brand-moment';
import { useLang, useT } from '@/i18n/use-t';
import { localized, mediaPath } from '@/lib/safe';

export function RequestBanner() {
    const t = useT(), lang = useLang();
    return <section className="request-banner">
        <div className="request-banner-copy"><div className="eyebrow">{t('conciergeEyebrow')}</div><h2 className="pre-line">{t('requestCta')}</h2><p>{t('requestCtaText')}</p><Link className="btn btn-primary btn-lg" href={`/${lang}/request`}>{t('consult')}<ArrowUpRight size={20} /></Link></div>
        <div className="concierge-visual" aria-hidden="true"><span className="concierge-ring" /><span className="concierge-orbit" /><div className="concierge-icon"><Headphones size={65} strokeWidth={1.25} /></div><span className="concierge-tag"><span className="status-dot" />{t('conciergeTag')}</span><p>{t('conciergeNote')}</p></div>
    </section>;
}
export function HowItWorks({ standalone = false }: { standalone?: boolean } = {}) {
    const t = useT();
    const icons = [Search, SlidersHorizontal, MessagesSquare, Ticket];
    const Heading = standalone ? 'h1' : 'h2';
    return <section className="section how-section"><div className="section-title"><div><div className="eyebrow">TICKETHUB / HOW IT WORKS</div><Heading>{t('how')}</Heading><p className="muted">{t('howIntro')}</p></div></div>
        <div className="steps">{[1, 2, 3, 4].map((n, i) => { const Icon = icons[i]; return <div className="step-card" key={n}><div className="step-top"><span className="step-number">0{n}</span><Icon size={24} strokeWidth={1.5} aria-hidden="true" /></div><h3>{t('step' + n)}</h3><p>{t('step' + n + 'Text')}</p></div>; })}</div>
    </section>;
}
export function FAQ({ searchable = false, compact = false }: { searchable?: boolean; compact?: boolean }) {
    const t = useT();
    const prefix = useId();
    const [open, setOpen] = useState<number | null>(null);
    const [query, setQuery] = useState('');
    const entries = (compact ? [1, 2, 3, 4] : [1, 2, 3, 4, 5, 6]).filter(n => (t('faq' + n) + ' ' + t('faq' + n + 'Answer')).toLocaleLowerCase().includes(query.toLocaleLowerCase().trim()));
    return <div className="faq-component">
        {searchable && <div className="search-input-wrap faq-search"><Search size={20} aria-hidden="true" /><label className="sr-only" htmlFor={`${prefix}-search`}>{t('faqSearch')}</label><Input id={`${prefix}-search`} value={query} onChange={event => setQuery(event.target.value)} placeholder={t('faqSearch')} /></div>}
        <div className="faq-list">{entries.map(n => <div className={`faq-item ${open === n ? 'is-open' : ''}`} key={n}>
            <h3><button type="button" id={`${prefix}-q${n}`} aria-expanded={open === n} aria-controls={`${prefix}-a${n}`} onClick={() => setOpen(open === n ? null : n)}><span>{t('faq' + n)}</span><Plus size={21} aria-hidden="true" /></button></h3>
            <div id={`${prefix}-a${n}`} role="region" aria-labelledby={`${prefix}-q${n}`} hidden={open !== n}><p>{t('faq' + n + 'Answer')}</p></div>
        </div>)}</div>
        {!entries.length && <p className="faq-no-results" role="status">{t('faqNoResults')}</p>}
    </div>;
}
export function AboutTeaser() {
    const t = useT(), lang = useLang();
    return <section className="section about-teaser"><div><div className="eyebrow">{t('about')}</div><h2 className="pre-line">{t('aboutApproachTitle')}</h2><p>{t('aboutApproachText')}</p><Link className="inline-arrow" href={`/${lang}/about`}>{t('aboutLink')}<ArrowUpRight size={18} /></Link></div>
        <div className="care-card"><div className="care-card-icon"><HeartHandshake size={36} strokeWidth={1.5} /></div><blockquote>{t('aboutQuote')}</blockquote><div className="care-card-bottom"><Logo className="care-logo" /><span>{t('teamName')}<small>{t('aboutSince')}</small></span><Sparkles size={24} /></div></div>
    </section>;
}
export function Home({ events, categories, failed }: { events: EventData[]; categories: Category[]; failed: boolean }) {
    const t = useT(), lang = useLang(), router = useRouter();
    const [kind, setKind] = useState('ALL');
    const [failedHero, setFailedHero] = useState<string | null>(null), [posterHero, setPosterHero] = useState(false);
    const featured = events.find(event => event.category.kind === 'SPORT' && mediaPath(event.image)) ?? events.find(event => mediaPath(event.image)) ?? events[0];
    const imageSource = mediaPath(featured?.image), image = imageSource === failedHero ? null : imageSource;
    const shown = events.filter(event => kind === 'ALL' || event.category.kind === kind);
    const kindTabs = [{ value: 'ALL', label: 'allEvents', Icon: Sparkles }, { value: 'SPORT', label: 'sports', Icon: CircleDot }, { value: 'CONCERT', label: 'concerts', Icon: Music2 }, { value: 'OTHER', label: 'other', Icon: Ticket }];
    return <div className="container home-page">
        <section className="hero"><div className="hero-copy"><div className="eyebrow">{t('heroEyebrow')}</div><h1>{t('heroTitle')}<br /><span className="hero-accent">{t('heroAccent')}</span></h1><p>{t('heroDescription')}</p><div className="actions"><Link className="btn btn-primary btn-lg" href={`/${lang}/events`}>{t('browse')}<ArrowUpRight size={20} /></Link><Link className="btn btn-secondary btn-lg" href={`/${lang}/request`}>{t('requestTickets')}</Link></div><div className="hero-footnote"><span className="hero-check"><Check size={14} strokeWidth={3} /></span><span>{t('heroFootnote')}</span></div></div>
            <div className={`hero-visual ${image ? 'has-event' : 'has-artwork'} ${posterHero ? 'is-poster' : ''}`}>{image && featured ? <><Image src={image} alt={localized(featured, 'title', lang)} fill sizes="(max-width: 700px) 100vw, 45vw" priority unoptimized onError={() => setFailedHero(image)} onLoad={e => setPosterHero(e.currentTarget.naturalWidth / e.currentTarget.naturalHeight < 1.2)} /><div className="hero-overlay" /><span className="hero-label"><Badge tone="accent">{localized(featured.category, 'name', lang)}</Badge></span><div className="hero-caption"><small>{t('upcoming')}</small><h2>{localized(featured, 'title', lang)}</h2><Link className="btn btn-primary" href={`/${lang}/events/${featured.slug}`}>{t('tickets')}<ArrowUpRight size={18} /></Link></div></> : <BrandMoment />}</div>
        </section>
        <form className="search-banner" onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); const p = new URLSearchParams(); for (const [key, value] of form.entries()) if (typeof value === 'string' && value.trim()) p.set(key, value.trim()); router.push(`/${lang}/events${p.size ? '?' + p : ''}`); }}>
            <div className="search-banner-field search-main"><Search size={22} aria-hidden="true" /><div><label htmlFor="home-q">{t('search')}</label><Input id="home-q" name="q" placeholder={t('searchPlaceholder')} autoComplete="off" /></div></div>
            <div className="search-banner-field"><SlidersHorizontal size={20} aria-hidden="true" /><div><label htmlFor="home-category">{t('category')}</label><Select id="home-category" name="category"><option value="">{t('allEvents')}</option>{categories.map(category => <option key={category.id} value={category.id}>{localized(category, 'name', lang)}</option>)}</Select></div></div>
            <div className="search-banner-field"><MapPin size={20} aria-hidden="true" /><div><label htmlFor="home-city">{t('city')}</label><Input id="home-city" name="city" placeholder={t('allCities')} /></div></div>
            <Button type="submit">{t('searchButton')}<ArrowRight size={18} /></Button>
        </form>
        <div className="benefits-strip">{[HeartHandshake, MessagesSquare, Sparkles].map((Icon, index) => <div key={index}><span className="benefit-icon"><Icon size={23} strokeWidth={1.5} aria-hidden="true" /></span><span><strong>{t('benefit' + (index + 1))}</strong><small>{t('benefit' + (index + 1) + 'Text')}</small></span></div>)}</div>
        <section className="section home-events"><div className="section-title"><div><div className="eyebrow">{t('events')}</div><h2>{t('upcoming')}</h2><p className="muted">{t('upcomingText')}</p></div><Link className="inline-arrow" href={`/${lang}/events`}>{t('viewAll')}<ArrowUpRight size={19} /></Link></div>
            <div className="chip-list event-tabs" role="group" aria-label={t('category')}>{kindTabs.map(({ value, label, Icon }) => <button className={`chip ${value === kind ? 'active' : ''}`} type="button" key={value} aria-pressed={value === kind} onClick={() => setKind(value)}><Icon size={17} aria-hidden="true" />{t(label)}</button>)}</div>
            <div aria-live="polite">{failed ? <div className="catalog-load-error"><ErrorState error={new Error('API_UNAVAILABLE')} retry={() => router.refresh()} /></div> : shown.length ? <div className="event-grid">{shown.slice(0, 6).map(event => <EventCard key={event.id} event={event} />)}</div> : <EmptyState title={t('homeEmpty')}><p>{t('homeEmptyText')}</p><Link className="btn btn-primary" href={`/${lang}/request`}>{t('requestTickets')}<ArrowUpRight size={18} /></Link></EmptyState>}</div>
        </section>
        <RequestBanner /><HowItWorks /><AboutTeaser />
        <section className="section home-faq"><div className="faq-intro"><div className="eyebrow">FAQ</div><h2>{t('faq')}</h2><p>{t('faqIntro')}</p><Link className="inline-arrow" href={`/${lang}/faq`}>{t('faqMore')}<ArrowUpRight size={18} /></Link></div><FAQ compact /></section>
    </div>;
}
