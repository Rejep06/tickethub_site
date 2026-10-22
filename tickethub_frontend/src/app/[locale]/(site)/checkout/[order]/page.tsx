import { redirect } from 'next/navigation';
export default async function Page({ params }: {
    params: Promise<{
        locale: string;
        order: string;
    }>;
}) {
    const { locale, order } = await params;
    redirect(`/${locale}/account/orders/${order}`);
}
