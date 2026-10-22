import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
import type { ReactNode } from 'react';
afterEach(() => {
    cleanup();
    sessionStorage.clear();
    localStorage.clear();
    vi.useRealTimers();
});
// jsdom does not implement the native dialog API. Focus/Escape still need E2E.
HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute('open', '');
};
HTMLDialogElement.prototype.close = function () {
    this.removeAttribute('open');
};
vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
    usePathname: () => '/ru/account',
    useSearchParams: () => new URLSearchParams()
}));
vi.mock('next/image', () => ({ default: ({ alt }: {
        alt: string;
    }) => <span role="img" aria-label={alt}/> }));
vi.mock('next/link', () => ({ default: ({ href, children }: {
        href: string;
        children: ReactNode;
    }) => <a href={href}>{children}</a> }));
// Browser preference API: individual appearance tests may replace this default.
Object.defineProperty(window, 'matchMedia', { configurable: true, writable: true, value: (query: string): MediaQueryList => ({
    matches: false, media: query, onchange: null,
    addListener: () => {}, removeListener: () => {},
    addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false
}) });
