'use client';
import { forwardRef, isValidElement, cloneElement, useId, useEffect, useRef, type ReactNode, type ButtonHTMLAttributes, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes } from 'react';
import { AlertCircle, Inbox, LoaderCircle, X } from 'lucide-react';
import { useT, useLang } from '@/i18n/use-t';
import { ApiError } from '@/lib/api/client';
import { supportReference } from '@/lib/auth-state';
import { errorDetails, errorFieldLabel } from '@/lib/api/error-details';
import { formatMoney } from '@/lib/money';
import ru from '@/messages/ru.json';
export function Button({ children, variant = 'primary', busy = false, className = '', disabled, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
    busy?: boolean;
}) {
    return <button {...props} disabled={disabled || busy} aria-busy={busy || undefined} className={`btn btn-${variant} ${className}`}>
  {busy && <LoaderCircle size={18} className="spin" aria-hidden/>}
  {children}
    </button>;
}
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className = '', ...props }, ref) {
    return <input {...props} ref={ref} className={`input ${className}`}/>;
});
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className = '', ...props }, ref) {
    return <textarea {...props} ref={ref} className={`input textarea ${className}`}/>;
});
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select({ className = '', children, ...props }, ref) {
    return <select {...props} ref={ref} className={`input ${className}`}>{children}</select>;
});
export function Field({ label, children, error, hint, htmlFor }: {
    label: string;
    children: ReactNode;
    error?: string;
    hint?: string;
    htmlFor?: string;
}) {
    const autoId = useId();
    if (isValidElement<{
        id?: string;
        'aria-describedby'?: string;
        'aria-invalid'?: boolean;
    }>(children) && (children.type === Input || children.type === Textarea || children.type === Select)) {
        const id = htmlFor ?? children.props.id ?? autoId;
        const description = [children.props['aria-describedby'], hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(' ') || undefined;
        return <div className="field">
  <label htmlFor={id}>{label}</label>
  {cloneElement(children, { id, 'aria-describedby': description, 'aria-invalid': error ? true : children.props['aria-invalid'] })}
  {hint && <small id={`${id}-hint`}>{hint}</small>}
  {error && <span id={`${id}-error`} className="field-error" role="alert">{error}</span>}
        </div>;
    }
    return <fieldset className="field field-group">
  {label && <legend>{label}</legend>}
  {children}
  {hint && <small>{hint}</small>}
  {error && <span className="field-error" role="alert">{error}</span>}
    </fieldset>;
}
export function Checkbox({ children, ...props }: InputHTMLAttributes<HTMLInputElement> & {
    children: ReactNode;
}) {
    return <label className="check">
  <input {...props} type="checkbox"/>
  <span>{children}</span>
    </label>;
}
export function Card({ children, className = '', id }: {
    children: ReactNode;
    className?: string;
    id?: string;
}) {
    return <div id={id} className={`card ${className}`}>{children}</div>;
}
export function Badge({ children, tone = 'neutral' }: {
    children: ReactNode;
    tone?: 'neutral' | 'good' | 'bad' | 'warn' | 'accent';
}) {
    return <span className={`badge badge-${tone}`}>{children}</span>;
}
export function StatusBadge({ status }: {
    status: string;
}) {
    const t = useT();
    const key = `state_${status}`;
    const tone = ['PAID', 'SENT', 'COMPLETED', 'PUBLISHED', 'AVAILABLE', 'APPROVED'].includes(status) ? 'good' : ['REJECTED', 'CANCELLED', 'BLOCKED', 'EXPIRED', 'FAILED'].includes(status) ? 'bad' : ['PARTIAL', 'PARTIALLY_SENT', 'PARTIALLY_REFUNDED', 'IN_PROGRESS', 'CHECKOUT_HELD', 'ORDER_HELD'].includes(status) ? 'warn' : 'neutral';
    return <Badge tone={tone}>{key in ru ? t(key) : status}</Badge>;
}
export function Currency({ value }: {
    value: number | null | undefined;
}) {
    return <span className="money">{formatMoney(value, useLang())}</span>;
}
export function Alert({ children, tone = 'warn' }: {
    children: ReactNode;
    tone?: 'warn' | 'bad' | 'good';
}) {
    return <div className={`alert alert-${tone}`} role={tone === 'bad' ? 'alert' : 'status'}>
  <AlertCircle size={20} aria-hidden/>
  <div>{children}</div>
    </div>;
}
export function ErrorState({ error, retry }: {
    error: unknown;
    retry?: () => void;
}) {
    const t = useT(), lang = useLang();
    let message = t('errorGeneric');
    if (error instanceof ApiError) {
        const key = 'error_' + error.code;
        message = key in ru ? t(key) : error.status === 404 ? t('notFoundText') : error.status === 403 ? t('accessDenied') : error.status >= 500 ? t('unavailable') : lang === 'ru' ? error.message : t('errorGeneric');
    }
    else if (error instanceof Error && ('error_' + error.message) in ru)
        message = t('error_' + error.message);
    const reference = supportReference(error);
    return <div className="error-state">
  <Alert tone="bad">
    <p>{message}</p>
    {error instanceof ApiError && error.status < 500 && errorDetails(error.details).length > 0 && <div className="api-error-details">{errorDetails(error.details).map((item, index) => <p key={index}>{errorFieldLabel(item.field, lang) && <strong>{errorFieldLabel(item.field, lang)}: </strong>}{item.message}</p>)}</div>}
    {reference && <details className="error-support"><summary>{t('supportDetails')}</summary><p className="small">{t('supportReferenceHint')}</p><code>{reference}</code></details>}
  </Alert>
  {retry && <Button variant="secondary" onClick={retry}>{t('retry')}</Button>}
    </div>;
}
export function FieldErrors({ error, name }: {
    error: unknown;
    name: string;
}) {
    const t = useT(), lang = useLang();
    if (!(error instanceof ApiError))
        return null;
    const value = error.details[name];
    if (!value)
        return null;
    const message = lang === 'ru' ? (Array.isArray(value) ? value.filter(x => typeof x === 'string').join(' ') : typeof value === 'string' ? value : t('checkField')) : t('checkField');
    return <span className="field-error" role="alert">{message}</span>;
}
export function Skeleton({ rows = 3 }: {
    rows?: number;
}) {
    const t = useT();
    return <div className="skeleton-stack" role="status" aria-label={t('loading')}>{Array.from({ length: rows }, (_, i) => <div className="skeleton" key={i}/>)}</div>;
}
export function EmptyState({ title, children }: {
    title?: string;
    children?: ReactNode;
}) {
    const t = useT();
    return <div className="empty-state">
  <Inbox size={36} aria-hidden/>
  <h3>{title || t('empty')}</h3>
  {children}
    </div>;
}
export function PageHeader({ title, description, children }: {
    title: string;
    description?: string;
    children?: ReactNode;
}) {
    return <div className="page-header">
  <div>
    <h1>{title}</h1>
    {description && <p>{description}</p>}
  </div>
  {children && <div className="actions">{children}</div>}
    </div>;
}
export function Modal({ open, onClose, title, children, busy = false }: {
    open: boolean;
    onClose: () => void;
    title: string;
    children: ReactNode;
    busy?: boolean;
}) {
    const ref = useRef<HTMLDialogElement>(null);
    const id = useId();
    const t = useT();
    useEffect(() => {
        const el = ref.current;
        if (!el)
            return;
        const focused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
        const previousOverflow = document.body.style.overflow;
        if (open && !el.open) {
            el.showModal();
            document.body.style.overflow = 'hidden';
        }
        if (!open && el.open)
            el.close();
        return () => {
            if (el.open)
                el.close();
            document.body.style.overflow = previousOverflow;
            focused?.focus();
        };
    }, [open]);
    return <dialog ref={ref} className="modal" aria-labelledby={id} onCancel={e => {
        e.preventDefault();
        if (!busy)
            onClose();
    }}>
  <div className="modal-head">
    <h2 id={id}>{title}</h2>
    <Button aria-label={t('close')} variant="ghost" disabled={busy} onClick={onClose}><X size={20}/></Button>
  </div>
  {children}
    </dialog>;
}
export function ConfirmDialog({ open, onClose, onConfirm, title, children, busy = false, danger = false }: {
    open: boolean;
    onClose: () => void;
    onConfirm: () => void;
    title: string;
    children?: ReactNode;
    busy?: boolean;
    danger?: boolean;
}) {
    const t = useT();
    return <Modal open={open} onClose={onClose} title={title} busy={busy}><div className="stack">
    {children}
    <div className="actions">
      <Button variant="secondary" onClick={onClose} disabled={busy}>{t('cancel')}</Button>
      <Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm} busy={busy}>{t('confirm')}</Button>
    </div>
  </div></Modal>;
}
export function Pagination({ count, page, pageSize = 24, onChange }: {
    count: number;
    page: number;
    pageSize?: number;
    onChange: (page: number) => void;
}) {
    const t = useT();
    if (count <= pageSize)
        return null;
    return <nav className="pagination" aria-label={t('page', { page })}>
  <Button variant="secondary" disabled={page <= 1} onClick={() => onChange(page - 1)}>{t('previous')}</Button>
  <span>{page} / {Math.ceil(count / pageSize)}</span>
  <Button variant="secondary" disabled={page * pageSize >= count} onClick={() => onChange(page + 1)}>{t('next')}</Button>
    </nav>;
}
export function Tabs({ value, onChange, options }: {
    value: string;
    onChange: (value: string) => void;
    options: {
        value: string;
        label: string;
    }[];
}) {
    return <div className="tabs" role="group">{options.map(option => <button type="button" key={option.value} className={option.value === value ? 'active' : ''} aria-pressed={option.value === value} onClick={() => onChange(option.value)}>{option.label}</button>)}</div>;
}
