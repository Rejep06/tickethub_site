'use client';
import { useId } from 'react';
/** Frames the uploaded raster logo without redrawing its wordmark or changing proportions.
 * The SVG filter removes the source white canvas, and only in dark mode makes its
 * black ink white. The original yellow is preserved; photos are never inverted.
 */
export function Logo({ className = '' }: { className?: string }) {
    const id = useId().replace(/:/g, '');
    return <span className={`brand-logo ${className}`}>
        <svg viewBox="86 278 470 84" role="img" aria-label="Tickethub" focusable="false">
            <defs>
                <filter id={`${id}-light`} colorInterpolationFilters="sRGB">
                    <feColorMatrix type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 -1 0 1" />
                </filter>
                <filter id={`${id}-dark`} colorInterpolationFilters="sRGB">
                    <feColorMatrix type="matrix" values="0 0 0 0 1  -1 1 0 0 1  -1 0 0 0 1  0 0 -1 0 1" />
                </filter>
            </defs>
            <image className="logo-light" href="/brand/tickethub-original.png" width="640" height="640" filter={`url(#${id}-light)`} />
            <image className="logo-dark" href="/brand/tickethub-original.png" width="640" height="640" filter={`url(#${id}-dark)`} />
        </svg>
    </span>;
}
