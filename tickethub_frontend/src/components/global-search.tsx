'use client';
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Search, ArrowUpRight, ArrowRight, X } from 'lucide-react';
import { api } from '@/lib/api/client';
import type { PaginatedEvent } from '@/lib/api/generated';
import { localized } from '@/lib/safe';
import { useT, useLang } from '@/i18n/use-t';
import { Button, ErrorState, Input, Modal } from './ui';

export function GlobalSearch() {
    const t = useT();
    const [open, setOpen] = useState(false);
    useEffect(() => {
        const shortcut = (event: KeyboardEvent) => {
            const target = event.target;
            const typing = target instanceof HTMLElement && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName));
            if (((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') || (!typing && event.key === '/' && !event.altKey && !event.ctrlKey && !event.metaKey)) {
                // Do not replace another open dialog, e.g. a checkout confirmation.
                if (document.querySelector('dialog[open]')) return;
                event.preventDefault(); setOpen(true);
            }
        };
        window.addEventListener('keydown', shortcut);
        return () => window.removeEventListener('keydown', shortcut);
    }, []);
    return <>
        <button type="button" className="icon-button header-search-button" aria-label={t('quickSearch')} title={`${t('quickSearch')} (Ctrl+K)`} onClick={() => setOpen(true)}><Search size={19} aria-hidden="true" /></button>
        {open && <SearchDialog onClose={() => setOpen(false)} />}
    </>;
}
function SearchDialog({ onClose }: { onClose: () => void }) {
    const t = useT(), lang = useLang(), router = useRouter();
    const [input, setInput] = useState('');
    const [query, setQuery] = useState('');
    const inputRef = useRef<HTMLInputElement>(null);
    useEffect(() => { inputRef.current?.focus(); }, []);
    useEffect(() => {
        const timer = setTimeout(() => setQuery(input.trim()), 300);
        return () => clearTimeout(timer);
    }, [input]);
    const result = useQuery({
        queryKey: ['api', 'quick-search', lang, query],
        queryFn: ({ signal }) => api<PaginatedEvent>(`events/?q=${encodeURIComponent(query)}&page_size=5`, { locale: lang, signal }),
        enabled: query.length >= 2, staleTime: 15000
    });
    const href = `/${lang}/events${input.trim() ? '?q=' + encodeURIComponent(input.trim()) : ''}`;
    const waiting = input.trim() !== query || result.isFetching;
    return <Modal open onClose={onClose} title={t('quickSearch')}>
        <form className="search-dialog-form" onSubmit={event => { event.preventDefault(); router.push(href); onClose(); }}>
            <label htmlFor="global-event-search" className="sr-only">{t('search')}</label>
            <div className="search-input-wrap"><Search size={22} aria-hidden="true" />
                <Input ref={inputRef} autoFocus id="global-event-search" placeholder={t('searchPlaceholder')} autoComplete="off" value={input} onChange={event => setInput(event.target.value)} />
                {input && <button type="button" className="icon-button" aria-label={t('clearSearch')} onClick={() => { setInput(''); inputRef.current?.focus(); }}><X size={17} /></button>}
            </div>
            <Button type="submit">{t('searchButton')} <ArrowRight size={17} /></Button>
        </form>
        <div className="search-dialog-content" aria-live="polite" aria-busy={waiting}>
            {input.trim().length < 2 ? <><p className="muted">{t('searchHint')}</p><div className="chip-list">{['sports', 'concerts', 'other'].map(route => <Link className="chip" key={route} onClick={onClose} href={`/${lang}/${route}`}>{t(route)} <ArrowUpRight size={15} /></Link>)}</div></> : waiting ? <p className="muted">{t('loading')}</p> : result.error ? <ErrorState error={result.error} retry={() => void result.refetch()} /> : result.data?.results.length ? <>
                <p className="eyebrow">{t('searchMatches')}</p>
                <div className="search-results">{result.data.results.map(event => <Link key={event.id} href={`/${lang}/events/${event.slug}`} onClick={onClose}>
                    <span><strong>{localized(event, 'title', lang)}</strong><small>{localized(event.venue, 'name', lang)}</small></span><ArrowUpRight size={19} aria-hidden="true" />
                </Link>)}</div><Link className="text-link" href={href} onClick={onClose}>{t('searchAllResults')} →</Link>
            </> : <p className="muted">{t('noResultsText')}</p>}
        </div>
    </Modal>;
}
