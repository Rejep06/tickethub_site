import type { Metadata } from 'next';
import { publicApi } from '@/lib/api/server';
import type { Page } from '@/lib/api/generated';
import { ContentPage } from '@/features/catalog/info';
export const metadata: Metadata = { title: 'Tickethub — документы' };
export default async function LegalPage({ params }: {
    params: Promise<{
        slug: string;
    }>;
}) {
    const { slug } = await params;
    let page: Page | null = null;
    try {
        page = await publicApi<Page>(`legal/${encodeURIComponent(slug)}/`);
    }
    catch {
    }
    return <ContentPage slug={slug} legal initial={page}/>;
}
