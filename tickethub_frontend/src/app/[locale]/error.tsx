'use client';
import { Button, Alert } from '@/components/ui';
import { useT } from '@/i18n/use-t';
export default function PageError({ reset }: {
    error: Error & {
        digest?: string;
    };
    reset: () => void;
}) {
    const t = useT();
    return <div className="container section stack">
  <Alert tone="bad">{t('errorGeneric')}</Alert>
  <Button onClick={reset}>{t('retry')}</Button>
    </div>;
}
