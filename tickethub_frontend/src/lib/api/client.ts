import { record } from '../safe';
import { normalizeDetails } from './error-details';
import { apiUrl, apiPath } from './url';
export class ApiError extends Error {
    constructor(public status: number, public code: string, message: string, public details: Record<string, unknown> = {}, public requestId?: string, public retryAfter?: number) {
        super(message);
        this.name = 'ApiError';
    }
}
export interface ApiOptions {
    method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
    body?: unknown;
    key?: string;
    signal?: AbortSignal;
    locale?: 'ru' | 'en';
    /** Bounded per-operation timeout. No automatic retry of writes. */
    timeoutMs?: number;
}
export async function readResponse<T>(response: Response): Promise<T> {
    if (response.status === 204)
        return undefined as T;
    let body: unknown;
    try {
        body = response.headers.get('content-type')?.includes('json') ? await response.json() : null;
    }
    catch {
        body = null;
    }
    if (!response.ok) {
        const data = record(body);
        const code = typeof data.code === 'string' ? data.code : response.status === 401 ? 'AUTH_REQUIRED' : response.status === 403 ? 'FORBIDDEN' : response.status === 413 ? 'REQUEST_TOO_LARGE' : 'HTTP_ERROR';
        const retry = Number(response.headers.get('Retry-After'));
        throw new ApiError(response.status, code, response.status < 500 && typeof data.message === 'string' ? data.message : 'API_UNAVAILABLE', response.status < 500 ? normalizeDetails(data.details) : {}, typeof data.request_id === 'string' ? data.request_id : response.headers.get('X-Request-ID') ?? undefined, Number.isFinite(retry) && retry > 0 ? retry : undefined);
    }
    if (body === null)
        throw new ApiError(502, 'INVALID_RESPONSE', 'API_UNAVAILABLE');
    return body as T;
}
export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
    // Validate before issuing CSRF or any other network request.
    apiPath(path);
    const { method = 'GET', body, key, signal, locale } = options;
    const timeoutMs = options.timeoutMs ?? 25000;
    if (!Number.isFinite(timeoutMs) || timeoutMs < 1 || timeoutMs > 300000) throw new Error('Invalid API timeout');
    const controller = new AbortController();
    const forwardAbort = () => controller.abort();
    if (signal?.aborted)
        controller.abort();
    signal?.addEventListener('abort', forwardAbort, { once: true });
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
        const headers = new Headers({ 'Accept': 'application/json', 'X-Request-ID': crypto.randomUUID() });
        if (method !== 'GET') {
            const csrf = await readResponse<{
                csrf_token: string;
            }>(await fetch(apiUrl('auth/csrf/'), {
                credentials: 'include', cache: 'no-store', signal: controller.signal
            }));
            if (!csrf.csrf_token)
                throw new ApiError(403, 'CSRF_FAILED', 'CSRF_FAILED');
            headers.set('X-CSRFToken', csrf.csrf_token);
        }
        const multipart = typeof FormData !== 'undefined' && body instanceof FormData;
        if (body !== undefined && !multipart)
            headers.set('Content-Type', 'application/json');
        const language = locale ?? (typeof document !== 'undefined' && document.documentElement.lang === 'en' ? 'en' : 'ru');
        headers.set('Accept-Language', language);
        if (key)
            headers.set('Idempotency-Key', key);
        const url = apiUrl(path, language);
        return await readResponse<T>(await fetch(url, {
            method, headers, credentials: 'include', cache: 'no-store', signal: controller.signal,
            body: body === undefined ? undefined : multipart ? body : JSON.stringify(body)
        }));
    }
    catch (error) {
        if (error instanceof ApiError)
            throw error;
        if (signal?.aborted)
            throw error;
        throw new ApiError(0, controller.signal.aborted ? 'TIMEOUT' : 'NETWORK_ERROR', 'NETWORK_ERROR');
    }
    finally {
        clearTimeout(timer);
        signal?.removeEventListener('abort', forwardAbort);
    }
}
