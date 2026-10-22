'use client';
import { ArrowUpRight, Sparkles } from 'lucide-react';
import { useT } from '@/i18n/use-t';
import { Logo } from './brand';
/** Brand artwork, not an event listing, customer review or purchasable ticket. */
export function BrandMoment({ compact = false }: { compact?: boolean }) {
    const t = useT();
    return <div className={`brand-moment ${compact ? 'brand-moment-compact' : ''}`} aria-hidden="true">
        <div className="moment-orbit orbit-one" /><div className="moment-orbit orbit-two" /><div className="moment-orbit orbit-three" />
        <div className="moment-spark"><Sparkles size={24} /></div>
        <div className="moment-word">LIVE<span>YOUR MOMENT</span></div>
        <div className="moment-ticket">
            <div className="moment-ticket-top"><Logo /><ArrowUpRight size={24} /></div>
            <p>{t('heroTicketTop')}</p><strong>{t('heroShort')}</strong>
            <div className="moment-ticket-stub"><span>{t('heroTicketBottom')}</span><span className="decorative-bars" /></div>
        </div>
        <div className="moment-caption"><span className="status-dot" />{t('heroLive')}</div>
    </div>;
}
