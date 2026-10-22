'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ConfirmDialog } from './index';
/** Protects tab close and ordinary in-app anchor navigation. Browser history remains browser-owned. */
export function UnsavedGuard({ dirty }: {
    dirty: boolean;
}) {
    const router = useRouter();
    const [href, setHref] = useState('');
    useEffect(() => {
        if (!dirty)
            return;
        const before = (e: BeforeUnloadEvent) => {
            e.preventDefault();
            e.returnValue = '';
        };
        const click = (e: MouseEvent) => {
            const link = e.target instanceof Element ? e.target.closest('a') : null;
            if (e.defaultPrevented || !link || link.hasAttribute('download') || link.target === '_blank' || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey || e.button !== 0)
                return;
            const url = new URL(link.href, location.href);
            if (!['http:', 'https:'].includes(url.protocol) || url.origin !== location.origin || url.href === location.href)
                return;
            e.preventDefault();
            e.stopPropagation();
            setHref(url.pathname + url.search + url.hash);
        };
        window.addEventListener('beforeunload', before);
        document.addEventListener('click', click, true);
        return () => {
            window.removeEventListener('beforeunload', before);
            document.removeEventListener('click', click, true);
        };
    }, [dirty]);
    return <ConfirmDialog open={!!href} onClose={() => setHref('')} title="Уйти без сохранения?" danger onConfirm={() => {
        const next = href;
        setHref('');
        router.push(next);
    }}><p>Несохранённые изменения будут потеряны.</p></ConfirmDialog>;
}
