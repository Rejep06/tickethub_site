import type { StaffOrder } from './api/generated';
/** UX gating mirrors services.py. The server still validates stock, event and permissions. */
export function orderActions(order: StaffOrder): string[] {
    const out: string[] = [];
    if (order.order_state === 'NEW')
        out.push('start');
    if (order.order_state === 'IN_PROGRESS')
        out.push('confirm');
    if (['NEW', 'IN_PROGRESS', 'CONFIRMED'].includes(order.order_state))
        out.push('contact', 'operations');
    if (!['CANCELLED', 'REJECTED'].includes(order.order_state))
        out.push('cancel');
    const everSent = order.deliveries.length > 0;
    if (['NEW', 'IN_PROGRESS'].includes(order.order_state) && order.payment.received_minor === 0 && !everSent)
        out.push('reject');
    out.push('payment'); // The ledger also records expenses and supplier refunds on closed orders.
    if (['CONFIRMED', 'COMPLETED'].includes(order.order_state) && order.payment.received_minor === order.total_minor && order.items.some(i => i.is_active))
        out.push('delivery');
    if (order.order_state === 'CONFIRMED' && order.delivery_state === 'SENT' && (order.payment.net_received_minor ?? 0) >= order.items.filter(i => i.is_active).reduce((sum, i) => sum + i.sale_price_minor, 0) && order.items.some(i => i.is_active) && order.cases.every(c => ['CLOSED', 'REJECTED'].includes(c.status)))
        out.push('complete');
    return out;
}
export function deliveryProgress(sent: number, total: number, locale: 'ru' | 'en' = 'ru'): string {
    return locale === 'ru' ? `Отправлено ${sent} из ${total} билетов` : `${sent} of ${total} tickets sent`;
}
