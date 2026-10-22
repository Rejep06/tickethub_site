'use client';
import { useEffect, useMemo, useRef, useState, type PointerEvent } from 'react';
import Image from 'next/image';
import type { DraftSeat } from '@/lib/seat-editor';
import { relativePoint } from '@/lib/geometry';
import { hasSeatPosition, selectRectangle } from '@/lib/seat-editor';
export type CanvasTool = 'select' | 'box' | 'add' | 'pan';
type Point = { x: number; y: number };
interface Gesture { kind: 'move' | 'pan' | 'box' | 'add'; start: Point; screen: Point; keys: Set<string>; additive: boolean; scroll: Point; moved: boolean }
export function EditorCanvas({ seats, selected, onSelect, onMove, onAdd, image, tool, zoom, setZoom, editable, onAspect }: {
    seats: DraftSeat[]; selected: Set<string>; onSelect: (keys: Set<string>) => void;
    onMove: (keys: Set<string>, dx: number, dy: number) => void; onAdd: (point: Point) => void;
    image: string | null; tool: CanvasTool; zoom: number; setZoom: (zoom: number) => void;
    editable: boolean; onAspect: (aspect: number) => void;
}) {
    const viewport = useRef<HTMLDivElement>(null), canvas = useRef<HTMLDivElement>(null), gesture = useRef<Gesture | null>(null);
    const [aspect, setAspect] = useState(1.6), [offset, setOffset] = useState<Point | null>(null), [box, setBox] = useState<{ start: Point; end: Point } | null>(null);
    // Invalid imported coordinates stay in the table/diagnostics; never draw them at (0, 0).
    const groups = useMemo(() => {
        const drawable = seats.filter(hasSeatPosition);
        return { chosen: drawable.filter(seat => selected.has(seat.key)), others: drawable.filter(seat => !selected.has(seat.key)) };
    }, [seats, selected]);
    const height = 1600 / aspect;
    useEffect(() => { if (!image) { setAspect(1.6); onAspect(1.6); } }, [image, onAspect]);
    useEffect(() => {
        const el = viewport.current;
        if (!el) return;
        function wheel(event: WheelEvent) { if (event.ctrlKey || event.metaKey) { event.preventDefault(); setZoom(Math.min(6, Math.max(1, zoom + (event.deltaY > 0 ? -.2 : .2)))); } }
        el.addEventListener('wheel', wheel, { passive: false });
        return () => el.removeEventListener('wheel', wheel);
    }, [zoom, setZoom]);
    function point(event: { clientX: number; clientY: number }): Point {
        const rect = canvas.current!.getBoundingClientRect();
        return relativePoint(event.clientX, event.clientY, rect);
    }
    function start(event: PointerEvent<SVGSVGElement>) {
        if (event.button !== 0 && event.button !== 1) return;
        event.preventDefault();
        const at = point(event);
        const key = event.target instanceof Element ? event.target.closest('[data-seat-key]')?.getAttribute('data-seat-key') : null;
        let keys = new Set(selected), kind: Gesture['kind'] = 'box';
        if (tool === 'pan' || event.altKey || event.button === 1) kind = 'pan';
        else if (key && tool !== 'box' && tool !== 'add') {
            if (event.shiftKey) { if (keys.has(key)) keys.delete(key); else keys.add(key); }
            else if (!keys.has(key)) keys = new Set([key]);
            onSelect(keys); kind = 'move';
        } else if (tool === 'add' && editable) kind = 'add';
        else if (!event.shiftKey) { keys = new Set(); onSelect(keys); }
        gesture.current = { kind, start: at, screen: { x: event.clientX, y: event.clientY }, keys, additive: event.shiftKey, scroll: { x: viewport.current!.scrollLeft, y: viewport.current!.scrollTop }, moved: false };
        event.currentTarget.setPointerCapture(event.pointerId);
    }
    function move(event: PointerEvent<SVGSVGElement>) {
        const current = gesture.current;
        if (!current) return;
        const dx = event.clientX - current.screen.x, dy = event.clientY - current.screen.y;
        if (Math.hypot(dx, dy) >= 4) current.moved = true;
        if (current.kind === 'pan') { viewport.current!.scrollLeft = current.scroll.x - dx; viewport.current!.scrollTop = current.scroll.y - dy; }
        else if (current.kind === 'box') setBox({ start: current.start, end: point(event) });
        else if (current.kind === 'move' && current.moved && editable) {
            const rect = canvas.current!.getBoundingClientRect();
            setOffset({ x: dx / rect.width, y: dy / rect.height });
        }
    }
    function finish(event: PointerEvent<SVGSVGElement>) {
        const current = gesture.current;
        gesture.current = null;
        if (current?.kind === 'box') onSelect(new Set([...(current.additive ? selected : []), ...selectRectangle(seats, current.start, point(event))]));
        else if (current?.kind === 'move' && current.moved && editable) {
            const rect = canvas.current!.getBoundingClientRect();
            onMove(current.keys, (event.clientX - current.screen.x) / rect.width, (event.clientY - current.screen.y) / rect.height);
        } else if (current?.kind === 'add' && !current.moved && editable) onAdd(point(event));
        setOffset(null); setBox(null);
        if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    }
    const dots = (items: DraftSeat[], active: boolean) => items.map(seat => <circle key={seat.key} data-seat-key={seat.key} cx={Number(seat.x) * 1600} cy={Number(seat.y) * height} r={active ? 8 : 6} className={active ? 'plan-dot is-selected' : 'plan-dot'}><title>{seat.sector} / ряд {seat.row} / место {seat.number}</title></circle>);
    return <div className="plan-viewport" ref={viewport} tabIndex={0} role="region" aria-label="Холст схемы. Для выбора с клавиатуры используйте список мест ниже.">
        <div className={`plan-canvas tool-${tool} ${!image ? 'without-background' : ''}`} ref={canvas} style={{ width: `${zoom * 100}%`, aspectRatio: aspect }}>
            {image && <Image src={image} alt="Фон схемы" fill unoptimized draggable={false} sizes="100vw" style={{ objectFit: 'fill', pointerEvents: 'none' }} onLoad={event => { if (event.currentTarget.naturalHeight) { const ratio = event.currentTarget.naturalWidth / event.currentTarget.naturalHeight; setAspect(ratio); onAspect(ratio); } }} />}
            <svg className="plan-svg" viewBox={`0 0 1600 ${height}`} preserveAspectRatio="none" aria-hidden="true" onPointerDown={start} onPointerMove={move} onPointerUp={finish} onPointerCancel={() => { gesture.current = null; setOffset(null); setBox(null); }}>
                <g>{dots(groups.others, false)}</g><g transform={offset ? `translate(${offset.x * 1600} ${offset.y * height})` : undefined}>{dots(groups.chosen, true)}</g>
                {box && <rect className="plan-selection-box" x={Math.min(box.start.x, box.end.x) * 1600} y={Math.min(box.start.y, box.end.y) * height} width={Math.abs(box.start.x - box.end.x) * 1600} height={Math.abs(box.start.y - box.end.y) * height} />}
            </svg>
            {!seats.length && !image && <div className="plan-empty-canvas"><strong>Ваша схема начинается здесь</strong><span>Добавьте блок рядов, импортируйте CSV<br />или поставьте первое место вручную.</span></div>}
        </div>
    </div>;
}
