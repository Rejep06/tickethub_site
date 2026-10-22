import { NextRequest, NextResponse } from 'next/server';
export function proxy(request: NextRequest) {
    const path = request.nextUrl.pathname;
    const stored = request.cookies.get('th-locale')?.value === 'en' ? 'en' : 'ru';
    if (path === '/en/staff' || path.startsWith('/en/staff/')) {
        const url = request.nextUrl.clone();
        url.pathname = path.replace('/en/staff', '/ru/staff');
        return NextResponse.redirect(url);
    }
    if (!/^\/(ru|en)(\/|$)/.test(path)) {
        const url = request.nextUrl.clone();
        url.pathname = path.startsWith('/staff') ? '/ru' + path : `/${stored}${path === '/' ? '' : path}`;
        return NextResponse.redirect(url);
    }
    const locale = path.split('/')[1];
    const headers = new Headers(request.headers);
    headers.set('x-tickethub-locale', locale);
    return NextResponse.next({ request: { headers } });
}
export const config = { matcher: ['/((?!api|_next|media|ops|health|.*\\..*).*)'] };
