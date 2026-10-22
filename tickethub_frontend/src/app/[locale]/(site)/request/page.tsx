import { RequestForm } from '@/features/requests/request-form';
export const metadata = { title: 'Подбор билетов / Ticket request', robots: { index: false, follow: false } };
export default function Page() {
    return <RequestForm />;
}
