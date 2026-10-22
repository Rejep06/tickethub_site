import type { CreateHoldInput } from './api/generated';
import { ApiError } from './api/client';
import { checkoutApi } from './api/endpoints';
import type { Store } from './api/attempts';
import { validDraft } from './drafts';
const storageKey = 'th.pendingHold';
/** Only event/selection/pricing identifiers. Never customer contact details or comments. */
export function readPendingHold(store: Store): CreateHoldInput | null {
    try {
        const raw: unknown = JSON.parse(store.getItem(storageKey) ?? 'null');
        if (!raw || typeof raw !== 'object' || !('event_id' in raw) || !('selection' in raw) || !('expected_total_minor' in raw))
            return null;
        if (!validDraft({ eventId: raw.event_id, slug: 'pending', selection: raw.selection, createdAt: 0 }) || typeof raw.expected_total_minor !== 'number' || !Number.isSafeInteger(raw.expected_total_minor) || raw.expected_total_minor < 0)
            return null;
        const value = raw as CreateHoldInput;
        if (value.expected_offer_versions && Object.values(value.expected_offer_versions).some(v => !Number.isSafeInteger(v) || v < 1))
            return null;
        return value;
    }
    catch {
        return null;
    }
}
export async function reserveRecoverably(body: CreateHoldInput, store: Store = sessionStorage) {
    store.setItem(storageKey, JSON.stringify(body));
    try {
        const hold = await checkoutApi.hold(body);
        store.removeItem(storageKey);
        return hold;
    }
    catch (error) {
        if (error instanceof ApiError && error.status >= 400 && error.status < 500 && !['PENDING_ATTEMPT', 'IDEMPOTENCY_CONFLICT'].includes(error.code))
            store.removeItem(storageKey);
        throw error;
    }
}
