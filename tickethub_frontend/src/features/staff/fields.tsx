'use client';
import { useState } from 'react';
import { useApi } from '@/lib/hooks';
import { text } from '@/lib/safe';
import { Button, Checkbox, ErrorState, Field, FieldErrors, Input, Modal, Pagination, Select, Skeleton, Textarea } from '@/components/ui';
export type StaffRow = Record<string, unknown> & {
    id: string;
};
export interface StaffPage {
    count: number;
    results: StaffRow[];
    next: string | null;
    previous: string | null;
}
export interface StaffField {
    name: string;
    label: string;
    type?: 'text' | 'textarea' | 'number' | 'money' | 'boolean' | 'datetime' | 'date' | 'select' | 'reference' | 'multiref' | 'password';
    required?: boolean;
    options?: string[];
    lookup?: string;
    filterBy?: string;
    filterParam?: string;
    hint?: string;
    nullable?: boolean;
    min?: number;
    max?: number;
    default?: unknown;
    createOnly?: boolean;
}
export function rowLabel(row: StaffRow) {
    return text(row.title_ru) || text(row.name_ru) || text(row.name) || (row.sector ? [row.sector, row.row, row.number].filter(Boolean).join(' / ') : '') || text(row.number) || text(row.email) || row.id;
}
export function ReferencePicker({ path, value, onChange, required = false, disabled = false }: {
    path: string;
    value: string;
    onChange: (s: string) => void;
    required?: boolean;
    disabled?: boolean;
}) {
    const [open, setOpen] = useState(false), [page, setPage] = useState(1), [search, setSearch] = useState(''), [label, setLabel] = useState('');
    const result = useApi<StaffPage>(path + (path.includes('?') ? '&' : '?') + `page=${page}&page_size=24`, open);
    return <div className="reference-picker">
  <div className="input-group">
    <Input required={required} disabled={disabled} aria-label="Идентификатор объекта" value={value} onChange={e => {
        setLabel('');
        onChange(e.target.value);
    }} placeholder="UUID или выбрать из списка"/>
    <Button type="button" variant="secondary" disabled={disabled} onClick={() => setOpen(true)}>Выбрать</Button>
  </div>
  {label && <small>{label}</small>}
  <Modal open={open} onClose={() => setOpen(false)} title="Выбор объекта"><div className="stack">
      <Field label="Фильтр внутри текущей страницы"><Input value={search} onChange={e => setSearch(e.target.value)}/></Field>
      {result.isPending ? <Skeleton /> : result.error ? <ErrorState error={result.error} retry={() => void result.refetch()}/> : <div className="lookup-list">{result.data?.results.filter(row => (rowLabel(row) + ' ' + row.id).toLowerCase().includes(search.toLowerCase())).map(row => <button key={row.id} type="button" onClick={() => {
        onChange(row.id);
        setLabel(rowLabel(row));
        setOpen(false);
    }}>
          <strong>{rowLabel(row)}</strong>
          <small>{row.id}</small>
        </button>)}</div>}
      {result.data && <Pagination count={result.data.count} page={page} onChange={p => {
        setPage(p);
        setSearch('');
    }}/>}
      <small>Показана одна страница API. Для следующей используйте пагинацию. Можно вставить известный UUID напрямую.</small>
    </div></Modal>
    </div>;
}
export function StaffFields({ fields, values, setValue, error, isNew = false, disabled = false }: {
    fields: StaffField[];
    values: Record<string, unknown>;
    setValue: (key: string, value: unknown) => void;
    error?: unknown;
    isNew?: boolean;
    disabled?: boolean;
}) {
    return <div className="form-grid">{fields.map(field => {
        if (field.createOnly && !isNew)
            return null;
        const value = values[field.name];
        const required = field.required && !(field.type === 'password' && !isNew);
        const lookup = (field.lookup ?? '') + (field.filterBy && values[field.filterBy] ? `?${field.filterParam ?? field.filterBy}=${encodeURIComponent(text(values[field.filterBy]))}` : '');
        let input;
        if (field.type === 'boolean')
            input = <Checkbox disabled={disabled} checked={value === true} onChange={e => setValue(field.name, e.target.checked)}>{field.label}</Checkbox>;
        else if (field.type === 'reference')
            input = <ReferencePicker disabled={disabled} required={required} path={lookup} value={text(value)} onChange={v => setValue(field.name, v)}/>;
        else if (field.type === 'multiref')
            input = <div className="stack">
    {(Array.isArray(value) ? value : []).map((v, i) => <div key={i} className="input-group">
      <ReferencePicker disabled={disabled} path={lookup} value={text(v)} onChange={x => {
                const a = Array.isArray(value) ? [...value] : [];
                a[i] = x;
                setValue(field.name, a);
            }}/>
      <Button type="button" variant="ghost" onClick={() => setValue(field.name, (Array.isArray(value) ? value : []).filter((_, j) => i !== j))}>×</Button>
    </div>)}
    <Button disabled={disabled} type="button" variant="secondary" onClick={() => setValue(field.name, [...(Array.isArray(value) ? value : []), ''])}>Добавить участника</Button>
  </div>;
        else if (field.type === 'select')
            input = <Select disabled={disabled} required={required} value={String(value ?? '')} onChange={e => setValue(field.name, e.target.value)}>
    <option value="">—</option>
    {field.options?.map(option => <option key={option} value={option}>{option}</option>)}
  </Select>;
        else if (field.type === 'textarea')
            input = <Textarea disabled={disabled} required={required} value={String(value ?? '')} onChange={e => setValue(field.name, e.target.value)}/>;
        else
            input = <Input disabled={disabled} required={required} type={field.type === 'datetime' ? 'datetime-local' : field.type === 'date' ? 'date' : field.type === 'number' ? 'number' : field.type === 'password' ? 'password' : 'text'} inputMode={field.type === 'money' ? 'decimal' : undefined} min={field.min} max={field.max} autoComplete={field.type === 'password' ? 'new-password' : undefined} value={String(value ?? '')} onChange={e => setValue(field.name, e.target.value)}/>;
        return <div key={field.name} className={field.type === 'textarea' ? 'field-wide' : ''}>
    <Field label={field.type === 'boolean' ? '' : field.label + (required ? ' *' : '')} hint={field.hint}>{input}</Field>
    <FieldErrors error={error} name={field.name}/>
  </div>;
    })}</div>;
}
