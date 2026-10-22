import type { Locale } from './money';
export function safeNext(value: string | null | undefined, fallback = '/ru/account'): string {
    if (!value || /[\\\r\n\x00]/.test(value) || !/^\/(ru|en)(\/|$)/.test(value))
        return fallback;
    try {
        const decoded = decodeURIComponent(value);
        if (/[\\\r\n\x00]/.test(decoded) || decoded.startsWith('//'))
            return fallback;
        const url = new URL(value, 'https://tickethub.invalid');
        return url.origin === 'https://tickethub.invalid' && /^\/(ru|en)(\/|$)/.test(url.pathname) ? url.pathname + url.search + url.hash : fallback;
    }
    catch {
        return fallback;
    }
}
export function localized(value: object, field: string, locale: Locale): string {
    const record = value as Record<string, unknown>;
    const text = record[`${field}_${locale}`];
    const fallback = record[`${field}_ru`];
    return typeof text === 'string' && text ? text : typeof fallback === 'string' ? fallback : '';
}
export function text(value: unknown, fallback = ''): string {
    return typeof value === 'string' && value ? value : fallback;
}
export function record(value: unknown): Record<string, unknown> {
    return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
export function mediaPath(value: string | null | undefined): string | null {
    if (!value)
        return null;
    // Backend returns absolute localhost URLs as well as relative media paths.
    try {
        const url = new URL(value, 'https://tickethub.invalid');
        if (!['https:', 'http:'].includes(url.protocol) || !url.pathname.startsWith('/media/'))
            return null;
        return url.pathname + url.search;
    }
    catch {
        return null;
    }
}
export function queryString(values: Record<string, string | number | null | undefined>): string {
    const params = new URLSearchParams();
    Object.entries(values).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '')
            params.set(key, String(value));
    });
    return params.toString();
}
