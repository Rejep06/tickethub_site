'use client';
import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import Image from 'next/image';
import { ZoomIn, ZoomOut, Maximize, Hand, X } from 'lucide-react';
import { useLang, useT } from '@/i18n/use-t';
import { Button } from '@/components/ui';
import { formatMoney } from '@/lib/money';
import {
    buildSeatModel, fitCamera, clampCamera, zoomAt, pinchCamera, resizeCamera, nearestSeat,
    screenToWorld, worldToScreen, canInspectSeat, boundsOf, drawSeatMap, MAX_MAP_ZOOM,
    type MapSeat, type Point, type Camera, type Size, type SectorLabel
} from '@/lib/seat-viewport';

interface Gesture { camera: Camera; points: Map<number, Point>; moved: boolean }
export function SeatViewport({ seats, image, sector, row, available, selected, active, onInspect, onChoose, onSector, onReset, onAmbiguous }: {
    seats: MapSeat[]; image: string | null; sector: string; row: string;
    available: Map<string, { sale_price_minor: number }>; selected: Set<string>; active: string | null;
    onInspect: (id: string | null) => void; onChoose: (id: string) => void; onSector: (name: string) => void; onReset: () => void; onAmbiguous: () => void;
}) {
    const t = useT(), lang = useLang();
    const [imageState, setImageState] = useState({ src: image, aspect: 1.6, failed: false });
    const aspect = imageState.src === image ? imageState.aspect : 1.6;
    const backgroundFailed = imageState.src === image && imageState.failed;
    const [size, setSize] = useState<Size>({ width: 1, height: 1 });
    const [camera, setCamera] = useState<Camera>({ scale: 1, x: 0, y: 0 });
    const [dragging, setDragging] = useState(false);
    const [engaged, setEngaged] = useState(false), [hover, setHover] = useState<string | null>(null);
    const model = useMemo(() => buildSeatModel(seats, aspect), [seats, aspect]);
    const world = useMemo(() => ({ width: 1000, height: 1000 / aspect }), [aspect]);
    const availableSet = useMemo(() => new Set(available.keys()), [available]);
    const viewport = useRef<HTMLDivElement>(null), canvas = useRef<HTMLCanvasElement>(null);
    const cameraRef = useRef(camera), sizeRef = useRef(size), pointers = useRef(new Map<number, Point>()), gesture = useRef<Gesture | null>(null);
    const frame = useRef<number | null>(null), labels = useRef<SectorLabel[]>([]), engagedRef = useRef(false);
    const updateCamera = useCallback((next: Camera) => {
        cameraRef.current = next;
        if (frame.current !== null) return;
        frame.current = requestAnimationFrame(() => { frame.current = null; setCamera(cameraRef.current); });
    }, []);
    useEffect(() => () => {
        if (frame.current !== null) {
            cancelAnimationFrame(frame.current);
            // StrictMode replays setup -> cleanup -> setup with the same refs.
            // A cancelled id must not keep the next camera update permanently queued.
            frame.current = null;
        }
    }, []);
    const engage = useCallback((value: boolean) => { engagedRef.current = value; setEngaged(value); }, []);
    useEffect(() => {
        const el = viewport.current;
        if (!el) return;
        const resize = () => {
            const next = { width: Math.max(1, el.clientWidth), height: Math.max(1, el.clientHeight) }, old = sizeRef.current;
            sizeRef.current = next; setSize(next);
            updateCamera(old.width <= 1 ? fitCamera(world, next) : resizeCamera(cameraRef.current, old, next, world));
        };
        resize();
        const observer = new ResizeObserver(resize); observer.observe(el);
        return () => observer.disconnect();
    }, [world, updateCamera]);
    // A selection in the sector/row controls changes the camera, not seat coordinates.
    useEffect(() => {
        const points = model.seats.filter(p => (!sector || p.seat.sector === sector) && (!row || p.seat.row === row));
        const target = sector || row ? boundsOf(points) : null;
        updateCamera(clampCamera(fitCamera(model.world, sizeRef.current, target, target ? 60 : 24), model.world, sizeRef.current));
        setHover(null);
        // The actual geometry may refresh while the user is inspecting a seat; do not reset on stock polling.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sector, row, aspect, updateCamera]);
    useEffect(() => {
        const el = viewport.current;
        if (!el) return;
        const wheel = (event: WheelEvent) => {
            // Until the map is activated, the wheel belongs to the page.
            if (!engagedRef.current && !event.ctrlKey && !event.metaKey) return;
            event.preventDefault(); engage(true);
            const rect = el.getBoundingClientRect();
            const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? el.clientHeight : 1);
            updateCamera(zoomAt(cameraRef.current, { x: event.clientX - rect.left, y: event.clientY - rect.top }, Math.exp(-Math.max(-250, Math.min(250, delta)) * .004), world, sizeRef.current));
            setHover(null);
        };
        el.addEventListener('wheel', wheel, { passive: false });
        return () => el.removeEventListener('wheel', wheel);
    }, [world, engage, updateCamera]);
    useEffect(() => {
        const el = canvas.current, ctx = el?.getContext('2d');
        if (!ctx || !el || size.width <= 1) return;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        el.width = Math.round(size.width * dpr); el.height = Math.round(size.height * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        labels.current = drawSeatMap(ctx, model, camera, size, { available: availableSet, selected, sector, row, active, hover });
    }, [model, camera, size, availableSet, selected, sector, row, active, hover]);
    function local(event: { clientX: number; clientY: number }): Point {
        const rect = viewport.current!.getBoundingClientRect(); return { x: event.clientX - rect.left, y: event.clientY - rect.top };
    }
    function start(event: ReactPointerEvent<HTMLCanvasElement>) {
        if (event.pointerType === 'touch' && !engagedRef.current) return;
        if (event.button !== 0 && event.button !== 1) return;
        event.preventDefault(); setDragging(true); engage(true); viewport.current?.focus({ preventScroll: true }); setHover(null);
        pointers.current.set(event.pointerId, local(event));
        gesture.current = { camera: cameraRef.current, points: new Map(pointers.current), moved: pointers.current.size > 1 };
        event.currentTarget.setPointerCapture(event.pointerId);
    }
    function move(event: ReactPointerEvent<HTMLCanvasElement>) {
        const at = local(event), current = gesture.current;
        if (!current || !pointers.current.has(event.pointerId)) {
            if (event.pointerType === 'mouse') {
                const p = nearestSeat(model, at, cameraRef.current, 16, sector, row);
                setHover(p && canInspectSeat(p, cameraRef.current) ? p.seat.id : null);
            }
            return;
        }
        pointers.current.set(event.pointerId, at);
        const ids = [...current.points.keys()];
        if (ids.length >= 2) {
            const now: [Point, Point] = [pointers.current.get(ids[0])!, pointers.current.get(ids[1])!];
            const before: [Point, Point] = [current.points.get(ids[0])!, current.points.get(ids[1])!];
            current.moved = true; updateCamera(pinchCamera(current.camera, before, now, model.world, sizeRef.current));
        } else {
            const before = current.points.get(event.pointerId);
            if (!before) return;
            const dx = at.x - before.x, dy = at.y - before.y;
            if (Math.hypot(dx, dy) > 5) current.moved = true;
            if (current.moved) updateCamera(clampCamera({ ...current.camera, x: current.camera.x + dx, y: current.camera.y + dy }, model.world, sizeRef.current));
        }
    }
    function inspect(at: Point) {
        const label = labels.current.find(item => at.x >= item.x && at.x <= item.x + item.width && at.y >= item.y && at.y <= item.y + item.height);
        if (label) { onSector(label.sector); return; }
        const p = nearestSeat(model, at, cameraRef.current, 22, sector, row);
        if (p) {
            if (p.coincident) { onAmbiguous(); return; }
            if (!canInspectSeat(p, cameraRef.current)) {
                if (!sector && cameraRef.current.scale / fitCamera(model.world, sizeRef.current).scale < 2) { onSector(p.seat.sector); return; }
                const center = worldToScreen(p, cameraRef.current);
                updateCamera(zoomAt(cameraRef.current, center, Math.max(2, 24 / (p.spacing * cameraRef.current.scale)), model.world, sizeRef.current));
                return;
            }
            onInspect(p.seat.id); return;
        }
        const worldPoint = screenToWorld(at, cameraRef.current);
        if (!sector) {
            const target = model.sectors.find(s => worldPoint.x >= s.bounds.minX && worldPoint.x <= s.bounds.maxX && worldPoint.y >= s.bounds.minY && worldPoint.y <= s.bounds.maxY);
            if (target) onSector(target.name);
        }
    }
    function finish(event: ReactPointerEvent<HTMLCanvasElement>, cancel = false) {
        const current = gesture.current;
        if (!pointers.current.has(event.pointerId)) return;
        pointers.current.delete(event.pointerId);
        if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
        if (pointers.current.size) gesture.current = { camera: cameraRef.current, points: new Map(pointers.current), moved: true };
        else { gesture.current = null; setDragging(false); if (current && !current.moved && !cancel) inspect(local(event)); }
    }
    function zoom(factor: number) {
        engage(true);
        updateCamera(zoomAt(cameraRef.current, { x: sizeRef.current.width / 2, y: sizeRef.current.height / 2 }, factor, model.world, sizeRef.current));
    }
    function reset() { onReset(); updateCamera(fitCamera(model.world, sizeRef.current)); setHover(null); }
    function keyboard(event: ReactKeyboardEvent<HTMLDivElement>) {
        if (event.target !== event.currentTarget) return;
        if (['+', '=', '-', '0', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Escape'].includes(event.key)) event.preventDefault();
        if (event.key === '+' || event.key === '=') zoom(1.5);
        else if (event.key === '-') zoom(1 / 1.5);
        else if (event.key === '0') reset();
        else if (event.key === 'Escape') { engage(false); setHover(null); event.currentTarget.blur(); }
        else if (event.key.startsWith('Arrow')) updateCamera(clampCamera({ ...cameraRef.current,
            x: cameraRef.current.x + (event.key === 'ArrowLeft' ? 60 : event.key === 'ArrowRight' ? -60 : 0),
            y: cameraRef.current.y + (event.key === 'ArrowUp' ? 60 : event.key === 'ArrowDown' ? -60 : 0) }, model.world, sizeRef.current));
    }
    const ratio = size.width > 1 ? camera.scale / fitCamera(model.world, size).scale : 1;
    const hovered = hover ? model.byId.get(hover) : null, tooltipAt = hovered ? worldToScreen(hovered, camera) : null;
    const inspected = active ? model.byId.get(active) : null;
    return <div className="seat-camera-wrap">
        <div className="seat-camera-toolbar"><span>{sector ? `${t('sector')} ${sector}` : t('wholeVenue')}</span><div className="actions">
            <Button type="button" variant="secondary" aria-label={t('zoomOut')} disabled={ratio <= 1.01} onClick={() => zoom(1 / 1.5)}><ZoomOut size={18}/></Button>
            <output className="camera-zoom" aria-label={t('mapScale')}>{Math.round(ratio * 100)}%</output>
            <Button type="button" variant="secondary" aria-label={t('zoomIn')} disabled={ratio >= MAX_MAP_ZOOM - .01} onClick={() => zoom(1.5)}><ZoomIn size={18}/></Button>
            <Button type="button" variant="ghost" aria-label={t('zoomReset')} onClick={reset}><Maximize size={18}/><span>{t('wholeMap')}</span></Button>
        </div></div>
        <div ref={viewport} tabIndex={0} role="region" aria-label={t('mapKeyboardLabel')} className={`seat-viewport ${engaged ? 'is-engaged' : ''}`} onKeyDown={keyboard} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node)) engage(false); }}>
            <div className="seat-image-plane" style={{ width: model.world.width, height: model.world.height, transform: `translate(${camera.x}px, ${camera.y}px) scale(${camera.scale})` }}>
                {image && !backgroundFailed && <Image key={image} src={image} alt="" fill unoptimized sizes="100vw" draggable={false} onError={() => setImageState({ src: image, aspect: 1.6, failed: true })} onLoad={event => {
                    const el = event.currentTarget; if (el.naturalWidth > 0 && el.naturalHeight > 0) setImageState({ src: image, aspect: el.naturalWidth / el.naturalHeight, failed: false });
                }} />}
            </div>
            <canvas ref={canvas} className="seat-points-canvas" aria-hidden="true" onPointerDown={start} onPointerMove={move} onPointerUp={event => finish(event)} onPointerCancel={event => finish(event, true)} onLostPointerCapture={event => finish(event, true)} onPointerLeave={() => setHover(null)} onDoubleClick={event => { event.preventDefault(); updateCamera(zoomAt(cameraRef.current, local(event), 2, model.world, sizeRef.current)); }} />
            {!engaged && <button type="button" className="map-touch-activate" onClick={() => { engage(true); viewport.current?.focus({ preventScroll: true }); }}><Hand size={18}/>{t('activateMap')}</button>}
            {engaged && <button type="button" className="map-release" onClick={() => { engage(false); viewport.current?.blur(); }} aria-label={t('releaseMap')}><X size={16}/><span>{t('releaseMap')}</span></button>}
            {inspected && <div className="seat-inspector" aria-live="polite">
                <button type="button" className="inspector-close" aria-label={t('close')} onClick={() => onInspect(null)}><X size={16}/></button>
                <div><small>{t('sector')} {inspected.seat.sector}</small><strong>{t('row')} {inspected.seat.row} · {t('seat')} {inspected.seat.number}</strong>
                <span>{available.has(inspected.seat.id) ? formatMoney(available.get(inspected.seat.id)?.sale_price_minor, lang) : t('unavailableSeat')}</span></div>
                <Button type="button" variant={selected.has(inspected.seat.id) ? 'secondary' : 'primary'} disabled={!available.has(inspected.seat.id) && !selected.has(inspected.seat.id)} onClick={() => onChoose(inspected.seat.id)}>{t(selected.has(inspected.seat.id) ? 'removeSeat' : 'selectSeat')}</Button>
            </div>}
            {hovered && tooltipAt && !dragging && <div className="map-tooltip" role="tooltip" style={{ left: Math.max(8, Math.min(size.width - 214, tooltipAt.x - 103)), top: Math.max(8, Math.min(size.height - 90, tooltipAt.y - 87)) }}>
                <strong>{t('sector')} {hovered.seat.sector}</strong><span>{t('row')} {hovered.seat.row} · {t('seat')} {hovered.seat.number}</span><b>{available.has(hovered.seat.id) ? formatMoney(available.get(hovered.seat.id)?.sale_price_minor, lang) : t('unavailableSeat')}</b>
            </div>}
        </div>
        <div className="map-gesture-hint"><span>{engaged ? t('mapGestureActive') : t('mapGestureIdle')}</span><span>{t('mapListAlternative')}</span></div>
        {backgroundFailed && <p className="muted small">{t('mapBackgroundFailed')}</p>}
    </div>;
}
