/** Only a display preference is stored. No account or session information. */
export const THEME_STORAGE_KEY = 'tickethub.theme';
export type ThemePreference = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';
export function parseTheme(value: string | null | undefined): ThemePreference {
    return value === 'light' || value === 'dark' ? value : 'system';
}
export function resolveTheme(preference: ThemePreference, prefersDark: boolean): ResolvedTheme {
    return preference === 'system' ? (prefersDark ? 'dark' : 'light') : preference;
}
// Trusted, static first-paint script. It contains no interpolated user/backend content.
// Execute in <head> so a stored dark preference does not flash a white page.
export const THEME_INIT_SCRIPT = `(function(){var p='system';try{var s=localStorage.getItem('${THEME_STORAGE_KEY}');if(s==='light'||s==='dark')p=s;}catch(e){}var d=window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.dataset.theme=p==='system'?(d?'dark':'light'):p;document.documentElement.dataset.themePreference=p;})();`;
