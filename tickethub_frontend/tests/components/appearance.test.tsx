import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ThemeToggle, ThemePicker } from '@/components/theme-toggle';
import { FAQ } from '@/features/catalog/home';
import { Logo } from '@/components/brand';
import { GlobalSearch } from '@/components/global-search';
import { THEME_STORAGE_KEY } from '@/lib/theme';
import { renderApp } from './support';
import ru from '@/messages/ru.json';

let prefersDark = false;
let listeners: Set<() => void>;
beforeEach(() => {
    prefersDark = false; listeners = new Set();
    delete document.documentElement.dataset.theme;
    delete document.documentElement.dataset.themePreference;
    Object.defineProperty(window, 'matchMedia', { configurable: true, writable: true, value: (query: string) => ({
        get matches() { return prefersDark; }, media: query, onchange: null,
        addEventListener: (_: string, listener: () => void) => listeners.add(listener),
        removeEventListener: (_: string, listener: () => void) => listeners.delete(listener),
        addListener: () => {}, removeListener: () => {}, dispatchEvent: () => true
    }) });
});
describe('appearance and navigation — isolated component checks', () => {
    it('switches both ways, updates accessible state and stores only the preference', async () => {
        const user = userEvent.setup(); renderApp(<ThemeToggle />);
        const toggle = screen.getByRole('button', { name: ru.toggleTheme });
        await user.click(toggle);
        expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
        expect(toggle).toHaveAttribute('aria-pressed', 'true');
        expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
        await user.click(toggle);
        expect(document.documentElement).toHaveAttribute('data-theme', 'light');
        expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light');
    });
    it('restores a saved dark preference on mount', async () => {
        localStorage.setItem(THEME_STORAGE_KEY, 'dark'); renderApp(<ThemeToggle />);
        await waitFor(() => expect(document.documentElement).toHaveAttribute('data-theme', 'dark'));
    });
    it('system mode follows OS changes; an explicit choice does not', async () => {
        const user = userEvent.setup(); renderApp(<ThemePicker />);
        await user.click(screen.getByRole('button', { name: ru.systemTheme }));
        act(() => { prefersDark = true; listeners.forEach(notify => notify()); });
        expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
        await user.click(screen.getByRole('button', { name: ru.lightTheme }));
        act(() => { prefersDark = true; listeners.forEach(notify => notify()); });
        expect(document.documentElement).toHaveAttribute('data-theme', 'light');
    });
    it('responds to a theme choice in a different tab', async () => {
        renderApp(<ThemeToggle />);
        act(() => {
            localStorage.setItem(THEME_STORAGE_KEY, 'dark');
            window.dispatchEvent(new StorageEvent('storage', { key: THEME_STORAGE_KEY, newValue: 'dark' }));
        });
        await waitFor(() => expect(document.documentElement).toHaveAttribute('data-theme', 'dark'));
    });
    it('opens one FAQ answer at a time and keeps the controls labelled', async () => {
        const user = userEvent.setup(); renderApp(<FAQ />);
        const first = screen.getByRole('button', { name: ru.faq1 });
        const second = screen.getByRole('button', { name: ru.faq2 });
        await user.click(first);
        expect(first).toHaveAttribute('aria-expanded', 'true');
        expect(screen.getByRole('region', { name: ru.faq1 })).toBeVisible();
        await user.click(second);
        expect(first).toHaveAttribute('aria-expanded', 'false');
        expect(second).toHaveAttribute('aria-expanded', 'true');
    });
    it('filters FAQ by question or answer and reports no matches', async () => {
        const user = userEvent.setup(); renderApp(<FAQ searchable />);
        const input = screen.getByRole('textbox', { name: ru.faqSearch });
        await user.type(input, 'рассадку');
        expect(screen.getByRole('button', { name: ru.faq2 })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: ru.faq1 })).not.toBeInTheDocument();
        await user.clear(input); await user.type(input, 'zzzzzzzz');
        expect(screen.getByRole('status')).toHaveTextContent(ru.faqNoResults);
    });
    it('retains the supplied logo, with unique filter ids per instance', () => {
        const { container } = renderApp(<><Logo /><Logo /></>);
        expect(screen.getAllByRole('img', { name: 'Tickethub' })).toHaveLength(2);
        const filters = [...container.querySelectorAll('filter')].map(element => element.id);
        expect(new Set(filters).size).toBe(4);
        for (const image of container.querySelectorAll('image')) expect(image).toHaveAttribute('href', '/brand/tickethub-original.png');
    });
    it('opens quick search using Ctrl+K, without starting an empty API search', async () => {
        const fetchSpy = vi.spyOn(globalThis, 'fetch');
        renderApp(<GlobalSearch />);
        fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
        expect(await screen.findByRole('dialog', { name: ru.quickSearch })).toBeVisible();
        expect(fetchSpy).not.toHaveBeenCalled();
        fireEvent(screen.getByRole('dialog'), new Event('cancel', { cancelable: true }));
        await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    });
});
