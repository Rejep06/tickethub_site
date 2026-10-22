'use client';
import Link from 'next/link';
import { useT, useLang } from '@/i18n/use-t';
export default function NotFound() {
    const t = useT(), lang = useLang();
    return <div className="container section stack">
  <h1>{t('notFound')}</h1>
  <p>{t('notFoundText')}</p>
  <Link className="btn btn-primary" href={`/${lang}/events`}>{t('browse')}</Link>
    </div>;
}
