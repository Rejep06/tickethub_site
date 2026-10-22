'use client';
import { useState } from 'react';
import { editorApi, type BlockInput, type SeatPreview, type EditorSeatInput } from '@/lib/api/editor';
import { ApiError } from '@/lib/api/client';
import { useTask } from '@/lib/hooks';
import { Alert, Button, Checkbox, ErrorState, Field, Input, Modal, Select, Textarea } from '@/components/ui';
const initial = { sector: '', rows: '5', seats_per_row: '12', row_start: '1', seat_start: '1', seat_step: '1', x: '15', y: '15', width: '50', row_spacing: '4', angle: '0', curve: '0', aisles_after: '' };
type Form = typeof initial;
const numberFields: { key: keyof Form; label: string; min?: number; max?: number; step?: number }[] = [
    { key: 'rows', label: 'Количество рядов', min: 1, max: 100, step: 1 }, { key: 'seats_per_row', label: 'Мест в ряду', min: 1, max: 500, step: 1 },
    { key: 'row_start', label: 'Первый ряд', min: 1, step: 1 }, { key: 'seat_start', label: 'Первое место', min: 1, step: 1 },
    { key: 'x', label: 'Начало X, %', min: 0, max: 100 }, { key: 'y', label: 'Начало Y, %', min: 0, max: 100 },
    { key: 'width', label: 'Ширина ряда, %', min: 0, max: 100 }, { key: 'row_spacing', label: 'Расстояние между рядами, %', min: .01, max: 100 },
    { key: 'angle', label: 'Угол, °' }, { key: 'curve', label: 'Изгиб ряда, %', min: -100, max: 100 }
];
export function SeatBatchDialog({ id, kind, onClose, onApply }: { id: string; kind: 'block' | 'csv'; onClose: () => void; onApply: (seats: EditorSeatInput[]) => void }) {
    const [form, setForm] = useState<Form>(initial), [reverse, setReverse] = useState(false), [csv, setCsv] = useState(''), [preview, setPreview] = useState<SeatPreview | null>(null);
    const task = useTask();
    function change(key: keyof Form, value: string) { setForm(current => ({ ...current, [key]: value })); setPreview(null); task.setError(null); }
    async function generate() {
        setPreview(null);
        if (kind === 'csv') { setPreview(await editorApi.csvPreview(id, csv)); return; }
        function number(key: keyof Form) { const value = Number(form[key]); if (!form[key].trim() || !Number.isFinite(value)) throw new ApiError(400, 'INVALID_GEOMETRY', 'Заполните числовые параметры.', { [key]: ['Нужно конечное число.'] }); return value; }
        const body: BlockInput = { sector: form.sector.trim(), rows: number('rows'), seats_per_row: number('seats_per_row'), row_start: number('row_start'), seat_start: number('seat_start'), seat_step: number('seat_step') as BlockInput['seat_step'], x: number('x') / 100, y: number('y') / 100, width: number('width') / 100, row_spacing: number('row_spacing') / 100, angle: number('angle'), curve: number('curve') / 100, reverse_alternate: reverse, aisles_after: form.aisles_after.trim() ? form.aisles_after.trim().split(/[,;\s]+/).map(Number) : [] };
        setPreview(await editorApi.blockPreview(id, body));
    }
    return <Modal open title={kind === 'block' ? 'Блок рядов' : 'Импорт мест из CSV'} onClose={onClose} busy={task.busy}><div className="stack">
        <form className="stack" onSubmit={event => { event.preventDefault(); void task.run(generate); }}><fieldset disabled={task.busy} className="stack">
            {kind === 'block' ? <>
                <div className="grid-2"><Field label="Сектор"><Input required maxLength={50} value={form.sector} onChange={event => change('sector', event.target.value)} /></Field><Field label="Шаг нумерации"><Select value={form.seat_step} onChange={event => change('seat_step', event.target.value)}>{[1, 2, -1, -2].map(step => <option key={step} value={step}>{step > 0 ? '+' : ''}{step}</option>)}</Select></Field>{numberFields.map(({ key, label, ...props }) => <Field key={key} label={label}><Input type="number" required step="any" {...props} value={form[key]} onChange={event => change(key, event.target.value)} /></Field>)}</div>
                <Field label="Проходы после позиций" hint="Например, 6, 12. Проход делит группу соседства; визуальный интервал можно увеличить перемещением выделения."><Input value={form.aisles_after} onChange={event => change('aisles_after', event.target.value)} placeholder="6, 12" /></Field>
                <Checkbox checked={reverse} onChange={event => { setReverse(event.target.checked); setPreview(null); }}>Обратная нумерация в каждом втором ряду</Checkbox>
            </> : <>
                <Field label="CSV-файл" hint="UTF-8, до 512 КБ. Колонки: sector,row,number,x,y. Координаты 0…1."><Input type="file" accept=".csv,text/csv" onChange={event => { const file = event.target.files?.[0]; if (!file) return; void task.run(async () => { if (file.size > 512 * 1024) throw new ApiError(400, 'INVALID_CSV', 'CSV должен быть меньше 512 КБ.'); setCsv(await file.text()); setPreview(null); }); }} /></Field>
                <Field label="Содержимое CSV"><Textarea required rows={10} value={csv} onChange={event => { setCsv(event.target.value); setPreview(null); }} placeholder={'sector,row,number,x,y\nA,1,1,0.2,0.3\nA,1,2,0.25,0.3'} /></Field>
            </>}
            <Button type="submit" busy={task.busy}>Рассчитать предпросмотр</Button>
        </fieldset></form>
        {task.error ? <ErrorState error={task.error} /> : null}
        {preview && <div className="stack"><div className="batch-preview" aria-label={`Предпросмотр ${preview.count} мест`}><svg viewBox="0 0 1600 1000" role="img" aria-label="Геометрия новых мест">{preview.seats.map((seat, i) => <circle key={i} cx={Number(seat.x) * 1600} cy={Number(seat.y) * 1000} r={9} className="plan-dot is-selected" />)}</svg></div><strong>Новых мест: {preview.count}</strong><Alert>Это предпросмотр. Сначала добавьте места на холст, затем нажмите «Сохранить изменения» в редакторе.</Alert><Button disabled={task.busy} onClick={() => void task.run(async () => { onApply(preview.seats); onClose(); })}>Добавить на холст</Button></div>}
        <small>До 2000 изменений за одно сохранение. Для больших схем добавляйте и сохраняйте блоки по очереди.</small>
    </div></Modal>;
}
