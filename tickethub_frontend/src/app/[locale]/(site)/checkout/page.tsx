import { Checkout } from '@/features/checkout/checkout';
import { RequireAuth } from '@/features/auth/session';
export const metadata = { title: 'Оформление / Checkout', robots: { index: false, follow: false } };
export default function Page() {
    return <RequireAuth><Checkout /></RequireAuth>;
}
