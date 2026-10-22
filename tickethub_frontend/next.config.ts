import type { NextConfig } from 'next';
import createNextIntlPlugin from 'next-intl/plugin';
const backend = new URL(process.env.BACKEND_ORIGIN || 'http://127.0.0.1:8000');
if (!['http:', 'https:'].includes(backend.protocol))
    throw new Error('BACKEND_ORIGIN must be HTTP(S)');
const config: NextConfig = {
    output: 'standalone',
    poweredByHeader: false,
    reactStrictMode: true,
    devIndicators: false,
    // Keep room for multipart framing around a 100 MiB file in local development.
    // In production Nginx sends /api/ directly to Django (see infra/nginx.conf.template).
    ...(process.env.NODE_ENV === 'development' ? { experimental: { proxyClientMaxBodySize: 110 * 1024 * 1024 } } : {}),
    // Keep the client's slash AND explicitly restore it at the upstream boundary.
    // :path* may be captured without its trailing delimiter. Never rely on Django
    // APPEND_SLASH redirects for POST/PATCH/DELETE (the request body must be preserved).
    skipTrailingSlashRedirect: true,
    async rewrites() {
        return { beforeFiles: [
                { source: '/api/:path*', destination: `${backend.origin}/api/:path*/` },
                { source: '/media/:path*', destination: `${backend.origin}/media/:path*` }
            ], afterFiles: [], fallback: [] };
    },
    async headers() {
        return [{ source: '/:path*', headers: [
                    { key: 'X-Content-Type-Options', value: 'nosniff' },
                    { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
                    { key: 'X-Frame-Options', value: 'DENY' },
                    { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' }
                ] }, { source: '/:locale/:area(account|checkout|staff)/:path*', headers: [
                    { key: 'Cache-Control', value: 'private, no-store, max-age=0' },
                    { key: 'X-Robots-Tag', value: 'noindex, nofollow' }
                ] }];
    }
};
export default createNextIntlPlugin('./src/i18n/request.ts')(config);
