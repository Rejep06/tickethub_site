import type { ReactNode } from 'react';
import { StaffLayout } from '@/features/staff/layout';
export const metadata = { title: 'Рабочая панель Tickethub', robots: { index: false, follow: false } };
export default function Layout({ children }: {
    children: ReactNode;
}) {
    return <StaffLayout>{children}</StaffLayout>;
}
