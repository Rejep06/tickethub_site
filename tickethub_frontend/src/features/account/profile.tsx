'use client';
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useT, useLang } from '@/i18n/use-t';
import { useApi, useTask } from '@/lib/hooks';
import { api } from '@/lib/api/client';
import { authApi } from '@/lib/api/endpoints';
import { clearPrivateDrafts } from '@/lib/api/attempts';
import { useSession, LogoutButton } from '@/features/auth/session';
import { ContactFields } from '@/features/checkout/checkout';
import type { EmailChangeStarted, PaginatedPrivacy, Privacy, Profile } from '@/lib/api/generated';
import { Alert, Button, Card, ErrorState, Field, Input, PageHeader, Select, StatusBadge, Textarea, Pagination, Skeleton } from '@/components/ui';
export function ProfilePage() {
    const t = useT(), lang = useLang(), session = useSession(), task = useTask(), client = useQueryClient();
    const [name, setName] = useState(''), [phone, setPhone] = useState(''), [locale, setLocale] = useState<'ru' | 'en'>(lang), [saved, setSaved] = useState(false);
    useEffect(() => {
        if (session.data) {
            setName(session.data.name);
            setPhone(session.data.phone);
            setLocale(session.data.locale);
        }
    }, [session.data]);
    return <div className="stack">
  <PageHeader title={t('profile')}><LogoutButton /></PageHeader>
  <Card><form className="stack" onSubmit={e => {
        e.preventDefault();
        setSaved(false);
        void task.run(async () => {
            await authApi.update({ name, phone, locale });
            await client.invalidateQueries({ queryKey: ['session'] });
            setSaved(true);
        });
    }}>
      <ContactFields name={name} phone={phone} email={session.data?.email ?? ''} setName={setName} setPhone={setPhone}/>
      <Field label="RU / EN"><Select value={locale} onChange={e => setLocale(e.target.value as 'ru' | 'en')}>
          <option value="ru">Русский</option>
          <option value="en">English</option>
        </Select></Field>
      {task.error ? <ErrorState error={task.error}/> : null}
      {saved && <Alert tone="good">{t('saved')}</Alert>}
      <Button type="submit" busy={task.busy}>{t('save')}</Button>
    </form></Card>
  <EmailChange />
  <PrivacyRequests />
    </div>;
}
function EmailChange() {
    const t = useT(), task = useTask(), client = useQueryClient();
    const [email, setEmail] = useState(''), [oldCode, setOld] = useState(''), [newCode, setNew] = useState(''), [started, setStarted] = useState(false), [saved, setSaved] = useState(false);
    return <Card>
  <h2>{t('emailChangeTitle')}</h2>
  <form className="stack" onSubmit={e => {
        e.preventDefault();
        void task.run(async () => {
            if (!started) {
                setSaved(false);
                await api<EmailChangeStarted>('me/email-change/start/', { method: 'POST', body: { new_email: email } });
                setStarted(true);
            }
            else {
                const profile = await api<Profile>('me/email-change/confirm/', { method: 'POST', body: { old_code: oldCode, new_code: newCode } });
                setOld('');
                setNew('');
                clearPrivateDrafts();
                client.clear();
                client.setQueryData(['session'], profile);
                setStarted(false);
                setEmail('');
                setSaved(true);
            }
        });
    }}>
    <Field label={t('newEmail')}><Input type="email" required value={email} readOnly={started} onChange={e => setEmail(e.target.value)} autoComplete="email"/></Field>
    {started && <><Field label={t('oldCode')}><Input required inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={oldCode} onChange={e => setOld(e.target.value.replace(/\D/g, ''))}/></Field><Field label={t('newCode')}><Input required inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={newCode} onChange={e => setNew(e.target.value.replace(/\D/g, ''))}/></Field><Button type="button" variant="ghost" onClick={() => setStarted(false)}>{t('changeEmail')}</Button></>}
    {task.error ? <ErrorState error={task.error}/> : null}
    {saved && <Alert tone="good">{t('emailChanged')}</Alert>}
    <Button type="submit" busy={task.busy}>{t(started ? 'confirm' : 'sendCode')}</Button>
  </form>
    </Card>;
}
function PrivacyRequests() {
    const t = useT(), task = useTask();
    const [page, setPage] = useState(1), [kind, setKind] = useState<'ACCESS' | 'CORRECT' | 'DELETE'>('ACCESS'), [comment, setComment] = useState(''), [saved, setSaved] = useState(false);
    const data = useApi<PaginatedPrivacy>(`privacy/requests/?page=${page}`);
    return <Card><h2>{t('privacyRequests')}</h2><p>{t('privacyHint')}</p><form className="stack" onSubmit={e => {
        e.preventDefault();
        void task.run(async () => {
            await api<Privacy>('privacy/requests/', { method: 'POST', body: { kind, comment } });
            setSaved(true);
            await data.refetch();
        });
    }}>
    <Field label={t('caseType')}><Select value={kind} onChange={e => setKind(e.target.value as typeof kind)}>
        <option value="ACCESS">{t('requestData')}</option>
        <option value="DELETE">{t('requestDelete')}</option>
      </Select></Field>
    <Field label={t('comment')}><Textarea maxLength={2000} value={comment} onChange={e => setComment(e.target.value)}/></Field>
    {task.error ? <ErrorState error={task.error}/> : null}
    {saved && <Alert tone="good">{t('privacySent')}</Alert>}
    <Button busy={task.busy} type="submit">{t('confirm')}</Button>
  </form>{data.isPending && <Skeleton />}{data.error && <ErrorState error={data.error} retry={() => void data.refetch()}/>} {data.data?.results.map(item => <div className="ticket-item" key={item.id}>
    <StatusBadge status={item.status}/>
    <p>{item.comment}</p>
    <p>{item.response}</p>
  </div>)}{data.data && <Pagination count={data.data.count} page={page} onChange={setPage}/>}</Card>;
}
