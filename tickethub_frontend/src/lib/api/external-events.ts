/** Actual contract: external_events/serializers.py, views.py, services.py.
 * IMPORT_ONLY is the only implemented provider mode. No ticket inventory API.
 */
import { api } from './client';
export interface ImportWarning { code: string; message: string; resource?: string }
export interface ExternalDate {
    id: string; external_date_id: string; event: string; source_active: boolean;
    source_start_at: string | null; last_seen_at: string;
}
export interface ImportResource { status: string; code?: string; bytes?: number; sha256?: string; snapshot_id?: string }
export interface ImportReport {
    status: 'RUNNING' | 'PARTIAL' | 'FAILED'; source_id: string; mode: 'IMPORT_ONLY';
    created: { events: string[]; venues: number; seats: number; ticket_units: number };
    updated: { events: string[] }; warnings: ImportWarning[];
    resources: Record<string, ImportResource>; error_code?: string;
}
export interface ExternalSource {
    id: string; provider: string; external_event_id: string; event_source_id: string;
    external_place_id: string; external_layout_id: string; url: string; title: string;
    venue: string | null; status: 'NEW' | 'RUNNING' | 'PARTIAL' | 'FAILED';
    last_attempt_at: string | null; last_metadata_sync_at: string | null;
    diagnostics: Partial<ImportReport>; dates: ExternalDate[];
}
export interface ExternalPage { count: number; next: string | null; previous: string | null; results: ExternalSource[] }
export interface ImportPreview {
    status: 'PREVIEW'; url: string; title: string;
    venue: { name: string; address: string; city: string };
    provider: { external_event_id: string; event_source_id: string; external_layout_id: string };
    dates: { external_date_id: string; start_at: string | null }[];
    dates_authoritative: boolean; seats_count: number | null; standing_zones_count: number | null;
    supported_mode: 'IMPORT_ONLY'; warnings: ImportWarning[];
}
const payload = (url: string) => ({ provider: 'portalbilet', mode: 'IMPORT_ONLY', url });
// The provider's default network budget is 35s; the old generic 25s timer was too short.
// Mutations are NEVER retried automatically after a timeout (they may have committed).
export const externalEventsApi = {
    preview: (url: string) => api<ImportPreview>('staff/external-events/preview/', { method: 'POST', body: payload(url), timeoutMs: 90000 }),
    import: (url: string) => api<ImportReport>('staff/external-events/import/', { method: 'POST', body: payload(url), timeoutMs: 90000 }),
    sync: (id: string) => api<ImportReport>(`staff/external-events/${id}/sync/`, { method: 'POST', body: {}, timeoutMs: 90000 })
};
/** Convenience UX only. The server remains authoritative for provider URL validation. */
export function portalBiletUrl(value: string): string | null {
    try {
        const raw = value.trim();
        if (/[\\\x00-\x20\x7f]/.test(raw)) return null;
        const url = new URL(raw);
        if (url.protocol !== 'https:' || !['portalbilet.ru', 'www.portalbilet.ru'].includes(url.hostname) || url.username || url.password || (url.port && url.port !== '443')) return null;
        const parts = url.pathname.replace(/^\/+|\/+$/g, '').split('/');
        if (parts.length !== 2 || parts.some(part => part.length > 220 || !/^[a-z0-9]+(?:[-_][a-z0-9]+)*$/.test(part))) return null;
        return `https://portalbilet.ru/${parts.join('/')}`;
    } catch { return null; }
}
