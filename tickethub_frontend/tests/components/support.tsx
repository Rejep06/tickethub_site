import type { ReactNode } from 'react';
import { NextIntlClientProvider } from 'next-intl';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import { ToastProvider } from '@/components/ui/toast';
import ru from '@/messages/ru.json';
import type { Hold, Profile, Seat, StaffOrder } from '@/lib/api/generated';
export const ids = { order: '10000000-0000-4000-8000-000000000001', event: '10000000-0000-4000-8000-000000000002', user: '10000000-0000-4000-8000-000000000003', seat: '10000000-0000-4000-8000-000000000004' };
export const profile: Profile = { id: ids.user, email: 'test@example.test', name: 'Тест', phone: '+79990000000', locale: 'ru', email_verified_at: '2026-10-01T12:00:00Z' };
export const hold: Hold = { id: ids.order, event: ids.event, quote: null, status: 'ACTIVE', expires_at: '2026-10-01T12:10:00Z', server_now: '2026-10-01T12:00:00Z', total_minor: 100000, currency: 'RUB', items: [] };
export const seat: Seat = { id: ids.seat, plan: ids.event, sector: 'A', row: '1', number: '5', x: '.5', y: '.5', adjacency_group: '', adjacency_position: null };
export const staffOrder: StaffOrder = {
    id: ids.order, number: 'TH-TEST-1', event: ids.event, origin: 'SITE_DIRECT', order_state: 'CONFIRMED', payment_state: 'UNPAID', delivery_state: 'NOT_SENT', sent_count: 0,
    customer_name: 'Тест', customer_phone: profile.phone, customer_email: profile.email, customer_comment: '', subtotal_minor: 400000, discount_minor: 0, promo_code: '', total_minor: 400000, currency: 'RUB',
    payment: { received_minor: 0, refunded_minor: 0, net_received_minor: 0 },
    event_snapshot: { title_ru: 'Тестовое событие', title_en: 'Test event', start_at: '2026-10-30T12:00:00Z', timezone: 'Europe/Moscow' },
    fan_id_answer: 'NOT_SURE', fan_id_help_state: 'NOT_NEEDED', delivery_due_at: '2026-10-29T12:00:00Z',
    items: Array.from({ length: 4 }, (_, i) => ({ id: `20000000-0000-4000-8000-${String(i + 1).padStart(12, '0')}`, name_ru: 'Категория', name_en: 'Category', sector: 'A', row: '1', seat_number: String(i + 1), original_price_minor: 100000, discount_minor: 0, sale_price_minor: 100000, is_active: true, ticket_unit: `30000000-0000-4000-8000-${String(i + 1).padStart(12, '0')}`, purchase_price_minor: null })),
    history: [], cases: [], created_at: '2026-10-01T12:00:00Z', updated_at: '2026-10-01T12:00:00Z', version: 7, user: ids.user, manager: null, review_due_at: '2026-10-02T12:00:00Z', settlement_due_at: null, first_contact_at: null, confirmed_at: null, first_paid_at: null, internal_notes: '', ticket_request: null, quote: null, deliveries: [], financial_entries: []
};
export function renderApp(ui: ReactNode) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    return { ...render(<NextIntlClientProvider locale="ru" messages={ru} timeZone="UTC"><QueryClientProvider client={client}><ToastProvider>{ui}</ToastProvider></QueryClientProvider></NextIntlClientProvider>), client };
}
