'use client';
import { useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { Search, SlidersHorizontal, X, ArrowUpRight } from 'lucide-react';
import type { PaginatedEvent, Category, Venue } from '@/lib/api/generated';
import { api } from '@/lib/api/client';
import { localized, queryString } from '@/lib/safe';
import { useLang, useT } from '@/i18n/use-t';
import { EventCard } from './event-card';
import { Input, Select, Field, Button, Pagination, EmptyState, ErrorState, Skeleton, PageHeader, Modal } from '@/components/ui';
import { catalogPath, inclusiveDateToExclusive, exclusiveDateToInclusive } from '@/lib/catalog';

export function Catalog({ initial, initialPath, categories, venues }: { initial: PaginatedEvent | null; initialPath: string; categories: Category[]; venues: Venue[] }) {
    const t = useT(), lang = useLang(), router = useRouter(), params = useSearchParams();
    const path = catalogPath(new URLSearchParams(params.toString()));
    const [search, setSearch] = useState(params.get('q') || '');
    const [filtersOpen, setFiltersOpen] = useState(false);
    const last = useRef(search);
    const query = useQuery({ queryKey: ['api', lang, path], queryFn: ({ signal }) => api<PaginatedEvent>(path, { signal, locale: lang }), initialData: initial && path === initialPath ? initial : undefined });
    const update = (values: Record<string, string>) => {
        const next = new URLSearchParams(params.toString()); next.delete('page');
        Object.entries(values).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key));
        router.push(`/${lang}/events${next.size ? '?' + next : ''}`, { scroll: false });
    };
    useEffect(() => { const next = params.get('q') || ''; last.current = next; setSearch(next); }, [params]);
    useEffect(() => {
        if (search === last.current) return;
        const timer = setTimeout(() => {
            last.current = search; const next = new URLSearchParams(params.toString()); next.delete('page');
            if (search.trim()) next.set('q', search.trim());
            else next.delete('q');
            router.push(`/${lang}/events${next.size ? '?' + next : ''}`, { scroll: false });
        }, 300);
        return () => clearTimeout(timer);
    }, [search, lang, router, params]);
    const filterKeys = ['q', 'category', 'city', 'venue', 'date_from', 'date_to'];
    const activeFilters = filterKeys.filter(key => params.get(key));
    const filterLabel = (key: string) => {
        const value = params.get(key) || '';
        if (key === 'category') return localized(categories.find(category => category.id === value) ?? {}, 'name', lang) || t('category');
        if (key === 'venue') return localized(venues.find(venue => venue.id === value) ?? {}, 'name', lang) || t('venue');
        if (key === 'date_from') return `${t('dateFrom')}: ${value.slice(0, 10)}`;
        if (key === 'date_to') return `${t('dateTo')}: ${exclusiveDateToInclusive(value)}`;
        return value;
    };
    const fields = <FilterFields params={new URLSearchParams(params.toString())} categories={categories} venues={venues} update={update} />;
    return <div className="container section catalog-page"><div className="eyebrow">{t('events')}</div><PageHeader title={t('catalogTitle')} description={t('catalogIntro')} />
        <div className="catalog-layout"><aside className="catalog-sidebar"><form className="catalog-filters" onSubmit={event => { event.preventDefault(); update({ q: search.trim() }); }}>
            <div className="split"><h2><SlidersHorizontal size={18} />{t('filter')}</h2><button type="button" className="filter-reset" onClick={() => router.push(`/${lang}/events`)}>{t('reset')}</button></div>{fields}
            <div className="filter-help"><MessagesIcon /><strong>{t('helpfulSelection')}</strong><Link href={`/${lang}/request`}>{t('requestTickets')}<ArrowUpRight size={16} /></Link></div>
        </form></aside>
        <div className="catalog-content"><form className="catalog-search" onSubmit={event => { event.preventDefault(); update({ q: search.trim() }); }}><div className="search-input-wrap"><Search size={20} aria-hidden="true" /><label className="sr-only" htmlFor="catalog-search">{t('search')}</label><Input id="catalog-search" value={search} onChange={event => setSearch(event.target.value)} placeholder={t('searchPlaceholder')} />{search && <button type="button" className="icon-button" aria-label={t('clearSearch')} onClick={() => { setSearch(''); update({ q: '' }); }}><X size={17} /></button>}</div><button type="button" className="btn btn-secondary catalog-mobile-filter" onClick={() => setFiltersOpen(true)}><SlidersHorizontal size={18} />{t('filter')}{activeFilters.length > 0 && <span className="filter-count">{activeFilters.length}</span>}</button></form>
            <div className="catalog-toolbar"><span className="muted" aria-live="polite">{query.isFetching ? t('updating') : query.data ? t('found', { count: query.data.count }) : ''}</span><Select aria-label={t('sort')} value={params.get('ordering') || 'start_at'} onChange={event => update({ ordering: event.target.value })}><option value="start_at">{t('soonest')}</option><option value="-start_at">{t('latest')}</option><option value="-created_at">{t('newest')}</option></Select></div>
            {activeFilters.length > 0 && <div className="chip-list applied-filters">{activeFilters.map(key => <button type="button" key={key} className="chip" aria-label={t('filterRemove', { label: filterLabel(key) })} onClick={() => update({ [key]: '' })}>{filterLabel(key)}<X size={14} /></button>)}</div>}
            {query.isPending ? <Skeleton /> : query.error ? <ErrorState error={query.error} retry={() => void query.refetch()} /> : query.data?.results.length ? <><div className="event-grid" aria-busy={query.isFetching}>{query.data.results.map(event => <EventCard key={event.id} event={event} />)}</div><Pagination count={query.data.count} page={Number(params.get('page')) || 1} onChange={page => router.push(`/${lang}/events?${queryString({ ...Object.fromEntries(params.entries()), page })}`)} /></> : <EmptyState title={t('noResults')}><p>{t('noResultsText')}</p><Link className="btn btn-primary" href={`/${lang}/request`}>{t('requestSubmit')}</Link></EmptyState>}
        </div></div>
        {filtersOpen && <Modal open onClose={() => setFiltersOpen(false)} title={t('filter')}><form className="stack" onSubmit={event => { event.preventDefault(); setFiltersOpen(false); }}>{fields}<div className="actions"><Button type="button" variant="secondary" onClick={() => router.push(`/${lang}/events`)}>{t('reset')}</Button><Button type="submit">{t('showResults')}</Button></div></form></Modal>}
    </div>;
}
function MessagesIcon() { return <span className="filter-help-mark" aria-hidden="true">th.</span>; }
function FilterFields({ params, categories, venues, update }: { params: URLSearchParams; categories: Category[]; venues: Venue[]; update: (values: Record<string, string>) => void }) {
    const t = useT(), lang = useLang();
    return <><Field label={t('category')}><Select value={params.get('category') || ''} onChange={event => update({ category: event.target.value })}><option value="">{t('allEvents')}</option>{categories.map(category => <option key={category.id} value={category.id}>{localized(category, 'name', lang)}</option>)}</Select></Field>
        <Field label={t('city')}><Input key={params.get('city') || 'city'} defaultValue={params.get('city') || ''} onBlur={event => { if (event.target.value !== (params.get('city') || '')) update({ city: event.target.value }); }} placeholder={t('allCities')} /></Field>
        <Field label={t('venue')}><Select value={params.get('venue') || ''} onChange={event => update({ venue: event.target.value })}><option value="">{t('all')}</option>{venues.map(venue => <option key={venue.id} value={venue.id}>{localized(venue, 'name', lang)}</option>)}</Select></Field>
        <Field label={t('dateFrom')}><Input type="date" value={(params.get('date_from') || '').slice(0, 10)} onChange={event => update({ date_from: event.target.value ? event.target.value + 'T00:00:00Z' : '' })} /></Field>
        <Field label={t('dateTo')}><Input type="date" value={exclusiveDateToInclusive(params.get('date_to') || '')} min={(params.get('date_from') || '').slice(0, 10)} onChange={event => update({ date_to: inclusiveDateToExclusive(event.target.value) })} /></Field></>;
}
