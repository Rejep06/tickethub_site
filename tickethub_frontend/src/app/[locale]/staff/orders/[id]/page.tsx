import { StaffOrderDetail } from '@/features/staff/order-detail';
export default async function Page({ params }: {
    params: Promise<{
        id: string;
    }>;
}) {
    const { id } = await params;
    return <StaffOrderDetail id={id}/>;
}
