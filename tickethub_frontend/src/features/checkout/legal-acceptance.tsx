'use client';
import Link from 'next/link';
import { useConfig } from '@/features/auth/session';
import { useLang, useT } from '@/i18n/use-t';
import { Checkbox } from '@/components/ui';
export function documentsAccepted(versions: Record<string, number>, accepted: Record<string, number>): boolean {
    return Object.entries(versions).every(([key, version]) => accepted[key] === version);
}
export function LegalAcceptance({ accepted, onChange }: {
    accepted: Record<string, number>;
    onChange: (value: Record<string, number>) => void;
}) {
    const config = useConfig(), t = useT(), lang = useLang();
    return <div className="stack-sm">{Object.entries(config?.legal_versions ?? {}).map(([slug, version]) => <div key={`${slug}-${version}`}>
    <Checkbox checked={accepted[slug] === version} onChange={e => {
        const copy = { ...accepted };
        if (e.target.checked)
            copy[slug] = version;
        else
            delete copy[slug];
        onChange(copy);
    }}>{t('acceptDocument', { document: ['offer', 'privacy', 'refund-policy'].includes(slug) ? t(slug) : slug, version })}</Checkbox>
    <Link className="text-link" href={`/${lang}/legal/${slug}`} target="_blank" rel="noopener noreferrer">{['offer', 'privacy', 'refund-policy'].includes(slug) ? t(slug) : slug} ↗</Link>
  </div>)}</div>;
}
