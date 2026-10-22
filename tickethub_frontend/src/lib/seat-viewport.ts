/** Camera, spatial lookup and marker geometry. All coordinates are derived from API x/y. */
export interface Point { x: number; y: number }
export interface Size { width: number; height: number }
export interface Bounds { minX: number; minY: number; maxX: number; maxY: number }
export interface Camera extends Point { scale: number }
export interface MapSeat { id: string; sector: string; row: string; number: string; x: string | number; y: string | number }
export interface PlotSeat extends Point { seat: MapSeat; spacing: number; radius: number; coincident: boolean }
export interface Sector { name: string; bounds: Bounds; seats: PlotSeat[] }
export interface SeatModel { world: Size; seats: PlotSeat[]; sectors: Sector[]; byId: Map<string, PlotSeat>; grid: Map<string, PlotSeat[]>; cell: number; invalidCount: number }
export const MAX_MAP_ZOOM = 128;
const clamp = (n: number, low: number, high: number) => Math.min(high, Math.max(low, n));
export function boundsOf(points: Point[]): Bounds | null {
    if (!points.length) return null;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const p of points) { minX = Math.min(minX, p.x); minY = Math.min(minY, p.y); maxX = Math.max(maxX, p.x); maxY = Math.max(maxY, p.y); }
    return { minX, minY, maxX, maxY };
}
export function fitCamera(world: Size, view: Size, bounds?: Bounds | null, padding = 24): Camera {
    const b = bounds ?? { minX: 0, minY: 0, maxX: world.width, maxY: world.height };
    const w = Math.max(world.width / MAX_MAP_ZOOM, b.maxX - b.minX), h = Math.max(world.height / MAX_MAP_ZOOM, b.maxY - b.minY);
    const scale = Math.min(Math.max(1, view.width - padding * 2) / w, Math.max(1, view.height - padding * 2) / h);
    return { scale, x: view.width / 2 - (b.minX + b.maxX) / 2 * scale, y: view.height / 2 - (b.minY + b.maxY) / 2 * scale };
}
export function clampCamera(camera: Camera, world: Size, view: Size): Camera {
    const min = fitCamera(world, view).scale, scale = clamp(camera.scale, min, min * MAX_MAP_ZOOM);
    const w = world.width * scale, h = world.height * scale;
    return { scale, x: w <= view.width ? (view.width - w) / 2 : clamp(camera.x, view.width - w - 32, 32), y: h <= view.height ? (view.height - h) / 2 : clamp(camera.y, view.height - h - 32, 32) };
}
export function screenToWorld(point: Point, camera: Camera): Point { return { x: (point.x - camera.x) / camera.scale, y: (point.y - camera.y) / camera.scale }; }
export function worldToScreen(point: Point, camera: Camera): Point { return { x: point.x * camera.scale + camera.x, y: point.y * camera.scale + camera.y }; }
export function zoomAt(camera: Camera, anchor: Point, factor: number, world: Size, view: Size): Camera {
    if (!Number.isFinite(factor) || factor <= 0) return camera;
    const min = fitCamera(world, view).scale, scale = clamp(camera.scale * factor, min, min * MAX_MAP_ZOOM);
    const before = screenToWorld(anchor, camera);
    return clampCamera({ scale, x: anchor.x - before.x * scale, y: anchor.y - before.y * scale }, world, view);
}
export function pinchCamera(camera: Camera, start: [Point, Point], now: [Point, Point], world: Size, view: Size): Camera {
    const mid = (points: [Point, Point]) => ({ x: (points[0].x + points[1].x) / 2, y: (points[0].y + points[1].y) / 2 });
    const distance = (p: [Point, Point]) => Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y);
    const a = mid(start), b = mid(now), d = distance(start);
    const min = fitCamera(world, view).scale, scale = clamp(camera.scale * (d > 1 ? distance(now) / d : 1), min, min * MAX_MAP_ZOOM);
    const target = screenToWorld(a, camera);
    return clampCamera({ scale, x: b.x - target.x * scale, y: b.y - target.y * scale }, world, view);
}
export function resizeCamera(camera: Camera, oldView: Size, nextView: Size, world: Size): Camera {
    const oldFit = fitCamera(world, oldView), nextFit = fitCamera(world, nextView);
    if (camera.scale <= oldFit.scale * 1.01) return nextFit;
    const center = screenToWorld({ x: oldView.width / 2, y: oldView.height / 2 }, camera), scale = camera.scale * nextFit.scale / oldFit.scale;
    return clampCamera({ scale, x: nextView.width / 2 - center.x * scale, y: nextView.height / 2 - center.y * scale }, world, nextView);
}
export function buildSeatModel(seats: MapSeat[], aspect = 1.6): SeatModel {
    const world = { width: 1000, height: 1000 / (Number.isFinite(aspect) && aspect > 0 ? aspect : 1.6) }, cell = 10;
    const plots: PlotSeat[] = [], grid = new Map<string, PlotSeat[]>(), groups = new Map<string, PlotSeat[]>(), sectorGroups = new Map<string, PlotSeat[]>(), positions = new Map<string, PlotSeat[]>();
    let invalidCount = 0;
    for (const seat of seats) {
        const x = Number(seat.x), y = Number(seat.y);
        if (seat.x === '' || seat.y === '' || !Number.isFinite(x) || !Number.isFinite(y) || x < 0 || x > 1 || y < 0 || y > 1) { invalidCount++; continue; }
        const p: PlotSeat = { seat, x: x * world.width, y: y * world.height, spacing: Infinity, radius: 2, coincident: false };
        plots.push(p);
        for (const [map, key] of [[grid, `${Math.floor(p.x / cell)},${Math.floor(p.y / cell)}`], [groups, JSON.stringify([seat.sector, seat.row])], [sectorGroups, seat.sector], [positions, `${p.x.toFixed(6)},${p.y.toFixed(6)}`]] as const) {
            const items = map.get(key) ?? []; items.push(p); map.set(key, items);
        }
    }
    for (const points of positions.values()) if (points.length > 1) for (const p of points) p.coincident = true;
    // Two sorted axes work for straight or curved rows, without assuming number order.
    for (const points of groups.values()) for (const axis of ['x', 'y'] as const) {
        const sorted = [...points].sort((a, b) => a[axis] - b[axis]);
        for (let i = 0; i < sorted.length; i++) for (let j = i + 1; j <= i + 3 && j < sorted.length; j++) {
            const a = sorted[i], b = sorted[j], d = Math.hypot(a.x - b.x, a.y - b.y);
            if (d > 1e-6) { a.spacing = Math.min(a.spacing, d); b.spacing = Math.min(b.spacing, d); }
        }
    }
    // Also respect neighbouring rows. Cap bucket work on malicious/coincident geometry.
    for (const p of plots) {
        const gx = Math.floor(p.x / cell), gy = Math.floor(p.y / cell);
        for (let x = gx - 1; x <= gx + 1; x++) for (let y = gy - 1; y <= gy + 1; y++) {
            const bucket = grid.get(`${x},${y}`) ?? [];
            for (let i = 0; i < Math.min(80, bucket.length); i++) {
                const q = bucket[i], distance = Math.hypot(q.x - p.x, q.y - p.y);
                if (distance > 1e-6) p.spacing = Math.min(p.spacing, distance);
            }
        }
        if (!Number.isFinite(p.spacing)) p.spacing = 10;
        p.radius = Math.min(4, p.spacing * .30);
    }
    return { world, seats: plots, grid, cell, invalidCount, byId: new Map(plots.map(p => [p.seat.id, p])),
        sectors: [...sectorGroups].map(([name, items]) => ({ name, seats: items, bounds: boundsOf(items)! })).sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true })) };
}
export function querySeats(model: SeatModel, bounds: Bounds): PlotSeat[] {
    const { cell, grid } = model, result: PlotSeat[] = [];
    const x0 = Math.max(0, Math.floor(bounds.minX / cell)), y0 = Math.max(0, Math.floor(bounds.minY / cell));
    const x1 = Math.min(Math.floor(model.world.width / cell), Math.floor(bounds.maxX / cell)), y1 = Math.min(Math.floor(model.world.height / cell), Math.floor(bounds.maxY / cell));
    const inside = (p: PlotSeat) => p.x >= bounds.minX && p.x <= bounds.maxX && p.y >= bounds.minY && p.y <= bounds.maxY;
    // Avoid iterating millions of empty cells for unusually tall/wide source images.
    if ((x1 - x0 + 1) * (y1 - y0 + 1) > Math.max(1, grid.size * 2)) {
        for (const bucket of grid.values()) for (const p of bucket) if (inside(p)) result.push(p);
    } else {
        for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) for (const p of grid.get(`${x},${y}`) ?? [])
            if (inside(p)) result.push(p);
    }
    return result;
}
export function nearestSeat(model: SeatModel, screen: Point, camera: Camera, hitPixels = 20, sector = '', row = ''): PlotSeat | null {
    const at = screenToWorld(screen, camera), r = hitPixels / camera.scale;
    let nearest: PlotSeat | null = null, distance = r;
    for (const p of querySeats(model, { minX: at.x - r, minY: at.y - r, maxX: at.x + r, maxY: at.y + r })) {
        if ((sector && p.seat.sector !== sector) || (row && p.seat.row !== row)) continue;
        const d = Math.hypot(p.x - at.x, p.y - at.y);
        if (d < distance) { distance = d; nearest = p; }
    }
    return nearest;
}
export function markerRadius(seat: PlotSeat, camera: Camera): number { return Math.max(.5, Math.min(13, seat.radius * camera.scale)); }
export function canInspectSeat(seat: PlotSeat, camera: Camera): boolean { return !seat.coincident && seat.spacing * camera.scale >= 16; }
export interface MapPalette { available: string; availableBorder: string; unavailable: string; selected: string; selectedBorder: string; ink: string; label: string }
export const DEFAULT_MAP_PALETTE: MapPalette = { available: '#d5f4e2', availableBorder: '#187248', unavailable: '#c9ced5', selected: '#ffeb00', selectedBorder: '#161b21', ink: '#18222c', label: '#ffffff' };
export interface SectorLabel { sector: string; x: number; y: number; width: number; height: number }
export function drawSeatMap(ctx: CanvasRenderingContext2D, model: SeatModel, camera: Camera, view: Size, options: {
    available: Set<string>; selected: Set<string>; active?: string | null; hover?: string | null; sector?: string; row?: string; palette?: MapPalette;
}): SectorLabel[] {
    const colors = options.palette ?? DEFAULT_MAP_PALETTE;
    ctx.clearRect(0, 0, view.width, view.height);
    const a = screenToWorld({ x: -30, y: -30 }, camera), b = screenToWorld({ x: view.width + 30, y: view.height + 30 }, camera);
    const visible = querySeats(model, { minX: a.x, minY: a.y, maxX: b.x, maxY: b.y });
    const matches = (p: PlotSeat) => (!options.sector || options.sector === p.seat.sector) && (!options.row || options.row === p.seat.row);
    for (const state of ['muted', 'unavailable', 'available', 'selected'] as const) {
        ctx.beginPath(); ctx.globalAlpha = state === 'muted' ? .23 : 1;
        ctx.fillStyle = state === 'selected' ? colors.selected : state === 'available' ? colors.available : colors.unavailable;
        ctx.strokeStyle = state === 'selected' ? colors.selectedBorder : colors.availableBorder; ctx.lineWidth = state === 'selected' ? 1.5 : .9;
        for (const p of visible) {
            const s = options.selected.has(p.seat.id) ? 'selected' : !matches(p) ? 'muted' : options.available.has(p.seat.id) ? 'available' : 'unavailable';
            if (s !== state) continue;
            const at = worldToScreen(p, camera), r = markerRadius(p, camera);
            ctx.moveTo(at.x + r, at.y); ctx.arc(at.x, at.y, r, 0, Math.PI * 2);
        }
        ctx.fill(); if (state === 'selected' || state === 'available') ctx.stroke();
    }
    ctx.globalAlpha = 1; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    for (const p of visible) {
        const r = markerRadius(p, camera), at = worldToScreen(p, camera);
        if (r >= 7 && canInspectSeat(p, camera) && matches(p)) {
            ctx.fillStyle = colors.ink; ctx.font = `600 ${Math.min(12, r * 1.15)}px Arial, sans-serif`;
            ctx.fillText(options.selected.has(p.seat.id) ? '✓' : p.seat.number, at.x, at.y + .5, r * 1.65);
        }
        if (p.seat.id === options.active || p.seat.id === options.hover) {
            ctx.beginPath(); ctx.arc(at.x, at.y, r + 3, 0, Math.PI * 2); ctx.strokeStyle = colors.selectedBorder; ctx.lineWidth = 2; ctx.stroke();
        }
    }
    const labels: SectorLabel[] = [];
    if (camera.scale / fitCamera(model.world, view).scale < 2.1 && !options.row) {
        ctx.font = '600 12px Arial, sans-serif';
        for (const sector of model.sectors) {
            if (options.sector && options.sector !== sector.name) continue;
            const b = sector.bounds, at = worldToScreen({ x: (b.minX + b.maxX) / 2, y: b.minY }, camera);
            const text = sector.name.length > 20 ? sector.name.slice(0, 18) + '…' : sector.name, width = Math.max(38, Math.min(158, ctx.measureText(text).width + 20));
            const label = { sector: sector.name, x: at.x - width / 2, y: at.y - 30, width, height: 24 };
            if (label.x < 2 || label.x + width > view.width - 2 || label.y < 2 || label.y + 24 > view.height) continue;
            if (labels.some(other => label.x < other.x + other.width + 5 && label.x + width + 5 > other.x && label.y < other.y + other.height + 5 && label.y + 29 > other.y)) continue;
            ctx.beginPath(); ctx.roundRect(label.x, label.y, width, 24, 7); ctx.fillStyle = colors.label; ctx.fill(); ctx.lineWidth = 1; ctx.strokeStyle = '#c9ced5'; ctx.stroke();
            ctx.fillStyle = colors.ink; ctx.fillText(text, at.x, label.y + 12); labels.push(label);
        }
    }
    return labels;
}
