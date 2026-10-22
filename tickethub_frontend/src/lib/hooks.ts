'use client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { api } from './api/client';
import { useLang } from '@/i18n/use-t';
export function useApi<T>(path: string, enabled = true, poll?: number) {
    const locale = useLang();
    return useQuery<T>({ queryKey: ['api', locale, path], queryFn: ({ signal }) => api<T>(path, { signal, locale }), enabled, refetchInterval: poll, refetchIntervalInBackground: false });
}
export function useWrite<T, V>(fn: (value: V) => Promise<T>, onSuccess?: (data: T) => void) {
    const client = useQueryClient();
    return useMutation({ mutationFn: fn, onSuccess: async (data) => {
            await client.invalidateQueries({ queryKey: ['api'] });
            onSuccess?.(data);
        } });
}
/** Synchronous lock additionally prevents two clicks before React's next render. */
export function useTask() {
    const lock = useRef(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<unknown>(null);
    async function run(fn: () => Promise<void>) {
        if (lock.current)
            return;
        lock.current = true;
        setBusy(true);
        setError(null);
        try {
            await fn();
        }
        catch (e) {
            setError(e);
        }
        finally {
            lock.current = false;
            setBusy(false);
        }
    }
    return { busy, error, setError, run };
}
