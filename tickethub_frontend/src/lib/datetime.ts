import type { Locale } from './money';
export function eventTime(value: string | null | undefined, timezone: string, locale: Locale = 'ru'): string {
    if (!value || !Number.isFinite(Date.parse(value)))
        return locale === 'ru' ? 'Дата уточняется' : 'Date to be announced';
    try {
        return new Intl.DateTimeFormat(locale === 'ru' ? 'ru-RU' : 'en-GB', {
            dateStyle: 'long', timeStyle: 'short', timeZone: timezone
        }).format(new Date(value));
    }
    catch {
        return locale === 'ru' ? 'Часовой пояс не указан' : 'Timezone unavailable';
    }
}
export function auditTime(value: string | null | undefined, locale: Locale = 'ru'): string {
    return value ? eventTime(value, 'UTC', locale) + ' UTC' : '—';
}
/** Monotonic clock avoids extending a hold when the computer clock changes. */
export function remainingSeconds(expiresAt: string, serverNow: string, receivedAt: number, now: number): number {
    const total = Date.parse(expiresAt) - Date.parse(serverNow);
    if (!Number.isFinite(total))
        return 0;
    return Math.max(0, Math.ceil((total - Math.max(0, now - receivedAt)) / 1000));
}
export function countdown(seconds: number): string {
    const s = Math.max(0, Math.floor(seconds));
    return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}
export function toLocalInput(value: string | null | undefined): string {
    if (!value)
        return '';
    const date = new Date(value);
    if (!Number.isFinite(date.getTime()))
        return '';
    const offset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}
export function fromLocalInput(value: string): string {
    const d = new Date(value);
    if (!Number.isFinite(d.getTime()))
        throw new Error('INVALID_DATE');
    return d.toISOString();
}
