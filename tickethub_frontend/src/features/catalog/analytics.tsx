'use client';
import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api/client';
import type { ClientEventInput } from '@/lib/api/generated';
import { useConfig } from '@/features/auth/session';
import { Checkbox } from '@/components/ui';
import { useT } from '@/i18n/use-t';
export function useEventAnalytics(eventId: string) {
    const config = useConfig();
    return useCallback((eventType: ClientEventInput['event_type']) => {
        if (!config?.client_analytics_enabled || sessionStorage.getItem('th.analytics') !== 'yes')
            return;
        const marker = `th.tracked.${eventId}.${eventType}`;
        if (sessionStorage.getItem(marker))
            return;
        const clientEventId = crypto.randomUUID();
        sessionStorage.setItem(marker, clientEventId);
        void api('analytics/events/', { method: 'POST', body: { event_id: eventId, client_event_id: clientEventId, event_type: eventType, analytics_consent: true } satisfies ClientEventInput }).catch(() => {
            sessionStorage.removeItem(marker);
        });
    }, [config?.client_analytics_enabled, eventId]);
}
export function AnalyticsConsent() {
    const t = useT(), config = useConfig();
    const [value, setValue] = useState(false);
    useEffect(() => {
        setValue(sessionStorage.getItem('th.analytics') === 'yes');
    }, []);
    if (!config?.client_analytics_enabled)
        return null;
    return <div className="stack-sm">
  <Checkbox checked={value} onChange={e => {
        setValue(e.target.checked);
        sessionStorage.setItem('th.analytics', e.target.checked ? 'yes' : 'no');
    }}>{t('analyticsConsent')}</Checkbox>
  <small>{t('analyticsHint')}</small>
    </div>;
}
