import 'server-only';
import { headers } from 'next/headers';
import { readResponse } from './client';
import { apiPath, type ApiLocale } from './url';
/** Public data only: no shared authentication cookies, and no cached personal responses. */
export async function publicApi<T>(path: string, locale?: ApiLocale): Promise<T> {
    const language = locale ?? ((await headers()).get('x-tickethub-locale') === 'en' ? 'en' : 'ru');
    const base = process.env.API_INTERNAL_URL || `${process.env.BACKEND_ORIGIN || 'http://127.0.0.1:8000'}/api/v1/`;
    const url = new URL(apiPath(path, language), base.endsWith('/') ? base : base + '/');
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    try {
        return await readResponse<T>(await fetch(url, {
            headers: {
                Accept: 'application/json',
                'Accept-Language': language,
                'X-Forwarded-Proto': 'https'
            },
            cache: 'no-store',
            signal: controller.signal
        }));
    } finally {
        clearTimeout(timer);
    }
}
