'use client';
import { useEffect, useRef } from 'react';
import { Tag, Check } from 'lucide-react';
import { useTask } from '@/lib/hooks';
import { checkoutApi } from '@/lib/api/endpoints';
import type { Hold } from '@/lib/api/generated';
import { normalizedPromoCode, promoMatchesHold, validPromoCode, type PromoSelection } from '@/lib/promotions';
import { useT } from '@/i18n/use-t';
import { Alert, Button, Currency, ErrorState, Field, Input } from '@/components/ui';

export function PromoCodeField({ hold, value, onChange, disabled = false }: {
    hold: Hold;
    value: PromoSelection;
    onChange: (value: PromoSelection) => void;
    disabled?: boolean;
}) {
    const t = useT(), task = useTask(), generation = useRef(0);
    useEffect(() => () => { generation.current += 1; }, [hold.id]);
    const applied = !!value.quote && promoMatchesHold(value.quote, hold, value.code);
    async function apply() {
        if (!validPromoCode(value.code)) throw new Error('PROMO_INVALID');
        const sequence = ++generation.current;
        const code = normalizedPromoCode(value.code);
        const quote = await checkoutApi.promo({ hold_id: hold.id, code });
        if (sequence !== generation.current) return;
        if (!promoMatchesHold(quote, hold, code)) throw new Error('PROMO_CHANGED');
        onChange({ code, quote });
    }
    return <section className="promo-code stack-sm" aria-label={t('promoCode')}>
        <Field label={t('promoCode')} hint={t('promoHint')}>
            <Input value={value.code} maxLength={40} autoComplete="off" autoCapitalize="characters" spellCheck={false}
                disabled={disabled || task.busy} placeholder={t('promoPlaceholder')}
                onChange={e => { generation.current += 1; task.setError(null); onChange({ code: e.target.value, quote: null }); }}
                onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); if (!disabled && !task.busy && value.code.trim()) void task.run(apply); } }} />
        </Field>
        <div className="actions">
            <Button type="button" variant="secondary" busy={task.busy} disabled={disabled || !value.code.trim() || applied} onClick={() => void task.run(apply)}><Tag size={16}/>{t('promoApply')}</Button>
            {value.code && <Button type="button" variant="ghost" disabled={disabled || task.busy} onClick={() => { generation.current += 1; task.setError(null); onChange({ code: '', quote: null }); }}>{t('promoRemove')}</Button>}
        </div>
        {task.error ? <ErrorState error={task.error}/> : null}
        {applied && value.quote && <Alert tone="good"><Check size={15} aria-hidden="true"/> {t('promoApplied', { code: value.quote.code })}: −<Currency value={value.quote.discount_minor}/></Alert>}
        {!!value.code.trim() && !applied && <small>{t('promoApplyRequired')}</small>}
    </section>;
}

export function PriceSummary({ subtotal, discount = 0, total, code = '' }: {
    subtotal: number;
    discount?: number;
    total: number;
    code?: string;
}) {
    const t = useT();
    return <div className="checkout-price-summary stack-sm" aria-live="polite">
        {discount > 0 && <><div className="split"><span>{t('ticketSubtotal')}</span><Currency value={subtotal}/></div>
            <div className="split"><span>{t('promoDiscount')} <strong>{code}</strong></span><span>−<Currency value={discount}/></span></div></>}
        <div className="split"><strong>{t('total')}</strong><strong><Currency value={total}/></strong></div>
    </div>;
}
