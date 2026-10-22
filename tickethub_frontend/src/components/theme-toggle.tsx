'use client';
import { useSyncExternalStore } from 'react';
import { Sun, Moon, Monitor } from 'lucide-react';
import { useT } from '@/i18n/use-t';
import { parseTheme, resolveTheme, THEME_STORAGE_KEY, type ThemePreference } from '@/lib/theme';

const changeEvent = 'tickethub:theme';
let temporaryPreference: ThemePreference | null = null;
function readPreference(): ThemePreference {
    if (typeof window === 'undefined') return 'system';
    if (temporaryPreference) return temporaryPreference;
    try { return parseTheme(localStorage.getItem(THEME_STORAGE_KEY)); }
    catch { return 'system'; }
}
function readResolved() {
    if (typeof window === 'undefined') return 'light';
    return resolveTheme(readPreference(), window.matchMedia('(prefers-color-scheme: dark)').matches);
}
function applyTheme() {
    document.documentElement.dataset.theme = readResolved();
    document.documentElement.dataset.themePreference = readPreference();
}
function subscribe(notify: () => void) {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const update = () => { applyTheme(); notify(); };
    const storage = (event: StorageEvent) => {
        if (event.key === THEME_STORAGE_KEY || event.key === null) {
            temporaryPreference = null;
            update();
        }
    };
    applyTheme();
    window.addEventListener(changeEvent, update);
    window.addEventListener('storage', storage);
    media.addEventListener('change', update);
    return () => {
        window.removeEventListener(changeEvent, update);
        window.removeEventListener('storage', storage);
        media.removeEventListener('change', update);
    };
}
function chooseTheme(preference: ThemePreference) {
    // Also works in browsers that disallow localStorage.
    temporaryPreference = preference;
    try {
        localStorage.setItem(THEME_STORAGE_KEY, preference);
        temporaryPreference = null;
    } catch { /* Keep the preference for this tab's lifetime. */ }
    applyTheme();
    window.dispatchEvent(new Event(changeEvent));
}
export function ThemeToggle() {
    const t = useT();
    const theme = useSyncExternalStore(subscribe, readResolved, () => 'light');
    const dark = theme === 'dark';
    return <button type="button" className="icon-button theme-toggle" aria-label={t('toggleTheme')}
        aria-pressed={dark} title={t(dark ? 'switchToLight' : 'switchToDark')}
        onClick={() => chooseTheme(dark ? 'light' : 'dark')}>
        <Sun size={19} className="theme-sun" aria-hidden="true" />
        <Moon size={19} className="theme-moon" aria-hidden="true" />
    </button>;
}
export function ThemePicker() {
    const t = useT();
    const preference = useSyncExternalStore(subscribe, readPreference, () => 'system');
    const choices = [
        { value: 'light', label: 'lightTheme', Icon: Sun },
        { value: 'dark', label: 'darkTheme', Icon: Moon },
        { value: 'system', label: 'systemTheme', Icon: Monitor }
    ] as const;
    return <div className="theme-picker" role="group" aria-label={t('appearance')}>
        {choices.map(({ value, label, Icon }) => <button type="button" key={value}
            aria-label={t(label)} title={t(label)} aria-pressed={preference === value}
            onClick={() => chooseTheme(value)}><Icon size={17} aria-hidden="true" /></button>)}
    </div>;
}
