'use client';
import { useEffect, useState, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { NextIntlClientProvider } from 'next-intl';
import { ToastProvider } from './ui/toast';
import { PublicConfigProvider } from '@/features/auth/session';
import type { PublicConfig } from '@/lib/api/generated';
export default function Providers({ children, locale, messages, config }: {
    children: ReactNode;
    locale: string;
    messages: Record<string, string>;
    config: PublicConfig | null;
}) {
    useEffect(() => { document.documentElement.lang = locale; }, [locale]);
    const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { staleTime: 15000, retry: false, refetchOnWindowFocus: true }, mutations: { retry: false } } }));
    return <NextIntlClientProvider locale={locale} messages={messages}><QueryClientProvider client={client}><PublicConfigProvider initial={config}><ToastProvider>{children}</ToastProvider></PublicConfigProvider></QueryClientProvider></NextIntlClientProvider>;
}
