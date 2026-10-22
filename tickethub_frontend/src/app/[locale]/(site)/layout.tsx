import type { ReactNode } from 'react';
import { PublicHeader, PublicFooter } from '@/components/public-layout';
export default function SiteLayout({ children }: {
    children: ReactNode;
}) {
    return <><PublicHeader /><main id="main">{children}</main><PublicFooter /></>;
}
