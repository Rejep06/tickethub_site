'use client';
import { useMemo, useState } from 'react';
import { Check, List, Map as MapIcon } from 'lucide-react';
import type { Seat, Availability, SeatMap } from '@/lib/api/generated';
import { useLang, useT } from '@/i18n/use-t';
import { formatMoney } from '@/lib/money';
import { mediaPath } from '@/lib/safe';
import { Field, Select, Tabs, EmptyState, Input, Pagination } from '@/components/ui';
import { SeatViewport } from './seat-viewport';
const NO_SEATS: Seat[] = [];
const PAGE_SIZE = 80;
export function SeatPicker({ map, availability, selected, onChoose }: {
    map: SeatMap; availability: Availability; selected: string[]; onChoose: (id: string) => void;
}) {
    const t = useT(), lang = useLang();
    const [tab, setTab] = useState('map'), [sector, setSector] = useState(''), [row, setRow] = useState(''), [active, setActive] = useState<string | null>(null);
    const [minPrice, setMinPrice] = useState(''), [maxPrice, setMaxPrice] = useState(''), [page, setPage] = useState(1), [ambiguous, setAmbiguous] = useState(false);
    const available = useMemo(() => new Map((availability.available_seats ?? []).flatMap(s => s.seat_id && typeof s.sale_price_minor === 'number' ? [[s.seat_id, { sale_price_minor: s.sale_price_minor }] as const] : [])), [availability.available_seats]);
    const seats = map.seats ?? NO_SEATS;
    const sectors = useMemo(() => [...new Set(seats.map(s => s.sector))].sort((a, b) => a.localeCompare(b, undefined, { numeric: true })), [seats]);
    const rows = useMemo(() => [...new Set(seats.filter(s => !sector || s.sector === sector).map(s => s.row))].sort((a, b) => a.localeCompare(b, undefined, { numeric: true })), [seats, sector]);
    const selectedSet = useMemo(() => new Set(selected), [selected]);
    const hasMap = !!map.plan && seats.length > 0;
    const isList = !hasMap || tab === 'list';
    const listed = useMemo(() => {
        const minimum = minPrice.trim() && Number.isFinite(Number(minPrice)) ? Math.max(0, Number(minPrice)) * 100 : null;
        const maximum = maxPrice.trim() && Number.isFinite(Number(maxPrice)) ? Math.max(0, Number(maxPrice)) * 100 : null;
        return seats.filter(s => {
            if ((sector && s.sector !== sector) || (row && s.row !== row)) return false;
            if (selectedSet.has(s.id)) return true; // Never hide the ability to remove an old selection.
            const offer = available.get(s.id);
            return offer && (minimum === null || offer.sale_price_minor >= minimum) && (maximum === null || offer.sale_price_minor <= maximum);
        }).sort((a, b) => a.sector.localeCompare(b.sector, undefined, { numeric: true }) || a.row.localeCompare(b.row, undefined, { numeric: true }) || a.number.localeCompare(b.number, undefined, { numeric: true }));
    }, [seats, sector, row, available, selectedSet, minPrice, maxPrice]);
    const effectivePage = Math.max(1, Math.min(page, Math.ceil(listed.length / PAGE_SIZE)));
    function choose(id: string) { if (available.has(id) || selectedSet.has(id)) onChoose(id); }
    function changeSector(value: string) { setSector(value); setRow(''); setPage(1); setActive(null); }
    return <div className="stack-sm seat-picker">
        <div className="split"><Tabs value={isList ? 'list' : 'map'} onChange={value => { setTab(value); setActive(null); }} options={[...(hasMap ? [{ value: 'map', label: t('seatMap') }] : []), { value: 'list', label: t('seatList') }]} /><span className="small muted seat-pick-count" aria-live="polite">{t('selectedCount', { count: selected.length })}</span></div>
        <div className="seat-filter-row">
            <Field label={t('sector')}><Select value={sector} onChange={e => changeSector(e.target.value)}><option value="">{t('allSectors')}</option>{sectors.map(s => <option key={s} value={s}>{s}</option>)}</Select></Field>
            <Field label={t('row')}><Select value={row} onChange={e => { setRow(e.target.value); setPage(1); setActive(null); }}><option value="">{t('allRows')}</option>{rows.map(r => <option key={r} value={r}>{r}</option>)}</Select></Field>
            {isList && <><Field label={t('seatPriceFrom')}><Input type="number" inputMode="decimal" min={0} value={minPrice} onChange={e => { setMinPrice(e.target.value); setPage(1); }} /></Field><Field label={t('seatPriceTo')}><Input type="number" inputMode="decimal" min={0} value={maxPrice} onChange={e => { setMaxPrice(e.target.value); setPage(1); }} /></Field></>}
        </div>
        {!isList ? <SeatViewport seats={seats} image={mediaPath(map.plan?.image)} sector={sector} row={row} available={available} selected={selectedSet} active={active} onInspect={setActive} onChoose={choose} onSector={changeSector} onReset={() => { changeSector(''); setActive(null); }} onAmbiguous={() => { setTab('list'); setAmbiguous(true); }} /> : <>
            {ambiguous && <p className="muted small">{t('mapCoincidentSeats')}</p>}
            <div className="seat-list">
                {listed.slice((effectivePage - 1) * PAGE_SIZE, effectivePage * PAGE_SIZE).map(seat => <button className="seat-list-item" type="button" key={seat.id} aria-pressed={selectedSet.has(seat.id)} onClick={() => choose(seat.id)}>
                    <span><strong>{t('sector')} {seat.sector} · {t('row')} {seat.row} · {t('seat')} {seat.number}</strong><small>{t(selectedSet.has(seat.id) ? 'selected' : 'available')}</small></span>
                    <strong>{available.has(seat.id) ? formatMoney(available.get(seat.id)?.sale_price_minor, lang) : t('unavailableSeat')} {selectedSet.has(seat.id) && <Check size={18} aria-hidden />}</strong>
                </button>)}
                {!listed.length && <EmptyState title={t('noSeatsForFilters')} />}
            </div><Pagination count={listed.length} page={effectivePage} pageSize={PAGE_SIZE} onChange={setPage} />
        </>}
        <div className="seat-legend"><span><i className="legend-dot" />{t('available')}</span><span><i className="legend-dot legend-selected" />{t('selectedShort')}</span><span><i className="legend-dot legend-unavailable" />{t('unavailableSeat')}</span></div>
        <p className="seat-map-footnote"><span>{isList ? <List size={15} aria-hidden /> : <MapIcon size={15} aria-hidden />}{t('seatSelectionNote')}</span></p>
    </div>;
}
