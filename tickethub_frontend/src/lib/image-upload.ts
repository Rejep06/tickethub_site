import { ApiError } from './api/client';

/** Frontend preflight mirrors the October image contract. The server is authoritative. */
export const MAX_IMAGE_BYTES = 100 * 1024 * 1024;
export const MAX_SVG_BYTES = 10 * 1024 * 1024;
export const MAX_IMAGE_SIDE = 20_000;
export const MAX_IMAGE_PIXELS = 300_000_000;
export const IMAGE_UPLOAD_TIMEOUT_MS = 300_000;
export type ImageType = 'image/png' | 'image/jpeg' | 'image/webp' | 'image/svg+xml';
interface Rights { rightsSource: string; rightsConfirmed: boolean }
// `mode` is optional for existing file selections created by older call sites.
export type ImageSelection = Rights & (
    { mode?: 'file'; file: File; imageUrl?: never } |
    { mode: 'url'; imageUrl: string; file?: never }
);
export interface ImageInfo { type: ImageType; width: number | null; height: number | null; previewSafe: boolean }
export interface ImageUrlInput { image_url: string; expected_version: number; rights_source: string; rights_confirmed: true }
function invalid(field: string, message: string): never {
    throw new ApiError(400, 'VALIDATION_ERROR', 'Проверьте изображение.', { [field]: [message] });
}
export function imageSignature(bytes: Uint8Array): Exclude<ImageType, 'image/svg+xml'> | null {
    if (bytes.length >= 8 && [137,80,78,71,13,10,26,10].every((b, i) => bytes[i] === b)) return 'image/png';
    if (bytes.length >= 3 && bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255) return 'image/jpeg';
    const ascii = (start: number, end: number) => String.fromCharCode(...bytes.slice(start, end));
    if (bytes.length >= 12 && ascii(0, 4) === 'RIFF' && ascii(8, 12) === 'WEBP') return 'image/webp';
    return null;
}
export async function checkImageHeader(file: Blob): Promise<ImageType> {
    if (!file.size) invalid('image', 'Файл пустой. Выберите изображение.');
    if (file.size > MAX_IMAGE_BYTES) invalid('image', 'Файл больше 100 МиБ.');
    const bytes = new Uint8Array(await file.slice(0, 65536).arrayBuffer());
    const type = imageSignature(bytes);
    if (type) return type;
    // Only recognise an XML root here; this is NOT an SVG sanitizer. Never embed it.
    const text = new TextDecoder().decode(bytes).replace(/^\uFEFF/, '').replace(/<!--[\s\S]*?-->/g, '').replace(/<\?[\s\S]*?\?>/g, '').trimStart();
    if (/^<svg[\s>]/i.test(text)) {
        if (file.size > MAX_SVG_BYTES) invalid('image', 'SVG больше 10 МиБ.');
        return 'image/svg+xml';
    }
    return invalid('image', 'Не удалось распознать формат. Выберите PNG, JPEG, WebP или статический SVG.');
}
export function checkImageDimensions(width: number, height: number): void {
    if (!Number.isFinite(width) || !Number.isFinite(height) || width < 1 || height < 1) invalid('image', 'Не удалось прочитать размеры изображения.');
    if (width > MAX_IMAGE_SIDE || height > MAX_IMAGE_SIDE) invalid('image', 'Ширина и высота не должны превышать 20 000 px.');
    if (width * height > MAX_IMAGE_PIXELS) invalid('image', 'Площадь изображения превышает 300 Мп. Например, 20 000 × 15 000 допустимо, а 20 000 × 20 000 — нет.');
}
/** Read container headers, not decoded pixels. No 1.2+ GB browser allocation for a 300 MP JPEG. */
export async function rasterDimensions(file: Blob, type: ImageType): Promise<{ width: number; height: number } | null> {
    const bytes = new Uint8Array(await file.slice(0, 32).arrayBuffer());
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    if (type === 'image/png' && bytes.length >= 24) return { width: view.getUint32(16), height: view.getUint32(20) };
    if (type === 'image/webp' && bytes.length >= 30) {
        const chunk = String.fromCharCode(...bytes.slice(12, 16));
        const uint24 = (offset: number) => bytes[offset] + bytes[offset + 1] * 256 + bytes[offset + 2] * 65536;
        if (chunk === 'VP8X') return { width: uint24(24) + 1, height: uint24(27) + 1 };
        if (chunk === 'VP8 ' && bytes[23] === 0x9d && bytes[24] === 1 && bytes[25] === 0x2a) return { width: view.getUint16(26, true) & 0x3fff, height: view.getUint16(28, true) & 0x3fff };
        if (chunk === 'VP8L' && bytes[20] === 0x2f) return { width: 1 + bytes[21] + ((bytes[22] & 0x3f) << 8), height: 1 + (bytes[22] >> 6) + (bytes[23] << 2) + ((bytes[24] & 0x0f) << 10) };
    }
    if (type === 'image/jpeg') {
        // Skip metadata by its segment length. Bound requests even on malformed input.
        let offset = 2;
        for (let count = 0; count < 4096 && offset + 4 <= file.size; count++) {
            const part = new Uint8Array(await file.slice(offset, offset + 12).arrayBuffer());
            if (part[0] !== 0xff) return null;
            if (part[1] === 0xff) { offset++; continue; }
            const marker = part[1];
            if (marker === 0xda || marker === 0xd9) return null;
            if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd8)) { offset += 2; continue; }
            const length = part[2] * 256 + part[3];
            if (length < 2 || offset + 2 + length > file.size) return null;
            if ([0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf].includes(marker) && part.length >= 9)
                return { width: part[7] * 256 + part[8], height: part[5] * 256 + part[6] };
            offset += 2 + length;
        }
    }
    return null; // Let the backend validate uncommon/malformed containers; do not decode them here.
}
export async function inspectImage(file: File): Promise<ImageInfo> {
    const type = await checkImageHeader(file);
    const size = type === 'image/svg+xml' ? null : await rasterDimensions(file, type);
    if (size) checkImageDimensions(size.width, size.height);
    // Small raster previews only. Untrusted SVG and huge bitmaps are never rendered locally.
    return { type, width: size?.width ?? null, height: size?.height ?? null,
        previewSafe: type !== 'image/svg+xml' && !!size && size.width * size.height <= 16_000_000 && file.size <= 16 * 1024 * 1024 };
}
export function imageUrl(value: string): string {
    const raw = value.trim();
    if (!raw || /[\s\\\u0000-\u001f]/.test(raw)) return invalid('image_url', 'Вставьте прямую HTTPS-ссылку на изображение.');
    let url: URL;
    try { url = new URL(raw); } catch { return invalid('image_url', 'Не удалось прочитать ссылку. Пример: https://example.com/arena.svg'); }
    if (url.protocol !== 'https:' || url.username || url.password || !url.hostname) return invalid('image_url', 'Нужна HTTPS-ссылка без логина и пароля в адресе.');
    // SSRF and redirects are validated on the backend, not by trusting this client check.
    if (url.hash) return invalid('image_url', 'Уберите часть адреса после #. Нужна ссылка на сам файл.');
    return url.href;
}
function rights(selection: ImageSelection, version: number) {
    if (!selection.rightsSource.trim()) invalid('rights_source', 'Укажите источник или основание использования.');
    if (selection.rightsSource.trim().length > 500) invalid('rights_source', 'Максимум 500 символов.');
    if (!selection.rightsConfirmed) invalid('rights_confirmed', 'Подтвердите право использовать изображение.');
    if (!Number.isInteger(version) || version < 1) invalid('expected_version', 'Обновите данные мероприятия или схемы.');
}
export function imageFormData(selection: ImageSelection, version: number): FormData {
    rights(selection, version);
    if (selection.mode === 'url' || !selection.file) invalid('image', 'Выберите файл или переключитесь на загрузку по ссылке.');
    const body = new FormData();
    body.set('image', selection.file);
    body.set('rights_source', selection.rightsSource.trim());
    body.set('rights_confirmed', 'true');
    body.set('expected_version', String(version));
    return body;
}
export function imageRequestBody(selection: ImageSelection, version: number): FormData | ImageUrlInput {
    rights(selection, version);
    return selection.mode === 'url'
        ? { image_url: imageUrl(selection.imageUrl), expected_version: version, rights_source: selection.rightsSource.trim(), rights_confirmed: true }
        : imageFormData(selection, version);
}
export async function validateImageSelection(selection: ImageSelection, version: number): Promise<void> {
    imageRequestBody(selection, version);
    if (selection.mode !== 'url') await inspectImage(selection.file);
}
