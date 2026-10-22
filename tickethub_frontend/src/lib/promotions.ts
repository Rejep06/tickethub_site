import type { CreateOrderInput, Hold, PromoPreviewResult } from './api/generated';

export interface PromoSelection {
    code: string;
    quote: PromoPreviewResult | null;
}
export function normalizedPromoCode(code: string): string {
    return code.trim().toUpperCase();
}
export function validPromoCode(code: string): boolean {
    return /^[A-Z0-9][A-Z0-9_-]{2,39}$/.test(normalizedPromoCode(code));
}
export function promoMatchesHold(quote: PromoPreviewResult, hold: Pick<Hold, 'id' | 'total_minor'>, code: string): boolean {
    return quote.hold_id === hold.id && quote.code === normalizedPromoCode(code)
        && Number.isSafeInteger(quote.promo_version) && quote.promo_version > 0
        && Number.isSafeInteger(quote.discount_minor) && quote.discount_minor > 0
        && Number.isSafeInteger(quote.total_minor) && quote.total_minor > 0
        && quote.subtotal_minor === hold.total_minor && quote.currency === 'RUB'
        && quote.total_minor + quote.discount_minor === hold.total_minor;
}
/** Only carry a server-calculated, explicitly applied quote to order submission. */
export function orderPromoFields(hold: Pick<Hold, 'id' | 'total_minor'>, selection: PromoSelection): Partial<CreateOrderInput> {
    if (!selection.code.trim()) return { expected_total_minor: hold.total_minor };
    if (!selection.quote || !promoMatchesHold(selection.quote, hold, selection.code)) throw new Error('PROMO_APPLY_REQUIRED');
    return {
        promo_code: selection.quote.code,
        expected_promo_version: selection.quote.promo_version,
        expected_discount_minor: selection.quote.discount_minor,
        expected_total_minor: selection.quote.total_minor
    };
}
