'use client';
import { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { ArrowUpRight, CircleDot, Music2, Ticket } from 'lucide-react';
import type { Category, Event as EventData } from '@/lib/api/generated';
import { useLang, useT } from '@/i18n/use-t';
import { localized, mediaPath } from '@/lib/safe';
import { EmptyState, ErrorState } from '@/components/ui';
import { EventCard } from './event-card';
import { RequestBanner } from './home';

function CategoryCard({ category }: { category: Category }) {
    const lang = useLang(), t = useT();
    const [failed, setFailed] = useState<string | null>(null);
    const source = mediaPath(category.image), image = source === failed ? null : source;
    const Icon = category.kind === 'SPORT' ? CircleDot : category.kind === 'CONCERT' ? Music2 : Ticket;
    return <Link className={`category-card ${image ? 'with-photo' : ''}`} href={`/${lang}/events?category=${encodeURIComponent(category.id)}`}>
        <div className="category-card-image">{image ? <Image src={image} alt="" fill sizes="(max-width: 600px) 90vw, (max-width: 1000px) 45vw, 30vw" unoptimized onError={() => setFailed(image)} /> : <Icon size={42} strokeWidth={1.2} aria-hidden />}</div>
        <div className="category-card-content"><h2>{localized(category, 'name', lang)}</h2><span>{t('categoryBrowse')}<ArrowUpRight size={18} aria-hidden /></span></div>
    </Link>;
}
export function CategoryLanding({ kind, categories, events, failed, categoriesFailed = false }: {
    kind: 'SPORT' | 'CONCERT' | 'OTHER'; categories: Category[]; events: EventData[]; failed: boolean; categoriesFailed?: boolean;
}) {
    const t = useT(), lang = useLang(), router = useRouter();
    const label = kind === 'SPORT' ? 'sports' : kind === 'CONCERT' ? 'concerts' : 'other';
    // Prefer specific subcategories; a parent with children is still accessible in the catalogue filter.
    const parents = new Set(categories.map(category => category.parent).filter(Boolean));
    const leaves = categories.filter(category => !parents.has(category.id));
    return <div className="container category-page">
        <nav className="breadcrumb" aria-label={t('navigation')}><Link href={`/${lang}/events`}>{t('events')}</Link><span aria-hidden>/</span><span>{t(label)}</span></nav>
        <header className="category-page-heading"><div><h1>{t(label)}</h1><p>{t(`categoryIntro_${kind}`)}</p></div><Link className="btn btn-secondary" href={`/${lang}/events?kind=${kind}`}>{t('categoryAllEvents')}<ArrowUpRight size={18} /></Link></header>
        {categoriesFailed ? <ErrorState error={new Error('API_UNAVAILABLE')} retry={() => router.refresh()} /> : leaves.length > 0 && <section className="category-grid" aria-label={t('category')}>{leaves.map(category => <CategoryCard key={category.id} category={category} />)}</section>}
        <section className="section category-events"><div className="section-title"><h2>{t('categoryEvents')}</h2><Link className="inline-arrow" href={`/${lang}/events?kind=${kind}`}>{t('viewAll')}<ArrowUpRight size={18} /></Link></div>
            {failed ? <ErrorState error={new Error('API_UNAVAILABLE')} retry={() => router.refresh()} /> : events.length ? <div className="event-grid">{events.map(event => <EventCard key={event.id} event={event} />)}</div> : <EmptyState title={t('categoryEmpty')}><p>{t('categoryEmptyText')}</p><Link className="btn btn-primary" href={`/${lang}/request`}>{t('requestTickets')}</Link></EmptyState>}
        </section><RequestBanner />
    </div>;
}
