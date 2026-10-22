import type { Seat } from './api/generated';
import type { BulkEditInput, EditorSeatInput } from './api/editor';
export const EDITOR_BATCH_LIMIT = 2000;
export const EDITOR_PLAN_LIMIT = 50000;
export interface DraftSeat extends Required<EditorSeatInput> { key: string; id?: string; x: string; y: string }
const identityFields = ['sector', 'row', 'number', 'x', 'y'] as const;
const fields = [...identityFields, 'adjacency_group', 'adjacency_position'] as const;
export function coordinate(value: string | number): string {
    if ((typeof value !== 'string' && typeof value !== 'number') || (typeof value === 'string' && !value.trim())) throw new Error('INVALID_GEOMETRY');
    const n = Number(value);
    if (!Number.isFinite(n) || n < 0 || n > 1) throw new Error('INVALID_GEOMETRY');
    return n.toFixed(6);
}
export function normalizeSeat(seat: EditorSeatInput): Required<EditorSeatInput> & { x: string; y: string } {
    const labels = { sector: storedText(seat.sector).trim(), row: storedText(seat.row).trim(), number: storedText(seat.number).trim() };
    if (!labels.sector || labels.sector.length > 50 || !labels.row || labels.row.length > 30 || !labels.number || labels.number.length > 30) throw new Error('INVALID_SEAT_LABEL');
    const position = seat.adjacency_position ?? null;
    const group = storedText(seat.adjacency_group);
    if (group.length > 80 || position !== null && (!Number.isInteger(position) || position < 0 || position > 1000000)) throw new Error('INVALID_GEOMETRY');
    return { ...labels, x: coordinate(seat.x), y: coordinate(seat.y), adjacency_group: group, adjacency_position: position };
}
/** Read and edit are different operations: do not validate imported data during render.
 * Keep missing/overlong labels as they are; never invent a row/seat number or truncate it.
 * A numeric label (including 0) is converted to text, without changing its meaning.
 */
function storedText(value: unknown): string {
    return typeof value === 'string' ? value : typeof value === 'number' && Number.isFinite(value) ? String(value) : '';
}
function storedCoordinate(value: unknown): string {
    try { return coordinate(value as string | number); }
    catch { return storedText(value); }
}
export function hasSeatPosition(seat: Pick<EditorSeatInput, 'x' | 'y'>): boolean {
    try { coordinate(seat.x); coordinate(seat.y); return true; }
    catch { return false; }
}
export function seatDrafts(seats: Seat[]): DraftSeat[] {
    return seats.map(seat => ({
        key: seat.id, id: seat.id,
        sector: storedText(seat.sector), row: storedText(seat.row), number: storedText(seat.number),
        x: storedCoordinate(seat.x), y: storedCoordinate(seat.y),
        adjacency_group: storedText(seat.adjacency_group), adjacency_position: seat.adjacency_position ?? null
    }));
}
export interface SeatIssue { key: string; id?: string; messages: string[] }
/** Non-throwing diagnostics for existing/imported seats. Staff can repair one record at a time. */
export function seatIssues(seats: DraftSeat[]): SeatIssue[] {
    const messages = new Map<string, string[]>();
    const identities = new Map<string, string[]>();
    const keys = new Set<string>();
    const add = (key: string, message: string) => {
        const items = messages.get(key) ?? [];
        if (!items.includes(message)) items.push(message);
        messages.set(key, items);
    };
    for (const seat of seats) {
        for (const [field, label, limit] of [['sector', 'Сектор', 50], ['row', 'Ряд', 30], ['number', 'Номер места', 30]] as const) {
            const value = storedText(seat[field]).trim();
            if (!value) add(seat.key, `${label}: значение не указано.`);
            else if (value.length > limit) add(seat.key, `${label}: не более ${limit} символов (сейчас ${value.length}).`);
        }
        for (const field of ['x', 'y'] as const) {
            try { coordinate(seat[field]); }
            catch { add(seat.key, `${field.toUpperCase()}: нужна координата от 0 до 1.`); }
        }
        if (storedText(seat.adjacency_group).length > 80) add(seat.key, 'Группа соседства: не более 80 символов.');
        const position = seat.adjacency_position;
        if (position !== null && (!Number.isInteger(position) || position < 0 || position > 1000000)) add(seat.key, 'Позиция в группе: целое число от 0 до 1 000 000.');
        if (!seat.key || keys.has(seat.key)) add(seat.key, 'Повторяющийся или отсутствующий идентификатор места.');
        keys.add(seat.key);
        const identity = JSON.stringify([seat.sector, seat.row, seat.number].map(value => storedText(value).trim()));
        const group = identities.get(identity) ?? []; group.push(seat.key); identities.set(identity, group);
    }
    for (const group of identities.values()) if (group.length > 1) {
        for (const key of group) add(key, 'Такие сектор, ряд и номер уже есть у другого места.');
    }
    return seats.filter(seat => messages.has(seat.key)).map(seat => ({ key: seat.key, id: seat.id, messages: messages.get(seat.key)! }));
}
export function newSeatDrafts(seats: EditorSeatInput[], key = () => crypto.randomUUID()): DraftSeat[] {
    return seats.map(seat => ({ ...normalizeSeat(seat), key: `new:${key()}` }));
}
export function validateSeats(seats: DraftSeat[]): void {
    if (seats.length > EDITOR_PLAN_LIMIT) throw new Error('PLAN_LIMIT');
    const positions = new Set<string>(), keys = new Set<string>();
    for (const seat of seats) {
        const normalized = normalizeSeat(seat), position = JSON.stringify([normalized.sector, normalized.row, normalized.number]);
        if (positions.has(position) || keys.has(seat.key)) throw new Error('DUPLICATE_SEAT');
        positions.add(position); keys.add(seat.key);
    }
}
/** Mirror the backend's conservative group invalidation after geometry changes. */
export function clearAffectedAdjacency(before: DraftSeat[], after: DraftSeat[]): DraftSeat[] {
    const next = new Map(after.map(seat => [seat.key, seat]));
    const affected = new Set<string>();
    for (const seat of before) {
        const changed = next.get(seat.key);
        if (seat.adjacency_group && (!changed || identityFields.some(field => seat[field] !== changed[field]))) affected.add(seat.adjacency_group);
    }
    return after.map(seat => affected.has(seat.adjacency_group) ? { ...seat, adjacency_group: '', adjacency_position: null } : seat);
}
function seatValues(seat: DraftSeat): Required<EditorSeatInput> & { x: string; y: string } {
    return {
        sector: seat.sector, row: seat.row, number: seat.number,
        x: storedCoordinate(seat.x), y: storedCoordinate(seat.y),
        adjacency_group: seat.adjacency_group, adjacency_position: seat.adjacency_position
    };
}
/** A read-only diff for counters/dirty state. No business-validation exceptions during render. */
export function draftChanges(original: DraftSeat[], current: DraftSeat[], version: number): BulkEditInput {
    const prior = new Map(original.filter(seat => seat.id).map(seat => [seat.id!, seatValues(seat)]));
    const seen = new Set<string>();
    const result: BulkEditInput = { expected_version: version, create: [], update: [], delete: [] };
    for (const seat of current) {
        const values = seatValues(seat);
        if (!seat.id) { result.create.push(values); continue; }
        const previous = prior.get(seat.id);
        seen.add(seat.id);
        if (!previous || fields.some(field => values[field] !== previous[field])) result.update.push({ id: seat.id, ...values });
    }
    for (const id of prior.keys()) if (!seen.has(id)) result.delete.push(id);
    return result;
}
/** Validate mutations, not the whole snapshot. Untouched legacy seats are never rewritten. */
export function planChanges(original: DraftSeat[], current: DraftSeat[], version: number): BulkEditInput {
    if (!Number.isInteger(version) || version < 1) throw new Error('VERSION_CONFLICT');
    if (current.length > EDITOR_PLAN_LIMIT) throw new Error('PLAN_LIMIT');
    const prior = new Set(original.filter(seat => seat.id).map(seat => seat.id!));
    const seen = new Set<string>(), keys = new Set<string>();
    for (const seat of current) {
        if (keys.has(seat.key)) throw new Error('DUPLICATE_SEAT');
        keys.add(seat.key);
        if (seat.id) {
            if (!prior.has(seat.id) || seen.has(seat.id)) throw new Error('INVALID_SEAT_ID');
            seen.add(seat.id);
        }
    }
    const changes = draftChanges(original, current, version);
    const updated = new Set(changes.update.map(seat => seat.id));
    const identities = new Map<string, { count: number; changed: boolean }>();
    for (const seat of current) {
        const key = JSON.stringify([seat.sector, seat.row, seat.number].map(value => storedText(value).trim()));
        const previous = identities.get(key);
        identities.set(key, { count: (previous?.count ?? 0) + 1, changed: !!previous?.changed || !seat.id || updated.has(seat.id) });
    }
    // Existing duplicates remain visible as diagnostics, but a mutation must not introduce a collision.
    for (const value of identities.values()) if (value.count > 1 && value.changed) throw new Error('DUPLICATE_SEAT');
    return {
        ...changes,
        create: changes.create.map(normalizeSeat),
        update: changes.update.map(seat => ({ id: seat.id, ...normalizeSeat(seat as EditorSeatInput) }))
    };
}
export function changeCount(changes: BulkEditInput): number { return changes.create.length + changes.update.length + changes.delete.length; }
export function assertBatch(changes: BulkEditInput): void {
    if (changeCount(changes) < 1 || changeCount(changes) > EDITOR_BATCH_LIMIT) throw new Error('BATCH_LIMIT');
}
export interface Transform { dx?: number; dy?: number; angle?: number; flipX?: boolean; flipY?: boolean; aspect?: number }
export function transformSeats(seats: DraftSeat[], selection: Set<string>, transform: Transform): DraftSeat[] {
    const selected = seats.filter(seat => selection.has(seat.key));
    if (!selected.length) return seats;
    const values = selected.map(seat => ({ x: Number(seat.x), y: Number(seat.y) }));
    const cx = values.reduce((sum, p) => sum + p.x, 0) / values.length;
    const cy = values.reduce((sum, p) => sum + p.y, 0) / values.length;
    const { dx = 0, dy = 0, angle = 0, aspect = 1.6 } = transform;
    if (![dx, dy, angle, aspect].every(Number.isFinite) || aspect <= 0) throw new Error('INVALID_GEOMETRY');
    const radians = angle * Math.PI / 180, cos = Math.cos(radians), sin = Math.sin(radians);
    return clearAffectedAdjacency(seats, seats.map(seat => {
        if (!selection.has(seat.key)) return seat;
        const x = (Number(seat.x) - cx) * aspect * (transform.flipX ? -1 : 1);
        const y = (Number(seat.y) - cy) * (transform.flipY ? -1 : 1);
        // Reject out-of-bounds transforms. Never silently clamp several seats together.
        return { ...seat, x: coordinate(cx + (x * cos - y * sin) / aspect + dx), y: coordinate(cy + x * sin + y * cos + dy) };
    }));
}
function csvCell(value: string): string {
    // Spreadsheet programs may evaluate formulas even in quoted cells.
    const safe = /^[\s]*[=+\-@\t\r]/.test(value) ? "'" + value : value;
    return '"' + safe.replaceAll('"', '""') + '"';
}
export function seatsCsv(seats: DraftSeat[]): string {
    return '\uFEFFsector,row,number,x,y\r\n' + seats.map(seat => [seat.sector, seat.row, seat.number, seat.x, seat.y].map(csvCell).join(',')).join('\r\n') + '\r\n';
}
export function selectRectangle(seats: DraftSeat[], start: { x: number; y: number }, end: { x: number; y: number }): string[] {
    return seats.filter(seat => hasSeatPosition(seat) && Number(seat.x) >= Math.min(start.x, end.x) && Number(seat.x) <= Math.max(start.x, end.x) && Number(seat.y) >= Math.min(start.y, end.y) && Number(seat.y) <= Math.max(start.y, end.y)).map(seat => seat.key);
}
