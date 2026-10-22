'use client';
import { useEffect, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Menu, X, ArrowUpRight, Download, LayoutDashboard, ShoppingBag, Inbox, CalendarDays, MapPin, Grid2X2, Tags, Ticket, Truck, Users, Undo2, ChartNoAxesCombined, Layers, UserRound, Bell, Settings, FileText, Shield, type LucideIcon } from 'lucide-react';
import { Logo } from '@/components/brand';
import { ThemeToggle } from '@/components/theme-toggle';
import { RequireStaff, useStaffAccess, LogoutButton } from '@/features/auth/session';
import { Button } from '@/components/ui';
type StaffLink = { route: string; label: string; Icon: LucideIcon };
const links: StaffLink[] = [
    { route: 'dashboard', label: 'Обзор', Icon: LayoutDashboard },
    { route: 'orders', label: 'Заказы', Icon: ShoppingBag },
    { route: 'requests', label: 'Заявки', Icon: Inbox },
    { route: 'events', label: 'Мероприятия', Icon: CalendarDays },
    { route: 'venues', label: 'Площадки', Icon: MapPin },
    { route: 'seating-plans', label: 'Схемы мест', Icon: Grid2X2 },
    { route: 'promo-codes', label: 'Промокоды', Icon: Tags },
    { route: 'offers', label: 'Предложения', Icon: Tags },
    { route: 'tickets', label: 'Билеты и остатки', Icon: Ticket },
    { route: 'suppliers', label: 'Поставщики', Icon: Truck },
    { route: 'customers', label: 'Клиенты', Icon: Users },
    { route: 'refunds', label: 'Возвраты', Icon: Undo2 },
    { route: 'analytics', label: 'Аналитика', Icon: ChartNoAxesCombined },
    { route: 'categories', label: 'Категории', Icon: Layers },
    { route: 'participants', label: 'Участники', Icon: UserRound },
    { route: 'notifications', label: 'Уведомления', Icon: Bell }
];
const adminLinks: StaffLink[] = [
    { route: 'external-events', label: 'Импорт мероприятий', Icon: Download },
    { route: 'team', label: 'Команда', Icon: Users },
    { route: 'content', label: 'Документы', Icon: FileText },
    { route: 'privacy', label: 'Запросы по данным', Icon: Shield },
    { route: 'settings', label: 'Настройки', Icon: Settings }
];
export function StaffLayout({ children }: { children: ReactNode }) {
    const path = usePathname();
    if (path.endsWith('/login')) return <div className="container section"><Link href="/ru/" className="text-link">← На сайт</Link>{children}</div>;
    return <RequireStaff><StaffShell>{children}</StaffShell></RequireStaff>;
}
function StaffShell({ children }: { children: ReactNode }) {
    const path = usePathname(), { isAdmin } = useStaffAccess();
    const [open, setOpen] = useState(false);
    useEffect(() => {
        if (!open) return;
        const close = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false); };
        window.addEventListener('keydown', close);
        return () => window.removeEventListener('keydown', close);
    }, [open]);
    return <div className="staff-shell">
        <a href="#main" className="skip-link">К содержимому</a>
        {open && <button type="button" className="staff-menu-backdrop" aria-label="Закрыть меню" onClick={() => setOpen(false)} />}
        <aside id="staff-menu" className={`staff-sidebar ${open ? 'is-open' : ''}`}>
            <div className="split"><Link href="/ru/staff/dashboard" aria-label="Tickethub — рабочая панель"><Logo /></Link><Button variant="ghost" className="mobile-only" aria-label="Закрыть меню" onClick={() => setOpen(false)}><X /></Button></div>
            <span className="staff-nav-label">РАБОЧАЯ ПАНЕЛЬ</span>
            <nav className="staff-nav" aria-label="Панель сотрудников">{[...links, ...(isAdmin ? adminLinks : [])].map(({ route, label, Icon }) => {
                const active = path === '/ru/staff/' + route || path.startsWith('/ru/staff/' + route + '/');
                return <Link key={route} className={active ? 'active' : ''} aria-current={active ? 'page' : undefined} href={'/ru/staff/' + route} onClick={() => setOpen(false)}><Icon size={17} aria-hidden="true" />{label}</Link>;
            })}</nav>
            <Link href="/ru/" className="text-link">Открыть сайт <ArrowUpRight size={16} /></Link>
        </aside>
        <div className="staff-main"><header className="staff-topbar">
            <Button variant="ghost" className="mobile-only" aria-label="Открыть меню" aria-controls="staff-menu" aria-expanded={open} onClick={() => setOpen(true)}><Menu /></Button>
            <span>Tickethub <span className="muted">/ {isAdmin ? 'Администратор' : 'Менеджер'}</span></span>
            <div className="actions"><ThemeToggle /><LogoutButton /></div>
        </header><main id="main" className="staff-content">{children}</main></div>
    </div>;
}
