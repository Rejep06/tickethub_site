import type { ReactNode } from 'react';
import type { Metadata } from 'next';
import { headers } from 'next/headers';
import '@/styles/globals.css';
import { THEME_INIT_SCRIPT } from '@/lib/theme';
export const metadata: Metadata = { metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'), title: { default: 'Tickethub — билеты на события', template: '%s | Tickethub' }, description: 'Ваше место в больших событиях. Билеты на спорт и концерты, внимательный подбор и поддержка команды Tickethub.' };
export default async function RootLayout({ children }: {
    children: ReactNode;
}) {
    const h = await headers();
    const locale = h.get('x-tickethub-locale') === 'en' ? 'en' : 'ru';
    return <html lang={locale} suppressHydrationWarning><head><script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} /></head><body>{children}</body></html>;
}
