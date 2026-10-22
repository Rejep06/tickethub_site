# Проверки: автономные, компонентные и сквозные

## Автономные тесты

`npm test` строго компилирует 13 независимых TypeScript-модулей и запускает Node test runner. Если локального TypeScript нет, скрипт может использовать уже установленный глобальный и печатает его версию. При отсутствии обоих честно падает.

Проверяются деньги, даты/таймер, безопасный next, media paths, whitelist хранения черновика, версии согласий, whitelist фильтров, координаты/ряды, HTTP-ошибки, CSRF/cookies/язык, 409/429/500, idempotency key при одинаковом/изменённом теле, потерянный ответ Hold, клиентский контракт OTP→Hold→Order, действия staff, частичная отправка и раздельные refund approval/settle.

Функция fetch в этих тестах подменяется. **Это не вызовы Django и не интеграционный тест PostgreSQL.** Успешные автономные тесты не доказывают корректность Next render, миграций, блокировки последнего места или email-доставки.

## Компонентные тесты

```bash
npm run test:components
```

Vitest/jsdom + Testing Library: 12 сценариев в `tests/components/critical.test.tsx`. Labels/errors, статус заказа, OTP, 401/403 guards, HoldClock, клавиатурный список мест, отправка 2 из 4, подтверждение оплаты, ошибка оплаты и недопустимая сумма. Next navigation и API services подменены. Нативный dialog в jsdom реализован тестовым shim; его реальное focus/Escape поведение требует браузера.

Эти тесты написаны, но в среде подготовки **не выполнены**. Их selectors и mock contracts были сверены с исходниками; это не эквивалент passed.

## Настоящие E2E

В `tests/e2e/live.spec.ts` четыре теста, без `page.route` и без mock backend. Условия: запущенный Next, настоящая Django/PostgreSQL, свежий demo seed в отдельной тестовой БД, правильный CSRF origin. Для Chromium:

```bash
npx playwright install chromium
E2E_BASE_URL=http://localhost:3000 npm run test:e2e
```

Два теста чтения открывают реальное событие и проверяют RU/EN, а один также меняет viewport 320/375/430/768/1024/1440. Demo slug по умолчанию `demo-category`; меняется через `E2E_EVENT_SLUG`. Эти проверки не являются полноценным accessibility или cross-browser audit.

Два изменяющих теста требуют `E2E_ALLOW_WRITES=1`; без него они явно skipped. Для покупателя нужны:

```dotenv
E2E_CUSTOMER_EMAIL=ваш-тестовый-email
E2E_OTP_FILE=/абсолютный/путь/к/временному-otp.txt
```

Запустите backend с console email, откройте `docker compose logs -f api`. После запроса кода тест ждёт до 120 секунд. Запишите **только новый код из письма на этот email** в `E2E_OTP_FILE`. Время изменения файла должно быть новее запроса; старый файл не принимается. Это операторский тест реальной OTP-доставки, а не endpoint обхода входа. После завершения удалите временный файл и приватные логи. Не добавляйте код в Git.

Для staff-теста нужны:

```dotenv
E2E_STAFF_EMAIL=реальный-test-staff-email
E2E_STAFF_PASSWORD=пароль-тестового-сотрудника
E2E_ORDER_ID=UUID-одноразового-заказа-в-NEW
```

Создайте этот заказ в той же тестовой БД, но не берите его в работу заранее. Тест делает password login, открывает Order и подтверждает Start. Повторный запуск на уже изменённом заказе — не валидная исходная фикстура. Новая БД/заказ предпочтительнее очистки рабочей истории.

Пример запуска Bash:

```bash
export E2E_BASE_URL=http://localhost:3000
export E2E_ALLOW_WRITES=1
# Остальные значения задавайте локально, не сохраняйте пароли в репозитории.
npm run test:e2e
```

PowerShell:

```powershell
$env:E2E_BASE_URL = 'http://localhost:3000'
$env:E2E_ALLOW_WRITES = '1'
npm run test:e2e
```

Пароли не поставляются. Trace/screenshots/video отключены в конфигурации, чтобы по умолчанию не сохранять содержимое входа и приватных страниц. Включайте запись только на тестовых данных с продуманным хранением отчётов.

## Релизный минимум, который ещё нужно выполнить

Настоящий full typecheck/lint/build; все component tests; реальные OTP/Hold/Order/Quote/staff/money/delivery/refund; конкурентная покупка последнего места на PostgreSQL; негативная проверка доступа к чужим заказам и admin API; восстановление после неопределённого результата; карты и формы на целевых экранах; keyboard/Safari/Android/iOS; Lighthouse/контраст; smoke после deployment/backup restore.

Список результатов хранится отдельно в `verification.md`. Не меняйте NOT RUN на PASSED на основании того, что тест написан или JSX синтаксически корректен.
