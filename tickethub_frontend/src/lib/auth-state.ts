import { ApiError } from './api/client';
/** A missing session is normal for a guest; a CSRF/permission failure is not. */
export function isAuthRequired(error: unknown): boolean {
    return error instanceof ApiError && (error.status === 401 || error.code === 'AUTH_REQUIRED' || error.code === 'NOT_AUTHENTICATED');
}
export function supportReference(error: unknown): string | null {
    if (!(error instanceof ApiError) || isAuthRequired(error) || error.code === 'VALIDATION_ERROR') return null;
    return error.requestId && /^[a-zA-Z0-9_-]{1,128}$/.test(error.requestId) ? error.requestId : null;
}
