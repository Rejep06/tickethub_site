import { notFound } from 'next/navigation';
import { setRequestLocale } from 'next-intl/server';
import type { ReactNode } from 'react';
import Providers from '@/components/providers';
import { publicApi } from '@/lib/api/server';
import type { PublicConfig } from '@/lib/api/generated';
export const dynamic = 'force-dynamic';
export default async function LocaleLayout({ children, params }: {
    children: ReactNode;
    params: Promise<{
        locale: string;
    }>;
}) {
    const { locale } = await params;
    if (locale !== 'ru' && locale !== 'en')
        notFound();
    setRequestLocale(locale);
    const messages = (await import(`../../messages/${locale}.json`)).default;
    let config: PublicConfig | null = null;
    try {
        config = await publicApi<PublicConfig>('public/config/');
    }
    catch {
    }
    return <Providers locale={locale} messages={messages} config={config}>{children}</Providers>;
}
