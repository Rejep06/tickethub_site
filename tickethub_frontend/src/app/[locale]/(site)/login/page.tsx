import { Login } from '@/features/auth/login';
export const metadata = { title: 'Вход / Sign in', robots: { index: false, follow: false } };
export default function Page() {
    return <div className="container section"><Login /></div>;
}
