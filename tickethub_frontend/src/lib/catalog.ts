/** Only parameters actually accepted by events/views.py. Dates use [from,to). */
export function catalogPath(search: URLSearchParams): string {
    const p = new URLSearchParams();
    for (const k of ['q', 'category', 'kind', 'city', 'venue', 'participant', 'date_from', 'date_to', 'status', 'ordering', 'page', 'page_size']) {
        const v = search.get(k);
        if (v)
            p.set(k, v);
    }
    if (!p.has('ordering'))
        p.set('ordering', 'start_at');
    return 'events/?' + p.toString();
}

/** The public form says "through this date"; the backend uses [from, to). */
export function inclusiveDateToExclusive(value: string): string {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return '';
    const date = new Date(value + 'T00:00:00Z');
    if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== value) return '';
    date.setUTCDate(date.getUTCDate() + 1);
    return date.toISOString();
}
export function exclusiveDateToInclusive(value: string): string {
    if (!value) return '';
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return '';
    date.setUTCDate(date.getUTCDate() - 1);
    return date.toISOString().slice(0, 10);
}

/** Homepage and category landing show the same published catalogue as /events. */
export function homeCatalogPath(kind: 'ALL' | 'SPORT' | 'CONCERT' | 'OTHER' = 'ALL'): string {
    const query = new URLSearchParams({ ordering: 'start_at', page_size: '6' });
    if (kind !== 'ALL') query.set('kind', kind);
    return catalogPath(query);
}
