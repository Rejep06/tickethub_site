export const ANALYTICS_PREFERENCE_KEY = 'th.analytics.v1';
export const ANALYTICS_PREFERENCE_EVENT = 'th:analytics-preference';
// A failed storage write must never undo a visitor's decision to stop tracking.
let deniedInThisTab = false;
/** No stored positive choice (or blocked storage) means no optional analytics. */
export function hasAnalyticsConsent(storage: Pick<Storage, 'getItem'>): boolean {
    if (deniedInThisTab) return false;
    try { return storage.getItem(ANALYTICS_PREFERENCE_KEY) === 'yes'; } catch { return false; }
}
export function setAnalyticsConsent(storage: Pick<Storage, 'setItem'>, allowed: boolean): boolean {
    deniedInThisTab = !allowed;
    try { storage.setItem(ANALYTICS_PREFERENCE_KEY, allowed ? 'yes' : 'no'); return true; }
    catch { deniedInThisTab = true; return false; }
}
