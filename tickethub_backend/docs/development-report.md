# Дополнение: PortalBilet + редактор схем

**Editor: CODED / UI CHECKED WITH STUBBED FETCH / DB UNVERIFIED.**
**PortalBilet: PARTIAL; actual coordinates/ticket mapping NOT IMPLEMENTED OR VERIFIED.**

96 автономных проверок прошли; 8 сценариев интерфейса прошли с тестовыми ответами API. 29 новых Django/PostgreSQL-тестов написаны, 0 выполнены. Запуск Django и миграций заблокирован отсутствующими зависимостями. Настоящие JSON PortalBilet получить не удалось (DNS/tool errors); адаптер bootstrap основан на предоставленном справочнике, не реальных fixtures.

Подробности и журналы: [portalbilet-and-editor.md](portalbilet-and-editor.md), `verification/additions/`.

---

## Ниже — исторический отчёт предыдущей версии

# Tickethub — отчёт разработки

Дата: 1 октября 2026. Основа: переданный `tickethub_stage2_blocked.zip`. Приоритет — текущая инструкция `docs/spec/04_current_instructions.txt`, затем Backend-ТЗ. Существующий проект продолжен; с нуля не заменялся.

## BACKEND STATUS

**CODE: COMPLETE для согласованного актуального перечня MVP.** Это означает, что сценарии написаны, а не что доказана их работоспособность в неизвестном окружении.

**VERIFICATION: PARTIALLY VERIFIED.** Автономные расчёты/проверки исходников исполнены; **Django / PostgreSQL / Docker runtime verification: BLOCKED**. Backend не имеет статуса FULLY VERIFIED и не допускается к реальной продаже без последующих проверок.

| Категория | Статус | Фактический результат |
|---|---|---|
| Прикладные модули | CODED | 9 apps, 29 моделей, 144 документированные операции API |
| Исходники Python | STATICALLY CHECKED | 175 файлов скомпилированы compileall; AST и явные локальные импорты проверены |
| Автономные проверки | EXECUTED / TESTED | 50 выполнено, 50 прошло, 0 ошибок |
| Django/DRF-тесты | CODED / BLOCKED | 187 тестовых методов написано; 0 исполнено |
| Настоящая конкуренция PostgreSQL | CODED / BLOCKED | TransactionTestCase с двумя соединениями и ожидаемыми 201/409 написан; не выполнен |
| Миграции | CODED / STATICALLY CHECKED / BLOCKED | 18 модулей; не применены, makemigrations не смог импортировать Django |
| API, Admin, seed_demo | CODED / BLOCKED | Команды запуска сделаны, выполнение приложения не началось из-за отсутствия Django |
| Docker/Compose/Nginx | CODED / STATICALLY CHECKED / BLOCKED | YAML/shell разобраны; реальных сборки, nginx -t и контейнеров не было |
| OpenAPI | CODED / STATICALLY CHECKED | Контракт написан по маршрутам/полям; YAML и внутренние ссылки проверены; не runtime-generated |
| Production/backup | CODED / BLOCKED | Настройки/HTTPS-ready конфигурация/pg_dump и инструкция restore; на сервер не развёрнуто |

## Что реализовано по этапам

| Этап | Сохранённый/добавленный результат | Проверка в этой среде |
|---|---|---|
| 2 | Исходные User/config/health/CSRF/request ID/errors сохранены, настройки расширены; Docker и миграции | Статика; запуск Django заблокирован |
| 3 | HMAC OTP, лимиты PostgreSQL, сессии клиента/сотрудника, CSRF, профиль, подтверждённая смена email | Исходники и написанные auth/access-тесты |
| 4 | RU/EN Events, Categories, Participants, Venues, схемы/места, безопасные изображения | Статика; catalog/plan/image-тесты написаны |
| 5 | Реальные TicketUnit, preview/hold/release, срок 600 сек, истечение без cron, блокировки и constraints | PG concurrency test написан, не выполнен |
| 6 | Order/OrderItem, неизменяемый клиентский снимок, постоянное закрепление, history/version/idempotency | Тесты заказов/доступа написаны |
| 7 | Подбор без Event, приватное событие, версии Quote, Quote→Hold→Order | Тесты заявок/конверсии написаны |
| 8 | Staff API и реальные Admin-формы, вызов services, права, очереди/сроки, закупка/поставщик | Admin/access-тесты написаны |
| 9 | Журнал фактических денег, частичная оплата, сторно, обращения/решения/возвраты, уникальная выдача | Чистые функции денег исполнены; ORM/API-тесты написаны |
| 10 | Продажи/денежные даты/события/периоды/CSV, простая воронка | Чистые функции воронки исполнены; ORM-отчёты не запускались |
| 11 | Полные тестовые файлы, production, HTTPS-ready Nginx, backup/restore, seed, verify, документы | Доступные статические проверки выполнены |

После невозможности установки разработка не остановилась на foundation: все приложения получили модели, сервисы/API/Admin там, где они нужны. Отдельного notifications app, Allocation, брокера, MFA-зависимости и фиктивного gateway нет. Новые зависимости объяснены в README.

## Actually tested

**50 standalone unittest методов**: 28 проверяют реальные чистые функции денег/выдачи/прибыли/воронки из production-модулей; 12 — чтение окружения/создание .env; 10 — статическую целостность исходников. Они не подменяют Django фальшивым ORM.

Последний лог: [offline-tests.log](verification/offline-tests.log). Отдельно [static-checks.json](verification/static-checks.json), [environment.json](verification/environment.json), [test-inventory.json](verification/test-inventory.json).

Проверены синтаксис Python/shell, YAML трёх Compose-файлов и OpenAPI, существование явных локальных импортов, совпадение имён модельных полей с migration operations, отсутствие циклов локальных зависимостей миграций и первичные ключи serialize=False. Это не эквивалент Django check или успешной миграции.

Первый автономный прогон обнаружил дефект **самой статической проверки**: она перезаписывала набор AddField при другом порядке обхода CreateModel. Проверка исправлена на объединение независимо от порядка файлов. Начальный лог сохранён: offline-tests-initial-failure.log. Финальный прогон — 50/50.

## Команды, действительно предпринятые, но заблокированные

```text
python manage.py makemigrations --check --dry-run --settings=config.settings.test
python manage.py migrate --noinput --settings=config.settings.test
python manage.py check --settings=config.settings.test
python manage.py test --noinput --verbosity=2 --settings=config.settings.test
python manage.py runserver 127.0.0.1:8000 --noreload --settings=config.settings.test
python manage.py seed_demo --settings=config.settings.test
sh scripts/verify_backend.sh
```

Первые шесть завершились exit code 1 **до работы команды**, с `ModuleNotFoundError: No module named 'django'`. Последняя завершилась exit code 1: `BLOCKED: Docker is not installed.` Это не семь упавших бизнес-тестов и не выполненная проверка базы.

Все stdout/exit codes: [runtime-attempts.json](verification/runtime-attempts.json) и соответствующие `migration-check.log`, `migrate.log`, `django-check.log`, `django-tests.log`, `runserver.log`, `seed-demo.log`, `docker-verify.log`.

## Tests

| Набор | Написано методов | Реально выполнено | Passed | Failed |
|---|---:|---:|---:|---:|
| Автономные | 50 | 50 | 50 | 0 |
| Django/DRF/PostgreSQL | 187 | 0 | — | — |
| Всего методов в исходниках | 237 | 50 | 50 | 0 среди выполненных |

Число методов получено по AST, это не заявленный результат обнаружения Django test runner. Один конкурентный тест входит в Django-число, а не считается второй раз. Детализация ниже.

| Файл Django tests | Методов |
|---|---:|
| `backend/analytics/tests/test_reports.py` | 11 |
| `backend/core/tests/test_api.py` | 11 |
| `backend/core/tests/test_integrations.py` | 11 |
| `backend/events/tests/test_catalog.py` | 13 |
| `backend/orders/tests/test_access_api.py` | 7 |
| `backend/orders/tests/test_delivery.py` | 9 |
| `backend/orders/tests/test_orders.py` | 18 |
| `backend/payments/tests/test_payments.py` | 13 |
| `backend/payments/tests/test_refunds.py` | 11 |
| `backend/ticket_requests/tests/test_requests_quotes.py` | 15 |
| `backend/tickets/tests/test_concurrency.py` | 1 |
| `backend/tickets/tests/test_reservations.py` | 16 |
| `backend/users/tests/test_admin.py` | 4 |
| `backend/users/tests/test_auth_api.py` | 21 |
| `backend/users/tests/test_email_change.py` | 5 |
| `backend/users/tests/test_models.py` | 15 |
| `backend/venues/tests/test_plans.py` | 6 |

## Migrations

18 migration modules, включая сохранённый исходный users/0001_initial.py. Остальные написаны вручную по моделям: сначала создание таблиц/локальных полей, затем межприложенные отношения, индексы и constraints; зависимости разделены, чтобы избежать циклов.

При сверке исправлены пропуск ForeignKey в первоначальном вспомогательном анализаторе и serialize=False у первичных ключей. Неиспользуемое поле replacement_of удалено из исходников и ещё **не применённых** миграций. Модель/миграция User не заменяется стандартным auth.User.

**Не подтверждены**: идентичность Django migration state, SQL PostgreSQL, constraints при реальном commit, начало с чистой БД. Verify проверяет их до следующего шага. Нет --fake или фиктивного SQLite-обхода. После первого развёртывания существующие миграции менять нельзя.

## External blockers

В среде автора нет Django, DRF, psycopg, phonenumbers, drf-spectacular, Gunicorn и исполняемых PostgreSQL/Docker. Попытка pip не получила доступных дистрибутивов (`dependencies-install.log`); сетевые попытки ранее также не позволили доставить пакеты. Pillow присутствует в среде как отдельная библиотека, но это не делает Django-приложение установленным. Никаких результатов PostgreSQL или SMTP не выдумано.

Реальный SMTP/домен/сертификат/сервер нужны для окончательной эксплуатационной проверки; код использует env и не содержит секретов. Их отсутствие не оставило бизнес-сервисы пустыми.

## Docker

Development: api+db. Verification: новый изолированный Compose project/volume и свежая БД на каждый запуск. Production: backend+db+nginx, TLS-ready, отдельные static/media, непривилегированная роль приложения PostgreSQL, явные migrations, healthchecks. Никаких Celery/Redis. Реальных сборки/старта/health/Admin входа Docker в этой среде **не было**.

requirements.lock намеренно отсутствует: production lock формируется только после реально успешных проверок из pip freeze. Development использует диапазоны и семейства образов; production требует указать проверенные digests. Конфигурация production готова к заполнению, а не объявляется развёрнутой.

## Main API

`/api/v1/events/`, `/auth/otp/request/`, `/auth/otp/verify/`, `/auth/staff/login/`, `/me/`, `/checkout/preview/`, `/checkout/holds/`, `/orders/`, `/ticket-requests/`, `/quotes/{id}/start-checkout/`, `/staff/...`; `/ops/`; `/health/live/`, `/health/ready/`. Все API-маршруты, auth, request/response/errors: [frontend-api.md](frontend-api.md).

## Known limitations и что не утверждается

Это кодово завершённый MVP по **последней упрощённой инструкции**, а не буквальная реализация всех более широких механизмов предыдущего архитектурного плана/v2. Нет автоматического переноса денег на новый состав заказа, отдельной enterprise-очереди, Journey/Big Data или внешних продаж. Настройки изменяются через env, юридические тексты не сочинены.

В этом окружении невозможно подтвердить отсутствие runtime-дефектов. Ни «один билет точно невозможно продать дважды в production», ни «все тесты прошли» не заявляются: есть реализация locks/constraints и написанный настоящий PostgreSQL-тест, который ещё должен быть выполнен.

OpenAPI authored по исходникам, не получен от работающего Django. Нет измерений нагрузки, проверки почтовой доставляемости и восстановления backup. Письмо после неопределённого SMTP-ответа может потребовать ручного retry и быть продублировано. Схемы/изображения требуют реальных прав. Произвольный комментарий не даёт гарантии автоматического распознавания случайно присланных документов; таких полей/загрузок не предусмотрено.

Фактические электронные билеты отправляет сотрудник, backend фиксирует факт. Next.js frontend не входит в поставку. Код не содержит production-секретов и не менял реальный сервер.

## Следующая обязательная проверка

Запустить `scripts/verify_backend.sh` в окружении с Docker/PyPI и свежей PostgreSQL. Исправить любые найденные Django/runtime-ошибки; затем повторить весь прогон с lock. Только после SMTP/staging/backup restore/manual end-to-end можно менять статус на VERIFIED и включать приём реальных заказов.

Будущее вне MVP: банковские карты, СБП API, TicketFile/скачивание из кабинета, необязательная MFA; Redis/Celery только при подтверждённой необходимости.
