import { SeatEditor } from '@/features/staff/seat-editor';
export default async function Page({ params }: {
    params: Promise<{
        id: string;
    }>;
}) {
    const { id } = await params;
    return <SeatEditor id={id}/>;
}
