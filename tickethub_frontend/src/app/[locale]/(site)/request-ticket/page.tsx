import { redirect } from 'next/navigation';
export default async function Page({ params, searchParams }: {
    params: Promise<{
        locale: string;
    }>;
    searchParams: Promise<Record<string, string | undefined>>;
}) {
    const { locale } = await params;
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(await searchParams))
        if (v)
            q.set(k, v);
    redirect(`/${locale}/request?${q}`);
}
