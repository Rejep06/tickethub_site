/** DRF field errors can be strings, lists or nested dictionaries. */
export interface ErrorDetail { field: string; message: string }
export function normalizeDetails(value: unknown): Record<string, unknown> {
    if (value && typeof value === 'object' && !Array.isArray(value)) return value as Record<string, unknown>;
    return typeof value === 'string' || Array.isArray(value) ? { non_field_errors: value } : {};
}
export function errorDetails(value: unknown): ErrorDetail[] {
    const result: ErrorDetail[] = [];
    function visit(item: unknown, field: string, depth: number) {
        if (depth > 6 || result.length >= 40) return;
        if (typeof item === 'string' && item.trim()) result.push({ field, message: item.slice(0, 1000) });
        else if (Array.isArray(item)) item.slice(0, 40).forEach((child, i) => visit(child, typeof child === 'string' ? field : `${field}.${i + 1}`, depth + 1));
        else if (item && typeof item === 'object') Object.entries(item).slice(0, 40).forEach(([key, child]) => visit(child, field ? `${field}.${key}` : key, depth + 1));
    }
    visit(value, '', 0);
    return result;
}
export function fieldError(value: unknown, field: string): string | undefined {
    const messages = errorDetails(value).filter(item => item.field === field || item.field.startsWith(field + '.')).map(item => item.message);
    return messages.length ? [...new Set(messages)].join(' ') : undefined;
}
const labels: Record<string, string> = {
    image: 'Изображение', image_url: 'Ссылка на изображение', rights_source: 'Источник изображения', rights_confirmed: 'Право использования',
    image_rights_source: 'Источник обложки', image_rights_confirmed: 'Право использования обложки',
    expected_version: 'Версия записи', version: 'Версия', non_field_errors: '', __all__: '',
    sector: 'Сектор', row: 'Ряд', number: 'Номер места', x: 'Координата X', y: 'Координата Y',
    start_at: 'Дата начала', sale_deadline: 'Окончание продаж', seating_plan: 'Схема мест',
    description_ru: 'Описание RU', description_en: 'Описание EN', url: 'Ссылка', text: 'CSV',
    create: 'Новые места', update: 'Изменённые места', delete: 'Удаление мест'
};
export function errorFieldLabel(field: string, locale: 'ru' | 'en'): string {
    if (['non_field_errors', '__all__'].includes(field)) return '';
    return field.split('.').map(part => locale === 'ru' ? labels[part] ?? part : part).filter(Boolean).join(' → ');
}
