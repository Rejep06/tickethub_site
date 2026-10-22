import { ExternalSourcePage } from '@/features/staff/external-events';
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
    const { id } = await params;
    return <ExternalSourcePage id={id} />;
}
