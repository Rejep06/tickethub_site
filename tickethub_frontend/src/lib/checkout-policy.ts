import type { Availability, PublicConfig } from './api/generated';
/** Manual orders do not require online_payments_enabled. Server availability remains authoritative. */
export function canCheckout(config: PublicConfig | null, availability: Availability | undefined): boolean {
    return config?.order_intake_enabled === true && availability?.orderable === true;
}
export function intakeMessage(config: PublicConfig | null, availability: Availability | undefined): string {
    if (!config) return 'checkoutChecking';
    if (config.legal_ready === false) return 'error_LEGAL_NOT_READY';
    if (!config.order_intake_enabled) return 'error_FORMS_DISABLED';
    const code = availability?.reason_code ?? '';
    return ['FORMS_DISABLED', 'LEGAL_NOT_READY', 'EVENT_CLOSED', 'EVENT_STARTED', 'SALES_CLOSED'].includes(code)
        ? 'error_' + code : 'error_EVENT_NOT_ORDERABLE';
}
