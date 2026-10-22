'use client';
import { createContext, useContext, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { authApi } from '@/lib/api/endpoints';
import { api } from '@/lib/api/client';
import { isAuthRequired } from '@/lib/auth-state';
import { clearPrivateDrafts } from '@/lib/api/attempts';
import { useApi, useTask } from '@/lib/hooks';
import type { PublicConfig, Profile, PaginatedStaffOrder, Settings } from '@/lib/api/generated';
import { ErrorState, Skeleton, Button, Alert, Card } from '@/components/ui';
import { useT, useLang } from '@/i18n/use-t';
const ConfigContext = createContext<PublicConfig | null>(null);
export function PublicConfigProvider({ initial, children }: {
    initial: PublicConfig | null;
    children: ReactNode;
}) {
    const locale = useLang();
    const config = useQuery({ queryKey: ['api', locale, 'public/config/'], queryFn: () => api<PublicConfig>('public/config/', { locale }), initialData: initial ?? undefined, staleTime: 30000 });
    return <ConfigContext.Provider value={config.data ?? null}>{children}</ConfigContext.Provider>;
}
export function useConfig() {
    return useContext(ConfigContext);
}
export function useSession() {
    const locale = useLang();
    return useQuery<Profile | null>({ queryKey: ['session'], queryFn: async () => {
        try { return await authApi.me(locale); } catch (error) { if (isAuthRequired(error)) return null; throw error; }
    }, retry: false, staleTime: 30000 });
}
export function useStaffAccess() {
    const staff = useApi<PaginatedStaffOrder>('staff/orders/?page_size=1');
    const admin = useApi<Settings>('staff/settings/', staff.isSuccess);
    return { staff, admin, isAdmin: admin.isSuccess };
}
export function RequireAuth({ children }: {
    children: ReactNode;
}) {
    const session = useSession(), path = usePathname(), params = useSearchParams(), t = useT(), lang = useLang();
    if (session.isPending)
        return <Skeleton />;
    if (session.error && !isAuthRequired(session.error))
        return <div className="container section"><ErrorState error={session.error} retry={() => void session.refetch()}/></div>;
    if (!session.data || isAuthRequired(session.error))
        return <div className="container section"><Card className="auth-invitation narrow stack">
            <span className="eyebrow">TICKETHUB</span><h1>{t('signInContinueTitle')}</h1><p>{t('signInContinueText')}</p>
            <Link className="btn btn-primary" href={`/${lang}/login?next=${encodeURIComponent(path + (params.size ? '?' + params.toString() : ''))}`}>{t('login')}</Link>
            <Link className="text-link" href={`/${lang}/events`}>{t('browse')}</Link>
        </Card></div>;
    return <>{children}</>;
}
export function RequireStaff({ children }: {
    children: ReactNode;
}) {
    const { staff } = useStaffAccess(), path = usePathname();
    if (staff.isPending)
        return <Skeleton />;
    if (staff.error)
        return <div className="narrow stack">
  <Alert tone="bad">Недостаточно прав. Для панели нужен отдельный вход сотрудника по паролю.</Alert>
  <Link className="btn btn-primary" href={`/ru/staff/login?next=${encodeURIComponent(path)}`}>Вход сотрудника</Link>
  <ErrorState error={staff.error} retry={() => void staff.refetch()}/>
        </div>;
    return <>{children}</>;
}
export function LogoutButton() {
    const t = useT(), lang = useLang(), router = useRouter(), client = useQueryClient(), task = useTask();
    return <div>
  <Button variant="ghost" busy={task.busy} onClick={() => void task.run(async () => {
        await authApi.logout();
        clearPrivateDrafts();
        client.clear();
        router.replace(`/${lang}/login`);
        router.refresh();
    })}>{t('logout')}</Button>
  {task.error ? <ErrorState error={task.error}/> : null}
    </div>;
}
