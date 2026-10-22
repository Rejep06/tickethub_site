export type Locale = 'ru' | 'en';
/** All business money is integer kopecks. null is unknown, never zero. */
export function formatMoney(minor: number | null | undefined, locale: Locale = 'ru'): string {
    if (minor == null || !Number.isSafeInteger(minor))
        return '—';
    return new Intl.NumberFormat(locale === 'ru' ? 'ru-RU' : 'en-GB', {
        style: 'currency', currency: 'RUB', currencyDisplay: locale === 'ru' ? 'symbol' : 'code',
        minimumFractionDigits: minor % 100 ? 2 : 0, maximumFractionDigits: 2
    }).format(minor / 100);
}
export function minorFromRub(value: string): number {
    const input = value.trim().replace(/[\s\u00a0\u202f]/g, '').replace(',', '.');
    if (!/^\d+(?:\.\d{1,2})?$/.test(input))
        throw new Error('INVALID_MONEY');
    const [whole, fraction = ''] = input.split('.');
    const minor = Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
    if (!Number.isSafeInteger(minor))
        throw new Error('INVALID_MONEY');
    return minor;
}
export function rubInput(minor: number | null | undefined): string {
    if (minor == null || !Number.isSafeInteger(minor))
        return '';
    const value = Math.abs(minor);
    return `${minor < 0 ? '-' : ''}${Math.trunc(value / 100)}${value % 100 ? '.' + String(value % 100).padStart(2, '0') : ''}`;
}
/** UI name for the single ruble-to-kopeck conversion implementation. */
export const parseRubles = minorFromRub;
