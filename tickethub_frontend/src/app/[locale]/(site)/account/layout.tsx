import type { ReactNode } from 'react';
import { AccountLayout } from '@/features/account/layout';
export const metadata = { robots: { index: false, follow: false } };
export default function Layout({ children }: {
    children: ReactNode;
}) {
    return <AccountLayout>{children}</AccountLayout>;
}
