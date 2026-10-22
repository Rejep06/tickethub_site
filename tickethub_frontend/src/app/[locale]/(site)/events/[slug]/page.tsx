import { cache } from 'react';
import { notFound } from 'next/navigation';
import type { Metadata } from 'next';
import { publicApi } from '@/lib/api/server';
import { ApiError } from '@/lib/api/client';
import type { Event } from '@/lib/api/generated';
import { localized, mediaPath } from '@/lib/safe';
import { EventDetail } from '@/features/catalog/event-detail';
const getEvent = cache(async (slug: string) => {
    try {
        return await publicApi<Event>(`events/${encodeURIComponent(slug)}/`);
    }
    catch (e) {
        if (e instanceof ApiError && e.status === 404)
            notFound();
        throw e;
    }
});
type Props = {
    params: Promise<{
        locale: 'ru' | 'en';
        slug: string;
    }>;
};
export async function generateMetadata({ params }: Props): Promise<Metadata> {
    const { slug, locale } = await params;
    try {
        const event = await getEvent(slug), title = localized(event, 'title', locale), description = localized(event, 'description', locale).slice(0, 180), image = mediaPath(event.image);
        return { title, description, alternates: { canonical: `/${locale}/events/${slug}`, languages: { ru: `/ru/events/${slug}`, en: `/en/events/${slug}` } }, openGraph: { title, description, type: 'website', images: image ? [image] : [] } };
    }
    catch {
        return { title: 'Tickethub', robots: { index: false, follow: false } };
    }
}
export default async function EventPage({ params }: Props) {
    const { slug } = await params;
    return <EventDetail event={await getEvent(slug)}/>;
}
