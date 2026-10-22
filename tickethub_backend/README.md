> **Обновление 20.10.2026:** установка и миграция — `../UPDATE_tickethub_launch.md`; единый сервер с доменом — `../DEPLOY_tickethub.md`; текущие результаты проверок — `../VERIFICATION_tickethub_launch.md`. Ниже сохранена документация проекта; прежние отчёты относятся к предыдущим версиям.

> **Обновление: PortalBilet + визуальный редактор.** Это частичная интеграция: редактор реализован, импорт создаёт только распознанные черновики и диагностические снимки. Автоматическое декодирование схемы/внешних билетов не завершено, реальные payload недоступны. Django/PostgreSQL-проверка не выполнена. Актуальные детали: [portalbilet-and-editor.md](docs/portalbilet-and-editor.md). Ниже — документация предыдущей версии backend.

# Tickethub — backend MVP

Продолжение `tickethub_stage2_blocked.zip`, а не новый проект. Python 3.13, Django 5.2 LTS, DRF, PostgreSQL 17; девять Django apps в одном приложении. Онлайн-оплаты, TicketFile, Redis, Celery и обязательной MFA нет.

**Статус поставки:** сценарии MVP написаны; доступные автономные проверки выполнены. В среде автора не установились Django/DRF/PostgreSQL, отсутствует Docker. Поэтому Django-тесты, миграции, конкурентные блокировки и запуск HTTP **не подтверждены выполнением**. Этот архив нельзя считать проверенным production-релизом. Точные результаты — в [отчёте](docs/development-report.md).

## 1. Что реализовано

Клиентский email-код и Django session; парольный вход сотрудников; профиль и подтверждённая смена email. Публичный RU/EN каталог, площадки, ручная схема и места. Реальные единицы билетов, доступность, 10-минутный резерв, неизменяемые клиентские снимки заказа. Подбор отсутствующего события, версии Quote, обычный checkout из предложения. Менеджерские операции, Django Admin, журнал ручных денег и сторно, обращения/возвраты, частичная выдача. Отчёты по продажам/движению денег/воронке. Контент, согласия, простой журнал писем и ручная повторная отправка.

Успешный `POST orders/` прекращает действие checkout-таймера: билеты остаются `ORDER_HELD`. Клиент не получает supplier, purchase_price, profit или internal_notes. Деньги — **целые копейки**: `100000` означает 1 000 ₽.

## 2. Локальный запуск

Нужны Docker Engine/Desktop с современным Compose v2 (поддержка `up --wait`), Python 3 на хосте для создания `.env` и доступ к реестрам образов/PyPI. PostgreSQL отдельно на хосте не нужен. На Windows команды shell выполняйте в WSL; в production используйте Linux.

```bash
unzip tickethub_backend_complete.zip
cd tickethub
python3 scripts/create_local_env.py
```

Скрипт создаёт `.env` со случайными локальными секретами и не перезаписывает существующий файл. Вариант вручную: `cp .env.example .env`, затем заполнить секреты. Не используйте development `.env` для production. На Linux перед сборкой можно установить `LOCAL_UID`/`LOCAL_GID` в `.env` по выводу `id -u` / `id -g`: это права на создаваемые файлы при bind mount.

```bash
docker compose config --quiet
docker compose build api
docker compose up -d --wait db

# Обязательно до применения: миграции были написаны без установленного Django.
docker compose run --rm api python manage.py makemigrations --check --dry-run

docker compose run --rm api python manage.py migrate
docker compose run --rm api python manage.py check
docker compose run --rm api python manage.py createsuperuser
docker compose run --rm api python manage.py seed_demo
docker compose up -d api
```

Первая проверка должна завершиться без предлагаемых новых миграций. При несовпадении **не продолжайте на рабочей базе**: сравните модели и миграции, исправьте их на отдельной чистой БД и повторите проверку. `--fake` не является исправлением.

Откройте:

```text
http://localhost:8000/ops/
http://localhost:8000/api/v1/events/
http://localhost:8000/api/v1/events/demo-seats/
http://localhost:8000/api/v1/events/demo-category/
http://localhost:8000/health/live/
http://localhost:8000/health/ready/
```

Admin входит по email/паролю, заданным `createsuperuser`. `seed_demo` **не создаёт администратора или известный пароль**. Он добавляет две демонстрационные карточки, площадку, размеченную схему, предложения и билеты. Повторный запуск не сбрасывает заказы/остатки. В production demo запрещено. Даты создаются относительно первого запуска; повтор не переносит старые demo-события в будущее.

```bash
docker compose logs --tail=100 api
docker compose stop
docker compose up -d
```

Не выполняйте `down --volumes` для базы с нужными данными. По умолчанию наружу опубликован только localhost:8000; порт PostgreSQL не публикуется.

## 3. Тесты и независимая проверка

```bash
# Полная проверка на НОВОЙ отдельной PostgreSQL и отдельном проекте Compose:
sh scripts/verify_backend.sh

# Обычный повтор Django-тестов в локальном окружении:
docker compose run --rm api python manage.py test --settings=config.settings.test --verbosity=2

# Проверки, не требующие Django (не заменяют команды выше):
python3 -m unittest discover -s checks -v
```

`verify_backend.sh` создаёт случайное имя Compose-проекта, секреты и пустой volume БД, проверяет Compose/build, `makemigrations --check`, migrate, check, тесты, два запуска seed_demo и настоящий Gunicorn/HTTP health/каталог/страницу входа Admin. Останавливается при первой ошибке. В конце удаляет **только свои** контейнеры/volumes, не локальную или production-БД.

Конкурентный тест использует два потока, отдельные PostgreSQL backend PID и настоящий API-запрос за последним местом. SQLite не подменяет эту проверку. Отсутствие PostgreSQL не приводит к фиктивному успешному skip.

После успешной проверки скрипт сохраняет `docs/verification/requirements.executed.txt`. Просмотрите его и зафиксируйте:

```bash
cp docs/verification/requirements.executed.txt backend/requirements.lock
# Повторите проверку с REQUIREMENTS_FILE=requirements.lock в тестовом окружении.
```

В поставке **нет выдуманного lock-файла**: версии не разрешались установленным pip. Диапазоны — в `backend/requirements.txt`. Development-образы имеют семейство версий, production требует указать одобренные digests, нигде нет `latest`.

## 4. Как создать первое своё событие

В `/ops/` создайте Category (SPORT/CONCERT/OTHER), Venue с IANA timezone, при необходимости Participant. Для мест: сначала SeatingPlan DRAFT и изображение с подтверждением прав, затем Seat (sector/row/number и x/y 0..1), затем публикация схемы. Редактор через API поддерживает ряд, предпросмотр и клонирование версии; опубликованная схема не редактируется.

Создайте Event с обоими названиями, точной датой, площадкой и выбранной опубликованной схемой либо без неё. Явно задайте Fan ID true/false, согласованные RU/EN условия возврата и отметку их проверки. Непроверенные условия допускают подбор, но не прямой заказ. Deadline продаж должен быть раньше события. Обычный срок выдачи — за 24 часа; для более позднего оформления сотрудник согласует и задаёт будущий срок отдельно.

Создайте TicketOffer: SEAT при схеме, CATEGORY/STANDING без неё; mode AVAILABLE для имеющегося запаса либо REQUEST для подбора. Цена в копейках. Создайте отдельный TicketUnit **на каждый билет**, при необходимости поставщика, закупку и reference. Для места — Seat нужной схемы. Для эксклюзивного закрепления поставщика укажите действительный `allocation_until`. `NULL` закупки означает «неизвестна», не 0 ₽.

Публикуйте Event и проверяйте `orderable`/`availability`, а не только флаг публикации. Юридические тексты проект не придумывает: до production их должен подготовить и утвердить владелец проекта.

## 5. Первый тестовый заказ

Используйте отдельное окно/профиль браузера для клиента, чтобы не заменить парольную сессию Admin клиентским OTP. В development код приходит в **локальный console email backend**: `docker compose logs -f api`. Это только для разработки; такие логи нельзя публиковать. Production использует SMTP.

Полный контракт, поля, ошибки и готовая функция `api()` для fetch находятся в [frontend-api.md](docs/frontend-api.md). В локальном окне на origin `http://localhost:8000` можно последовательно вызвать:

```javascript
await api('auth/otp/request/', {method:'POST', body:{email:'you@example.com', locale:'ru'}});
await api('auth/otp/verify/', {method:'POST', body:{email:'you@example.com', code:'КОД_ИЗ_ПИСЬМА'}});
await api('me/', {method:'PATCH', body:{name:'Ваше имя', phone:'ВАШ_МЕЖДУНАРОДНЫЙ_НОМЕР'}});
// Затем checkout/preview/, checkout/holds/ и orders/ по контракту.
// Idempotency-Key — один UUID на операцию, не новый UUID на каждый сетевой retry.
```

Получите UUID события/предложения из каталога. Preview возвращает рассчитанный итог и версии предложений. Hold создаётся по ним. Отправьте Order из `hold_id`. Для demo без юридических страниц `accepted_documents: {}`; для Fan ID=true нужен ответ HAS_FAN_ID/NEEDS_HELP/NOT_SURE. Никаких паспортных полей/загрузок нет.

В окне сотрудника откройте Order. Через admin actions возьмите в работу/подтвердите. В карточке есть формы контакта, ручной оплаты, ручной отправки и отмены, вызывающие services. Сначала действительно отправьте билет по email, потом отметьте выбранные OrderItem. Кнопка «отправлено» **не отправляет PDF автоматически**. После полной оплаты и выдачи завершите заказ. Те же операции доступны по `/api/v1/staff/`.

## 6. Структура и зависимости

```text
backend/config/       настройки, корневой URL, WSGI
backend/users/        аккаунты, OTP, парольный staff-вход
backend/events/       RU/EN каталог и условия
backend/venues/       площадки, версии схем, места
backend/tickets/      предложения, реальный запас, checkout
backend/orders/       заказы, позиции, история, выдача, обращения
backend/ticket_requests/ подбор и Quote
backend/payments/     неизменяемый журнал фактических денег
backend/analytics/    отчёты и ограниченная воронка
backend/core/         общие ошибки, доступ, контент, письма, Admin
infra/                Docker, Nginx, начальная роль PostgreSQL
scripts/              проверка, окружение, backup, cron
checks/               автономные проверки
```

Django/DRF — выбранный стек; psycopg — драйвер PostgreSQL; Gunicorn — процесс production-приложения; drf-spectacular — OpenAPI; Pillow — безопасное декодирование/пересохранение изображений; phonenumberslite — международная проверка телефона. Последние две задачи не решаются одной строкой регулярного выражения или самим ORM. Других сервисов инфраструктуры не требуется.

Практическое объяснение моделей и операций: [backend-guide.md](docs/backend-guide.md). Deployment/HTTPS/backup: [production.md](docs/production.md). Изменения относительно оригинала: [changes.md](docs/changes.md).

## 7. Перед приёмом реальных заказов

Сначала успешно выполните изолированную проверку и staging smoke-test с настоящим SMTP, зафиксируйте зависимости/образы. Заполните `.env.production`, подготовьте сертификат и домен, опубликуйте утверждённые юридические версии, проверьте реальные контакты, процессы поставщиков/возврата и восстановление backup. Только после этого включайте PUBLIC_FORMS_ENABLED/ORDER_INTAKE_ENABLED. Выключение этих флагов не закрывает существующим клиентам историю и обращения.

Backend не включает Next.js и не развёрнут на вашем сервере. Отсутствие фактической проверки — ограничение этой поставки, а не обещание безопасного запуска без неё.
