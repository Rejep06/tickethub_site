import type { MetadataRoute } from 'next';
import { publicApi } from '@/lib/api/server';
import type { PaginatedEvent } from '@/lib/api/generated';
export const dynamic = 'force-dynamic';
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
    const base = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';
    const rows: MetadataRoute.Sitemap = [];
    for (const locale of ['ru', 'en'])
        for (const p of ['', '/events', '/sports', '/concerts', '/other', '/about', '/how-it-works', '/faq', '/contacts'])
            rows.push({ url: base + '/' + locale + p });
    for (let page = 1; page <= 100; page++) {
        let data: PaginatedEvent;
        try {
            data = await publicApi<PaginatedEvent>(`events/?page_size=100&page=${page}`);
        }
        catch {
            break;
        }
        for (const event of data.results)
            for (const locale of ['ru', 'en'])
                rows.push({ url: `${base}/${locale}/events/${event.slug}`, alternates: { languages: { ru: `${base}/ru/events/${event.slug}`, en: `${base}/en/events/${event.slug}` } } });
        if (!data.next)
            break;
    }
    return rows;
}
