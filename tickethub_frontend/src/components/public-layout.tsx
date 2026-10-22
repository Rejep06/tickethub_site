'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';
import { Menu, UserRound, X, ArrowUpRight, ArrowRight } from 'lucide-react';
import { useT, useLang } from '@/i18n/use-t';
import { useSession, useConfig } from '@/features/auth/session';
import { ThemeToggle, ThemePicker } from './theme-toggle';
import { GlobalSearch } from './global-search';
import { Logo } from './brand';
export { Logo } from './brand';

export function PublicHeader() {
    const t = useT(), locale = useLang(), path = usePathname(), params = useSearchParams(), session = useSession();
    const signedIn = !!session.data && !session.error;
    const [menu, setMenu] = useState(false);
    const other = locale === 'ru' ? 'en' : 'ru';
    const newPath = path.replace(/^\/(ru|en)(?=\/|$)/, `/${other}`) + (params.size ? '?' + params.toString() : '');
    useEffect(() => {
        if (!menu) return;
        const close = (event: KeyboardEvent) => { if (event.key === 'Escape') setMenu(false); };
        window.addEventListener('keydown', close);
        return () => window.removeEventListener('keydown', close);
    }, [menu]);
    const nav = ['events', 'sports', 'concerts', 'about'];
    return <><a href="#main" className="skip-link">{t('skip')}</a><header className="public-header">
        <div className="container header-inner">
            <Link href={`/${locale}`} className="logo-link" aria-label="Tickethub"><Logo /></Link>
            <nav className="header-nav desktop-only" aria-label={t('menu')}>{nav.map(route => <Link key={route} href={`/${locale}/${route}`} className={path === `/${locale}/${route}` ? 'active' : ''} aria-current={path === `/${locale}/${route}` ? 'page' : undefined}>{t(route)}</Link>)}</nav>
            <div className="header-actions">
                <GlobalSearch />
                <ThemeToggle />
                <Link className="lang-switch" href={newPath} hrefLang={other} aria-label={other === 'en' ? 'Switch to English' : 'Переключить на русский'} onClick={() => { document.cookie = `th-locale=${other}; Path=/; Max-Age=31536000; SameSite=Lax`; }}>{other.toUpperCase()}</Link>
                <span className="header-divider desktop-only" aria-hidden="true" />
                <Link className="icon-button account-link" href={`/${locale}/${signedIn ? 'account' : 'login'}`} aria-label={t(signedIn ? 'account' : 'login')}><UserRound size={19} aria-hidden="true" /><span className="header-account-label">{t(signedIn ? 'account' : 'login')}</span></Link>
                <Link className="btn btn-primary header-request" href={`/${locale}/request`}>{t('requestTickets')}<ArrowUpRight size={16} aria-hidden="true" /></Link>
                <button type="button" className="icon-button mobile-only menu-button" aria-expanded={menu} aria-controls="mobile-menu" aria-label={t(menu ? 'close' : 'menu')} onClick={() => setMenu(!menu)}>{menu ? <X size={22} /> : <Menu size={22} />}</button>
            </div>
        </div>
        {menu && <nav id="mobile-menu" className="mobile-nav" aria-label={t('menu')} onClick={() => setMenu(false)}>
            {[...nav, 'faq', 'contacts'].map(route => <Link key={route} href={`/${locale}/${route}`}>{t(route)}<ArrowUpRight size={19} /></Link>)}
            <Link href={`/${locale}/${signedIn ? 'account' : 'login'}`}>{t(signedIn ? 'account' : 'login')}<UserRound size={19} aria-hidden="true" /></Link>
            <Link className="btn btn-primary" href={`/${locale}/request`}>{t('requestTickets')}<ArrowRight size={18} /></Link>
        </nav>}
    </header></>;
}
export function PublicFooter() {
    const t = useT(), locale = useLang(), config = useConfig();
    return <footer className="public-footer"><div className="container">
        <div className="footer-topline"><p>{t('footerNote')}</p><Link className="round-link" href={`/${locale}/events`} aria-label={t('browse')}><ArrowUpRight size={28} aria-hidden="true" /></Link></div>
        <div className="footer-grid">
            <div className="footer-brand"><Link href={`/${locale}`} aria-label="Tickethub"><Logo /></Link><p className="muted pre-line">{t('footerText')}</p><div className="footer-theme"><small>{t('appearance')}</small><ThemePicker /></div></div>
            <div><h3>{t('events')}</h3>{['sports', 'concerts', 'other'].map(r => <Link key={r} href={`/${locale}/${r}`}>{t(r)}</Link>)}</div>
            <div><h3>Tickethub</h3>{['about', 'how-it-works', 'faq', 'contacts'].map(r => <Link key={r} href={`/${locale}/${r}`}>{t(r === 'how-it-works' ? 'how' : r)}</Link>)}</div>
            <div><h3>{t('contacts')}</h3>
                {config?.contacts?.email && <a href={`mailto:${config.contacts.email}`}>{config.contacts.email}</a>}
                {config?.contacts?.phone && <a href={`tel:${config.contacts.phone.replace(/[^+\d]/g, '')}`}>{config.contacts.phone}</a>}
                {config?.contacts?.hours && <small className="working-hours">{config.contacts.hours}</small>}
                <Link href={`/${locale}/request`} className="footer-consult">{t('consult')} <ArrowUpRight size={15} aria-hidden="true" /></Link>
            </div>
        </div>
        <div className="footer-bottom"><span>© {new Date().getFullYear()} Tickethub</span><div className="actions">{['privacy', 'offer', 'refund-policy'].map(r => <Link href={`/${locale}/legal/${r}`} key={r}>{t(r)}</Link>)}</div></div>
    </div></footer>;
}
