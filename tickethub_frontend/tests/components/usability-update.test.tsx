/** Isolated components. Run with Vitest; these mocks are never used by the application. */
import { useState } from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError } from '@/lib/api/client';
import { authApi, requestApi } from '@/lib/api/endpoints';
import { PublicConfigProvider } from '@/features/auth/session';
import { RequestForm } from '@/features/requests/request-form';
import { ImageUpload, ImagePicker } from '@/features/staff/image-upload';
import { inspectImage, validateImageSelection, type ImageSelection } from '@/lib/image-upload';
import { ErrorState } from '@/components/ui';
import { SeatPicker } from '@/features/seat-map/seat-picker';
import { ids, profile, seat, renderApp } from './support';
import ru from '@/messages/ru.json';
vi.mock('@/lib/api/client', async () => ({ ...await vi.importActual<typeof import('@/lib/api/client')>('@/lib/api/client'), api: vi.fn() }));
vi.mock('@/lib/image-upload', async () => ({ ...await vi.importActual<typeof import('@/lib/image-upload')>('@/lib/image-upload'), inspectImage: vi.fn(), validateImageSelection: vi.fn() }));
vi.mock('@/lib/api/endpoints', () => ({ authApi: {me:vi.fn(),requestCode:vi.fn(),verifyCode:vi.fn(),update:vi.fn()}, requestApi:{create:vi.fn()} }));
beforeEach(() => {
    vi.mocked(api).mockReset().mockResolvedValue({version:8});
    vi.mocked(inspectImage).mockReset().mockResolvedValue({type:'image/svg+xml',width:null,height:null,previewSafe:false});
    vi.mocked(validateImageSelection).mockReset().mockResolvedValue(undefined);
    vi.mocked(authApi.me).mockReset().mockRejectedValue(new ApiError(401,'AUTH_REQUIRED','Войдите',{},'test-uuid'));
    vi.mocked(authApi.verifyCode).mockReset().mockResolvedValue(profile);
    vi.mocked(authApi.requestCode).mockReset().mockResolvedValue({expires_in:600,resend_after:60,detail:'Код отправлен'});
    vi.mocked(requestApi.create).mockReset();
    Object.defineProperty(URL,'createObjectURL',{configurable:true,writable:true,value:vi.fn()});
});
function Picker() {const [value,setValue]=useState<ImageSelection|null>(null);return <ImagePicker value={value} onChange={setValue}/>;}
describe('image and error UX',()=>{
    it('sends URL mode as JSON with rights and version, not as a multipart file',async()=>{
        const user=userEvent.setup();renderApp(<ImageUpload endpoint="staff/events/e/image/" version={7}/>);
        await user.click(screen.getByRole('button',{name:'По ссылке'}));
        await user.type(screen.getByLabelText('Ссылка на изображение'),'https://cdn.example.test/plan.svg');
        await user.type(screen.getByLabelText('Источник / основание использования'),'Организатор');
        await user.click(screen.getByRole('checkbox'));
        await user.click(screen.getByRole('button',{name:'Сохранить обложку'}));
        await waitFor(()=>expect(api).toHaveBeenCalledWith('staff/events/e/image/',expect.objectContaining({method:'POST',body:{image_url:'https://cdn.example.test/plan.svg',expected_version:7,rights_source:'Организатор',rights_confirmed:true},timeoutMs:300000})));
    });
    it('does not preview or fetch the remote address before saving',async()=>{
        const user=userEvent.setup();renderApp(<Picker/>);
        await user.click(screen.getByRole('button',{name:'По ссылке'}));
        await user.type(screen.getByLabelText('Ссылка на изображение'),'https://cdn.example.test/large.jpg');
        expect(api).not.toHaveBeenCalled();expect(screen.queryByRole('img')).not.toBeInTheDocument();
    });
    it('accepts static SVG input without embedding the untrusted file',async()=>{
        renderApp(<Picker/>);
        fireEvent.change(screen.getByLabelText('Файл изображения'),{target:{files:[new File(['<svg/>'],'plan.svg')]}});
        expect(await screen.findByText('SVG будет доступен для просмотра после проверки сервером.')).toBeInTheDocument();
        expect(URL.createObjectURL).not.toHaveBeenCalled();expect(screen.queryByRole('img')).not.toBeInTheDocument();
    });
    it('keeps server error reference inside a CLOSED disclosure',()=>{
        renderApp(<ErrorState error={new ApiError(503,'API_UNAVAILABLE','',{},'support-test')}/>);
        const id=screen.getByText('support-test');const details=id.closest('details');
        expect(details).not.toHaveAttribute('open');expect(screen.getByText(ru.supportDetails)).toBeInTheDocument();
    });
});
describe('guest ticket request',()=>{
    it('shows the form for a guest, authenticates inline, and keeps the typed request without auto-submitting',async()=>{
        const user=userEvent.setup();renderApp(<PublicConfigProvider initial={{public_forms_enabled:true,legal_versions:{}}}><RequestForm/></PublicConfigProvider>);
        await user.type(screen.getByLabelText(ru.eventName),'Матч в субботу');
        await waitFor(()=>expect(authApi.me).toHaveBeenCalled());
        expect(screen.queryByText(/test-uuid/)).not.toBeInTheDocument();
        await user.click(screen.getByRole('button',{name:ru.requestContinue}));
        expect(screen.getByRole('dialog')).toBeInTheDocument();
        await user.type(screen.getByLabelText(ru.email),profile.email);
        await user.click(screen.getByRole('button',{name:ru.sendCode}));
        await user.type(await screen.findByLabelText(ru.code),'123456');
        await user.click(screen.getByRole('button',{name:ru.verifyCode}));
        await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
        expect(screen.getByLabelText(ru.eventName)).toHaveValue('Матч в субботу');
        expect(requestApi.create).not.toHaveBeenCalled();
        expect(screen.getByRole('button',{name:ru.requestSubmit})).toBeInTheDocument();
    });
});
describe('accessible list remains an alternative to the canvas',()=>{
    it('does not offer an unavailable place, but permits removal of a prior selection',async()=>{
        const user=userEvent.setup(),choose=vi.fn();renderApp(<SeatPicker map={{plan:null,seats:[seat]}} availability={{available_seats:[]}} selected={[seat.id]} onChoose={choose}/>);
        const button=screen.getByRole('button',{name:/Сектор A.*Ряд 1.*Место 5/});await user.click(button);expect(choose).toHaveBeenCalledWith(seat.id);
    });
    it('filters by price and does not render an entire 50,000-seat list at once',async()=>{
        const user=userEvent.setup();const seats=Array.from({length:180},(_,i)=>({...seat,id:`${ids.seat}-${i}`,number:String(i+1)}));
        renderApp(<SeatPicker map={{plan:null,seats}} availability={{available_seats:seats.map((s,i)=>({seat_id:s.id,sale_price_minor:(i+1)*10000}))}} selected={[]} onChoose={vi.fn()}/>);
        expect(screen.getAllByRole('button',{name:/Сектор A.*Ряд 1.*Место/})).toHaveLength(80);
        await user.type(screen.getByLabelText(ru.seatPriceFrom),'17900');
        expect(screen.getAllByRole('button',{name:/Сектор A.*Ряд 1.*Место/})).toHaveLength(2);
    });
});
