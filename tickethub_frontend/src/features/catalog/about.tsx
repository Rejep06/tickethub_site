'use client';
import Link from 'next/link';
import { ArrowUpRight, HeartHandshake, MessagesSquare, Headphones, Sparkles } from 'lucide-react';
import { useT, useLang } from '@/i18n/use-t';
import { Logo } from '@/components/brand';
import { BrandMoment } from '@/components/brand-moment';
import { RequestBanner } from './home';
export function About() {
    const t = useT(), lang = useLang();
    return <div className="container about-page">
        <section className="about-hero section"><div className="eyebrow">{t('aboutEyebrow')}</div><h1 className="pre-line">{t('aboutTitle')}</h1><p>{t('aboutLead')}</p><div className="actions"><Link className="btn btn-primary btn-lg" href={`/${lang}/request`}>{t('consult')}<ArrowUpRight size={20} /></Link><Link className="btn btn-secondary btn-lg" href={`/${lang}/events`}>{t('browse')}</Link></div></section>
        <section className="about-story"><div className="about-art"><BrandMoment /></div><div className="stack"><div className="eyebrow">{t('aboutStoryEyebrow')}</div><h2 className="pre-line">{t('aboutApproachTitle')}</h2><p>{t('aboutStory')}</p><div className="about-facts"><div><strong>01<span>/</span></strong><h3>{t('aboutSince')}</h3><p>{t('aboutSinceText')}</p></div><div><HeartHandshake size={38} strokeWidth={1.5} aria-hidden="true" /><h3>{t('aboutDetail')}</h3><p>{t('aboutDetailText')}</p></div></div></div></section>
        <section className="section about-values"><div className="section-title"><h2 className="pre-line">{t('aboutValuesTitle')}</h2></div><div className="grid-3">{[MessagesSquare, Sparkles, Headphones].map((Icon, index) => <article className="value-card" key={index}><span className="value-icon"><Icon size={29} strokeWidth={1.5} aria-hidden="true" /></span><h3>{t('aboutValue' + (index + 1))}</h3><p>{t('aboutValue' + (index + 1) + 'Text')}</p></article>)}</div></section>
        <section className="team-story"><div className="team-logo-card"><Logo /><span>{t('teamCardNote')}</span><MessagesSquare size={30} strokeWidth={1.4} aria-hidden /></div><div><div className="eyebrow">{t('aboutTeamEyebrow')}</div><h2>{t('aboutTeamTitle')}</h2><p>{t('aboutTeamText')}</p><blockquote>{t('aboutQuote')}</blockquote></div></section>
        <div className="section"><RequestBanner /></div>
    </div>;
}
