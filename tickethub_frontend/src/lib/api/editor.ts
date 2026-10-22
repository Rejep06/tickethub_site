/** Additive API in venues/editor_api.py and venues/editor_services.py.
 * Deliberately separate from generated.ts: the supplied OpenAPI is historical.
 */
import { api } from './client';
import type { Plan, Seat } from './generated';
export interface EditorSnapshot { plan: Plan; seats: Seat[] }
export interface EditorSeatInput {
    sector: string; row: string; number: string;
    x: string | number; y: string | number;
    adjacency_group?: string; adjacency_position?: number | null;
}
export interface BlockInput {
    sector: string; rows: number; seats_per_row: number; row_start: number;
    seat_start: number; seat_step: -2 | -1 | 1 | 2;
    x: number; y: number; width: number; row_spacing: number;
    angle: number; curve: number; reverse_alternate: boolean; aisles_after: number[];
}
export interface SeatPreview { seats: EditorSeatInput[]; count: number; saved: false }
export interface BulkEditInput {
    expected_version: number;
    create: EditorSeatInput[];
    update: (Partial<EditorSeatInput> & { id: string })[];
    delete: string[];
}
export interface BulkEditResult { version: number; created_ids: string[]; created: number; updated: number; deleted: number }
export const editorApi = {
    snapshot: (id: string) => api<EditorSnapshot>(`staff/plans/${id}/preview/`),
    blockPreview: (id: string, body: BlockInput) => api<SeatPreview>(`staff/plans/${id}/block-preview/`, { method: 'POST', body }),
    csvPreview: (id: string, text: string) => api<SeatPreview>(`staff/plans/${id}/csv-preview/`, { method: 'POST', body: { text } }),
    save: (id: string, body: BulkEditInput) => api<BulkEditResult>(`staff/plans/${id}/bulk-edit/`, { method: 'POST', body }),
    publish: (id: string, version: number) => api<Plan>(`staff/plans/${id}/publish/`, { method: 'POST', body: { expected_version: version } }),
    clone: (id: string) => api<Plan>(`staff/plans/${id}/clone-version/`, { method: 'POST', body: {} })
};
