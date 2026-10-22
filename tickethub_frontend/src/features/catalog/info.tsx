'use client';
import Link from 'next/link';
import { ArrowUpRight, Mail, Phone, MessagesSquare } from 'lucide-react';
import { useT, useLang } from '@/i18n/use-t';
import { useConfig } from '@/features/auth/session';
import { useApi } from '@/lib/hooks';
import type { Page } from '@/lib/api/generated';
import { ApiError } from '@/lib/api/client';
import { localized } from '@/lib/safe';
import { Alert, ErrorState, PageHeader, Skeleton } from '@/components/ui';
import { FAQ, HowItWorks, RequestBanner } from './home';
import { About } from './about';
export function Info({ type }: { type: string }) {
    const t = useT(), lang = useLang(), config = useConfig();
    if (type === 'how-it-works') return <div className="container section"><HowItWorks standalone /><RequestBanner /></div>;
    if (type === 'faq') return <div className="container section faq-page"><PageHeader title={t('faq')} description={t('faqIntro')} /><FAQ searchable /><div className="help-strip"><div><h2>{t('questionStill')}</h2><p>{t('questionStillText')}</p></div><Link className="btn btn-primary" href={`/${lang}/request`}>{t('consult')}<ArrowUpRight size={18} /></Link></div></div>;
    if (type === 'contacts') return <div className="container section contacts-page"><div className="eyebrow">TICKETHUB / HELLO</div><PageHeader title={t('contacts')} description={t('contactsIntro')} /><div className="contact-grid">
        {config?.contacts?.email && <a className="contact-card" href={`mailto:${config.contacts.email}`}><Mail size={30} strokeWidth={1.5} /><h2>{t('contactEmail')}</h2><p>{config.contacts.email}</p><ArrowUpRight size={22} /></a>}
        {config?.contacts?.phone && <a className="contact-card" href={`tel:${config.contacts.phone.replace(/[^+\d]/g, '')}`}><Phone size={30} strokeWidth={1.5} /><h2>{t('contactPhone')}</h2><p>{config.contacts.phone}</p><ArrowUpRight size={22} /></a>}
        <Link className="contact-card contact-card-accent" href={`/${lang}/request`}><MessagesSquare size={30} strokeWidth={1.5} /><h2>{t('contactRequest')}</h2><p>{t('contactRequestText')}</p><ArrowUpRight size={22} /></Link>
    </div>{config?.contacts?.hours && <p className="contact-hours">{t('workingHours')}: {config.contacts.hours}</p>}<div className="section"><RequestBanner /></div></div>;
    return <About />;
}
export function ContentPage({ slug, legal = false, initial = null }: { slug: string; legal?: boolean; initial?: Page | null }) {
    const t = useT(), lang = useLang(), path = `${legal ? 'legal' : 'content'}/${encodeURIComponent(slug)}/`;
    const data = useApi<Page>(path, !initial);
    const page = initial ?? data.data;
    return <div className="container section narrow legal-page">{page ? <><PageHeader title={localized(page, 'title', lang)} /><article className="prose preserve-lines">{localized(page, 'body', lang)}</article></> : data.isPending ? <Skeleton /> : data.error instanceof ApiError && data.error.status === 404 ? <div className="stack"><Alert>{t('legalMissing')}</Alert><Link className="btn btn-secondary" href={`/${lang}/contacts`}>{t('contacts')}</Link></div> : <ErrorState error={data.error} retry={() => void data.refetch()} />}</div>;
}
