# Обновление Tickethub: оформление заказа менеджеру и промокоды

Версия: manager-checkout-promocodes, 21.10.2026. Patch предназначен **только для предыдущего `tickethub_launch_update.zip`**. Полный архив содержит backend, frontend и production-конфигурацию. При наличии собственных изменений сначала сравните файлы; не заменяйте вслепую отличающийся проект.

## Что меняется

Доступные билеты ведут в оформление заказа. Онлайн-платёж не нужен: создаётся `NEW`, билеты закрепляются как `ORDER_HELD`, менеджер получает заказ в панели и письмо, если настроена почта. Необязательные метаданные/просроченный автоматический срок выдачи больше не закрывают ручной приём. Реальные остатки с ценой доступны и при старом режиме предложения `REQUEST`. Отменённое/завершённое событие, явно истёкший срок продаж, занятые и заблокированные билеты по-прежнему защищены.

Добавлены промокоды, предпросмотр скидки, подтверждение итоговой суммы, управление администратора и сохранение скидки в заказе/билетах. Предыдущие фото, категории, публикация, trailing slash, темы и исправления схем сохранены.

## 1. Сначала резервная копия

Остановите frontend (`Ctrl+C`). До остановки локального API сохраните базу и media. Из **папки `tickethub_backend`** в PowerShell:

```powershell
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-acl -f /tmp/before-checkout.dump'
docker compose cp db:/tmp/before-checkout.dump .\before-checkout.dump
docker compose exec -T api sh -c 'tar -C /app/media -czf /tmp/before-checkout-media.tar.gz .'
docker compose cp api:/tmp/before-checkout-media.tar.gz .\before-checkout-media.tar.gz
docker compose stop api
```

Если media отсутствует и изображений действительно нет, архив media можно пропустить. Сохраните копию исходников и локальных env отдельно. Не используйте перенаправление бинарного `pg_dump` через старый PowerShell; выше он создаётся файлом в контейнере.

**Не удаляйте `.env`, `.env.local`, `.env.production`, `node_modules`, `package-lock.json`, media и Docker-volumes. `down -v` не нужен.** В ZIP нет ваших секретов, базы и пользовательских изображений.

## 2. Замените исходники обоих приложений

Скопируйте содержимое patch в общий каталог, где лежат `tickethub_backend` и `tickethub_frontend`, подтвердив замену файлов. Корневые `deploy/` и `compose.production.yml` относятся к серверному развёртыванию.

Frontend и backend нужно обновить вместе. Только frontend не создаст таблицы промокодов и не снимет серверную блокировку оформления.

Зависимости Node и Python не менялись. Новый backend-app использует уже предусмотренные Django/DRF/PostgreSQL. Полный `npm install` для установленного проекта не требуется; на чистой машине используется `npm ci` по существующему lock.

## 3. Миграции и настройки локального backend

Из `tickethub_backend`:

```powershell
docker compose run --rm api python manage.py migrate --noinput
docker compose run --rm api python manage.py makemigrations --check --dry-run
```

Новые миграции: `orders.0003_manager_checkout_discounts`, `promotions.0001_initial`. Исторические суммы сохраняются, скидки старых заказов — ноль. Активных промокодов миграция не создаёт. Если ранее не применено обновление каталога, его миграции также выполнятся: служебные категории/непроверенные описания могут снять событие с публикации, как было описано в предыдущем релизе.

В существующем **backend `.env`** проверьте:

```env
PUBLIC_FORMS_ENABLED=true
ORDER_INTAKE_ENABLED=true
SITE_URL=http://localhost:3000
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000
```

Не добавляйте повторяющиеся ключи, исправьте имеющиеся. Для писем менеджеру укажите реальные SMTP-настройки и `STAFF_NOTIFICATION_EMAILS`. Без SMTP в локальном режиме письма могут печататься в консоль; заказ всё равно существует в БД/панели. На production используется только SMTP.

Примените env и проверьте:

```powershell
docker compose up -d --force-recreate api
docker compose exec api python manage.py check
docker compose exec api python manage.py checkout_status
# Дополнительно замените YOUR_EVENT_SLUG реальным slug из адреса события:
docker compose exec api python manage.py checkout_status --event YOUR_EVENT_SLUG
```

`online_payments_enabled: False` — ожидаемо. Для заказа нужны `order_intake_enabled: True`, доступное событие и реальные билеты. На production также нужны утверждённые документы, потому что там согласия обязательны.

## 4. Перезапустите frontend

Из `tickethub_frontend`:

```powershell
Remove-Item -Recurse -Force .next -ErrorAction SilentlyContinue
npm run dev
```

Обновите браузер через `Ctrl+F5`. Для проверки production-сборки, не одновременно с dev:

```powershell
npm run generate:api
npm run check:translations
npm run typecheck
npm run lint
npm test
npm run test:components
npm run build
```

Не скрывайте ошибки сборки `--force` или отключением typecheck. В среде подготовки полный Next/Django недоступен; смотрите `VERIFICATION_tickethub_checkout.md`.

## 5. Проверка руками

Покупатель: выбрать доступные места → «Перейти к оформлению» → вход при необходимости → контакты/согласия → серверный резерв → промокод по желанию → «Оформить заказ».

Менеджер: `/ru/staff/orders` → тот же номер заказа → «Взять в работу» → контакт с клиентом → подтверждение → запись реально полученной оплаты → отметка отправки билетов. Новые заказы видны без ручного переноса из email. В открытой вкладке список обновляется каждые 15 секунд.

Промокоды: администратор открывает `/ru/staff/promo-codes`, создаёт код, задаёт скидку/период/лимиты. Менеджер имеет только просмотр. Ни одного активного кода заранее не создано.

Проверьте скидку в заказе клиента и карточке менеджера. Успешный заказ не должен исчезать после истечения исходного checkout-таймера. SMTP-сбой не должен отменять заказ; проверьте очередь уведомлений и повторите доставку отдельно.

## 6. Сервер с доменом

Полная инструкция — `DEPLOY_tickethub.md`: VPS, DNS, Docker, перенос данных с Windows, env, реальные тесты на отдельной PostgreSQL, сборка, Nginx, HTTPS, SMTP, включение приёма, промокоды, backup, обновления и восстановление. Для сервера используйте корневой `compose.production.yml`, а не локальный `compose.yaml`.

При обновлении уже запущенного сервера: backup → новые исходники → изолированные тесты/сборка → остановка приложений → migrate/collectstatic → пересоздание backend/frontend/scheduler/nginx → `checkout_status` → тестовый заказ. Не откатывайте миграции со скидками поверх уже созданных дисконтированных заказов без согласованного плана сохранения данных.
