import type { Metadata } from 'next';
import { publicApi } from '@/lib/api/server';
import type { PaginatedEvent, PaginatedCategory } from '@/lib/api/generated';
import { Home } from '@/features/catalog/home';
export async function generateMetadata({ params }: {
    params: Promise<{
        locale: string;
    }>;
}): Promise<Metadata> {
    const { locale } = await params;
    return { title: locale === 'en' ? 'Tickets for unmissable events' : 'Билеты на события, которые нельзя пропустить', alternates: { canonical: `/${locale}`, languages: { ru: '/ru', en: '/en', 'x-default': '/ru' } } };
}
export default async function HomePage() {
    const [events, categories] = await Promise.allSettled([publicApi<PaginatedEvent>('events/?ordering=start_at&page_size=100&date_from=' + encodeURIComponent(new Date().toISOString())), publicApi<PaginatedCategory>('categories/?page_size=100')]);
    return <Home events={events.status === 'fulfilled' ? events.value.results : []} categories={categories.status === 'fulfilled' ? categories.value.results : []} failed={events.status === 'rejected'}/>;
}
