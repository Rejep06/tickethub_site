> Обновление 21.10.2026: порядок ручного оформления, приоритет реального остатка над старым REQUEST и API промокодов описаны в `../../MANAGER_CHECKOUT_PROMOS.md` в корне полного проекта. Это дополнение имеет приоритет над прежними условиями прямого оформления в данном документе.

> **Дополнение контракта:** новые `/staff/external-events/` и операции редактора описаны в [portalbilet-and-editor.md](portalbilet-and-editor.md). Старые маршруты сохранены. Исторические OpenAPI/api-contract.json этой версии пока не включают новые методы; после запуска Django схему нужно сгенерировать заново.

# Tickethub: контракт для Next.js

Это контракт написанного backend MVP. HTTP-ответы пока не подтверждены запуском: зависимости и PostgreSQL в среде разработки недоступны. `openapi.yaml` составлен по исходникам, а не выдан работающим сервером. Проверка выполняется `scripts/verify_backend.sh`.

## Общие правила

База: `/api/v1/`. JSON, `snake_case`, завершающий `/`. UUID передаётся строкой. Все денежные `*_minor` — целые копейки RUB: **100000 = 1 000 ₽**, не рубли и не float. Даты — ISO8601 с часовым поясом; фильтр `to` не включается. Для отображения даты события используйте `venue.timezone`. Координаты схемы — нормализованные Decimal-строки `0..1`.

`Page<T>`: `{count, next, previous, results: T[]}`; `page_size` по умолчанию 24, максимум 100. `T[]` — обычный массив без пагинации. Возвращаются RU и EN поля; frontend выбирает язык сам. Ссылки изображений могут быть относительными к тому же origin.

`PUBLIC` — доступен без входа; `USER` — любая авторизованная сессия, но только собственные приватные объекты; `STAFF` — MANAGER/ADMIN, вошедший **по паролю**; `ADMIN` — роль ADMIN и парольная сессия. Email OTP сотрудника не даёт staff-доступа.

Обычные изменяющие запросы передают `X-CSRFToken` и cookies. OTP, парольный вход и клиентская аналитика требуют CSRF даже без авторизации. Preview не изменяет данные; всё равно отправляйте CSRF из общего клиента. После login CSRF меняется: получите свежий токен. JWT и токены в localStorage не нужны.

`Idempotency-Key` — UUID, созданный один раз на намерение пользователя. При сетевом повторе отправляйте **тот же ключ и неизменённое тело**, включая expected_version. Новый ключ на каждый retry не защищает от дубля. Ключи финансовых операций уникальны в рамках заказа, заказов и заявок — в рамках пользователя. Изменение тела при том же ключе даёт `409 IDEMPOTENCY_CONFLICT`. Резерв при повторе возвращает тот же объект и его текущее состояние, а не продлевает срок.

`expected_version` берётся из последнего ответа изменяемого объекта. После `409 VERSION_CONFLICT` перечитайте объект, покажите изменения сотруднику, затем сформируйте новое действие. Для `Quote.send/withdraw` нужна **request_version**, для approve/reject возврата — **Case.version**, для фактического возврата/сторно/отправки — **Order.version** (`order_version` в связанных ответах).

Ошибка Django API: `{code, message, details, request_id}`. 400 — данные, 401 — вход, 403 — доступ/CSRF, 404 — отсутствует или чужой объект, 409 — конфликт бизнеса/версии, 429 — ограничение, 503 — внешняя недоступность. Непредвиденная 500 не раскрывает внутренние данные. Ошибки Nginx до Django могут иметь HTML: клиент должен учитывать Content-Type.

## Маршруты

Для каждой строки ниже указаны METHOD, PATH, AUTH, REQUEST, RESPONSE и специфичные ERRORS. Общие ошибки доступа/валидации применимы к остальным защищённым запросам также. `—` означает отсутствие тела. Для пустого изменяющего действия передавайте `{}`.

| METHOD / PATH | AUTH | REQUEST | RESPONSE | ERRORS / особенности |
|---|---|---|---|---|
| `GET /api/v1/` | PUBLIC | `—` | 200 `ApiInfo` |  |
| `GET /api/v1/public/config/` | PUBLIC | `—` | 200 `PublicConfig` | Контакты, режимы запуска, актуальные версии документов. |
| `GET /api/v1/categories/` | PUBLIC | `—` | 200 `Page<Category>` |  |
| `GET /api/v1/participants/` | PUBLIC | `—` | 200 `Page<Participant>` |  |
| `GET /api/v1/venues/` | PUBLIC | `—` | 200 `Page<Venue>` |  |
| `GET /api/v1/events/` | PUBLIC | `—` | 200 `Page<Event>` |  |
| `GET /api/v1/events/{slug}/` | PUBLIC | `—` | 200 `Event` | Именно slug, не UUID. Неопубликованные/непубличные события — 404. |
| `GET /api/v1/events/{event_id}/offers/` | PUBLIC | `—` | 200 `Offer[]` | event_id — UUID публичного события. |
| `GET /api/v1/events/{event_id}/seat-map/` | PUBLIC | `—` | 200 `SeatMap` | event_id — UUID публичного события. |
| `GET /api/v1/events/{event_id}/availability/` | PUBLIC | `—` | 200 `Availability` | event_id — UUID публичного события. |
| `GET /api/v1/content/{slug}/` | PUBLIC | `—` | 200 `Page` | Только опубликованная и утверждённая версия; plain text, не доверенный HTML. |
| `GET /api/v1/legal/{slug}/` | PUBLIC | `—` | 200 `Page` | Только опубликованная и утверждённая версия; plain text, не доверенный HTML. |
| `GET /api/v1/auth/csrf/` | PUBLIC | `—` | 200 `CSRF` | Устанавливает csrftoken; возвращает токен для X-CSRFToken. |
| `POST /api/v1/auth/otp/request/` | PUBLIC+CSRF | `RequestCodeInput` | 200 `OTPRequested` | RATE_LIMITED, EMAIL_UNAVAILABLE; Код не возвращается API. |
| `POST /api/v1/auth/otp/verify/` | PUBLIC+CSRF | `VerifyCodeInput` | 200 `Profile` | OTP_INVALID, OTP_EXPIRED, RATE_LIMITED, FORMS_DISABLED; Устанавливает Django session; CSRF-токен после входа обновляется. |
| `POST /api/v1/auth/staff/login/` | PUBLIC+CSRF | `StaffLoginInput` | 200 `StaffLoginResult` | AUTH_REQUIRED, RATE_LIMITED; Отдельный парольный вход сотрудника. |
| `POST /api/v1/auth/logout/` | USER | `Empty` | 204 `—` | Завершает текущую сессию. |
| `GET /api/v1/me/` | USER | `—` | 200 `Profile` |  |
| `PATCH /api/v1/me/` | USER | `ProfileInput` | 200 `Profile` | Разрешены только name, phone, locale. Email/роль/password здесь запрещены. |
| `POST /api/v1/me/email-change/start/` | USER | `StartEmailChangeInput` | 200 `EmailChangeStarted` | EMAIL_UNAVAILABLE, RATE_LIMITED; Коды на текущий и новый email; старый должен быть подтверждён. |
| `POST /api/v1/me/email-change/confirm/` | USER | `ConfirmEmailChangeInput` | 200 `Profile` | OTP_INVALID, EMAIL_CHANGE_EXPIRED, EMAIL_CHANGED; Оба кода обязательны. Другие сессии отзываются; снимки заказов не меняются. |
| `GET /api/v1/staff/customers/` | STAFF | `—` | 200 `Page<Profile>` | Только покупатели; q ищет по email. |
| `GET /api/v1/staff/users/staff/` | ADMIN | `—` | 200 `Page<StaffUser>` | Пагинация; фильтры перечислены ниже. |
| `POST /api/v1/staff/users/staff/` | ADMIN | `StaffUserInput` | 201 `StaffUser` | VALIDATION_ERROR, INTEGRITY_CONFLICT; Создать запись; read-only поля запрещены. |
| `GET /api/v1/staff/users/staff/{id}/` | ADMIN | `—` | 200 `StaffUser` | Карточка. |
| `PATCH /api/v1/staff/users/staff/{id}/` | ADMIN | `StaffUserInput` | 200 `StaffUser` | VALIDATION_ERROR, VERSION_CONFLICT, INVALID_CHANGE; Частичное изменение. |
| `POST /api/v1/checkout/preview/` | PUBLIC | `PreviewInput` | 200 `PreviewResult` | EVENT_NOT_ORDERABLE, SEAT_UNAVAILABLE, INSUFFICIENT_STOCK, FORMS_DISABLED; Расчёт без резервирования. |
| `POST /api/v1/checkout/holds/` | USER | `CreateHoldInput` | 201 `Hold` | **Idempotency-Key**; SEAT_UNAVAILABLE, INSUFFICIENT_STOCK, PRICE_CHANGED, ORDER_EXISTS; Создать/заменить резерв; время существующего резерва не продлевается. |
| `GET /api/v1/checkout/holds/{id}/` | USER | `—` | 200 `Hold` | Только собственный; истечение вычисляется и без cron. |
| `POST /api/v1/checkout/holds/{id}/release/` | USER | `Empty` | 200 `Hold` | HOLD_CONVERTED; Повтор release безопасен; конвертированный резерв не освобождается. |
| `POST /api/v1/orders/` | USER | `CreateOrderInput` | 201 `Order` | **Idempotency-Key**; HOLD_EXPIRED, HOLD_CONVERTED, EVENT_CHANGED, PROFILE_INCOMPLETE, FAN_ID_ACK_REQUIRED, CONSENT_REQUIRED; 201 новый; 200 повтор того же ключа/тела. |
| `GET /api/v1/orders/` | USER | `—` | 200 `Page<Order>` | Только собственные заказы. |
| `GET /api/v1/orders/{id}/` | USER | `—` | 200 `Order` | Чужой UUID возвращает 404. |
| `POST /api/v1/orders/{id}/cases/` | USER | `CreateCaseInput` | 201 `Case` | INVALID_ITEMS; 201 новое; 200 идентичное открытое обращение. |
| `GET /api/v1/cases/{id}/` | USER | `—` | 200 `Case` | Только собственное обращение. |
| `POST /api/v1/ticket-requests/` | USER | `CreateRequestInput` | 201 `Request` | **Idempotency-Key**; PROFILE_INCOMPLETE, EVENT_REQUIRED, CONSENT_REQUIRED; Количество 1..100; без event_id нужны название или описание. 201/200. |
| `GET /api/v1/ticket-requests/` | USER | `—` | 200 `Page<Request>` |  |
| `GET /api/v1/ticket-requests/{id}/` | USER | `—` | 200 `Request` | Содержит собственные отправленные Quote; чужие и черновики не раскрываются. |
| `POST /api/v1/ticket-requests/{id}/cancel/` | USER | `VersionActionInput` | 200 `Request` | INVALID_TRANSITION; expected_version — версия заявки. |
| `POST /api/v1/quotes/{id}/start-checkout/` | USER | `QuoteCheckoutInput` | 201 `Hold` | **Idempotency-Key**; QUOTE_UNAVAILABLE, QUOTE_EXPIRED, SEAT_UNAVAILABLE, PRICE_CHANGED; Предложение принадлежит пользователю; наличие и срок проверяются повторно. |
| `GET /api/v1/staff/categories/` | STAFF | `—` | 200 `Page<Category>` | Пагинация; фильтры перечислены ниже. |
| `POST /api/v1/staff/categories/` | STAFF | `CategoryInput` | 201 `Category` | VALIDATION_ERROR, INTEGRITY_CONFLICT; Создать запись; read-only поля запрещены. |
| `GET /api/v1/staff/categories/{id}/` | STAFF | `—` | 200 `Category` | Карточка. |
| `PATCH /api/v1/staff/categories/{id}/` | STAFF | `CategoryInput` | 200 `Category` | VALIDATION_ERROR, VERSION_CONFLICT, INVALID_CHANGE; Частичное изменение. |
| `GET /api/v1/staff/participants/` | STAFF | `—` | 200 `Page<Participant>` | Пагинация; фильтры перечислены ниже. |
| `POST /api/v1/staff/participants/` | STAFF | `ParticipantInput` | 201 `Participant` | VALIDATION_ERROR, INTEGRITY_CONFLICT; Создать запись; read-only поля запрещены. |
| `GET /api/v1/staff/participants/{id}/` | STAFF | `—` | 200 `Participant` | Карточка. |
| `PATCH /api/v1/staff/participants/{id}/` | STAFF | `ParticipantInput` | 200 `Participant` | VALIDATION_ERROR, VERSION_CONFLICT, INVALID_CHANGE; Частичное изменение. |
| `GET /api/v1/staff/venues/` | STAFF | `—` | 200 `Page<Venue>` | Пагинация; фильтры перечислены ниже. |
| `POST /api/v1/staff/venues/` | STAFF | `VenueInput` | 201 `Venue` | VALIDATION_ERROR, INTEGRITY_CONFLICT; Создать запись; read-only поля запрещены. |
| `GET /api/v1/staff/venues/{id}/` | STAFF | `—` | 200 `Venue` | Карточка. |
| `PATCH /api/v1/staff/venues/{id}/` | STAFF | `VenueInput` | 200 `Venue` | VALIDATION_ERROR, VERSION_CONFLICT, INVALID_CHANGE; Частичное изменение. |
| `GET /api/v1/staff/events/` | STAFF | `—` | 200 `Page<StaffEvent>` | Пагинация; фильтры перечислены ниже. |
| `POST /api/v1/staff/events/` | STAFF | `StaffEventInput` | 201 `StaffEvent` | VALIDATION_ERROR, INTEGRITY_CONFLICT; Создать запись; read-only поля запрещены. |
| `GET /api/v1/staff/events/{id}/` | STAFF | `—` | 200 `StaffEvent` | Карточка. |
| `PATCH /api/v1/staff/events/{id}/` | STAFF | `StaffEventInput` | 200 `StaffEvent` | VALIDATION_ERROR, VERSION_CONFLICT, INVALID_CHANGE; Частичное изменение; expected_version обязателен. |
| `GET /api/v1/staff/plans/` | STAFF | `—` | 200 `Page<Plan>` | Пагинация; фильтры перечислены ниже. |
| `POST /api/v1/staff/plans/` | STAFF | `PlanInput` | 201 `Plan` | VALIDATION_ERROR, INTEGRITY_CONFLICT; Создать запись; read-only поля запрещены. |
| `GET /api/v1/staff/plans/{id}/` | STAFF | `—` | 200 `Plan` | Карточка. |
| `PATCH /api/v1/staff/plans/{id}/` | STAFF | `PlanInput` | 200 `Plan` | VALIDATION_ERROR, VERSION_CONFLICT, INVALID_CHANGE; Частичное изменение; expected_version обязателен. |
| `GET /api/v1/staff/seats/` | STAFF | `—` | 200 `Page<Seat>` | Пагинация; фильтры перечислены ниже. |
| `POST /api/v1/staff/seats/` | STAFF | `SeatInput` | 201 `Seat` | VALIDATION_ERROR, INTEGRITY_CONFLICT; Создать запись; read-only поля запрещены. |
| `GET /api/v1/staff/seats/{id}/` | STAFF | `—` | 200 `Seat` | Карточка. |
| `PATCH /api/v1/staff/seats/{id}/` | STAFF | `SeatInput` | 200 `Seat` | VALIDATION_ERROR, VERSION_CONFLICT, INVALID_CHANGE; Частичное изменение. |
| `DELETE /api/v1/staff/seats/{id}/` | STAFF | `—` | 204 `—` | PLAN_IMMUTABLE; Только место черновика схемы. |
| `GET /api/v1/staff/suppliers/` | STAFF | `—` | 200 `Page<Supplier>` | Пагинация; фильтры перечислены ниже. |
| `POST /api/v1/staff/suppliers/` | STAFF | `SupplierInput` | 201 `Supplier` | VALIDATION_ERROR, INTEGRITY_CONFLICT; Создать запись; read-only поля запрещены. |
| `GET /api/v1/staff/suppliers/{id}/` | STAFF | `—` | 200 `Supplier` | Карточка. |
| `PATCH /api/v1/staff/suppliers/{id}/` | STAFF | `SupplierInput` | 200 `Supplier` | VALIDATION_ERROR, VERSION_CONFLICT, INVALID_CHANGE; Частичное изменение. |
| `GET /api/v1/staff/offers/` | STAFF | `—` | 200 `Page<StaffOffer>` | Пагинация; фильтры перечислены ниже. |
| `POST /api/v1/staff/offers/` | STAFF | `StaffOfferInput` | 201 `StaffOffer` | VALIDATION_ERROR, INTEGRITY_CONFLICT; Создать запись; read-only поля запрещены. |
| `GET /api/v1/staff/offers/{id}/` | STAFF | `—` | 200 `StaffOffer` | Карточка. |
| `PATCH /api/v1/staff/offers/{id}/` | STAFF | `StaffOfferInput` | 200 `StaffOffer` | VALIDATION_ERROR, VERSION_CONFLICT, INVALID_CHANGE; Частичное изменение; expected_version обязателен. |
| `GET /api/v1/staff/units/` | STAFF | `—` | 200 `Page<StaffUnit>` | Пагинация; фильтры перечислены ниже. |
| `POST /api/v1/staff/units/` | STAFF | `StaffUnitInput` | 201 `StaffUnit` | VALIDATION_ERROR, INTEGRITY_CONFLICT; Создать запись; read-only поля запрещены. |
| `GET /api/v1/staff/units/{id}/` | STAFF | `—` | 200 `StaffUnit` | Карточка. |
| `PATCH /api/v1/staff/units/{id}/` | STAFF | `StaffUnitInput` | 200 `StaffUnit` | VALIDATION_ERROR, VERSION_CONFLICT, INVALID_CHANGE; Частичное изменение; expected_version обязателен. |
| `POST /api/v1/staff/events/{id}/publish/` | STAFF | `VersionActionInput` | 200 `StaffEvent` | VERSION_CONFLICT, VALIDATION_ERROR; Проверяет условия и версию события. |
| `POST /api/v1/staff/events/{id}/unpublish/` | STAFF | `VersionActionInput` | 200 `StaffEvent` | VERSION_CONFLICT, VALIDATION_ERROR; Проверяет условия и версию события. |
| `POST /api/v1/staff/events/{id}/image/` | STAFF | `EventImageInput` | 200 `StaffEvent` | multipart/form-data; размер до 10 МБ, PNG/JPEG/WebP; JPEG без метаданных. |
| `POST /api/v1/staff/plans/{id}/image/` | STAFF | `PlanImageInput` | 200 `Plan` | PLAN_IMMUTABLE; multipart/form-data; только черновик. |
| `POST /api/v1/staff/plans/{id}/publish/` | STAFF | `VersionActionInput` | 200 `Plan` | INVALID_PLAN, PLAN_IMMUTABLE; Фон, права и места обязательны. |
| `POST /api/v1/staff/plans/{id}/clone-version/` | STAFF | `Empty` | 201 `Plan` | Новый самостоятельный черновик с копией мест. |
| `GET /api/v1/staff/plans/{id}/seats/` | STAFF | `—` | 200 `Seat[]` |  |
| `POST /api/v1/staff/plans/{id}/create-row/` | STAFF | `RowInput` | 201 `Seat[]` | DUPLICATE_SEAT, PLAN_LIMIT, PLAN_IMMUTABLE; До 500 мест за запрос, до 5000 на план; x/y 0..1. |
| `GET /api/v1/staff/plans/{id}/preview/` | STAFF | `—` | 200 `PlanPreview` |  |
| `POST /api/v1/staff/units/{id}/block/` | STAFF | `UnitBlockInput` | 200 `StaffUnit` | UNIT_OCCUPIED, STOCK_NOT_CONFIRMED; Причина обязательна; для unblock confirmed_valid=true. |
| `POST /api/v1/staff/units/{id}/unblock/` | STAFF | `UnitBlockInput` | 200 `StaffUnit` | UNIT_OCCUPIED, STOCK_NOT_CONFIRMED; Причина обязательна; для unblock confirmed_valid=true. |
| `POST /api/v1/staff/units/{id}/renew-allocation/` | STAFF | `RenewAllocationInput` | 200 `StaffUnit` | STOCK_NOT_CONFIRMED, INVALID_DEADLINE; Только продление подтверждённого EXCLUSIVE_ALLOCATION. Не разблокирует возвращённый билет. |
| `GET /api/v1/staff/orders/` | STAFF | `—` | 200 `Page<StaffOrder>` | Список. |
| `GET /api/v1/staff/orders/{id}/` | STAFF | `—` | 200 `StaffOrder` | Карточка. |
| `POST /api/v1/staff/orders/{id}/start/` | STAFF | `VersionActionInput` | 200 `StaffOrder` | INVALID_TRANSITION, VERSION_CONFLICT, PAYMENT_REQUIRED, DELIVERY_REQUIRED, OPEN_CASE; expected_version — текущая версия заказа. |
| `POST /api/v1/staff/orders/{id}/confirm/` | STAFF | `VersionActionInput` | 200 `StaffOrder` | INVALID_TRANSITION, VERSION_CONFLICT, PAYMENT_REQUIRED, DELIVERY_REQUIRED, OPEN_CASE; expected_version — текущая версия заказа. |
| `POST /api/v1/staff/orders/{id}/complete/` | STAFF | `VersionActionInput` | 200 `StaffOrder` | INVALID_TRANSITION, VERSION_CONFLICT, PAYMENT_REQUIRED, DELIVERY_REQUIRED, OPEN_CASE; expected_version — текущая версия заказа. |
| `POST /api/v1/staff/orders/{id}/cancel/` | STAFF | `CancelOrderInput` | 200 `StaffOrder` | INVALID_TRANSITION, SETTLEMENT_CONFIRMATION_REQUIRED; Для безопасного неоплаченного заказа нужно no_pending_settlements=true; деньги/отправки не стираются. |
| `POST /api/v1/staff/orders/{id}/reject/` | STAFF | `CancelOrderInput` | 200 `StaffOrder` | INVALID_TRANSITION, SETTLEMENT_CONFIRMATION_REQUIRED; Для безопасного неоплаченного заказа нужно no_pending_settlements=true; деньги/отправки не стираются. |
| `POST /api/v1/staff/orders/{id}/contact/` | STAFF | `ContactInput` | 200 `StaffOrder` | Фиксация первого контакта и внутренней заметки. |
| `POST /api/v1/staff/orders/{id}/operations/` | STAFF | `OrderOperationsInput` | 200 `StaffOrder` | Менеджер, сроки, помощь с Fan ID, внутренняя заметка; не состояние оплаты. |
| `POST /api/v1/staff/order-items/{id}/cost/` | STAFF | `UpdateItemCostInput` | 200 `StaffOrder` | INVALID_COST; Уточнение внутренней себестоимости с причиной; expected_version — заказа; ноль требует zero_confirmed=true. |
| `GET /api/v1/staff/orders/{id}/financial-entries/` | STAFF | `—` | 200 `FinancialEntry[]` |  |
| `POST /api/v1/staff/orders/{id}/financial-entries/` | STAFF | `RecordPaymentInput` | 201 `FinancialEntry` | **Idempotency-Key**; OVERPAYMENT, INVALID_TIME, ORDER_CLOSED; Факт денег вне сайта. 201/200; expected_version — заказа. |
| `POST /api/v1/staff/financial-entries/{id}/reverse/` | STAFF | `ReverseEntryInput` | 201 `FinancialEntry` | **Idempotency-Key**; ALREADY_REVERSED, DELIVERY_EXISTS, REFUND_LIMIT; Полное сторно одной записи. 201/200; expected_version — заказа. |
| `GET /api/v1/staff/orders/{id}/deliveries/` | STAFF | `—` | 200 `Delivery[]` |  |
| `POST /api/v1/staff/orders/{id}/deliveries/` | STAFF | `RecordDeliveryInput` | 201 `Delivery` | **Idempotency-Key**; PAYMENT_REQUIRED, EMAIL_MISMATCH, INVALID_ITEMS, OPEN_REFUND; Только факт уже отправленного email; полностью оплаченный подтверждённый заказ. 201/200. |
| `POST /api/v1/staff/deliveries/{id}/void/` | STAFF | `VersionActionInput` | 200 `Delivery` | INVALID_TRANSITION; Причина обязательна; expected_version — заказа. |
| `GET /api/v1/staff/ticket-requests/` | STAFF | `—` | 200 `Page<StaffRequest>` | Список. |
| `GET /api/v1/staff/ticket-requests/{id}/` | STAFF | `—` | 200 `StaffRequest` | Карточка. |
| `POST /api/v1/staff/ticket-requests/{id}/assign/` | STAFF | `RequestActionInput` | 200 `StaffRequest` | INVALID_TRANSITION; Версия заявки; assign использует manager_id, update-status использует status. |
| `POST /api/v1/staff/ticket-requests/{id}/update-status/` | STAFF | `RequestActionInput` | 200 `StaffRequest` | INVALID_TRANSITION; Версия заявки; assign использует manager_id, update-status использует status. |
| `POST /api/v1/staff/ticket-requests/{id}/start/` | STAFF | `VersionActionInput` | 200 `StaffRequest` | Взять заявку в работу. |
| `POST /api/v1/staff/ticket-requests/{id}/quotes/` | STAFF | `CreateQuoteInput` | 201 `StaffQuote` | SEAT_UNAVAILABLE, ADJACENCY_NOT_CONFIRMED, INVALID_TOTAL; Создаёт черновик новой версии; требуется точный список единиц и цены. |
| `GET /api/v1/staff/quotes/` | STAFF | `—` | 200 `Page<StaffQuote>` | Список. |
| `GET /api/v1/staff/quotes/{id}/` | STAFF | `—` | 200 `StaffQuote` | Карточка. |
| `POST /api/v1/staff/quotes/{id}/send/` | STAFF | `VersionActionInput` | 200 `StaffQuote` | INVALID_TRANSITION, QUOTE_EXPIRED, SEAT_UNAVAILABLE; ВАЖНО: expected_version = request_version, не коммерческая Quote.version. |
| `POST /api/v1/staff/quotes/{id}/withdraw/` | STAFF | `VersionActionInput` | 200 `StaffQuote` | INVALID_TRANSITION, QUOTE_EXPIRED, SEAT_UNAVAILABLE; ВАЖНО: expected_version = request_version, не коммерческая Quote.version. |
| `GET /api/v1/staff/refunds/` | STAFF | `—` | 200 `Page<StaffCase>` | Список. |
| `GET /api/v1/staff/refunds/{id}/` | STAFF | `—` | 200 `StaffCase` | Карточка. |
| `POST /api/v1/staff/refunds/{id}/decision/` | STAFF | `CaseDecisionInput` | 200 `StaffCase` | REFUND_LIMIT, REFUND_EXISTS, INVALID_TRANSITION; expected_version — Case.version; одобрение не переводит деньги. |
| `POST /api/v1/staff/refunds/{id}/approve/` | STAFF | `ApproveRefundInput` | 200 `StaffCase` | REFUND_LIMIT, REFUND_EXISTS, INVALID_TRANSITION; expected_version — Case.version; одобрение не переводит деньги. |
| `POST /api/v1/staff/refunds/{id}/reject/` | STAFF | `RejectRefundInput` | 200 `StaffCase` | REFUND_LIMIT, REFUND_EXISTS, INVALID_TRANSITION; expected_version — Case.version; одобрение не переводит деньги. |
| `POST /api/v1/staff/refunds/{id}/settle/` | STAFF | `MoneyOperationInput` | 201 `FinancialEntry` | **Idempotency-Key**; REFUND_NOT_APPROVED, REFUND_LIMIT; Факт возврата; expected_version — order_version. Допустимы части до approved_minor. 201/200. |
| `POST /api/v1/analytics/events/` | PUBLIC+CSRF | `ClientEventInput` | 201 `EventIdResult` | ANALYTICS_DISABLED, IDEMPOTENCY_CONFLICT; Только четыре разрешённых клиентских шага и analytics_consent=true; UUID дедупликация. |
| `GET /api/v1/staff/dashboard/summary/` | STAFF | `—` | 200 `Dashboard` | from/to — ISO8601, интервал [from,to); event/category — UUID. |
| `GET /api/v1/staff/analytics/sales/` | STAFF | `—` | 200 `Dashboard` | from/to — ISO8601, интервал [from,to); event/category — UUID. |
| `GET /api/v1/staff/analytics/cashflow/` | STAFF | `—` | 200 `Cashflow` | from/to — ISO8601, интервал [from,to); event/category — UUID. |
| `GET /api/v1/staff/analytics/funnel/` | STAFF | `—` | 200 `Funnel` | from/to — ISO8601, интервал [from,to); event/category — UUID. |
| `GET /api/v1/staff/analytics/export/` | STAFF | `—` | 200 `CSV` | Те же фильтры. UTF-8 BOM, суммы в копейках; строки защищены от формул. |
| `GET /api/v1/privacy/requests/` | USER | `—` | 200 `Page<Privacy>` |  |
| `POST /api/v1/privacy/requests/` | USER | `CreatePrivacyInput` | 201 `Privacy` | Запрос на доступ/исправление/удаление данных; без немедленного удаления финансов. |
| `GET /api/v1/staff/content/` | ADMIN | `—` | 200 `Page<StaffPage>` | Пагинация; фильтры перечислены ниже. |
| `POST /api/v1/staff/content/` | ADMIN | `StaffPageInput` | 201 `StaffPage` | VALIDATION_ERROR, INTEGRITY_CONFLICT; Создать запись; read-only поля запрещены. |
| `GET /api/v1/staff/content/{id}/` | ADMIN | `—` | 200 `StaffPage` | Карточка. |
| `PATCH /api/v1/staff/content/{id}/` | ADMIN | `StaffPageInput` | 200 `StaffPage` | VALIDATION_ERROR, VERSION_CONFLICT, INVALID_CHANGE; Частичное изменение. |
| `POST /api/v1/staff/content/{id}/publish/` | ADMIN | `Empty` | 200 `StaffPage` | Только реальный утверждённый текст. Публикация заменяет текущую версию. |
| `GET /api/v1/staff/privacy-requests/` | ADMIN | `—` | 200 `Page<StaffPrivacy>` | Список. |
| `GET /api/v1/staff/privacy-requests/{id}/` | ADMIN | `—` | 200 `StaffPrivacy` | Карточка. |
| `POST /api/v1/staff/privacy-requests/{id}/respond/` | ADMIN | `StaffPrivacyInput` | 200 `StaffPrivacy` | Разрешены status и response; остальные поля read-only. |
| `GET /api/v1/staff/notifications/` | STAFF | `—` | 200 `Page<Email>` | Список. |
| `GET /api/v1/staff/notifications/{id}/` | STAFF | `—` | 200 `Email` | Карточка. |
| `POST /api/v1/staff/notifications/{id}/retry/` | STAFF | `Empty` | 200 `Email` | Явная повторная отправка бизнес-письма; SMTP может дать дубль письма, не заказа. |
| `GET /api/v1/staff/settings/` | ADMIN | `—` | 200 `Settings` | Режимы читаются из env; API не меняет секреты. |
| `GET /api/v1/schema/` | STAFF | `—` | 200 `OpenAPI` | Runtime-схема drf-spectacular; в текущем окружении не генерировалась. |
| `GET /health/live/` | PUBLIC | `—` | 200 `Health` | 503 unavailable; ready выполняет SELECT 1; live не проверяет БД. |
| `GET /health/ready/` | PUBLIC | `—` | 200 `Health` | 503 unavailable; ready выполняет SELECT 1; live не проверяет БД. |

## Форматы запросов и ответов

Ниже поля API, не перечень полей БД. Суффикс `Input` обозначает вход. `?` — поле не обязательно на создании; PATCH всегда частичный, но бизнес-операция может требовать expected_version. Все прочие поля запрещены строгими входными сериализаторами. Точные JSON Schema находятся в `openapi.yaml`; дополнительные межтабличные правила — ниже.

### ApiInfo

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `name` | string | — |
| `version` | string | — |
| `implementation_stage` | string | — |
| `order_intake_enabled` | boolean | — |
| `online_payments_enabled` | boolean | — |

### PublicConfig

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `currency` | string | RUB |
| `locales` | string[] | — |
| `public_forms_enabled` | boolean | — |
| `order_intake_enabled` | boolean | — |
| `online_payments_enabled` | boolean | — |
| `ticket_download_enabled` | boolean | — |
| `client_analytics_enabled` | boolean | — |
| `legal_ready` | boolean | — |
| `hold_seconds` | integer | — |
| `direct_order_limit` | integer | — |
| `request_limit` | integer | — |
| `legal_versions` | object | — |
| `contacts` | object | — |

### Category

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `slug` | string | — |
| `name_ru` | string | длина ≤ 100 |
| `name_en` | string | длина ≤ 100 |
| `kind` | string | SPORT, CONCERT, OTHER; длина ≤ 7 |
| `parent` | uuid / null | — |
| `is_active` | boolean | — |
| `sort_order` | int64 | min 0 |

### Participant

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `name_ru` | string | длина ≤ 200 |
| `name_en` | string | длина ≤ 200 |
| `kind` | string | TEAM, ARTIST, OTHER; длина ≤ 10 |

### Venue

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `name_ru` | string | длина ≤ 200 |
| `name_en` | string | длина ≤ 200 |
| `country` | string | длина ≤ 2 |
| `city` | string | длина ≤ 100 |
| `city_en` | string | длина ≤ 100 |
| `address` | string | длина ≤ 300 |
| `address_en` | string | длина ≤ 300 |
| `timezone` | string | длина ≤ 64 |

### Event

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `slug` | string | длина ≤ 200 |
| `title_ru` | string | длина ≤ 250 |
| `title_en` | string | длина ≤ 250 |
| `description_ru` | string | — |
| `description_en` | string | — |
| `category` | Category | — |
| `venue` | Venue | — |
| `participants` | Participant[] | — |
| `start_at` | date-time / null | — |
| `date_tba` | boolean | — |
| `sale_deadline` | date-time / null | — |
| `status` | string | SCHEDULED, POSTPONED, CANCELLED, FINISHED; длина ≤ 10 |
| `image` | string | — |
| `seating_plan` | uuid / null | — |
| `fan_id_required` | boolean / null | — |
| `fan_id_description_ru` | string | — |
| `fan_id_description_en` | string | — |
| `refund_policy_ru` | string | — |
| `refund_policy_en` | string | — |
| `refund_policy_approved` | boolean | — |
| `delivery_due_at` | date-time | — |
| `price_from_minor` | int64 / null | — |
| `orderable` | boolean | — |
| `version` | int64 | min 0 |

### Offer

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `event` | uuid | — |
| `name_ru` | string | длина ≤ 200 |
| `name_en` | string | длина ≤ 200 |
| `description_ru` | string | — |
| `description_en` | string | — |
| `kind` | string | SEAT, CATEGORY, STANDING; длина ≤ 8 |
| `mode` | string | AVAILABLE, REQUEST; длина ≤ 9 |
| `sale_price_minor` | int64 / null | min 0 |
| `available_count` | integer | min 0 |
| `version` | int64 | min 0 |

### SeatMap

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `event_id` | uuid | — |
| `plan` | object / null | — |
| `seats` | Seat[] | — |

### Availability

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `event_id` | uuid | — |
| `event_version` | integer | — |
| `server_now` | date-time | — |
| `orderable` | boolean | — |
| `reason_code` | string / null | — |
| `offers` | object[] | — |
| `available_seats` | object[] | — |

### Page

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `slug` | string | — |
| `version` | int64 | min 0 |
| `title_ru` | string | длина ≤ 200 |
| `title_en` | string | длина ≤ 200 |
| `body_ru` | string | — |
| `body_en` | string | — |
| `published_at` | date-time / null | — |

### CSRF

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `csrf_token` | string | — |

### RequestCodeInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `email` | email | обязательно |
| `locale` | string | необязательно; ru, en |

### OTPRequested

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `detail` | string | — |
| `expires_in` | integer | 600 |
| `resend_after` | integer | 60 |

### VerifyCodeInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `email` | email | обязательно |
| `locale` | string | необязательно; ru, en |
| `code` | string | обязательно |

### Profile

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `email` | email | — |
| `name` | string | длина ≤ 100 |
| `phone` | string | длина ≤ 16 |
| `locale` | string | ru, en; длина ≤ 2 |
| `email_verified_at` | date-time / null | — |

### StaffLoginInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `email` | email | обязательно |
| `password` | string | обязательно; длина ≤ 128 |

### StaffLoginResult

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `email` | email | — |
| `staff_role` | string | MANAGER, ADMIN |

### Empty

| Поле | Тип | Обязательность / варианты |
|---|---|---|

### ProfileInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `name` | string | необязательно; длина ≤ 100 |
| `phone` | string | необязательно; длина ≤ 16 |
| `locale` | string | необязательно; ru, en; длина ≤ 2 |

### StartEmailChangeInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `new_email` | email | обязательно |

### EmailChangeStarted

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `detail` | string | — |
| `expires_in` | integer | 600 |

### ConfirmEmailChangeInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `old_code` | string | обязательно |
| `new_code` | string | обязательно |

### StaffUser

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `email` | email | — |
| `name` | string | длина ≤ 100 |
| `phone` | string | длина ≤ 16 |
| `locale` | string | ru, en; длина ≤ 2 |
| `staff_role` | string | длина ≤ 7 |
| `is_active` | boolean | — |

### StaffUserInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `email` | email | обязательно |
| `name` | string | необязательно; длина ≤ 100 |
| `phone` | string | необязательно; длина ≤ 16 |
| `locale` | string | необязательно; ru, en; длина ≤ 2 |
| `staff_role` | string | обязательно; длина ≤ 7 |
| `password` | string | обязательно |
| `is_active` | boolean | необязательно |

### PreviewInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `event_id` | uuid | обязательно |
| `selection` | SelectionInput | обязательно |

### PreviewResult

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `event_id` | uuid | — |
| `total_minor` | integer | — |
| `currency` | string | RUB |
| `event_version` | integer | — |
| `offer_versions` | object | — |
| `items` | PublicSelectionItem[] | — |
| `server_now` | date-time | — |

### CreateHoldInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `event_id` | uuid | обязательно |
| `selection` | SelectionInput | обязательно |
| `expected_total_minor` | int64 | обязательно; min 1 |
| `expected_offer_versions` | object | необязательно |

### Hold

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `event` | uuid | — |
| `quote` | uuid / null | — |
| `status` | string | — |
| `expires_at` | date-time | — |
| `server_now` | date-time | — |
| `total_minor` | int64 | min 0 |
| `currency` | string | RUB |
| `items` | HoldItem[] | — |

### CreateOrderInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `hold_id` | uuid | обязательно |
| `fan_id_answer` | string | необязательно; HAS_FAN_ID, NEEDS_HELP, NOT_SURE |
| `comment` | string | необязательно; длина ≤ 2000 |
| `accepted_documents` | object | необязательно |

### Order

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `number` | string | длина ≤ 25 |
| `event` | uuid | — |
| `origin` | string | SITE_DIRECT, SITE_REQUEST; длина ≤ 12 |
| `order_state` | string | NEW, IN_PROGRESS, CONFIRMED, COMPLETED, REJECTED, CANCELLED; длина ≤ 11 |
| `payment_state` | string | UNPAID, PARTIAL, PAID, PARTIALLY_REFUNDED, REFUNDED |
| `delivery_state` | string | NOT_SENT, PARTIALLY_SENT, SENT |
| `sent_count` | integer | — |
| `customer_name` | string | длина ≤ 100 |
| `customer_phone` | string | длина ≤ 16 |
| `customer_email` | email | — |
| `customer_comment` | string | длина ≤ 2000 |
| `total_minor` | int64 | min 0 |
| `currency` | string | RUB |
| `payment` | PublicMoney | — |
| `event_snapshot` | object | — |
| `fan_id_answer` | string | HAS_FAN_ID, NEEDS_HELP, NOT_SURE; длина ≤ 12 |
| `fan_id_help_state` | string | NOT_NEEDED, REQUESTED, IN_PROGRESS, INSTRUCTED; длина ≤ 12 |
| `delivery_due_at` | date-time | — |
| `items` | OrderItem[] | — |
| `history` | OrderHistory[] | — |
| `cases` | Case[] | — |
| `created_at` | date-time | — |
| `updated_at` | date-time | — |
| `version` | int64 | min 0 |

### CreateCaseInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `kind` | string | необязательно; REFUND_REQUEST, CANCEL_REQUEST, DELIVERY_ISSUE, OTHER |
| `item_ids` | string[] | необязательно |
| `reason` | string | обязательно; длина ≤ 2000 |
| `requested_minor` | int64 / null | необязательно; min 1 |

### Case

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `order` | uuid | — |
| `kind` | string | REFUND_REQUEST, CANCEL_REQUEST, DELIVERY_ISSUE, OTHER; длина ≤ 14 |
| `items` | string[] | — |
| `reason` | string | длина ≤ 2000 |
| `requested_minor` | int64 / null | min 0 |
| `approved_minor` | int64 / null | min 0 |
| `status` | string | NEW, IN_PROGRESS, NEED_INFO, APPROVED, REJECTED, CLOSED; длина ≤ 11 |
| `public_response` | string | — |
| `decided_at` | date-time / null | — |
| `created_at` | date-time | — |
| `version` | int64 | min 0 |

### CreateRequestInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `event_id` | uuid / null | необязательно |
| `custom_event_name` | string | необязательно; длина ≤ 250 |
| `city` | string | необязательно; длина ≤ 100 |
| `desired_date` | date / null | необязательно |
| `quantity` | int64 | обязательно; min 1; max 100 |
| `preferences` | string | необязательно; длина ≤ 500 |
| `together_required` | boolean | необязательно |
| `budget_minor` | int64 / null | необязательно; min 1 |
| `comment` | string | необязательно; длина ≤ 2000 |
| `accepted_documents` | object | необязательно |

### Request

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `number` | string | длина ≤ 25 |
| `event` | uuid / null | — |
| `custom_event_name` | string | длина ≤ 250 |
| `city` | string | длина ≤ 100 |
| `desired_date` | date / null | — |
| `quantity` | int64 | min 0 |
| `preferences` | string | длина ≤ 500 |
| `together_required` | boolean | — |
| `budget_minor` | int64 / null | min 0 |
| `comment` | string | длина ≤ 2000 |
| `status` | string | NEW, IN_PROGRESS, OFFERED, CONVERTED, CANCELLED, REJECTED; длина ≤ 11 |
| `customer_name` | string | длина ≤ 100 |
| `customer_email` | email | — |
| `customer_phone` | string | длина ≤ 16 |
| `public_response` | string | — |
| `quotes` | Quote[] | — |
| `created_at` | date-time | — |
| `updated_at` | date-time | — |
| `version` | int64 | min 0 |

### VersionActionInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `expected_version` | int64 | обязательно; min 1 |
| `reason` | string | необязательно; длина ≤ 2000 |

### QuoteCheckoutInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `expected_total_minor` | int64 | обязательно; min 1 |

### CategoryInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `slug` | string | обязательно |
| `name_ru` | string | обязательно; длина ≤ 100 |
| `name_en` | string | обязательно; длина ≤ 100 |
| `kind` | string | обязательно; SPORT, CONCERT, OTHER; длина ≤ 7 |
| `parent` | uuid / null | необязательно |
| `is_active` | boolean | необязательно |
| `sort_order` | int64 | необязательно; min 0 |

### ParticipantInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `name_ru` | string | обязательно; длина ≤ 200 |
| `name_en` | string | обязательно; длина ≤ 200 |
| `kind` | string | обязательно; TEAM, ARTIST, OTHER; длина ≤ 10 |

### VenueInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `name_ru` | string | обязательно; длина ≤ 200 |
| `name_en` | string | обязательно; длина ≤ 200 |
| `country` | string | обязательно; длина ≤ 2 |
| `city` | string | обязательно; длина ≤ 100 |
| `city_en` | string | необязательно; длина ≤ 100 |
| `address` | string | обязательно; длина ≤ 300 |
| `address_en` | string | необязательно; длина ≤ 300 |
| `timezone` | string | необязательно; длина ≤ 64 |

### StaffEvent

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `slug` | string | длина ≤ 200 |
| `title_ru` | string | длина ≤ 250 |
| `title_en` | string | длина ≤ 250 |
| `description_ru` | string | — |
| `description_en` | string | — |
| `category` | uuid | — |
| `venue` | uuid | — |
| `participants` | string[] | — |
| `seating_plan` | uuid / null | — |
| `start_at` | date-time / null | — |
| `date_tba` | boolean | — |
| `sale_deadline` | date-time / null | — |
| `status` | string | SCHEDULED, POSTPONED, CANCELLED, FINISHED; длина ≤ 10 |
| `visibility` | string | PUBLIC, UNLISTED; длина ≤ 8 |
| `is_published` | boolean | — |
| `image` | string | — |
| `image_rights_source` | string | длина ≤ 500 |
| `image_rights_confirmed` | boolean | — |
| `fan_id_required` | boolean / null | — |
| `fan_id_description_ru` | string | — |
| `fan_id_description_en` | string | — |
| `refund_policy_ru` | string | — |
| `refund_policy_en` | string | — |
| `refund_policy_approved` | boolean | — |
| `late_delivery_due_at` | date-time / null | — |
| `version` | int64 | min 0 |

### StaffEventInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `slug` | string | обязательно; длина ≤ 200 |
| `title_ru` | string | обязательно; длина ≤ 250 |
| `title_en` | string | обязательно; длина ≤ 250 |
| `description_ru` | string | необязательно |
| `description_en` | string | необязательно |
| `category` | uuid | обязательно |
| `venue` | uuid | обязательно |
| `participants` | string[] | необязательно |
| `seating_plan` | uuid / null | необязательно |
| `start_at` | date-time / null | необязательно |
| `date_tba` | boolean | необязательно |
| `sale_deadline` | date-time / null | необязательно |
| `status` | string | необязательно; SCHEDULED, POSTPONED, CANCELLED, FINISHED; длина ≤ 10 |
| `visibility` | string | необязательно; PUBLIC, UNLISTED; длина ≤ 8 |
| `is_published` | boolean | необязательно |
| `image_rights_source` | string | необязательно; длина ≤ 500 |
| `image_rights_confirmed` | boolean | необязательно |
| `fan_id_required` | boolean / null | необязательно |
| `fan_id_description_ru` | string | необязательно |
| `fan_id_description_en` | string | необязательно |
| `refund_policy_ru` | string | необязательно |
| `refund_policy_en` | string | необязательно |
| `refund_policy_approved` | boolean | необязательно |
| `late_delivery_due_at` | date-time / null | необязательно |
| `expected_version` | int64 | необязательно; min 1 |

### Plan

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `venue` | uuid | — |
| `name` | string | длина ≤ 200 |
| `image` | string | — |
| `rights_source` | string | длина ≤ 500 |
| `rights_confirmed` | boolean | — |
| `status` | string | DRAFT, PUBLISHED, ARCHIVED; длина ≤ 10 |
| `version` | int64 | min 0 |

### PlanInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `venue` | uuid | обязательно |
| `name` | string | обязательно; длина ≤ 200 |
| `rights_source` | string | необязательно; длина ≤ 500 |
| `rights_confirmed` | boolean | необязательно |
| `expected_version` | int64 | необязательно; min 1 |

### Seat

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `plan` | uuid | — |
| `sector` | string | длина ≤ 50 |
| `row` | string | длина ≤ 30 |
| `number` | string | длина ≤ 30 |
| `x` | string | — |
| `y` | string | — |
| `adjacency_group` | string | длина ≤ 80 |
| `adjacency_position` | int64 / null | min 0 |

### SeatInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `plan` | uuid | обязательно |
| `sector` | string | обязательно; длина ≤ 50 |
| `row` | string | обязательно; длина ≤ 30 |
| `number` | string | обязательно; длина ≤ 30 |
| `x` | string | обязательно |
| `y` | string | обязательно |
| `adjacency_group` | string | необязательно; длина ≤ 80 |
| `adjacency_position` | int64 / null | необязательно; min 0 |

### Supplier

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `name` | string | длина ≤ 200 |
| `contact` | string | длина ≤ 500 |
| `notes` | string | — |
| `is_active` | boolean | — |

### SupplierInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `name` | string | обязательно; длина ≤ 200 |
| `contact` | string | необязательно; длина ≤ 500 |
| `notes` | string | необязательно |
| `is_active` | boolean | необязательно |

### StaffOffer

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `event` | uuid | — |
| `name_ru` | string | длина ≤ 200 |
| `name_en` | string | длина ≤ 200 |
| `description_ru` | string | — |
| `description_en` | string | — |
| `sale_price_minor` | int64 / null | min 0 |
| `kind` | string | SEAT, CATEGORY, STANDING; длина ≤ 8 |
| `mode` | string | AVAILABLE, REQUEST; длина ≤ 9 |
| `is_active` | boolean | — |
| `version` | int64 | min 0 |

### StaffOfferInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `event` | uuid | обязательно |
| `name_ru` | string | обязательно; длина ≤ 200 |
| `name_en` | string | обязательно; длина ≤ 200 |
| `description_ru` | string | необязательно |
| `description_en` | string | необязательно |
| `sale_price_minor` | int64 / null | необязательно; min 0 |
| `kind` | string | обязательно; SEAT, CATEGORY, STANDING; длина ≤ 8 |
| `mode` | string | необязательно; AVAILABLE, REQUEST; длина ≤ 9 |
| `is_active` | boolean | необязательно |
| `expected_version` | int64 | необязательно; min 1 |

### StaffUnit

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `event` | uuid | — |
| `offer` | uuid | — |
| `seat` | uuid / null | — |
| `supplier` | uuid / null | — |
| `purchase_price_minor` | int64 / null | min 0 |
| `supplier_reference` | string | длина ≤ 200 |
| `stock_basis` | string | OWNED, EXCLUSIVE_ALLOCATION; длина ≤ 20 |
| `allocation_until` | date-time / null | — |
| `status` | string | AVAILABLE, CHECKOUT_HELD, ORDER_HELD, SOLD, BLOCKED; длина ≤ 13 |
| `internal_notes` | string | — |
| `version` | int64 | min 0 |

### StaffUnitInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `event` | uuid | обязательно |
| `offer` | uuid | обязательно |
| `seat` | uuid / null | необязательно |
| `supplier` | uuid / null | необязательно |
| `purchase_price_minor` | int64 / null | необязательно; min 0 |
| `supplier_reference` | string | необязательно; длина ≤ 200 |
| `stock_basis` | string | необязательно; OWNED, EXCLUSIVE_ALLOCATION; длина ≤ 20 |
| `allocation_until` | date-time / null | необязательно |
| `internal_notes` | string | необязательно |
| `expected_version` | int64 | необязательно; min 1 |

### EventImageInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `image` | binary | обязательно |
| `rights_source` | string | обязательно; длина ≤ 500 |
| `rights_confirmed` | boolean | обязательно |
| `expected_version` | int64 | обязательно; min 1 |

### PlanImageInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `image` | binary | обязательно |
| `rights_source` | string | обязательно; длина ≤ 500 |
| `rights_confirmed` | boolean | обязательно |
| `expected_version` | int64 | обязательно; min 1 |

### RowInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `sector` | string | обязательно; длина ≤ 50 |
| `row` | string | обязательно; длина ≤ 30 |
| `numbers` | string[] | обязательно |
| `x1` | string | обязательно; min 0; max 1 |
| `y1` | string | обязательно; min 0; max 1 |
| `x2` | string | обязательно; min 0; max 1 |
| `y2` | string | обязательно; min 0; max 1 |
| `adjacency_group` | string | необязательно; длина ≤ 80 |

### PlanPreview

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `plan` | Plan | — |
| `seats` | Seat[] | — |

### UnitBlockInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `expected_version` | int64 | обязательно; min 1 |
| `reason` | string | необязательно; длина ≤ 2000 |
| `confirmed_valid` | boolean | необязательно |

### RenewAllocationInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `expected_version` | int64 | обязательно; min 1 |
| `reason` | string | обязательно; длина ≤ 2000 |
| `allocation_until` | date-time | обязательно |
| `confirmed_valid` | boolean | обязательно |

### StaffOrder

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `number` | string | длина ≤ 25 |
| `event` | uuid | — |
| `origin` | string | SITE_DIRECT, SITE_REQUEST; длина ≤ 12 |
| `order_state` | string | NEW, IN_PROGRESS, CONFIRMED, COMPLETED, REJECTED, CANCELLED; длина ≤ 11 |
| `payment_state` | string | UNPAID, PARTIAL, PAID, PARTIALLY_REFUNDED, REFUNDED |
| `delivery_state` | string | NOT_SENT, PARTIALLY_SENT, SENT |
| `sent_count` | integer | — |
| `customer_name` | string | длина ≤ 100 |
| `customer_phone` | string | длина ≤ 16 |
| `customer_email` | email | — |
| `customer_comment` | string | длина ≤ 2000 |
| `total_minor` | int64 | min 0 |
| `currency` | string | RUB |
| `payment` | PublicMoney | — |
| `event_snapshot` | object | — |
| `fan_id_answer` | string | HAS_FAN_ID, NEEDS_HELP, NOT_SURE; длина ≤ 12 |
| `fan_id_help_state` | string | NOT_NEEDED, REQUESTED, IN_PROGRESS, INSTRUCTED; длина ≤ 12 |
| `delivery_due_at` | date-time | — |
| `items` | StaffOrderItem[] | — |
| `history` | StaffHistory[] | — |
| `cases` | StaffCase[] | — |
| `created_at` | date-time | — |
| `updated_at` | date-time | — |
| `version` | int64 | min 0 |
| `user` | uuid | — |
| `manager` | uuid / null | — |
| `review_due_at` | date-time | — |
| `settlement_due_at` | date-time / null | — |
| `first_contact_at` | date-time / null | — |
| `confirmed_at` | date-time / null | — |
| `first_paid_at` | date-time / null | — |
| `internal_notes` | string | — |
| `ticket_request` | uuid / null | — |
| `quote` | uuid / null | — |
| `deliveries` | Delivery[] | — |
| `financial_entries` | FinancialEntry[] | — |

### CancelOrderInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `expected_version` | int64 | обязательно; min 1 |
| `reason` | string | обязательно; длина ≤ 2000 |
| `no_pending_settlements` | boolean | необязательно |

### ContactInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `expected_version` | int64 | обязательно; min 1 |
| `note` | string | необязательно; длина ≤ 2000 |

### OrderOperationsInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `expected_version` | int64 | обязательно; min 1 |
| `manager_id` | uuid | необязательно |
| `internal_notes` | string | необязательно; длина ≤ 5000 |
| `review_due_at` | date-time | необязательно |
| `settlement_due_at` | date-time / null | необязательно |
| `delivery_due_at` | date-time | необязательно |
| `fan_id_help_state` | string | необязательно; NOT_NEEDED, REQUESTED, IN_PROGRESS, INSTRUCTED |

### UpdateItemCostInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `expected_version` | int64 | обязательно; min 1 |
| `reason` | string | обязательно; длина ≤ 2000 |
| `purchase_price_minor` | int64 | обязательно; min 0 |
| `zero_confirmed` | boolean | необязательно |

### FinancialEntry

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `order` | uuid | — |
| `order_version` | int64 | — |
| `kind` | string | PAYMENT, CUSTOMER_REFUND, DIRECT_EXPENSE, SUPPLIER_REFUND; длина ≤ 15 |
| `amount_minor` | int64 | min 0 |
| `occurred_at` | date-time | — |
| `method` | string | BANK_CARD, SBP, BANK_TRANSFER, CASH, OTHER; длина ≤ 13 |
| `reference` | string | длина ≤ 200 |
| `created_by` | uuid / null | — |
| `notes` | string | — |
| `direction` | string | NORMAL, REVERSAL; длина ≤ 8 |
| `reversal_of` | uuid / null | — |
| `refund_case` | uuid / null | — |
| `created_at` | date-time | — |

### RecordPaymentInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `expected_version` | int64 | обязательно; min 1 |
| `amount_minor` | int64 | обязательно; min 1 |
| `occurred_at` | date-time | обязательно |
| `method` | string | обязательно; BANK_CARD, SBP, BANK_TRANSFER, CASH, OTHER |
| `reference` | string | обязательно; длина ≤ 200 |
| `notes` | string | необязательно; длина ≤ 2000 |
| `kind` | string | обязательно; PAYMENT, DIRECT_EXPENSE, SUPPLIER_REFUND |

### ReverseEntryInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `expected_version` | int64 | обязательно; min 1 |
| `occurred_at` | date-time | обязательно |
| `reason` | string | обязательно; длина ≤ 2000 |

### Delivery

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `order` | uuid | — |
| `order_version` | int64 | — |
| `items` | string[] | — |
| `recipient_email` | email | — |
| `sent_at` | date-time | — |
| `sent_by` | uuid | — |
| `note` | string | — |
| `message_id` | string | длина ≤ 200 |
| `status` | string | SENT, VOIDED; длина ≤ 6 |
| `void_reason` | string | — |
| `voided_at` | date-time / null | — |
| `created_at` | date-time | — |

### RecordDeliveryInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `expected_version` | int64 | обязательно; min 1 |
| `item_ids` | string[] | обязательно |
| `recipient_email` | email | обязательно |
| `sent_at` | date-time | обязательно |
| `note` | string | необязательно; длина ≤ 2000 |
| `message_id` | string | необязательно; длина ≤ 200 |

### StaffRequest

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `number` | string | длина ≤ 25 |
| `event` | uuid / null | — |
| `custom_event_name` | string | длина ≤ 250 |
| `city` | string | длина ≤ 100 |
| `desired_date` | date / null | — |
| `quantity` | int64 | min 0 |
| `preferences` | string | длина ≤ 500 |
| `together_required` | boolean | — |
| `budget_minor` | int64 / null | min 0 |
| `comment` | string | длина ≤ 2000 |
| `status` | string | NEW, IN_PROGRESS, OFFERED, CONVERTED, CANCELLED, REJECTED; длина ≤ 11 |
| `customer_name` | string | длина ≤ 100 |
| `customer_email` | email | — |
| `customer_phone` | string | длина ≤ 16 |
| `public_response` | string | — |
| `quotes` | StaffQuote[] | — |
| `created_at` | date-time | — |
| `updated_at` | date-time | — |
| `version` | int64 | min 0 |
| `user` | uuid | — |
| `manager` | uuid / null | — |
| `internal_notes` | string | — |

### RequestActionInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `expected_version` | int64 | обязательно; min 1 |
| `manager_id` | uuid | необязательно |
| `event_id` | uuid | необязательно |
| `internal_notes` | string | необязательно; длина ≤ 5000 |
| `public_response` | string | необязательно; длина ≤ 2000 |
| `status` | string | необязательно; IN_PROGRESS, CANCELLED, REJECTED |

### CreateQuoteInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `expected_version` | int64 | обязательно; min 1 |
| `event_id` | uuid | обязательно |
| `expires_at` | date-time | обязательно |
| `public_comment` | string | необязательно; длина ≤ 2000 |
| `items` | QuoteItemInputInput[] | обязательно |
| `together_confirmed` | boolean | необязательно |

### StaffQuote

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `ticket_request` | uuid | — |
| `event` | QuoteEvent | — |
| `version` | int64 | min 0 |
| `status` | string | — |
| `expires_at` | date-time | — |
| `total_minor` | int64 | min 0 |
| `public_comment` | string | длина ≤ 2000 |
| `items` | StaffQuoteItem[] | — |
| `sent_at` | date-time / null | — |
| `together_confirmed` | boolean | — |
| `request_version` | int64 | — |

### StaffCase

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `order` | uuid | — |
| `kind` | string | REFUND_REQUEST, CANCEL_REQUEST, DELIVERY_ISSUE, OTHER; длина ≤ 14 |
| `items` | string[] | — |
| `reason` | string | длина ≤ 2000 |
| `requested_minor` | int64 / null | min 0 |
| `approved_minor` | int64 / null | min 0 |
| `status` | string | NEW, IN_PROGRESS, NEED_INFO, APPROVED, REJECTED, CLOSED; длина ≤ 11 |
| `public_response` | string | — |
| `decided_at` | date-time / null | — |
| `created_at` | date-time | — |
| `version` | int64 | min 0 |
| `user` | uuid | — |
| `internal_notes` | string | — |
| `decided_by` | uuid / null | — |
| `order_version` | int64 | — |

### CaseDecisionInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `expected_version` | int64 | обязательно; min 1 |
| `decision` | string | обязательно; APPROVED, REJECTED, IN_PROGRESS, NEED_INFO, CLOSED |
| `public_response` | string | обязательно; длина ≤ 2000 |
| `amount_minor` | int64 | необязательно; min 1 |
| `internal_notes` | string | необязательно; длина ≤ 2000 |

### ApproveRefundInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `expected_version` | int64 | обязательно; min 1 |
| `amount_minor` | int64 | обязательно; min 1 |
| `public_response` | string | обязательно; длина ≤ 2000 |
| `internal_notes` | string | необязательно; длина ≤ 2000 |

### RejectRefundInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `expected_version` | int64 | обязательно; min 1 |
| `public_response` | string | обязательно; длина ≤ 2000 |
| `internal_notes` | string | необязательно; длина ≤ 2000 |

### MoneyOperationInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `expected_version` | int64 | обязательно; min 1 |
| `amount_minor` | int64 | обязательно; min 1 |
| `occurred_at` | date-time | обязательно |
| `method` | string | обязательно; BANK_CARD, SBP, BANK_TRANSFER, CASH, OTHER |
| `reference` | string | обязательно; длина ≤ 200 |
| `notes` | string | необязательно; длина ≤ 2000 |

### ClientEventInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `event_id` | uuid | обязательно |
| `client_event_id` | uuid | обязательно |
| `event_type` | string | обязательно; EVENT_VIEW, TICKETS_VIEW, TICKET_SELECTED, CHECKOUT_STARTED |
| `analytics_consent` | boolean | обязательно |

### EventIdResult

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |

### Dashboard

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `currency` | string | — |
| `generated_at` | date-time | — |
| `orders_created` | integer | — |
| `cancelled_orders` | integer | — |
| `successful_sales` | SalesMetrics | — |
| `paid_cohort_including_cancelled` | SalesMetrics | — |
| `by_event` | object[] | — |
| `by_day` | object[] | — |
| `work_queue` | object | — |

### Cashflow

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `currency` | string | — |
| `received_minor` | int64 | — |
| `customer_refunds_minor` | int64 | — |
| `direct_expenses_minor` | int64 | — |
| `supplier_refunds_minor` | int64 | — |
| `net_cashflow_minor` | int64 | — |

### Funnel

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `cohort` | string | — |
| `note` | string | — |
| `web` | FunnelStep[] | — |
| `orders` | FunnelStep[] | — |
| `requests` | FunnelStep[] | — |

### Privacy

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `kind` | string | ACCESS, CORRECT, DELETE; длина ≤ 12 |
| `comment` | string | длина ≤ 2000 |
| `status` | string | NEW, IN_PROGRESS, CLOSED; длина ≤ 12 |
| `response` | string | — |
| `created_at` | date-time | — |
| `updated_at` | date-time | — |

### CreatePrivacyInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `kind` | string | обязательно; ACCESS, CORRECT, DELETE |
| `comment` | string | необязательно; длина ≤ 2000 |

### StaffPage

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `slug` | string | — |
| `version` | int64 | min 0 |
| `title_ru` | string | длина ≤ 200 |
| `title_en` | string | длина ≤ 200 |
| `body_ru` | string | — |
| `body_en` | string | — |
| `published_at` | date-time / null | — |
| `is_published` | boolean | — |
| `approved_by` | uuid / null | — |

### StaffPageInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `slug` | string | обязательно |
| `version` | int64 | необязательно; min 0 |
| `title_ru` | string | обязательно; длина ≤ 200 |
| `title_en` | string | обязательно; длина ≤ 200 |
| `body_ru` | string | обязательно |
| `body_en` | string | обязательно |

### StaffPrivacy

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `user` | uuid | — |
| `kind` | string | ACCESS, CORRECT, DELETE; длина ≤ 12 |
| `comment` | string | длина ≤ 2000 |
| `status` | string | NEW, IN_PROGRESS, CLOSED; длина ≤ 12 |
| `response` | string | — |
| `created_at` | date-time | — |
| `updated_at` | date-time | — |

### StaffPrivacyInput

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `status` | string | необязательно; NEW, IN_PROGRESS, CLOSED; длина ≤ 12 |
| `response` | string | необязательно |

### Email

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `id` | uuid | — |
| `recipient` | email | — |
| `subject` | string | длина ≤ 250 |
| `body` | string | — |
| `status` | string | PENDING, SENDING, SENT, FAILED; длина ≤ 8 |
| `attempts` | int64 | min 0 |
| `sent_at` | date-time / null | — |
| `object_id` | uuid / null | — |
| `error_code` | string | длина ≤ 40 |
| `created_at` | date-time | — |
| `updated_at` | date-time | — |

### Settings

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `currency` | string | RUB |
| `locales` | string[] | — |
| `public_forms_enabled` | boolean | — |
| `order_intake_enabled` | boolean | — |
| `online_payments_enabled` | boolean | — |
| `ticket_download_enabled` | boolean | — |
| `client_analytics_enabled` | boolean | — |
| `legal_ready` | boolean | — |
| `hold_seconds` | integer | — |
| `direct_order_limit` | integer | — |
| `request_limit` | integer | — |
| `legal_versions` | object | — |
| `contacts` | object | — |
| `configuration_source` | string | environment |
| `require_legal_acceptance` | boolean | — |

### Health

| Поле | Тип | Обязательность / варианты |
|---|---|---|
| `status` | string | ok, unavailable |

## Фильтры списков

`events/`, `staff/events/`: q (название RU/EN), category, venue, participant (UUID), city, date_from, date_to, status, ordering: start_at/-start_at/created_at/-created_at. Указанные даты фильтруют **время события**, не создание заказа. Публичный список содержит только опубликованные PUBLIC; CANCELLED/POSTPONED карточки могут оставаться информационными, но не допускают новый заказ.

`staff/orders/`: event, manager, user (UUID), state, q (номер заказа), from/to (created_at). Очередь просроченной выдачи — `staff/dashboard/summary/`; полный список можно отфильтровать по CONFIRMED и проверить delivery_state.

`staff/units/`: event, offer, supplier, status. `staff/offers/`: event. `staff/seats/`: plan. `staff/ticket-requests/`: status, manager. `staff/customers/`: q по email. Отчёты: from/to по ISO8601, event/category UUID. Дополнительные неизвестные query-параметры не меняют бизнес-логику.

## Прямой заказ: последовательность

1. Откройте каталог, карточку, offers, seat-map и availability. `orderable=false` означает «заявка менеджеру», даже при ненулевом остатке.
2. Войдите по коду, заполните name и международный phone через `PATCH me/`.
3. Передайте выбор в preview. При схеме: `{"mode":"SEATS","seat_ids":["<uuid>"]}`. Без схемы: `{"mode":"CATEGORY","offer_id":"<uuid>","quantity":2}`. Нельзя смешивать категории или выбирать количество вместо мест при наличии схемы.
4. Создайте Hold с total и offer_versions из preview. Билетные unit_id — внутренние; покупатель не отправляет их.
5. Покажите `expires_at` относительно `server_now`. Refresh не продлевает срок. Замена выбора атомарна и сохраняет первоначальный expires_at. При 409 покажите конфликт и обновите наличие.
6. Создайте Order из hold_id, ответа Fan ID и версий принятых документов. Не передавайте цену, закупку, поставщика, чужие контакты, user_id или статус.
7. После успешного ответа Order таймер оформления больше не действует. Переходите в карточку заказа; UI не должен вызывать release для него.

Пример резервирования (подставьте UUID и суммы фактического preview):

```json
{
  "event_id": "<event UUID>",
  "selection": {"mode": "CATEGORY", "offer_id": "<offer UUID>", "quantity": 2},
  "expected_total_minor": 200000,
  "expected_offer_versions": {"<offer UUID>": 1}
}
```

Пример отправки заказа:

```json
{
  "hold_id": "<hold UUID>",
  "fan_id_answer": "NEEDS_HELP",
  "accepted_documents": {"privacy": 1, "offer": 1, "refund-policy": 1},
  "comment": "Предпочитаю связь по email"
}
```

Версии документов берутся из public/config, не зашиваются в frontend. В локальном demo режиме без юридических страниц используйте `{}`. При Fan ID=false ответ можно не отправлять; при true нужны HAS_FAN_ID/NEEDS_HELP/NOT_SURE. Форм загрузки документов нет. Свободные комментарии должны содержать предупреждение **не присылать паспорт, СНИЛС, документы и данные Госуслуг**.

## Заявка и предложение

Без события: `{"custom_event_name":"Желаемое мероприятие","city":"Москва","quantity":2,"budget_minor":2000000,"together_required":true,"accepted_documents":{}}`. Бюджет — общий, не на один билет. Заявка не удерживает запас.

Менеджер берёт заявку в работу, создаёт непубличный Event либо связывает существующий, добавляет реальные TicketUnit, затем POST quotes с полным списком `{ticket_unit_id,price_minor}`. Публичный комментарий должен отражать существенные согласованные условия. Для together_required нужно together_confirmed и проверка соседства; отсутствие данных о рядах не превращает пожелание в автоматическую гарантию.

Созданный Quote — DRAFT. POST send использует версию заявки из request_version; отправленный Quote неизменяем. Для изменения создавайте следующую версию: отправка новой отзывает предыдущую. Срок не резервирует билеты. Клиент получает Quote внутри собственного TicketRequest; Event может быть UNLISTED, поэтому публичная карточка по slug для него вернёт 404.

Клиент POST start-checkout с expected_total_minor. Появляется обычный Hold, затем обычный Order. ACCEPTED/CONVERTED устанавливаются при успешном Order, а не при открытии предложения. Одно предложение не создаёт два заказа.

## Сотрудник: деньги, выдача, возврат

Рабочий путь: start → contact → confirm → financial-entries (PAYMENT) → deliveries → complete. Перед каждым действием берите актуальную Order.version. Деньги фиксируются **после фактического получения вне сайта**. BANK_CARD/SBP — только текстовый способ учёта; это не интеграция банка.

```json
{
  "expected_version": 3,
  "kind": "PAYMENT",
  "amount_minor": 200000,
  "occurred_at": "2026-10-01T12:00:00Z",
  "method": "BANK_TRANSFER",
  "reference": "Номер фактического подтверждения"
}
```

В примерах occurred_at иллюстративен: используйте реальное время между созданием заказа и текущим временем сервера. Частичная сумма даёт PARTIAL. Переплата отклоняется. Корректировка — reverse с причиной и затем правильная запись, не PATCH суммы.

Отправка: `item_ids` — идентификаторы **OrderItem** из заказа, не Seat/HoldItem/TicketUnit. Сотрудник сначала вручную отправляет письмо с билетами, затем делает POST deliveries. recipient_email может быть email-снимком заказа или текущим подтверждённым email покупателя. Выданные позиции считаются по множеству ID: повтор 2 из 4 остаётся 2 из 4. Обычная выдача до полной оплаты запрещена. Backend не отправляет PDF и не хранит TicketFile.

Возврат: клиент создаёт Case; менеджер approve (Case.version, amount_minor, public_response); затем settle (Order.version, фактические amount_minor, occurred_at, method, reference). APPROVED не значит REFUNDED. Можно фиксировать возврат частями до approved_minor. После полного исполнения решения выбранные позиции становятся неактивными. SENT/возвращённые единицы блокируются; только отдельное проверенное unblock разрешает повторную продажу. Сторно возврата не возвращает билету доступность автоматически.

Отмена безопасного неоплаченного и неотправленного заказа требует no_pending_settlements=true. При наличии денег либо истории выдачи отмена блокирует запас и сохраняет все финансовые записи. COMPLETED возможен только для подтверждённого, оплаченного, непустого заказа с выданными активными позициями и без незакрытых обращений.

## Семантика аналитики

`successful_sales` — текущие неотменённые оплаченные заказы, сгруппированные по первой полной оплате; отменённые не считаются успехом. `paid_cohort_including_cancelled` сохраняет оплаченный оборот и возвраты даже закрытых заказов. `cashflow` считает фактические даты всех проводок. Эти показатели нельзя смешивать в одной сумме.

`turnover_minor = gross_turnover_minor − refunded_minor`. При unknown_cost_count>0 profit_minor=null, profit_complete=false. purchase_cost_minor тогда содержит только известную часть. Прибыль учитывает себестоимость всех позиций выбранной когорты, реальные возвраты, прямые расходы и возвраты от поставщика. Средний чек — net turnover / число заказов, округление до копейки.

В funnel отдельно возвращаются web, orders, requests. count — уникальные пути/заказы/заявки, не число кликов. conversion — **доля 0..1**, не проценты; при нулевом знаменателе null. Предыдущие обязательные шаги должны присутствовать. Для web важен порядок; серверные факты учитывают, что деньги могут быть получены до подтверждения. Исторический факт остаётся после исправления, поэтому воронка не равна текущим успешным продажам.

## Минимальный fetch-клиент

```javascript
async function api(path, {method = 'GET', body, key} = {}) {
  const headers = {};
  if (method !== 'GET') {
    const csrf = await fetch('/api/v1/auth/csrf/', {credentials: 'same-origin'});
    if (!csrf.ok) throw new Error('Не удалось получить CSRF');
    headers['X-CSRFToken'] = (await csrf.json()).csrf_token;
  }
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (key) headers['Idempotency-Key'] = key;
  const response = await fetch('/api/v1/' + path, {
    method, credentials: 'same-origin', headers,
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  if (response.status === 204) return null;
  const type = response.headers.get('content-type') || '';
  const data = type.includes('application/json') ? await response.json() : {message: 'Ошибка прокси или сети'};
  if (!response.ok) throw Object.assign(new Error(data.message || 'Ошибка API'), {status: response.status, data});
  return data;
}
// key сохраняется на время одной попытки оформления, включая сетевые повторы.
const orderKey = crypto.randomUUID();
```

Для multipart изображения не задавайте Content-Type вручную: браузер сформирует boundary; передайте FormData, CSRF и expected_version. В development используйте same-origin proxy Next.js к Django или открывайте backend на localhost:8000. CORS/JWT в этот MVP не добавлены.
