'use client';
import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowUpRight, Check } from 'lucide-react';
import { Logo } from '@/components/brand';
import { ThemeToggle } from '@/components/theme-toggle';
import { authApi } from '@/lib/api/endpoints';
import { ApiError } from '@/lib/api/client';
import type { Profile } from '@/lib/api/generated';
import { safeNext } from '@/lib/safe';
import { useTask } from '@/lib/hooks';
import { useT, useLang } from '@/i18n/use-t';
import { Button, Field, Input, ErrorState, PageHeader } from '@/components/ui';
export function Login({ staff = false, inline = false, onAuthenticated }: {
    staff?: boolean; inline?: boolean; onAuthenticated?: () => void;
}) {
    const t = useT(), lang = useLang(), router = useRouter(), params = useSearchParams(), client = useQueryClient();
    const [email, setEmail] = useState(''), [until, setUntil] = useState(0), [seconds, setSeconds] = useState(0);
    const task = useTask();
    const emailForm = useForm<{
        email: string;
        password: string;
    }>({ defaultValues: { email: '', password: '' }, resolver: zodResolver(z.object({ email: z.email(t('invalidEmail')), password: staff ? z.string().min(1, t('required')) : z.string() })) });
    const codeForm = useForm<{
        code: string;
    }>({ defaultValues: { code: '' }, resolver: zodResolver(z.object({ code: z.string().regex(/^\d{6}$/, t('checkField')) })) });
    useEffect(() => {
        if (!until)
            return;
        const tick = () => setSeconds(Math.max(0, Math.ceil((until - Date.now()) / 1000)));
        tick();
        const id = setInterval(tick, 1000);
        return () => clearInterval(id);
    }, [until]);
    const destination = safeNext(params.get('next'), staff ? '/ru/staff/dashboard' : `/${lang}/account`);
    async function afterLogin(profile?: Profile) {
        if (inline && profile) {
            await client.cancelQueries();
            client.removeQueries({ queryKey: ['api'] });
            client.setQueryData(['session'], profile);
            onAuthenticated?.();
            return;
        }
        client.clear();
        router.replace(destination);
        router.refresh();
    }
    async function send(address: string) {
        try {
            const response = await authApi.requestCode({ email: address, locale: lang });
            setEmail(address);
            setUntil(Date.now() + (response.resend_after ?? 60) * 1000);
        }
        catch (e) {
            if (e instanceof ApiError && e.retryAfter)
                setUntil(Date.now() + e.retryAfter * 1000);
            throw e;
        }
    }
    return <div className={inline ? 'auth-inline' : 'container section'}><div className={inline ? '' : staff ? 'narrow' : 'auth-layout'}>
    {!staff && !inline && <aside className="auth-illustration">
      <div className="auth-brand"><Logo /><ArrowUpRight size={28} /></div><div className="auth-orbit" aria-hidden="true" />
      <div className="stack">
        <h2>{t('accountWelcome')}</h2>
        <p>{t('accountText')}</p><div className="auth-benefits">{[1, 2, 3].map(n => <div key={n}><Check size={17} />{t('authBenefit' + n)}</div>)}</div>
      </div>
    </aside>}
    <div className="auth-form stack">
      {inline ? <p>{t('authText')}</p> : <PageHeader title={staff ? 'Вход сотрудника' : t('authTitle')} description={staff ? 'Рабочая панель Tickethub. Вход по паролю.' : t('authText')}/>}
      {task.error && <ErrorState error={task.error}/>}
      <>{!email || staff ? <form className="stack" onSubmit={emailForm.handleSubmit(values => task.run(async () => {
        if (staff) {
            await authApi.staffLogin({ email: values.email, password: values.password });
            emailForm.resetField('password');
            await afterLogin();
        }
        else
            await send(values.email);
    }))}>
        <Field label={t('email')} error={emailForm.formState.errors.email?.message}><Input {...emailForm.register('email')} type="email" autoComplete="email" aria-invalid={!!emailForm.formState.errors.email} required/></Field>
        {staff && <Field label="Пароль" error={emailForm.formState.errors.password?.message}><Input {...emailForm.register('password')} type="password" autoComplete="current-password" required/></Field>}
        <Button type="submit" busy={task.busy} disabled={!staff && seconds > 0}>{staff ? 'Войти в панель' : t('sendCode')}</Button>
      </form> : <form className="stack" onSubmit={codeForm.handleSubmit(values => task.run(async () => {
        const profile = await authApi.verifyCode({ email, code: values.code, locale: lang });
        codeForm.reset();
        await afterLogin(profile);
    }))}>
        <p>{t('codeSent', { email })}</p>
        <Field label={t('code')} error={codeForm.formState.errors.code?.message}><Input {...codeForm.register('code')} className="code-input" inputMode="numeric" autoComplete="one-time-code" maxLength={6} pattern="[0-9]{6}" autoFocus required/></Field>
        <Button type="submit" busy={task.busy}>{t('verifyCode')}</Button>
        <Button variant="secondary" type="button" disabled={seconds > 0} busy={task.busy} onClick={() => void task.run(() => send(email))}>{seconds > 0 ? t('resendIn', { seconds }) : t('resend')}</Button>
        <Button variant="ghost" type="button" disabled={task.busy} onClick={() => {
        setEmail('');
        codeForm.reset();
        task.setError(null);
    }}>{t('changeEmail')}</Button>
      </form>}</>
      {staff && <div className="staff-login-note"><span className="muted">Рабочее пространство команды Tickethub</span><ThemeToggle /></div>}
    </div>
  </div></div>;
}
