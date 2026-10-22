/** Component scenarios for the uploaded backend update. Run: npm run test:components.
 * API and browser image decoding are isolated; this is NOT a live integration test.
 */
import { useState } from 'react';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError } from '@/lib/api/client';
import { inspectImage, validateImageSelection, type ImageSelection } from '@/lib/image-upload';
import { ImagePicker, ImageUpload } from '@/features/staff/image-upload';
import { SeatEditor } from '@/features/staff/seat-editor';
import { ErrorState } from '@/components/ui';
import { UnsavedGuard } from '@/components/ui/unsaved-guard';
import type { EditorSnapshot } from '@/lib/api/editor';
import { ids, seat, renderApp } from './support';

vi.mock('@/lib/api/client', async () => ({ ...await vi.importActual<typeof import('@/lib/api/client')>('@/lib/api/client'), api: vi.fn() }));
vi.mock('@/lib/image-upload', async () => ({ ...await vi.importActual<typeof import('@/lib/image-upload')>('@/lib/image-upload'), inspectImage: vi.fn(), validateImageSelection: vi.fn() }));
const snapshot: EditorSnapshot = { plan: { id: ids.event, venue: ids.user, name: 'Тестовая схема', image: '', rights_source: '', rights_confirmed: false, status: 'DRAFT', version: 7 }, seats: [seat] };
const file = () => new File(['bytes decoded by the mocked browser'], 'cover.png', { type: 'image/png' });
function Picker() { const [value, setValue] = useState<ImageSelection | null>(null); return <ImagePicker value={value} onChange={setValue} />; }
function readsOnly(data = snapshot) { vi.mocked(api).mockImplementation(async path => { if (path.endsWith('/preview/')) return data; throw new Error(`Unexpected API path: ${path}`); }); }
function writes() { return vi.mocked(api).mock.calls.filter(([, options]) => options?.method && options.method !== 'GET'); }
beforeEach(() => {
    vi.mocked(api).mockReset();
    vi.mocked(inspectImage).mockReset().mockResolvedValue({ type: 'image/png', width: 1600, height: 900, previewSafe: true });
    vi.mocked(validateImageSelection).mockReset().mockResolvedValue(undefined);
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, writable: true, value: vi.fn(() => 'blob:http://localhost/test') });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, writable: true, value: vi.fn() });
});
describe('event cover and detailed errors', () => {
    it('shows the field error without a technical ID for validation failures', () => {
        renderApp(<ErrorState error={new ApiError(400, 'VALIDATION_ERROR', 'Общее сообщение', { image: ['Файл не является PNG.'] }, 'request-test')} />);
        expect(screen.getByText('Изображение:')).toBeInTheDocument();
        expect(screen.getByText(/Файл не является PNG/)).toBeInTheDocument();
        expect(screen.queryByText(/request-test/)).not.toBeInTheDocument();
    });
    it('displays the stored cover without claiming a new upload', () => {
        renderApp(<ImageUpload endpoint={`staff/events/${ids.event}/image/`} version={7} image="/media/events/cover.jpg" />);
        expect(screen.getByRole('img', { name: 'Сохранённое изображение' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Сохранить обложку' })).toBeDisabled();
        expect(api).not.toHaveBeenCalled();
    });
    it('previews a selection without any API write and allows cancelling it', async () => {
        renderApp(<Picker />);
        fireEvent.change(screen.getByLabelText('Файл изображения'), { target: { files: [file()] } });
        expect(await screen.findByRole('img', { name: 'Предпросмотр выбранного изображения' })).toBeInTheDocument();
        expect(api).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole('button', { name: 'Отменить выбор' }));
        await waitFor(() => expect(screen.queryByRole('img')).not.toBeInTheDocument());
        expect(URL.revokeObjectURL).toHaveBeenCalled();
    });
    it('shows a readable invalid-image error without uploading it', async () => {
        vi.mocked(inspectImage).mockRejectedValue(new ApiError(400, 'VALIDATION_ERROR', 'Ошибка', { image: ['Файл повреждён. Выберите другое изображение.'] }));
        renderApp(<Picker />);
        fireEvent.change(screen.getByLabelText('Файл изображения'), { target: { files: [file()] } });
        expect((await screen.findAllByText(/Файл повреждён/)).length).toBeGreaterThan(0);
        expect(api).not.toHaveBeenCalled();
        expect(screen.queryByRole('img')).not.toBeInTheDocument();
    });
    it('submits the exact multipart contract with the current event version', async () => {
        vi.mocked(api).mockResolvedValue({ version: 8, image: '/media/new.jpg' });
        const user = userEvent.setup(), saved = vi.fn();
        renderApp(<ImageUpload endpoint={`staff/events/${ids.event}/image/`} version={7} onSaved={saved} />);
        fireEvent.change(screen.getByLabelText('Файл изображения'), { target: { files: [file()] } });
        await user.type(screen.getByLabelText('Источник / основание использования'), 'Собственное фото');
        await user.click(screen.getByRole('checkbox', { name: 'Подтверждаю право использовать это изображение' }));
        await user.click(screen.getByRole('button', { name: 'Сохранить обложку' }));
        await waitFor(() => expect(saved).toHaveBeenCalledOnce());
        const [path, options] = vi.mocked(api).mock.calls[0];
        expect(path).toBe(`staff/events/${ids.event}/image/`);
        expect(options?.method).toBe('POST');
        const body = options?.body as FormData;
        expect([...body.keys()].sort()).toEqual(['expected_version', 'image', 'rights_confirmed', 'rights_source']);
        expect(body.get('expected_version')).toBe('7');
        expect(body.get('rights_confirmed')).toBe('true');
        expect(screen.getByRole('button', { name: 'Сохранить обложку' })).toBeDisabled();
    });
    it('keeps the selected file after a version conflict, without automatic retry', async () => {
        vi.mocked(api).mockRejectedValue(new ApiError(409, 'VERSION_CONFLICT', 'Изменилась версия'));
        const user = userEvent.setup();
        renderApp(<ImageUpload endpoint={`staff/events/${ids.event}/image/`} version={7} />);
        fireEvent.change(screen.getByLabelText('Файл изображения'), { target: { files: [file()] } });
        await user.type(screen.getByLabelText('Источник / основание использования'), 'Собственное фото');
        await user.click(screen.getByRole('checkbox'));
        await user.click(screen.getByRole('button', { name: 'Сохранить обложку' }));
        expect(await screen.findByRole('button', { name: 'Обновить версию записи' })).toBeInTheDocument();
        expect(screen.getByText('cover.png')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Сохранить обложку' })).toBeDisabled();
        expect(api).toHaveBeenCalledOnce();
    });
    it('does not intercept a local draft download as navigation', () => {
        renderApp(<><UnsavedGuard dirty /><a href="blob:http://localhost/export" download="draft.csv">Скачать черновик</a></>);
        const link = screen.getByRole('link');
        // Cancel the browser's default download AFTER checking the capture-phase guard.
        let intercepted = true;
        link.addEventListener('click', event => { intercepted = event.defaultPrevented; event.preventDefault(); });
        fireEvent.click(link);
        expect(intercepted).toBe(false);
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
});
describe('versioned seat workspace', () => {
    it('opens seats on a neutral canvas without a background image', async () => {
        readsOnly(); renderApp(<SeatEditor id={ids.event} />);
        expect(await screen.findByRole('region', { name: /Холст схемы/ })).toBeInTheDocument();
        expect(screen.getByRole('checkbox', { name: 'Выбрать A, ряд 1, место 5' })).toBeInTheDocument();
        expect(writes()).toHaveLength(0);
    });
    it('stages a property edit locally and saves using one bulk request', async () => {
        let current = snapshot;
        vi.mocked(api).mockImplementation(async (path, options) => {
            if (path.endsWith('/preview/')) return current;
            if (path.endsWith('/bulk-edit/')) {
                expect(options?.body).toMatchObject({ expected_version: 7, create: [], delete: [], update: [{ id: ids.seat, number: '9' }] });
                current = { plan: { ...snapshot.plan, version: 8 }, seats: [{ ...seat, number: '9' }] };
                return { version: 8, created_ids: [], created: 0, updated: 1, deleted: 0 };
            }
            throw new Error(`Unexpected API path: ${path}`);
        });
        const user = userEvent.setup(); renderApp(<SeatEditor id={ids.event} />);
        await user.click(await screen.findByRole('checkbox', { name: 'Выбрать A, ряд 1, место 5' }));
        await user.clear(screen.getByLabelText('Место')); await user.type(screen.getByLabelText('Место'), '9');
        await user.click(screen.getByRole('button', { name: 'Применить на холсте' }));
        expect(writes()).toHaveLength(0);
        await user.click(screen.getAllByRole('button', { name: 'Сохранить изменения' })[0]);
        await waitFor(() => expect(screen.getByText(/Версия 8 ·/)).toBeInTheDocument());
        expect(writes()).toHaveLength(1);
        expect(screen.getByRole('checkbox', { name: 'Выбрать A, ряд 1, место 9' })).toBeInTheDocument();
    });
    it('undoes a staged property change without calling the backend', async () => {
        readsOnly(); const user = userEvent.setup(); renderApp(<SeatEditor id={ids.event} />);
        await user.click(await screen.findByRole('checkbox', { name: 'Выбрать A, ряд 1, место 5' }));
        await user.clear(screen.getByLabelText('Место')); await user.type(screen.getByLabelText('Место'), '9');
        await user.click(screen.getByRole('button', { name: 'Применить на холсте' }));
        await user.click(screen.getByRole('button', { name: 'Отменить изменение' }));
        expect(screen.getByRole('checkbox', { name: 'Выбрать A, ряд 1, место 5' })).toBeInTheDocument();
        expect(writes()).toHaveLength(0);
    });
    it('keeps the local change visible on a 409 and locks the save button', async () => {
        vi.mocked(api).mockImplementation(async path => { if (path.endsWith('/preview/')) return snapshot; throw new ApiError(409, 'VERSION_CONFLICT', 'Версия изменена'); });
        const user = userEvent.setup(); renderApp(<SeatEditor id={ids.event} />);
        await user.click(await screen.findByRole('checkbox', { name: 'Выбрать A, ряд 1, место 5' }));
        await user.clear(screen.getByLabelText('Место')); await user.type(screen.getByLabelText('Место'), '9');
        await user.click(screen.getByRole('button', { name: 'Применить на холсте' }));
        await user.click(screen.getAllByRole('button', { name: 'Сохранить изменения' })[0]);
        expect(await screen.findByText(/Ваши правки остались на холсте/)).toBeInTheDocument();
        expect(screen.getByRole('checkbox', { name: 'Выбрать A, ряд 1, место 9' })).toBeInTheDocument();
        expect(screen.getAllByRole('button', { name: 'Сохранить изменения' }).every(button => button.hasAttribute('disabled'))).toBe(true);
        expect(writes()).toHaveLength(1);
    });
    it('makes a published plan read-only while preserving inspection and cloning', async () => {
        readsOnly({ ...snapshot, plan: { ...snapshot.plan, status: 'PUBLISHED' } });
        const user = userEvent.setup(); renderApp(<SeatEditor id={ids.event} />);
        await user.click(await screen.findByRole('checkbox', { name: 'Выбрать A, ряд 1, место 5' }));
        expect(screen.getByLabelText('Место')).toBeDisabled();
        expect(screen.queryByRole('button', { name: 'Сохранить изменения' })).not.toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Создать копию' })).toBeEnabled();
        expect(writes()).toHaveLength(0);
    });
    it('does not delete a seat until the deletion has been confirmed and saved', async () => {
        readsOnly(); const user = userEvent.setup(); renderApp(<SeatEditor id={ids.event} />);
        await user.click(await screen.findByRole('checkbox', { name: 'Выбрать A, ряд 1, место 5' }));
        await user.click(screen.getByRole('button', { name: 'Убрать выделенные' }));
        const dialog = screen.getByRole('dialog', { name: 'Убрать 1 мест с холста?' });
        await user.click(within(dialog).getByRole('button', { name: 'Подтвердить' }));
        expect(screen.queryByRole('checkbox', { name: 'Выбрать A, ряд 1, место 5' })).not.toBeInTheDocument();
        expect(writes()).toHaveLength(0);
    });
});
