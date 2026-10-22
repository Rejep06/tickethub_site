/** Component tests use explicit API mocks. Real PostgreSQL checks live in backend/promotions/tests. */
import {useState} from 'react';
import {beforeEach, describe, expect, it, vi} from 'vitest';
import {fireEvent, screen, waitFor} from '@testing-library/react';
import {PromoCodeField, PriceSummary} from '@/features/checkout/promo-code';
import {checkoutApi} from '@/lib/api/endpoints';
import {ApiError} from '@/lib/api/client';
import {promoMatchesHold, type PromoSelection} from '@/lib/promotions';
import {hold, renderApp} from './support';
vi.mock('@/lib/api/endpoints', () => ({checkoutApi: {promo: vi.fn()}}));
const quote = {hold_id: hold.id, code: 'MATCH10', promo_version: 1, subtotal_minor: 100000, discount_minor: 10000, total_minor: 90000, currency: 'RUB' as const};
function Form() {
    const [value, setValue] = useState<PromoSelection>({code:'',quote:null});
    const applied = !!value.quote && promoMatchesHold(value.quote, hold, value.code);
    return <><PromoCodeField hold={hold} value={value} onChange={setValue}/>
        <PriceSummary subtotal={hold.total_minor} discount={applied ? value.quote?.discount_minor : 0} total={applied && value.quote ? value.quote.total_minor : hold.total_minor} code={value.quote?.code}/>
        <button disabled={!!value.code.trim() && !applied}>Оформить заказ</button></>;
}
beforeEach(() => vi.mocked(checkoutApi.promo).mockReset());
describe('promocode checkout UI', () => {
    it('does not apply a discount while only typing the code', () => {
        renderApp(<Form/>);
        fireEvent.change(screen.getByLabelText('Промокод'), {target:{value:'match10'}});
        expect(checkoutApi.promo).not.toHaveBeenCalled();
        expect(screen.getByRole('button',{name:'Оформить заказ'})).toBeDisabled();
    });
    it('applies an explicitly requested server quote', async () => {
        vi.mocked(checkoutApi.promo).mockResolvedValue(quote);
        renderApp(<Form/>);
        fireEvent.change(screen.getByLabelText('Промокод'), {target:{value:' match10 '}});
        fireEvent.click(screen.getByRole('button',{name:'Применить'}));
        await waitFor(() => expect(checkoutApi.promo).toHaveBeenCalledWith({hold_id:hold.id,code:'MATCH10'}));
        await waitFor(() => expect(screen.getByRole('button',{name:'Оформить заказ'})).toBeEnabled());
        expect(screen.getByText('Скидка по промокоду')).toBeInTheDocument();
    });
    it('a changed code invalidates the already displayed discount', async () => {
        vi.mocked(checkoutApi.promo).mockResolvedValue(quote);
        renderApp(<Form/>);
        fireEvent.change(screen.getByLabelText('Промокод'),{target:{value:'MATCH10'}});
        fireEvent.click(screen.getByRole('button',{name:'Применить'}));
        await waitFor(() => expect(screen.getByRole('button',{name:'Оформить заказ'})).toBeEnabled());
        fireEvent.change(screen.getByLabelText('Промокод'),{target:{value:'MATCH20'}});
        expect(screen.getByRole('button',{name:'Оформить заказ'})).toBeDisabled();
        expect(screen.queryByText('Скидка по промокоду')).not.toBeInTheDocument();
    });
    it('invalid server code is not silently ignored', async () => {
        vi.mocked(checkoutApi.promo).mockRejectedValue(new ApiError(400,'PROMO_INVALID','Invalid',{}));
        renderApp(<Form/>);
        fireEvent.change(screen.getByLabelText('Промокод'),{target:{value:'WRONG'}});
        fireEvent.click(screen.getByRole('button',{name:'Применить'}));
        await screen.findByRole('alert');
        expect(screen.getByRole('button',{name:'Оформить заказ'})).toBeDisabled();
        expect(screen.getByLabelText('Промокод')).toHaveValue('WRONG');
    });
    it('removing a code is an explicit return to the full price', () => {
        renderApp(<Form/>);
        fireEvent.change(screen.getByLabelText('Промокод'),{target:{value:'WRONG'}});
        fireEvent.click(screen.getByRole('button',{name:'Убрать промокод'}));
        expect(screen.getByLabelText('Промокод')).toHaveValue('');
        expect(screen.getByRole('button',{name:'Оформить заказ'})).toBeEnabled();
    });
    it('rejects a server quote that belongs to a different hold', async () => {
        vi.mocked(checkoutApi.promo).mockResolvedValue({...quote,hold_id:'another-hold'});
        renderApp(<Form/>);
        fireEvent.change(screen.getByLabelText('Промокод'),{target:{value:'MATCH10'}});
        fireEvent.click(screen.getByRole('button',{name:'Применить'}));
        await screen.findByRole('alert');
        expect(screen.getByRole('button',{name:'Оформить заказ'})).toBeDisabled();
    });
});
