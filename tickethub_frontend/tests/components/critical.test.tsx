import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiError, api } from '@/lib/api/client';
import { authApi, staffApi } from '@/lib/api/endpoints';
import { Login } from '@/features/auth/login';
import { RequireAuth, RequireStaff } from '@/features/auth/session';
import { HoldClock } from '@/features/checkout/checkout';
import { SeatPicker } from '@/features/seat-map/seat-picker';
import { OrderActionModal, StaffOrderDetail } from '@/features/staff/order-detail';
import { ErrorState, Field, Input, StatusBadge } from '@/components/ui';
import { hold, ids, profile, renderApp, seat, staffOrder } from './support';
vi.mock('@/lib/api/client', async () => {
    const actual = await vi.importActual<typeof import('@/lib/api/client')>('@/lib/api/client');
    return { ...actual, api: vi.fn() };
});
vi.mock('@/lib/api/endpoints', () => ({ authApi: { me: vi.fn(), requestCode: vi.fn(), verifyCode: vi.fn(), staffLogin: vi.fn(), logout: vi.fn(), update: vi.fn() }, staffApi: { payment: vi.fn(), delivery: vi.fn(), refund: vi.fn() }, checkoutApi: {} }));
beforeEach(() => {
    vi.mocked(api).mockReset();
    vi.mocked(authApi.requestCode).mockReset();
    vi.mocked(authApi.verifyCode).mockReset();
    vi.mocked(authApi.me).mockReset();
    vi.mocked(staffApi.payment).mockReset();
});
describe('critical buyer interfaces — isolated, not live API', () => {
    it('associates a field label and validation error with its input', () => {
        renderApp(<Field label="Имя" error="Нужно имя"><Input /></Field>);
        const input = screen.getByLabelText('Имя');
        expect(input).toHaveAttribute('aria-invalid', 'true');
        expect(input).toHaveAccessibleDescription('Нужно имя');
    });
    it('translates the order status', () => {
        renderApp(<StatusBadge status="PARTIALLY_SENT"/>);
        expect(screen.getByText('Частично отправлены')).toBeInTheDocument();
    });
    it('shows a human-readable 409, not an internal trace', () => {
        renderApp(<ErrorState error={new ApiError(409, 'SEAT_UNAVAILABLE', 'secret trace', {})}/>);
        expect(screen.queryByText('secret trace')).not.toBeInTheDocument();
        expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    it('runs the email → code flow without dropping email on a wrong code', async () => {
        vi.mocked(authApi.requestCode).mockResolvedValue({ detail: 'Код отправлен', expires_in: 600, resend_after: 60 });
        vi.mocked(authApi.verifyCode).mockRejectedValue(new ApiError(400, 'OTP_INVALID', 'Неверный код', {}));
        const user = userEvent.setup();
        renderApp(<Login />);
        await user.type(screen.getByLabelText('Email'), profile.email);
        await user.click(screen.getByRole('button', { name: 'Получить код' }));
        const code = await screen.findByLabelText('Код из 6 цифр');
        await user.type(code, '123456');
        await user.click(screen.getByRole('button', { name: 'Войти по коду' }));
        await waitFor(() => expect(authApi.verifyCode).toHaveBeenCalledWith({ email: profile.email, code: '123456', locale: 'ru' }));
        expect(code).toHaveValue('123456');
        expect(await screen.findByRole('alert')).toBeInTheDocument();
    });
    it('does not expose authenticated content for a 401 response', async () => {
        vi.mocked(authApi.me).mockRejectedValue(new ApiError(401, 'NOT_AUTHENTICATED', 'Войдите', {}));
        renderApp(<RequireAuth><p>Секрет клиента</p></RequireAuth>);
        await screen.findByRole('link', { name: 'Войти' });
        expect(screen.queryByText('Секрет клиента')).not.toBeInTheDocument();
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
    it('does not expose staff content when the real permission probe returns 403', async () => {
        vi.mocked(api).mockRejectedValue(new ApiError(403, 'PERMISSION_DENIED', 'Нет доступа', {}));
        renderApp(<RequireStaff><p>Закупочная стоимость</p></RequireStaff>);
        await screen.findByRole('link', { name: 'Вход сотрудника', exact: true });
        expect(screen.queryByText('Закупочная стоимость')).not.toBeInTheDocument();
    });
    it('renders server-based countdown and fires expiry once', () => {
        vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'performance'] });
        const expired = vi.fn();
        renderApp(<HoldClock hold={{ ...hold, expires_at: '2026-10-01T12:00:02Z' }} onExpire={expired}/>);
        expect(screen.getByRole('timer')).toHaveTextContent('00:02');
        act(() => vi.advanceTimersByTime(3000));
        expect(screen.getByRole('timer')).toHaveTextContent('00:00');
        expect(expired).toHaveBeenCalledTimes(1);
    });
    it('has keyboard-operable seat buttons without the image map', async () => {
        const choose = vi.fn();
        const user = userEvent.setup();
        renderApp(<SeatPicker map={{ seats: [seat], plan: null }} availability={{ available_seats: [{ seat_id: seat.id, sale_price_minor: 100000 }] }} selected={[]} onChoose={choose}/>);
        const button = screen.getByRole('button', { name: /Сектор A.*Ряд 1.*Место 5/ });
        button.focus();
        await user.keyboard('{Enter}');
        expect(choose).toHaveBeenCalledWith(seat.id);
    });
});
describe('staff money and delivery — mocked services', () => {
    it('shows partial delivery 2 of 4 without claiming full delivery', async () => {
        vi.mocked(api).mockResolvedValue({ ...staffOrder, sent_count: 2, payment_state: 'PAID', delivery_state: 'PARTIALLY_SENT' });
        renderApp(<StaffOrderDetail id={ids.order}/>);
        expect(await screen.findByText('Отправлено 2 из 4 билетов')).toBeInTheDocument();
    });
    it('payment requires a separate confirmation before API write', async () => {
        const close = vi.fn();
        vi.mocked(staffApi.payment).mockResolvedValue({} as Awaited<ReturnType<typeof staffApi.payment>>);
        renderApp(<OrderActionModal action={{ kind: 'payment', order: staffOrder }} close={close}/>);
        fireEvent.change(screen.getByLabelText('Номер / подтверждение операции'), { target: { value: 'test-reference' } });
        fireEvent.click(screen.getByRole('button', { name: 'Проверить действие' }));
        expect(staffApi.payment).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole('button', { name: 'Подтвердить', exact: true }));
        await waitFor(() => expect(staffApi.payment).toHaveBeenCalledWith(ids.order, expect.objectContaining({ amount_minor: 400000, expected_version: 7, reference: 'test-reference' })));
    });
    it('payment errors keep the dialog open and do not report success', async () => {
        const close = vi.fn();
        vi.mocked(staffApi.payment).mockRejectedValue(new ApiError(409, 'VERSION_CONFLICT', 'Версия изменилась', {}));
        renderApp(<OrderActionModal action={{ kind: 'payment', order: staffOrder }} close={close}/>);
        fireEvent.change(screen.getByLabelText('Номер / подтверждение операции'), { target: { value: 'test-reference' } });
        fireEvent.click(screen.getByRole('button', { name: 'Проверить действие' }));
        fireEvent.click(screen.getByRole('button', { name: 'Подтвердить', exact: true }));
        await waitFor(() => expect(staffApi.payment).toHaveBeenCalled());
        await screen.findByText(/Данные изменены/);
        expect(close).not.toHaveBeenCalled();
    });
    it('an invalid amount never enters the financial confirmation step', () => {
        renderApp(<OrderActionModal action={{ kind: 'payment', order: staffOrder }} close={vi.fn()}/>);
        fireEvent.change(screen.getByLabelText('Сумма, ₽'), { target: { value: '0' } });
        fireEvent.change(screen.getByLabelText('Номер / подтверждение операции'), { target: { value: 'test-reference' } });
        fireEvent.click(screen.getByRole('button', { name: 'Проверить действие' }));
        expect(screen.queryByRole('button', { name: 'Подтвердить', exact: true })).not.toBeInTheDocument();
        expect(staffApi.payment).not.toHaveBeenCalled();
    });
});
