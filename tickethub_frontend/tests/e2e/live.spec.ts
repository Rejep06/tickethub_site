import ru from '../../src/messages/ru.json';
import { test, expect, type Page } from '@playwright/test';
import { readFile, stat } from 'node:fs/promises';
import { resolve } from 'node:path';
const eventSlug = process.env.E2E_EVENT_SLUG || 'demo-category';
const allowWrites = process.env.E2E_ALLOW_WRITES === '1';
async function readFreshOtp(since: number): Promise<string> {
    const path = process.env.E2E_OTP_FILE;
    if (!path)
        throw new Error('E2E_OTP_FILE must point to a local six-digit code file.');
    const deadline = Date.now() + 120000;
    while (Date.now() < deadline) {
        try {
            const info = await stat(resolve(path));
            const value = (await readFile(resolve(path), 'utf8')).trim();
            if (info.mtimeMs >= since && /^\d{6}$/.test(value))
                return value;
        }
        catch {
        }
        await new Promise(r => setTimeout(r, 500));
    }
    throw new Error('A freshly written OTP was not provided within two minutes. Read the development mail console.');
}
async function customerLogin(page: Page) {
    const since = Date.now();
    await page.getByLabel(ru.email, { exact: true }).fill(process.env.E2E_CUSTOMER_EMAIL!);
    await page.getByRole('button', { name: ru.sendCode, exact: true }).click();
    await page.getByLabel(ru.code, { exact: true }).fill(await readFreshOtp(since));
    await page.getByRole('button', { name: ru.verifyCode, exact: true }).click();
}
test('real catalog and event render at desktop and mobile widths', async ({ page }) => {
    await page.goto('/ru/events');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await page.goto(`/ru/events/${eventSlug}`);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Выбрать билеты', exact: true })).toBeVisible();
    for (const width of [320, 375, 430, 768, 1024, 1440]) {
        await page.setViewportSize({ width, height: 900 });
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    }
});
test('English public event is the same real event, not a fake translation route', async ({ page }) => {
    await page.goto(`/en/events/${eventSlug}`);
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
});
test('OTP → category → server preview → hold → unpaid order → account', async ({ page }) => {
    test.skip(!allowWrites || !process.env.E2E_CUSTOMER_EMAIL || !process.env.E2E_OTP_FILE, 'Requires explicit disposable-database write permission, email, and a fresh OTP file.');
    await page.goto(`/ru/login?next=${encodeURIComponent('/ru/events/' + eventSlug)}`);
    await customerLogin(page);
    await expect(page).toHaveURL(new RegExp(`/ru/events/${eventSlug}`));
    await page.getByRole('button', { name: 'Выбрать билеты', exact: true }).first().click();
    await page.getByRole('button', { name: ru.continueCheckout, exact: true }).click();
    await page.getByLabel('Имя', { exact: true }).fill('E2E Test');
    await page.getByLabel(ru.phone, { exact: true }).fill('+447911123456');
    // Read the legal documents before running. In an isolated test database these are DEMO documents.
    for (const checkbox of await page.locator('input[type="checkbox"][required]').all())
        await checkbox.check();
    await page.getByRole('button', { name: ru.createHold, exact: true }).click();
    await page.getByRole('dialog').getByRole('button', { name: ru.confirmPrice, exact: true }).click();
    await expect(page.getByRole('timer')).toBeVisible();
    await page.reload();
    await expect(page.getByRole('timer')).toBeVisible();
    for (const checkbox of await page.locator('input[type="checkbox"][required]').all())
        await checkbox.check();
    let discountedTotal: number | null = null;
    if (process.env.E2E_PROMO_CODE) {
        await page.getByLabel(ru.promoCode, { exact: true }).fill(process.env.E2E_PROMO_CODE);
        const previewResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1/checkout/promo/' && response.request().method() === 'POST');
        await page.getByRole('button', { name: ru.promoApply, exact: true }).click();
        const response = await previewResponse;
        expect(response.status()).toBe(200);
        const preview = await response.json() as { total_minor: number; discount_minor: number };
        expect(preview.discount_minor).toBeGreaterThan(0);
        discountedTotal = preview.total_minor;
        await expect(page.getByRole('button', { name: 'Оформить заказ', exact: true })).toBeEnabled();
    }
    const createdResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1/orders/' && response.request().method() === 'POST');
    await page.getByRole('button', { name: 'Оформить заказ', exact: true }).click();
    const response = await createdResponse;
    expect([200, 201]).toContain(response.status());
    const order = await response.json() as { total_minor: number; promo_code: string; order_state: string };
    expect(order.order_state).toBe('NEW');
    if (discountedTotal !== null) {
        expect(order.total_minor).toBe(discountedTotal);
        expect(order.promo_code).toBe(process.env.E2E_PROMO_CODE!.trim().toUpperCase());
    }
    await expect(page).toHaveURL(/\/ru\/account\/orders\/[0-9a-f-]+/);
    await expect(page.getByText('Не оплачен', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: /Оплатить картой/ })).toHaveCount(0);
});
test('staff password login and explicit start action on a disposable NEW order', async ({ page }) => {
    test.skip(!allowWrites || !process.env.E2E_STAFF_EMAIL || !process.env.E2E_STAFF_PASSWORD || !process.env.E2E_ORDER_ID, 'Requires staff credentials and the ID of a disposable NEW order.');
    await page.goto('/ru/staff/login');
    await page.getByLabel(ru.email, { exact: true }).fill(process.env.E2E_STAFF_EMAIL!);
    await page.getByLabel('Пароль', { exact: true }).fill(process.env.E2E_STAFF_PASSWORD!);
    await page.getByRole('button', { name: 'Войти в панель', exact: true }).click();
    await expect(page).toHaveURL(/\/ru\/staff\/dashboard/);
    await page.goto(`/ru/staff/orders/${process.env.E2E_ORDER_ID}`);
    await page.getByRole('button', { name: 'Взять в работу', exact: true }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Проверить действие', exact: true }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Подтвердить', exact: true }).click();
    await expect(page.getByText('В работе', { exact: true })).toBeVisible();
});
