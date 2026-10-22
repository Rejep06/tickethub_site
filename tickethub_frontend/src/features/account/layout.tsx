'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';
import { useT, useLang } from '@/i18n/use-t';
import { RequireAuth } from '@/features/auth/session';
import { OrderList } from './orders';
import { RequestList } from './requests';
import { PageHeader } from '@/components/ui';
export function AccountLayout({ children }: {
    children: ReactNode;
}) {
    const t = useT(), lang = useLang(), path = usePathname();
    return <div className="container section">
  <nav className="account-nav">{[['', 'account'], ['/orders', 'orders'], ['/requests', 'requests'], ['/profile', 'profile']].map(([slug, key]) => <Link key={key} className={path === `/${lang}/account${slug}` ? 'active' : ''} href={`/${lang}/account${slug}`}>{t(key)}</Link>)}</nav>
  <RequireAuth>{children}</RequireAuth>
    </div>;
}
export function AccountHome() {
    const t = useT();
    return <div className="stack">
  <PageHeader title={t('accountWelcome')} description={t('accountText')}/>
  <h2>{t('orders')}</h2>
  <OrderList compact/>
  <h2>{t('requests')}</h2>
  <RequestList compact/>
    </div>;
}
