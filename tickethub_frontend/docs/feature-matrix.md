> Обновление 06.10.2026: новый дизайн, темы, тексты и trailing slash описаны в `../UPDATE.md`. Текущий отчёт — `verification.md`; исходные архитектура и ограничения ниже сохранены для справки.

# Матрица реализации

`CODED` означает написанный исходный код, не прошедший браузерную и Django-приёмку. `UNIT CHECKED` относится только к изолированным domain/contracts. Общий CODE — INCOMPLETE относительно полного Definition of Done и production-приёмки запроса.

| Область | Файлы / результат | Состояние |
| --- | --- | --- |
| RU/EN, layout, бренд | app/[locale], messages, public-layout, providers, globals.css | CODED; словари проверены |
| Главная и категории | catalog/home, info; реальные события, запрос подбора, контакты из config | CODED |
| Каталог | SSR, q/category/venue/city/date, URL, debounce, pagination | CODED; whitelist UNIT CHECKED |
| Event | настоящий backend Event/Offer/availability, Fan ID, правила | CODED |
| Места | изображение/точки, zoom/scroll, список, сектор/ряд, клавиатура | CODED; нет отдельного price-filter списка, browser QA не выполнен |
| Цена/наличие | серверный preview/Hold; конфликт не заменяет места; подтверждение цены | CODED; HTTP conflict UNIT CHECKED |
| Hold | expires_at/server_now, reload, release/expire, потерянный ответ | CODED; domain/retry UNIT CHECKED |
| Auth | OTP/cooldown, staff password, session/CSRF, safe next, cache clear | CODED; API contract UNIT CHECKED |
| Checkout | контакты, точные версии документов, idempotent Order, manual-payment copy | CODED; domain contract UNIT CHECKED |
| Заявки | существующее/свободное событие, qty/budget/рядом/контакты | CODED |
| Quote | список и принятие через настоящий start-checkout, непубличное событие | CODED |
| Кабинет | сводка, заказы/заявки, snapshot/history, payment/delivery, обращение | CODED |
| Профиль | имя/телефон/язык, коды смены email, privacy request, logout | CODED |
| Staff guard/layout | разные права staff/admin, sidebar/mobile menu | CODED; 401/403 клиента UNIT CHECKED |
| Staff orders | фильтры поддерживаемых полей, детали, контакт, операции, start/confirm/cancel/reject/complete | CODED; action gating UNIT CHECKED |
| Деньги | отдельное подтверждение, фактический ledger, расходы/возврат поставщика/сторно | CODED; contract/idempotency UNIT CHECKED |
| Отправка | выбранные items, recipient/time, partial progress, исправление отметки | CODED; 2/4 UNIT CHECKED |
| Возвраты | очередь, decision, отдельный settle, версии Case/Order | CODED; separate operation contract UNIT CHECKED |
| Staff заявки | очередь/start/ответ/назначение, создание/отправка/отзыв Quote | CODED |
| Каталог staff | события/площадки/категории/участники, RU/EN формы, изображения, публикация | CODED |
| Редактор схем | точки, drag, ряд с preview, явное сохранение, remove, clone/publish | CODED; geometry UNIT CHECKED; backend version gap |
| Остатки | предложения, units, cost/supplier, block/unblock/allocation | CODED; bulk unit endpoint отсутствует |
| Поставщики/клиенты | реальные списки и редактирование поставщиков; customer→orders | CODED; customer aggregates отсутствуют |
| Аналитика | sales/cashflow/days/events/funnels/CSV, unknown-cost warning | CODED; не интеграционно проверено |
| Admin | команда/версии контента, readonly settings, privacy | CODED |
| Error/loading/empty | UI-компоненты, сохранение формы, retry, no false success | CODED; часть unit-tested |
| SEO | SSR titles/descriptions/canonical/hreflang/OG, sitemap, private noindex | CODED; JSON-LD Event не добавлен |
| Responsive | CSS для основных брейкпоинтов; staff-таблицы прокручиваются локально | CODED, NOT BROWSER VERIFIED |
| Доступность | native controls/dialog, labels, aria, focus, список мест | CODED, WCAG/Lighthouse NOT VERIFIED |
| Тесты | 93 unit, 12 component, 4 live E2E | Только 93 unit выполнены |
| Deployment | Dockerfile, Compose overlay, Nginx template, CI | CODED; lock/network/runtime gates |

## Известные ограничения клиентского кода

Справочники публичных фильтров ограничены первой сотней категорий/площадок. Staff reference picker ищет на текущей странице, не во всём справочнике. Не реализованы отдельный price-filter списка мест, полноценная фиксация mobile итога/bottom sheet во всех сценариях, JSON-LD Event и полный browser Back guard несохранённых форм. Неопределённая финансовая попытка блокирует изменённый повтор; универсальный recovery wizard после закрытия вкладки не реализован. Компонентные/сквозные тесты ещё могут потребовать корректировок после первого настоящего выполнения.

Поэтому в отчёте не объявляется COMPLETE или production-ready. Список недостающих API — `backend-gaps.md`; тестовая неопределённость не подменяется backend gap.
