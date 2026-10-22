/** Django REST paths are canonical WITH a slash, including before a query string.
 * Used by browser fetches, SSR fetches and export links; never use for media URLs.
 */
export const API_BASE_PATH = '/api/v1/';
export type ApiLocale = 'ru' | 'en';

export function apiPath(path: string, locale?: ApiLocale): string {
    if (!path || /[\\\r\n\x00#]/.test(path) || path.startsWith('/')) {
        throw new Error('API path must be a relative REST path');
    }
    const queryAt = path.indexOf('?');
    const pathname = queryAt < 0 ? path : path.slice(0, queryAt);
    const query = queryAt < 0 ? '' : path.slice(queryAt + 1);
    const segments = pathname.replace(/\/+$/, '').split('/');
    if (!segments.length || segments.some(segment => {
        try {
            const decoded = decodeURIComponent(segment);
            return !decoded || decoded === '.' || decoded === '..' || /[\\/:\x00-\x20\x7f]/.test(decoded);
        } catch {
            return true;
        }
    })) {
        throw new Error('Invalid REST path');
    }
    const params = new URLSearchParams(query);
    // set() also removes duplicate lang parameters instead of appending another one.
    if (locale) params.set('lang', locale);
    const search = params.toString();
    return segments.join('/') + '/' + (search ? '?' + search : '');
}

export function apiUrl(path: string, locale?: ApiLocale): string {
    return API_BASE_PATH + apiPath(path, locale);
}
