import { StaffRequestDetail } from '@/features/staff/requests';
export default async function Page({ params }: {
    params: Promise<{
        id: string;
    }>;
}) {
    const { id } = await params;
    return <StaffRequestDetail id={id}/>;
}
