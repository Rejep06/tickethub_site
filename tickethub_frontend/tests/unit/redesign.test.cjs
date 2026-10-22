const { test, beforeEach, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { lib, json } = require('./helpers.cjs');
const { apiPath, apiUrl } = lib('api/url');
const { api } = lib('api/client');
const { parseTheme, resolveTheme, THEME_INIT_SCRIPT } = lib('theme');
const { inclusiveDateToExclusive, exclusiveDateToInclusive } = lib('catalog');
const originalFetch = global.fetch;
beforeEach(() => { global.document = { documentElement: { lang: 'ru' } }; });
after(() => { global.fetch = originalFetch; delete global.document; });

const paths = [
    ['me', 'ru', '/api/v1/me/?lang=ru'],
    ['me/', 'en', '/api/v1/me/?lang=en'],
    ['public/config', 'ru', '/api/v1/public/config/?lang=ru'],
    ['public/config/', 'ru', '/api/v1/public/config/?lang=ru'],
    ['auth/csrf', undefined, '/api/v1/auth/csrf/'],
    ['auth/csrf/', undefined, '/api/v1/auth/csrf/'],
    ['staff/orders/42/confirm', 'ru', '/api/v1/staff/orders/42/confirm/?lang=ru'],
    ['me///?lang=en&lang=ru', 'en', '/api/v1/me/?lang=en'],
    ['events?q=Live%20show&page=2', 'en', '/api/v1/events/?q=Live+show&page=2&lang=en'],
    ['events/?lang=en&city=London', 'ru', '/api/v1/events/?lang=ru&city=London']
];
for (const [input, locale, expected] of paths) test(`canonical REST URL: ${input} (${locale ?? 'no locale'})`, () => {
    assert.equal(apiUrl(input, locale), expected);
    assert.ok(new URL(apiUrl(input, locale), 'https://tickethub.test').pathname.endsWith('/'));
});
test('an existing query is preserved, with the slash before—not after—it', () => {
    const result = new URL(apiUrl('events?date_from=2026-10-01T00%3A00%3A00Z&q=a%2Fb', 'ru'), 'https://tickethub.test');
    assert.equal(result.pathname, '/api/v1/events/');
    assert.equal(result.searchParams.get('q'), 'a/b');
    assert.equal(result.searchParams.get('date_from'), '2026-10-01T00:00:00Z');
});
test('the API path builder also works for server-side new URL(base)', () => {
    assert.equal(new URL(apiPath('public/config?lang=en', 'ru'), 'https://django.test/api/v1/').href, 'https://django.test/api/v1/public/config/?lang=ru');
});
test('absolute, traversal, malformed and backslash paths are rejected', () => {
    for (const value of ['', '/me', '//host/me', 'https://host/me', '../me', 'staff/../me', 'me\\', 'me?lang=ru\\', 'me#token', 'me\n', 'staff//orders', 'staff/%2E%2E/me', 'staff/%2fme', 'staff/%5cme', 'staff/%00me', 'staff/%ZZ']) {
        assert.throws(() => apiPath(value), { name: 'Error' }, value);
    }
});
test('invalid mutation addresses trigger neither CSRF nor the mutation request', async () => {
    let calls = 0; global.fetch = async () => { calls++; return json({}); };
    await assert.rejects(() => api('me\\', { method: 'PATCH', body: {} }));
    assert.equal(calls, 0);
});
for (const endpoint of ['me', 'public/config']) test(`browser fetch sends ${endpoint} with canonical slash and explicit Russian locale`, async () => {
    const calls = []; global.fetch = async (url, init) => { calls.push({ url, init }); return json({}); };
    await api(endpoint, { locale: 'ru' });
    assert.equal(calls[0].url, `/api/v1/${endpoint}/?lang=ru`);
    assert.equal(calls[0].init.credentials, 'include');
});
for (const method of ['POST', 'PATCH', 'DELETE']) test(`${method} retains its body and uses an unlocalized canonical CSRF URL`, async () => {
    const calls = []; global.fetch = async (url, init) => { calls.push({ url, init }); return json(url === '/api/v1/auth/csrf/' ? { csrf_token: 'test-csrf' } : {}); };
    await api('staff/orders/abc/confirm', { method, body: { expected_version: 4 }, key: 'same-attempt', locale: 'ru' });
    assert.equal(calls.length, 2);
    assert.equal(calls[0].url, '/api/v1/auth/csrf/');
    assert.equal(calls[1].url, '/api/v1/staff/orders/abc/confirm/?lang=ru');
    assert.equal(calls[1].init.method, method);
    assert.equal(calls[1].init.body, '{"expected_version":4}');
    assert.equal(calls[1].init.headers.get('X-CSRFToken'), 'test-csrf');
    assert.equal(calls[1].init.headers.get('Idempotency-Key'), 'same-attempt');
});
test('Next rewrite source explicitly restores the upstream slash, without changing media', () => {
    // A static contract assertion, NOT a running Next proxy integration test.
    const config = fs.readFileSync(path.resolve('next.config.ts'), 'utf8');
    assert.match(config, /skipTrailingSlashRedirect:\s*true/);
    assert.ok(config.includes('destination: `${backend.origin}/api/:path*/`'));
    assert.ok(config.includes('destination: `${backend.origin}/media/:path*`'));
});
test('theme storage accepts only supported preferences', () => {
    for (const value of [null, undefined, '', 'unknown', '<script>', 'system']) assert.equal(parseTheme(value), 'system');
    assert.equal(parseTheme('dark'), 'dark'); assert.equal(parseTheme('light'), 'light');
});
test('explicit theme wins over OS preference', () => {
    assert.equal(resolveTheme('dark', false), 'dark'); assert.equal(resolveTheme('light', true), 'light');
});
test('system mode follows both OS preferences', () => {
    assert.equal(resolveTheme('system', true), 'dark'); assert.equal(resolveTheme('system', false), 'light');
});
for (const [saved, os, expected] of [['dark', false, 'dark'], ['light', true, 'light'], [null, true, 'dark'], [null, false, 'light'], ['bad', true, 'dark']]) {
    test(`first-paint script: stored=${saved}, OS dark=${os}`, () => {
        const root = { dataset: {} };
        vm.runInNewContext(THEME_INIT_SCRIPT, { document: { documentElement: root }, localStorage: { getItem: () => saved }, window: { matchMedia: () => ({ matches: os }) } });
        assert.equal(root.dataset.theme, expected);
        assert.equal(root.dataset.themePreference, parseTheme(saved));
    });
}
test('blocked localStorage does not prevent first paint in the OS theme', () => {
    const root = { dataset: {} };
    vm.runInNewContext(THEME_INIT_SCRIPT, { document: { documentElement: root }, localStorage: { getItem: () => { throw Error('SecurityError'); } }, window: { matchMedia: () => ({ matches: true }) } });
    assert.equal(root.dataset.theme, 'dark');
});
test('first paint works when matchMedia is unavailable', () => {
    const root = { dataset: {} };
    vm.runInNewContext(THEME_INIT_SCRIPT, { document: { documentElement: root }, localStorage: { getItem: () => null }, window: {} });
    assert.equal(root.dataset.theme, 'light');
});
for (const [inclusive, exclusive] of [['2026-10-31','2026-11-01T00:00:00.000Z'],['2028-02-29','2028-03-01T00:00:00.000Z'],['2026-12-31','2027-01-01T00:00:00.000Z']]) test(`inclusive catalog end date round trip: ${inclusive}`, () => {
    assert.equal(inclusiveDateToExclusive(inclusive), exclusive);
    assert.equal(exclusiveDateToInclusive(exclusive), inclusive);
});
test('invalid form dates never produce Invalid Date in an API filter', () => {
    for (const invalid of ['', '2026-02-30', 'hello', '2026-13-01']) assert.equal(inclusiveDateToExclusive(invalid), '');
    assert.equal(exclusiveDateToInclusive('not a date'), '');
});
test('public copy has no developer MVP or document warnings in either locale', () => {
    for (const locale of ['ru', 'en']) {
        const copy = fs.readFileSync(path.resolve(`src/messages/${locale}.json`), 'utf8');
        assert.doesNotMatch(copy, /MVP|СНИЛС|Госуслуг|noSensitive/);
        const data = JSON.parse(copy);
        for (let i = 1; i <= 6; i++) { assert.ok(data[`faq${i}`]); assert.ok(data[`faq${i}Answer`]); }
    }
});
