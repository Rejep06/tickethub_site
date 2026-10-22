import { notFound } from 'next/navigation';
import { resources } from '@/features/staff/resources';
import { ResourceList } from '@/features/staff/resource-page';
export default async function Page({ params }: {
    params: Promise<{
        resource: string;
    }>;
}) {
    const { resource } = await params;
    if (!resources[resource])
        notFound();
    return <ResourceList name={resource}/>;
}
