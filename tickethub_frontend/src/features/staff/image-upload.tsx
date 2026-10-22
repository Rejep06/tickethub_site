'use client';
import { useEffect, useRef, useState } from 'react';
import Image from 'next/image';
import { ImagePlus, Upload, X, CheckCircle2, Link2, FileImage } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/api/client';
import { fieldError } from '@/lib/api/error-details';
import { imageRequestBody, inspectImage, validateImageSelection, IMAGE_UPLOAD_TIMEOUT_MS, type ImageInfo, type ImageSelection } from '@/lib/image-upload';
import { mediaPath } from '@/lib/safe';
import { useTask } from '@/lib/hooks';
import { useToast } from '@/components/ui/toast';
import { UnsavedGuard } from '@/components/ui/unsaved-guard';
import { Alert, Badge, Button, Card, Checkbox, ErrorState, Field, Input, Tabs } from '@/components/ui';

/** Fields only (no nested form). Also used during event creation. */
export function ImagePicker({ value, onChange, image, source = '', kind = 'event', error, disabled = false }: {
    value: ImageSelection | null; onChange: (value: ImageSelection | null) => void;
    image?: string; source?: string; kind?: 'event' | 'plan'; error?: unknown; disabled?: boolean;
}) {
    const [mode, setMode] = useState<'file' | 'url'>(value?.mode === 'url' ? 'url' : 'file');
    const [preview, setPreview] = useState(''), [info, setInfo] = useState<ImageInfo | null>(null);
    const [localError, setLocalError] = useState<unknown>(null), [checking, setChecking] = useState(false);
    const [failedPreview, setFailedPreview] = useState(false);
    const fileInput = useRef<HTMLInputElement>(null);
    useEffect(() => { setFailedPreview(false); if (image) setMode('file'); }, [image]);
    useEffect(() => { if (!value) { setMode('file'); if (fileInput.current) fileInput.current.value = ''; } }, [value]);
    const file = value?.mode !== 'url' ? value?.file : undefined;
    useEffect(() => {
        if (!file) { setPreview(''); setInfo(null); setChecking(false); setLocalError(null); return; }
        let url = '';
        let disposed = false;
        setChecking(true); setLocalError(null); setInfo(null); setPreview(''); setFailedPreview(false);
        inspectImage(file).then(result => {
            if (disposed) return;
            if (result.previewSafe) { url = URL.createObjectURL(file); setPreview(url); }
            setInfo(result);
        }).catch(caught => { if (!disposed) setLocalError(caught); }).finally(() => { if (!disposed) setChecking(false); });
        return () => { disposed = true; if (url) URL.revokeObjectURL(url); };
    }, [file]);
    const current = failedPreview ? null : preview || (!value ? mediaPath(image) : null);
    const reported = localError ?? error, details = reported instanceof ApiError ? reported.details : {};
    function select(file: File | undefined) {
        if (!file || disabled) return;
        setMode('file');
        onChange({ mode: 'file', file, rightsSource: value?.rightsSource || source, rightsConfirmed: false });
    }
    return <div className="stack image-picker">
        <fieldset disabled={disabled} className="image-methods"><legend className="sr-only">Способ загрузки</legend>
            <Tabs value={mode} onChange={next => {
                setMode(next as 'file' | 'url'); setLocalError(null);
                onChange(next === 'url' ? { mode: 'url', imageUrl: '', rightsSource: value?.rightsSource || source, rightsConfirmed: false } : null);
            }} options={[{ value: 'file', label: 'С устройства' }, { value: 'url', label: 'По ссылке' }]} />
        </fieldset>
        {mode === 'file' ? <div className="cover-dropzone" onDragOver={event => event.preventDefault()} onDrop={event => {
            event.preventDefault(); if (!disabled) select(event.dataTransfer.files[0]);
        }}>
            {current ? <div className={`cover-preview cover-preview-${kind}`}>
                <Image src={current} alt={preview ? 'Предпросмотр выбранного изображения' : 'Сохранённое изображение'} fill unoptimized sizes="(max-width: 800px) 100vw, 60vw" style={{ objectFit: 'contain' }} onError={() => setFailedPreview(true)} />
                <span className="cover-preview-label"><Badge tone={preview ? 'accent' : 'neutral'}>{preview ? 'Ещё не загружено' : 'Сохранено'}</Badge></span>
            </div> : <div className="cover-placeholder"><ImagePlus size={38} strokeWidth={1.4} /><strong>{file ? 'Файл выбран' : kind === 'event' ? 'Добавьте обложку мероприятия' : 'Добавьте фон схемы'}</strong><span>{file ? checking ? 'Читаем параметры изображения…' : localError ? 'Не удалось проверить файл. Подробности ниже.' : info?.type === 'image/svg+xml' ? 'SVG будет доступен для просмотра после проверки сервером.' : 'Оригинал отправится без уменьшения. Предпросмотр большого файла пропущен.' : 'Перетащите файл сюда или выберите с устройства'}</span></div>}
            <Field label="Файл изображения" error={fieldError(details, 'image')} hint="PNG, JPEG, WebP — до 100 МиБ · статический SVG — до 10 МиБ">
                <Input ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml,.svg" disabled={disabled} onChange={event => select(event.target.files?.[0])} />
            </Field>
        </div> : <div className="image-url-pane stack-sm">
            <Field label="Ссылка на изображение" error={fieldError(details, 'image_url')} hint="Прямая HTTPS-ссылка на файл, не на страницу сайта.">
                <Input type="url" inputMode="url" autoComplete="off" spellCheck={false} placeholder="https://example.com/arena.svg" required disabled={disabled} value={value?.mode === 'url' ? value.imageUrl : ''} onChange={event => onChange({ mode: 'url', imageUrl: event.target.value, rightsSource: value?.rightsSource || source, rightsConfirmed: false })} />
            </Field>
            <p className="image-url-note"><Link2 size={19} aria-hidden /><span>Сервер скачает файл и сохранит его у нас. Предпросмотр появится после сохранения.</span></p>
        </div>}
        {file && <div className="split selected-image-info"><span className="break-word"><FileImage size={18} aria-hidden /> <strong>{file.name}</strong><br /><small>{(file.size / 1024 / 1024).toFixed(2)} МиБ{info?.width && info.height ? ` · ${info.width} × ${info.height} px` : checking ? ' · Проверяем файл…' : ''}</small></span><Button type="button" variant="ghost" disabled={disabled} onClick={() => { onChange(null); if (fileInput.current) fileInput.current.value = ''; }}><X size={16} />Отменить выбор</Button></div>}
        <details className="upload-specs"><summary>Размеры и форматы</summary><p>До 20 000 px по каждой стороне и до 300 Мп одновременно. Размер и прозрачность сохраняются; растр очищается от необязательных метаданных. Например, 20 000 × 15 000 допустимо.</p><p>SVG — статический, без скриптов, анимации, внешних ресурсов, элементов use и image. Окончательную проверку выполняет сервер.</p></details>
        {kind === 'event' && <p className="muted small">Обложка появится в афише и на странице события. Вертикальные постеры показываются целиком — текст не обрезается.</p>}
        {value && <>
            <Field label="Источник / основание использования" error={fieldError(details, 'rights_source')} hint="Например, собственное фото или материал организатора.">
                <Input maxLength={500} required disabled={disabled} value={value.rightsSource} onChange={event => onChange({ ...value, rightsSource: event.target.value, rightsConfirmed: false })} />
            </Field>
            <Field label="Право использования" error={fieldError(details, 'rights_confirmed')}><Checkbox required disabled={disabled} checked={value.rightsConfirmed} onChange={event => onChange({ ...value, rightsConfirmed: event.target.checked })}>Подтверждаю право использовать это изображение</Checkbox></Field>
        </>}
        {localError ? <ErrorState error={localError} /> : null}
    </div>;
}

export function ImageUpload({ endpoint, version, image, source, kind = 'event', disabled = false, onSaved, onBusyChange }: {
    endpoint: string; version: number; image?: string; source?: string;
    kind?: 'event' | 'plan'; disabled?: boolean; onSaved?: () => Promise<void> | void; onBusyChange?: (busy: boolean) => void;
}) {
    const [selection, setSelection] = useState<ImageSelection | null>(null), [saved, setSaved] = useState(false);
    const task = useTask(), client = useQueryClient(), notify = useToast();
    useEffect(() => { onBusyChange?.(task.busy); return () => onBusyChange?.(false); }, [task.busy, onBusyChange]);
    const stale = task.error instanceof ApiError && task.error.code === 'VERSION_CONFLICT';
    return <Card className="stack" id={kind === 'event' ? 'event-cover' : 'plan-background'}>
        <UnsavedGuard dirty={!!selection} />
        <div className="split"><div><span className="eyebrow">{kind === 'event' ? 'АФИША МЕРОПРИЯТИЯ' : 'РЕДАКТОР СХЕМЫ'}</span><h2>{kind === 'event' ? 'Обложка мероприятия' : 'Фоновое изображение'}</h2></div><ImagePlus size={26} /></div>
        {disabled && <Alert>Сначала сохраните или отмените изменения основной формы{kind === 'plan' ? ' и мест' : ''}, затем загрузите изображение.</Alert>}
        <form className="stack" onSubmit={event => {
            event.preventDefault(); if (!selection || disabled || stale) return;
            void task.run(async () => {
                await validateImageSelection(selection, version);
                await api(endpoint, { method: 'POST', body: imageRequestBody(selection, version), timeoutMs: IMAGE_UPLOAD_TIMEOUT_MS });
                setSelection(null); setSaved(true);
                notify(kind === 'event' ? 'Обложка мероприятия сохранена' : 'Фон схемы сохранён');
                await client.invalidateQueries({ queryKey: ['api'] });
                await onSaved?.();
            });
        }}>
            <ImagePicker value={selection} onChange={value => { setSelection(value); setSaved(false); task.setError(null); }} image={image} source={source} kind={kind} error={task.error} disabled={disabled || task.busy} />
            {task.error ? <ErrorState error={task.error} /> : null}
            {stale && <Alert>Запись изменилась в другой вкладке. Ваш выбор сохранён. Обновите версию, проверьте текущее изображение и повторите загрузку.</Alert>}
            {stale && <Button type="button" variant="secondary" onClick={() => void task.run(async () => { await client.invalidateQueries({ queryKey: ['api'] }); await onSaved?.(); })}>Обновить версию записи</Button>}
            {saved && <p className="upload-success" role="status"><CheckCircle2 size={18} />{kind === 'event' ? 'Обложка сохранена. Она будет видна покупателям после публикации мероприятия.' : 'Фон сохранён.'}</p>}
            <div className="actions"><Button type="submit" busy={task.busy} disabled={!selection || disabled || stale}><Upload size={18} />{kind === 'event' ? 'Сохранить обложку' : 'Загрузить фон'}</Button><small>{task.busy ? 'Отправляем и обрабатываем изображение…' : `Версия записи: ${version}`}</small></div>
        </form>
    </Card>;
}
