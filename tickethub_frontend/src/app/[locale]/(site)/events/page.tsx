import type { Metadata } from 'next';
import { publicApi } from '@/lib/api/server';
import type { PaginatedEvent, PaginatedCategory, PaginatedVenue } from '@/lib/api/generated';
import { catalogPath } from '@/lib/catalog';
import { Catalog } from '@/features/catalog/catalog';
type Params = {
    params: Promise<{
        locale: string;
    }>;
    searchParams: Promise<Record<string, string | string[] | undefined>>;
};
export async function generateMetadata({ params, searchParams }: Params): Promise<Metadata> {
    const { locale } = await params;
    const query = await searchParams;
    return { title: locale === 'en' ? 'Events' : 'Мероприятия', robots: Object.keys(query).length ? { index: false, follow: true } : undefined, alternates: { canonical: `/${locale}/events`, languages: { ru: '/ru/events', en: '/en/events' } } };
}
export default async function EventsPage({ searchParams }: Params) {
    const params = await searchParams;
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params))
        if (typeof v === 'string')
            q.set(k, v);
    const path = catalogPath(q);
    const [events, categories, venues] = await Promise.allSettled([publicApi<PaginatedEvent>(path), publicApi<PaginatedCategory>('categories/?page_size=100'), publicApi<PaginatedVenue>('venues/?page_size=100')]);
    return <Catalog initial={events.status === 'fulfilled' ? events.value : null} initialPath={path} categories={categories.status === 'fulfilled' ? categories.value.results : []} venues={venues.status === 'fulfilled' ? venues.value.results : []}/>;
}
