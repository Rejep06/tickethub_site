> Этот документ описывает предыдущий этап. Актуальные изменения изображений, карты и входа: [usability-update.md](usability-update.md); текущие результаты: [verification-usability.md](verification-usability.md).

# Развёртывание: один origin

**Шаблоны не запускались в этой среде.** Перед production обязательны настоящий lock-файл, успешно выполненные build/lint/types/tests, staging E2E, backend-проверки миграций/конкурентного резерва, SMTP и собственные юридические тексты. Не переносите текущую поставку прямо на рабочие продажи.

## Схема

```text
Браузер → HTTPS Nginx
                 /api/          → Django backend:8000
                 /ops/          → Django Admin
                 /health/       → Django health
                 /media/        → публичные афиши/схемы
                 /static/       → Django staticfiles
                 /_next/static/ → Next static
                 /              → Next frontend:3000
```

Не открывайте Node, PostgreSQL и Django напрямую в Интернет. Cookies живут на единственном HTTPS origin. Секреты Django/SMTP никогда не должны попадать в NEXT_PUBLIC переменные.

## Подготовка

Проекты лежат рядом: `tickethub/` и `tickethub_frontend/`. На подключённой машине разрешите зависимости, сохраните `package-lock.json`, выполните `npm ci` и все frontend-проверки. Dockerfile использует `npm ci`: отсутствие lock приводит к остановке, а не скрытой установке случайных версий.

Следуйте `docs/production.md` бэкенда: отдельные production-секреты, PostgreSQL роли/backup, approved image digests, requirements.lock, SMTP, migrations, cron. Настройте `SITE_URL=https://ваш-домен` и этот же HTTPS origin в `DJANGO_CSRF_TRUSTED_ORIGINS`. Сам Next не заменяет backend-защиту CSRF/permissions.

## Compose overlay

Шаблон рассчитан именно на service `backend` в приложенном `compose.prod.yaml`. Локальный compose использует другое имя `api`; этот overlay к локальному compose не применяется.

В backend production `.env` дополнительно задайте `NODE_IMAGE` с проверенным Node 24 digest. Сертификаты `fullchain.pem` / `privkey.pem` должны находиться в настроенном backend `TLS_CERT_DIR`. Выпуск сертификата не автоматизирован этой поставкой.

Из корня бэкенда:

```bash
docker compose --env-file .env.production \
  -f compose.prod.yaml \
  -f ../tickethub_frontend/infra/compose.frontend.yaml config --quiet

# Прежде проверьте итоговые volumes и зависимости, не публикуйте вывод с секретами.
docker compose --env-file .env.production \
  -f compose.prod.yaml \
  -f ../tickethub_frontend/infra/compose.frontend.yaml build frontend

# Выполняйте только после migrations/backend readiness и проверенного backup.
docker compose --env-file .env.production \
  -f compose.prod.yaml \
  -f ../tickethub_frontend/infra/compose.frontend.yaml up -d
```

Путь mount к Nginx template заменяет тот же target из исходного compose. Его static/media/certificates volumes остаются из базового файла. В Compose путь контекста считается относительно первого compose-файла: поэтому проекты должны лежать рядом, как показано выше.

Next standalone image работает не от root. Build-time `NEXT_PUBLIC_APP_URL` нужен для canonical/OG; `BACKEND_ORIGIN` в rewrites тоже фиксируется при сборке. Runtime `API_INTERNAL_URL` используется серверными публичными GET. При смене публичного домена или rewrite backend пересоберите frontend.

## Проверка после staging deploy

Проверьте каталог и реальную карточку, новый OTP и staff password login, CSRF после обоих входов, Hold после reload, повтор POST с прежним idempotency key при потерянном ответе, заказы разных пользователей, платёж/отправку/возврат в отдельной БД, админские права, мобильную карту и список.

Персональный HTML/API не кэшируется shared CDN. Nginx template не устанавливает shared proxy cache. Production CSP и HSTS должны быть введены после проверки конкретного домена/поддоменов и nonce-политики Next; здесь не заявляется настроенная строгая CSP или безопасный preload HSTS.

Файлы билетов запрещено складывать в публичный media volume ради добавления «Скачать». Для защищённого TicketFile нужен отдельный backend-контракт, permissions, lifecycle и audit; в данном MVP он отсутствует.
