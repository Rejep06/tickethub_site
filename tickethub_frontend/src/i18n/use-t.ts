'use client';
import { useLocale, useTranslations } from 'next-intl';
import type { Locale } from '@/lib/money';
export function useT() {
    return useTranslations();
}
export function useLang(): Locale {
    return useLocale() === 'en' ? 'en' : 'ru';
}
