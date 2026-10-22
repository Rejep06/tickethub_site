export interface Point {
    x: number;
    y: number;
}
export function clampCoordinate(value: number): number {
    return Math.max(0, Math.min(1, value));
}
export function relativePoint(clientX: number, clientY: number, rect: {
    left: number;
    top: number;
    width: number;
    height: number;
}): Point {
    if (rect.width <= 0 || rect.height <= 0)
        throw new Error('INVALID_GEOMETRY');
    return { x: clampCoordinate((clientX - rect.left) / rect.width), y: clampCoordinate((clientY - rect.top) / rect.height) };
}
export function rowPoints(start: Point, end: Point, numbers: string[]): (Point & {
    number: string;
})[] {
    if (numbers.length < 1 || numbers.length > 500 || new Set(numbers).size !== numbers.length || numbers.some(n => !n.trim()))
        throw new Error('INVALID_ROW');
    for (const p of [start, end])
        if (!Number.isFinite(p.x) || !Number.isFinite(p.y) || p.x < 0 || p.x > 1 || p.y < 0 || p.y > 1)
            throw new Error('INVALID_GEOMETRY');
    return numbers.map((number, i) => {
        const k = numbers.length === 1 ? 0 : i / (numbers.length - 1);
        return { number, x: start.x + (end.x - start.x) * k, y: start.y + (end.y - start.y) * k };
    });
}
