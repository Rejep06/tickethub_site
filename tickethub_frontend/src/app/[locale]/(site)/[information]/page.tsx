import Link from 'next/link';
import { notFound } from 'next/navigation';
import type { Metadata } from 'next';
import { publicApi } from '@/lib/api/server';
import type { PaginatedCategory } from '@/lib/api/generated';
import { localized } from '@/lib/safe';
import { Info } from '@/features/catalog/info';
import { PageHeader, Card, EmptyState } from '@/components/ui';
type Props = {
    params: Promise<{
        locale: 'ru' | 'en';
        information: string;
    }>;
};
const headings: Record<string, [
    string,
    string
]> = { sports: ['Спорт', 'Sports'], concerts: ['Концерты', 'Concerts'], other: ['Другие события', 'Other events'], contacts: ['Контакты', 'Contacts'], faq: ['Вопросы и ответы', 'FAQ'], about: ['О сервисе', 'About'], 'how-it-works': ['Как это работает', 'How it works'] };
export async function generateMetadata({ params }: Props): Promise<Metadata> {
    const { locale, information } = await params;
    return { title: headings[information]?.[locale === 'ru' ? 0 : 1] ?? 'Tickethub', alternates: { canonical: `/${locale}/${information}` } };
}
export default async function InformationPage({ params }: Props) {
    const { information, locale } = await params;
    if (!headings[information])
        notFound();
    if (['sports', 'concerts', 'other'].includes(information)) {
        const data = await publicApi<PaginatedCategory>('categories/?page_size=100');
        const kind = ({ sports: 'SPORT', concerts: 'CONCERT', other: 'OTHER' })[information];
        const categories = data.results.filter(c => c.kind === kind);
        return <div className="container section stack">
  <PageHeader title={headings[information][locale === 'ru' ? 0 : 1]}/>
  <div className="grid-3">{categories.map(c => <Card key={c.id}>
      <h2>{localized(c, 'name', locale)}</h2>
      <Link href={`/${locale}/events?category=${c.id}`} className="text-link">{locale === 'ru' ? 'Смотреть мероприятия' : 'Browse events'} →</Link>
    </Card>)}</div>
  {!categories.length && <EmptyState />}
  <Link href={`/${locale}/events`} className="btn btn-secondary">{locale === 'ru' ? 'Весь каталог' : 'All events'}</Link>
        </div>;
    }
    return <Info type={information}/>;
}
