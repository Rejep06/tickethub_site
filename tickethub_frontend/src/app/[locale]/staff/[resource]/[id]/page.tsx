import { notFound } from 'next/navigation';
import { resources } from '@/features/staff/resources';
import { ResourceEditor } from '@/features/staff/resource-page';
export default async function Page({ params }: {
    params: Promise<{
        resource: string;
        id: string;
    }>;
}) {
    const { resource, id } = await params;
    if (!resources[resource])
        notFound();
    return <ResourceEditor name={resource} id={id}/>;
}
