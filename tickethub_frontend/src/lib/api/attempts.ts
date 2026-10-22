import { api, ApiError } from './client';
export interface Store {
    getItem(key: string): string | null;
    setItem(key: string, value: string): void;
    removeItem(key: string): void;
}
export interface Attempt {
    key: string;
    fingerprint: string;
}
function stable(value: unknown): string {
    if (Array.isArray(value))
        return '[' + value.map(stable).join(',') + ']';
    if (value && typeof value === 'object')
        return '{' + Object.entries(value).filter(([, v]) => v !== undefined).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => JSON.stringify(k) + ':' + stable(v)).join(',') + '}';
    return JSON.stringify(value) ?? 'null';
}
export async function fingerprint(value: unknown): Promise<string> {
    const data = new TextEncoder().encode(stable(value));
    return [...new Uint8Array(await crypto.subtle.digest('SHA-256', data))].map(x => x.toString(16).padStart(2, '0')).join('');
}
export async function beginAttempt(store: Store, scope: string, body: unknown): Promise<Attempt> {
    const hash = await fingerprint(body);
    const raw = store.getItem('th.attempt.' + scope);
    if (raw) {
        let previous: Attempt;
        try {
            const value: unknown = JSON.parse(raw);
            if (!value || typeof value !== 'object' || !('key' in value) || !('fingerprint' in value) || typeof value.key !== 'string' || !/^[0-9a-f-]{36}$/i.test(value.key) || typeof value.fingerprint !== 'string' || !/^[0-9a-f]{64}$/i.test(value.fingerprint))
                throw new Error('Invalid attempt');
            previous = { key: value.key, fingerprint: value.fingerprint };
        }
        catch {
            throw new ApiError(409, 'PENDING_ATTEMPT', 'PENDING_ATTEMPT');
        }
        if (previous.fingerprint !== hash)
            throw new ApiError(409, 'PENDING_ATTEMPT', 'PENDING_ATTEMPT');
        return previous;
    }
    const attempt = { key: crypto.randomUUID(), fingerprint: hash };
    store.setItem('th.attempt.' + scope, JSON.stringify(attempt));
    return attempt;
}
export function clearAttempt(store: Store, scope: string): void {
    store.removeItem('th.attempt.' + scope);
}
// No automatic retries. Network/5xx outcomes remain unresolved until an identical retry.
// Storage contains only UUID + SHA-256, not email, phone, OTP, password or comments.
export async function idempotentPost<T>(path: string, body: unknown, scope: string): Promise<T> {
    const attempt = await beginAttempt(sessionStorage, scope, body);
    try {
        const result = await api<T>(path, { method: 'POST', body, key: attempt.key });
        clearAttempt(sessionStorage, scope);
        return result;
    }
    catch (error) {
        if (error instanceof ApiError && error.status >= 400 && error.status < 500 && !['IDEMPOTENCY_CONFLICT', 'PENDING_ATTEMPT'].includes(error.code))
            clearAttempt(sessionStorage, scope);
        throw error;
    }
}
export function clearPrivateDrafts(): void {
    for (const key of Object.keys(sessionStorage))
        if (key.startsWith('th.'))
            sessionStorage.removeItem(key);
}
