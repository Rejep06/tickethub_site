import { test, expect } from '@playwright/test';
import ru from '../../src/messages/ru.json';
// Requires a running Next frontend. No mock API, account credentials or writes.
test('theme persists across reload and RU/EN navigation', async ({ page }) => {
    await page.goto('/ru/about');
    await page.getByRole('button', { name: ru.darkTheme, exact: true }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await page.getByRole('link', { name: 'Switch to English' }).click();
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await page.getByRole('button', { name: 'Light theme', exact: true }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
});
test('about page fits desktop and mobile in both themes', async ({ page }) => {
    await page.goto('/ru/about');
    for (const theme of ['light', 'dark'] as const) {
        await page.getByRole('button', { name: theme === 'light' ? ru.lightTheme : ru.darkTheme, exact: true }).click();
        for (const width of [320, 390, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 900 });
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
            await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
        }
    }
});
test('mobile menu includes login and closes after navigation', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/ru/about');
    await page.getByRole('button', { name: ru.menu, exact: true }).click();
    await expect(page.locator('#mobile-menu').getByRole('link', { name: ru.login, exact: true })).toBeVisible();
    await page.locator('#mobile-menu').getByRole('link', { name: ru.faq, exact: true }).click();
    await expect(page).toHaveURL(/\/ru\/faq$/);
    await expect(page.locator('#mobile-menu')).toHaveCount(0);
});
test('FAQ can be searched and opened from the keyboard', async ({ page }) => {
    await page.goto('/ru/faq');
    await page.getByRole('textbox', { name: ru.faqSearch }).fill('места');
    const question = page.getByRole('button', { name: ru.faq1, exact: true });
    await question.focus(); await page.keyboard.press('Enter');
    await expect(question).toHaveAttribute('aria-expanded', 'true');
    await expect(page.getByRole('region', { name: ru.faq1 })).toBeVisible();
});
test('quick search opens by shortcut and returns focus after Escape', async ({ page }) => {
    await page.goto('/ru/about');
    const trigger = page.getByRole('button', { name: ru.quickSearch, exact: true });
    await trigger.focus(); await page.keyboard.press('Control+k');
    await expect(page.getByRole('dialog', { name: ru.quickSearch })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(trigger).toBeFocused();
});
test('browser API requests and the real proxy preserve trailing slashes', async ({ page }) => {
    const requests: string[] = [];
    page.on('request', request => { const url = new URL(request.url()); if (url.pathname.startsWith('/api/v1/')) requests.push(request.url()); });
    await page.goto('/ru/about');
    await page.getByRole('button', { name: ru.quickSearch, exact: true }).click();
    const search = page.waitForRequest(request => new URL(request.url()).pathname.startsWith('/api/v1/events'));
    await page.getByRole('textbox', { name: ru.search, exact: true }).fill('tickethub url check');
    const searchRequest = await search;
    expect(new URL(searchRequest.url()).pathname).toBe('/api/v1/events/');
    expect(new URL(searchRequest.url()).searchParams.get('lang')).toBe('ru');
    for (const address of requests) expect(new URL(address).pathname.endsWith('/')).toBe(true);
    // Actual upstream responses; a slash redirect is an error, not a successful check.
    for (const endpoint of ['/api/v1/public/config/?lang=ru', '/api/v1/auth/csrf/']) {
        const response = await page.request.get(endpoint, { maxRedirects: 0 });
        expect(response.status(), endpoint).toBe(200);
    }
});
