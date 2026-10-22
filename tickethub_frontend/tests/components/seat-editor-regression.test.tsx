/** The read snapshot may contain incomplete imported places. Do not crash or silently repair it. */
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '@/lib/api/client';
import { SeatEditor } from '@/features/staff/seat-editor';
import type { BulkEditInput, EditorSnapshot } from '@/lib/api/editor';
import { ids, seat, renderApp } from './support';

vi.mock('@/lib/api/client', async () => ({ ...await vi.importActual<typeof import('@/lib/api/client')>('@/lib/api/client'), api: vi.fn() }));
let snapshot: EditorSnapshot;
function writes() { return vi.mocked(api).mock.calls.filter(([, options]) => options?.method && options.method !== 'GET'); }
beforeEach(() => {
    snapshot = {
        plan: { id: ids.event, venue: ids.user, name: 'Импортированная схема', image: '', rights_source: '', rights_confirmed: false, status: 'DRAFT', version: 7 },
        seats: [{ ...seat, id: 'incomplete-row', row: '' }, { ...seat, id: 'incomplete-number', sector: 'B', number: '' }]
    };
    vi.mocked(api).mockReset().mockImplementation(async (path, options) => {
        if (path.endsWith('/preview/')) return structuredClone(snapshot);
        if (path.endsWith('/bulk-edit/')) {
            const payload = options?.body as BulkEditInput;
            snapshot = { ...snapshot, plan: { ...snapshot.plan, version: 8 }, seats: snapshot.seats.map(seat => ({ ...seat, ...payload.update.find(update => update.id === seat.id) })) };
            return { version: 8, created_ids: [], created: 0, updated: payload.update.length, deleted: 0 };
        }
        throw new Error(`Unexpected request in editor regression: ${path}`);
    });
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, writable: true, value: vi.fn() });
});
describe('imported seat diagnostics', () => {
    it('opens the editor with missing labels, shows field-specific problems and makes no write', async () => {
        renderApp(<SeatEditor id={ids.event} />);
        expect(await screen.findByText('Проверьте данные мест: 2')).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Импортированная схема' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Сохранить изменения' })).toBeDisabled();
        expect(screen.getByRole('button', { name: 'Опубликовать схему' })).toBeDisabled();
        expect(writes()).toHaveLength(0);
    });
    it('keeps every seat in the list and offers an explicit problems filter', async () => {
        renderApp(<SeatEditor id={ids.event} />); await screen.findByText('Проверьте данные мест: 2');
        expect(screen.getAllByRole('row')).toHaveLength(3); // header + both original seats
        fireEvent.click(screen.getByRole('button', { name: 'Показать места с ошибками' }));
        expect(screen.getByRole('checkbox', { name: 'Только с ошибками (2)' })).toBeChecked();
        expect(screen.getByText('Ряд: значение не указано.')).toBeInTheDocument();
        expect(writes()).toHaveLength(0);
    });
    it('repairs one seat at a time and only sends that seat, keeping the other incomplete record', async () => {
        const { container } = renderApp(<SeatEditor id={ids.event} />); await screen.findByText('Проверьте данные мест: 2');
        fireEvent.click(screen.getByRole('button', { name: 'Показать места с ошибками' }));
        const form = within(container.querySelector('.plan-inspector form') as HTMLFormElement);
        expect(form.getByLabelText('Ряд')).toHaveValue('');
        fireEvent.change(form.getByLabelText('Ряд'), { target: { value: '10' } });
        fireEvent.click(form.getByRole('button', { name: 'Применить на холсте' }));
        await waitFor(() => expect(screen.getByText('Проверьте данные мест: 1')).toBeInTheDocument());
        expect(writes()).toHaveLength(0);
        fireEvent.click(screen.getAllByRole('button', { name: 'Сохранить изменения' })[0]);
        await waitFor(() => expect(writes()).toHaveLength(1));
        const payload = writes()[0][1]?.body as BulkEditInput;
        expect(payload.expected_version).toBe(7); expect(payload.create).toEqual([]); expect(payload.delete).toEqual([]);
        expect(payload.update).toHaveLength(1); expect(payload.update[0]).toMatchObject({ id: 'incomplete-row', row: '10' });
        expect(snapshot.seats.find(seat => seat.id === 'incomplete-number')?.number).toBe('');
    });
});
