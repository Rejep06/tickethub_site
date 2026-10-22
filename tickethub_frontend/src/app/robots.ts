import type { MetadataRoute } from 'next';
export default function robots(): MetadataRoute.Robots {
    const base = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';
    return { rules: { userAgent: '*', allow: '/', disallow: ['/api/', '/ops/', '/staff/', '/ru/staff/', '/en/staff/', '/ru/account/', '/en/account/', '/ru/checkout', '/en/checkout', '/ru/login', '/en/login'] }, sitemap: base + '/sitemap.xml' };
}
