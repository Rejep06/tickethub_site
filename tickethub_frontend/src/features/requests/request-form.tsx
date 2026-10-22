'use client';
import { useEffect, useState } from 'react';
import { HeartHandshake, Check } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { useLang, useT } from '@/i18n/use-t';
import { useApi, useTask } from '@/lib/hooks';
import { authApi, requestApi } from '@/lib/api/endpoints';
import { Login } from '@/features/auth/login';
import { isAuthRequired } from '@/lib/auth-state';
import { useConfig, useSession } from '@/features/auth/session';
import { ContactFields, LegalConsent } from '@/features/checkout/checkout';
import { acceptedDocuments } from '@/lib/consents';
import { parseRubles } from '@/lib/money';
import { localized } from '@/lib/safe';
import type { Event } from '@/lib/api/generated';
import { Alert, Button, Card, Checkbox, ErrorState, Field, Input, PageHeader, Textarea, Modal } from '@/components/ui';
export function RequestForm() {
    const t = useT(), lang = useLang(), router = useRouter(), params = useSearchParams(), session = useSession(), config = useConfig(), task = useTask(), client = useQueryClient();
    const [loginOpen, setLoginOpen] = useState(false);
    useEffect(() => { if (isAuthRequired(task.error)) client.setQueryData(['session'], null); }, [task.error, client]);
    const slug = params.get('event') ?? '';
    const event = useApi<Event>(`events/${encodeURIComponent(slug)}/`, !!slug);
    const [name, setName] = useState(''), [phone, setPhone] = useState(''), [title, setTitle] = useState(''), [city, setCity] = useState(''), [date, setDate] = useState(''), [quantity, setQuantity] = useState(1), [budget, setBudget] = useState(''), [preferences, setPreferences] = useState((params.get('help') === 'fan-id' ? (lang === 'ru' ? 'Нужна помощь с оформлением Fan ID. ' : 'Need help applying for Fan ID. ') : '') + (params.get('category') ?? '')), [together, setTogether] = useState(false), [comment, setComment] = useState(''), [accepted, setAccepted] = useState<Record<string, number>>({});
    useEffect(() => {
        if (session.data) {
            setName(value => value || session.data?.name || '');
            setPhone(value => value || session.data?.phone || '');
        }
    }, [session.data]);
    useEffect(() => {
        if (event.data) {
            setTitle(localized(event.data, 'title', lang));
            setCity(lang === 'ru' ? event.data.venue.city : event.data.venue.city_en);
        }
    }, [event.data, lang]);
    return <div className="container section request-page">
  <div className="eyebrow">{t('requestEyebrow')}</div>
  <PageHeader title={t('requestTitle')} description={t('requestIntro')}/>
  <div className="request-layout"><Card><form className="stack" onSubmit={e => {
        e.preventDefault();
        if (!session.data || isAuthRequired(session.error)) { setLoginOpen(true); return; }
        void task.run(async () => {
            await authApi.update({ name, phone, locale: lang });
            const value = budget.trim() ? parseRubles(budget) : null;
            if (value !== null && value <= 0)
                throw new Error('INVALID_MONEY');
            const result = await requestApi.create({ event_id: event.data?.id ?? null, custom_event_name: event.data ? '' : title, city, desired_date: date || null, quantity, preferences, together_required: together, budget_minor: value, comment, accepted_documents: acceptedDocuments(config?.legal_versions ?? {}, accepted) });
            await client.invalidateQueries({ queryKey: ['api'] });
            router.push(`/${lang}/account/requests/${result.id}?success=1`);
        });
    }}>
      {event.error ? <ErrorState error={event.error}/> : null}
      <div className="form-grid">
        <Field label={t('eventName')}><Input required value={title} onChange={e => setTitle(e.target.value)} readOnly={!!event.data} maxLength={250}/></Field>
        <Field label={t('city')}><Input value={city} onChange={e => setCity(e.target.value)} maxLength={100}/></Field>
        <Field label={t('desiredDate')}><Input type="date" value={date} onChange={e => setDate(e.target.value)}/></Field>
        <Field label={t('quantity')}><Input required type="number" min={1} max={config?.request_limit ?? 100} value={quantity} onChange={e => setQuantity(Number(e.target.value))}/></Field>
        <Field label={t('budget')}><Input inputMode="decimal" placeholder={t('budgetPlaceholder')} value={budget} onChange={e => setBudget(e.target.value)}/></Field>
        <Field label={t('preferences')}><Textarea placeholder={t('preferencesPlaceholder')} value={preferences} onChange={e => setPreferences(e.target.value)} maxLength={500}/></Field>
      </div>
      <Checkbox checked={together} onChange={e => setTogether(e.target.checked)}>{t('together')}</Checkbox>
      <Field label={t('comment')} hint={t('commentHint')}><Textarea placeholder={t('commentPlaceholder')} value={comment} onChange={e => setComment(e.target.value)} maxLength={1000}/></Field>
      {session.data && !isAuthRequired(session.error) ? <><h2>{t('contactsTitle')}</h2><ContactFields name={name} phone={phone} email={session.data.email} setName={setName} setPhone={setPhone}/></> : <p className="request-login-note">{t('requestSignInText')}</p>}
      <LegalConsent accepted={accepted} onChange={setAccepted}/>
      {task.error ? isAuthRequired(task.error) ? <div className="stack-sm"><p>{t('sessionExpiredText')}</p><Button type="button" onClick={() => setLoginOpen(true)}>{t('login')}</Button></div> : <ErrorState error={task.error}/> : null}
      {session.error && !isAuthRequired(session.error) ? <ErrorState error={session.error} retry={() => void session.refetch()} /> : null}
      {!config?.public_forms_enabled && <Alert>{t('formsDisabled')}</Alert>}
      <Button type="submit" busy={task.busy} disabled={!config?.public_forms_enabled || !!slug && !event.data}>{t(session.data ? 'requestSubmit' : 'requestContinue')}</Button>
    </form></Card><aside className="request-aside"><HeartHandshake size={42} strokeWidth={1.5} aria-hidden="true" /><h2>{t('requestAsideTitle')}</h2><p>{t('requestAsideText')}</p><div className="request-points">{[1, 2, 3].map(n => <div key={n}><Check size={18} aria-hidden="true" /><span>{t('benefit' + n)}</span></div>)}</div><small>{t('requestAsideFoot')}</small></aside></div>
    <Modal open={loginOpen} onClose={() => setLoginOpen(false)} title={t('authTitle')}>{loginOpen && <Login inline onAuthenticated={() => { setLoginOpen(false); task.setError(null); }} />}</Modal>
    </div>;
}
