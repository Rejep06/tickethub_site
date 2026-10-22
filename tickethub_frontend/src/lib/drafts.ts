import type { SelectionInput } from './api/generated';
export interface SelectionDraft {
    eventId: string;
    slug: string;
    selection: SelectionInput;
    createdAt: number;
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function validDraft(value: unknown): value is SelectionDraft {
    if (!value || typeof value !== 'object')
        return false;
    const d = value as SelectionDraft;
    if (!uuid.test(d.eventId) || typeof d.slug !== 'string' || !d.selection || typeof d.createdAt !== 'number' || !Number.isFinite(d.createdAt))
        return false;
    const s = d.selection;
    return s.mode === 'SEATS' ? Array.isArray(s.seat_ids) && s.seat_ids.length > 0 && s.seat_ids.length <= 10 && new Set(s.seat_ids).size === s.seat_ids.length && s.seat_ids.every(id => uuid.test(id)) : s.mode === 'CATEGORY' && uuid.test(s.offer_id ?? '') && Number.isInteger(s.quantity) && (s.quantity ?? 0) > 0 && (s.quantity ?? 0) <= 10;
}
export function loadDraft(): SelectionDraft | null {
    try {
        const value: unknown = JSON.parse(sessionStorage.getItem('th.selection') || 'null');
        return validDraft(value) ? value : null;
    }
    catch {
        return null;
    }
}
export function saveDraft(draft: SelectionDraft): void {
    if (!validDraft(draft))
        throw new Error('INVALID_SELECTION');
    const selection: SelectionInput = draft.selection.mode === 'SEATS' ? { mode: 'SEATS', seat_ids: draft.selection.seat_ids } : { mode: 'CATEGORY', offer_id: draft.selection.offer_id, quantity: draft.selection.quantity };
    sessionStorage.setItem('th.selection', JSON.stringify({ eventId: draft.eventId, slug: draft.slug, selection, createdAt: draft.createdAt }));
}
