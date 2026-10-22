import { api } from './client';
import { idempotentPost } from './attempts';
import type * as T from './generated';
export const authApi = {
    me: (locale?: 'ru' | 'en') => api<T.Profile>('me/', { locale }),
    update: (body: T.ProfileInput) => api<T.Profile>('me/', { method: 'PATCH', body }),
    requestCode: (body: T.RequestCodeInput) => api<T.OTPRequested>('auth/otp/request/', { method: 'POST', body }),
    verifyCode: (body: T.VerifyCodeInput) => api<T.Profile>('auth/otp/verify/', { method: 'POST', body }),
    staffLogin: (body: T.StaffLoginInput) => api<T.StaffLoginResult>('auth/staff/login/', { method: 'POST', body }),
    logout: () => api<void>('auth/logout/', { method: 'POST', body: {} })
};
export const checkoutApi = {
    promo: (body: T.PromoPreviewInput) => api<T.PromoPreviewResult>('checkout/promo/', { method: 'POST', body }),
    preview: (body: T.PreviewInput) => api<T.PreviewResult>('checkout/preview/', { method: 'POST', body }),
    hold: (body: T.CreateHoldInput) => idempotentPost<T.Hold>('checkout/holds/', body, 'hold.' + body.event_id),
    getHold: (id: string) => api<T.Hold>(`checkout/holds/${id}/`),
    release: (id: string) => api<T.Hold>(`checkout/holds/${id}/release/`, { method: 'POST', body: {} }),
    order: (body: T.CreateOrderInput) => idempotentPost<T.Order>('orders/', body, 'order.' + body.hold_id),
    quote: (id: string, total: number) => idempotentPost<T.Hold>(`quotes/${id}/start-checkout/`, { expected_total_minor: total }, 'quote.' + id)
};
export const requestApi = {
    create: (body: T.CreateRequestInput) => idempotentPost<T.Request>('ticket-requests/', body, 'request'),
    cancel: (id: string, version: number) => api<T.Request>(`ticket-requests/${id}/cancel/`, { method: 'POST', body: { expected_version: version } })
};
export const staffApi = {
    action: <R>(path: string, body: unknown) => api<R>(path, { method: 'POST', body }),
    payment: (id: string, body: T.RecordPaymentInput) => idempotentPost<T.FinancialEntry>(`staff/orders/${id}/financial-entries/`, body, 'payment.' + id),
    delivery: (id: string, body: T.RecordDeliveryInput) => idempotentPost<T.Delivery>(`staff/orders/${id}/deliveries/`, body, 'delivery.' + id),
    refund: (id: string, body: T.MoneyOperationInput) => idempotentPost<T.FinancialEntry>(`staff/refunds/${id}/settle/`, body, 'refund.' + id)
};
