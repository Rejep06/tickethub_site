/** Run with the project's installed React in real StrictMode.
 * jsdom checks the component lifecycle/DOM transform; native mouse/touch/Canvas are browser checks.
 */
import { StrictMode } from 'react';
import { NextIntlClientProvider } from 'next-intl';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SeatViewport } from '@/features/seat-map/seat-viewport';
import ru from '@/messages/ru.json';

vi.mock('@/lib/seat-viewport', async () => ({
    ...await vi.importActual<typeof import('@/lib/seat-viewport')>('@/lib/seat-viewport'),
    drawSeatMap: vi.fn(() => [])
}));
let queued: Map<number, FrameRequestCallback>;
let nextId: number;
const seats = [{ id: 'seat-1', sector: '101', row: '1', number: '7', x: .2, y: .3 }];
const props = {
    seats, image: null, sector: '', row: '', available: new Map([['seat-1', { sale_price_minor: 750000 }]]),
    selected: new Set<string>(), active: null,
    onInspect: vi.fn(), onChoose: vi.fn(), onSector: vi.fn(), onReset: vi.fn(), onAmbiguous: vi.fn()
};
function tree() { return <StrictMode><NextIntlClientProvider locale="ru" messages={ru} timeZone="UTC"><SeatViewport {...props} /></NextIntlClientProvider></StrictMode>; }
function flushFrames() {
    act(() => {
        // Take the current queue: callbacks scheduled by a callback belong to the next frame.
        const callbacks = [...queued.values()]; queued.clear(); callbacks.forEach(callback => callback(16));
    });
}
function transform(): string { return (document.querySelector('.seat-image-plane') as HTMLElement).style.transform; }
beforeEach(() => {
    queued = new Map(); nextId = 0;
    vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback) => { const id = ++nextId; queued.set(id, callback); return id; }));
    vi.stubGlobal('cancelAnimationFrame', vi.fn((id: number) => { queued.delete(id); }));
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(960);
    vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(540);
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ x: 0, y: 0, left: 0, top: 0, right: 960, bottom: 540, width: 960, height: 540, toJSON: () => ({}) });
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ setTransform: vi.fn() } as unknown as CanvasRenderingContext2D);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('camera lifecycle regression', () => {
    it('starts at fit after StrictMode cancels and replays the initial scheduled frame', () => {
        render(tree()); flushFrames();
        expect(cancelAnimationFrame).toHaveBeenCalled();
        expect(screen.getByLabelText(ru.mapScale)).toHaveTextContent('100%');
        expect(transform()).not.toBe('translate(0px, 0px) scale(1)');
    });
    it('plus/minus change the background transform after StrictMode replay', () => {
        render(tree()); flushFrames(); const initial = transform();
        fireEvent.click(screen.getByRole('button', { name: ru.zoomIn })); flushFrames();
        expect(transform()).not.toBe(initial); expect(screen.getByLabelText(ru.mapScale)).toHaveTextContent('150%');
        fireEvent.click(screen.getByRole('button', { name: ru.zoomOut })); flushFrames();
        expect(screen.getByLabelText(ru.mapScale)).toHaveTextContent('100%');
    });
    it('coalesces repeated camera changes into a frame without losing the latest update', () => {
        render(tree()); flushFrames();
        fireEvent.click(screen.getByRole('button', { name: ru.zoomIn }));
        fireEvent.click(screen.getByRole('button', { name: ru.zoomIn })); flushFrames();
        expect(screen.getByLabelText(ru.mapScale)).toHaveTextContent('225%');
    });
    it('wheel zoom is still operational after activating the map', () => {
        render(tree()); flushFrames();
        fireEvent.click(screen.getByRole('button', { name: ru.activateMap })); const initial = transform();
        fireEvent.wheel(screen.getByRole('region', { name: ru.mapKeyboardLabel }), { deltaY: -100, clientX: 400, clientY: 200 }); flushFrames();
        expect(transform()).not.toBe(initial);
    });
    it('reset returns to fit and availability-only rerenders do not reset user zoom', () => {
        const view = render(tree()); flushFrames();
        fireEvent.click(screen.getByRole('button', { name: ru.zoomIn })); flushFrames(); const zoomed = transform();
        view.rerender(<StrictMode><NextIntlClientProvider locale="ru" messages={ru} timeZone="UTC"><SeatViewport {...props} available={new Map(props.available)} seats={seats.map(seat => ({ ...seat }))} /></NextIntlClientProvider></StrictMode>);
        flushFrames(); expect(transform()).toBe(zoomed);
        fireEvent.click(screen.getByRole('button', { name: ru.zoomReset })); flushFrames(); expect(screen.getByLabelText(ru.mapScale)).toHaveTextContent('100%');
    });
    it('cancels a pending frame on unmount and a fresh mount can zoom again', () => {
        const first = render(tree()); flushFrames();
        fireEvent.click(screen.getByRole('button', { name: ru.zoomIn })); first.unmount();
        expect(queued.size).toBe(0);
        render(tree()); flushFrames(); fireEvent.click(screen.getByRole('button', { name: ru.zoomIn })); flushFrames();
        expect(screen.getByLabelText(ru.mapScale)).toHaveTextContent('150%');
    });
});
