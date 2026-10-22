/** Isolated UI contracts, never synthetic production catalog data. */
import { screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '@/lib/api/client';
import { ExternalEventsPage, ExternalSourcePage } from '@/features/staff/external-events';
import type { ImportPreview, ImportReport } from '@/lib/api/external-events';
import { ids, renderApp } from './support';
const access = vi.hoisted(() => ({ admin: true }));
vi.mock('@/features/auth/session', () => ({ useStaffAccess: () => ({ admin: { isPending: false }, isAdmin: access.admin }) }));
vi.mock('@/lib/api/client', async () => ({ ...await vi.importActual<typeof import('@/lib/api/client')>('@/lib/api/client'), api: vi.fn() }));
const preview: ImportPreview = { status: 'PREVIEW', url: 'https://portalbilet.ru/moscow/test-event', title: 'Тест источника', venue: { name: 'Площадка', address: '', city: '' }, provider: { external_event_id: 'test', event_source_id: 'test', external_layout_id: '' }, dates: [{ external_date_id: 'date-test', start_at: null }], dates_authoritative: false, seats_count: null, standing_zones_count: null, supported_mode: 'IMPORT_ONLY', warnings: [] };
const report: ImportReport = { status: 'PARTIAL', source_id: ids.user, mode: 'IMPORT_ONLY', created: { events: [ids.event], venues: 1, seats: 0, ticket_units: 0 }, updated: { events: [] }, warnings: [{ code: 'LAYOUT_MAPPING_UNVERIFIED', message: 'Геометрия не перенесена.' }], resources: {} };
beforeEach(() => { access.admin = true; vi.mocked(api).mockReset().mockImplementation(async path => {
    if (path.startsWith('staff/external-events/?')) return { results: [], count: 0, next: null, previous: null };
    if (path.endsWith('/preview/')) return preview;
    if (path.endsWith('/import/')) return report;
    throw new Error(`Unexpected API path: ${path}`);
}); });
describe('PortalBilet import interface', () => {
    it('does not mount import or sources requests for a manager', () => {
        access.admin = false; renderApp(<ExternalEventsPage />);
        expect(screen.getByText('Раздел доступен только администратору.')).toBeInTheDocument();
        expect(api).not.toHaveBeenCalled();
        expect(screen.queryByRole('button', { name: 'Показать предпросмотр' })).not.toBeInTheDocument();
    });
    it('also protects source details on a direct URL', () => {
        access.admin = false; renderApp(<ExternalSourcePage id={ids.user} />);
        expect(api).not.toHaveBeenCalled();
        expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    it('does not submit a URL from an unsupported provider', async () => {
        const user = userEvent.setup(); renderApp(<ExternalEventsPage />);
        await user.type(screen.getByLabelText('Ссылка на мероприятие'), 'https://example.com/event');
        expect(screen.getByRole('button', { name: 'Показать предпросмотр' })).toBeDisabled();
        expect(vi.mocked(api).mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0);
    });
    it('shows preview without importing and invalidates it when the URL changes', async () => {
        const user = userEvent.setup(); renderApp(<ExternalEventsPage />);
        await user.type(screen.getByLabelText('Ссылка на мероприятие'), preview.url);
        await user.click(screen.getByRole('button', { name: 'Показать предпросмотр' }));
        expect(await screen.findByRole('heading', { name: 'Тест источника' })).toBeInTheDocument();
        expect(screen.getByText('Дата и время требуют проверки')).toBeInTheDocument();
        expect(vi.mocked(api).mock.calls.some(([path]) => path.endsWith('/import/'))).toBe(false);
        await user.clear(screen.getByLabelText('Ссылка на мероприятие'));
        expect(screen.queryByRole('button', { name: 'Импортировать черновики' })).not.toBeInTheDocument();
    });
    it('requires confirmation, preserves PARTIAL and offers a cover link for the created event', async () => {
        const user = userEvent.setup(); renderApp(<ExternalEventsPage />);
        await user.type(screen.getByLabelText('Ссылка на мероприятие'), preview.url);
        await user.click(screen.getByRole('button', { name: 'Показать предпросмотр' }));
        await user.click(await screen.findByRole('button', { name: 'Импортировать черновики' }));
        expect(vi.mocked(api).mock.calls.some(([path]) => path.endsWith('/import/'))).toBe(false);
        await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Подтвердить' }));
        await waitFor(() => expect(screen.getByText('Нужна проверка')).toBeInTheDocument());
        expect(screen.getByText(/Запрос обработан частично/)).toBeInTheDocument();
        expect(screen.getByRole('link', { name: /Дата 1 — проверить и добавить обложку/ })).toHaveAttribute('href', `/ru/staff/events/${ids.event}#event-cover`);
        const imports = vi.mocked(api).mock.calls.filter(([path]) => path.endsWith('/import/'));
        expect(imports).toHaveLength(1);
        expect(imports[0][1]?.body).toEqual({ provider: 'portalbilet', mode: 'IMPORT_ONLY', url: preview.url });
        expect(screen.queryByText('Импорт завершён')).not.toBeInTheDocument();
    });
});
