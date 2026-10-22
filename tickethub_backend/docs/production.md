# Production: подготовка и эксплуатация

Конфигурация написана, но Docker/Nginx/PostgreSQL в среде автора **не запускались**. Это инструкция проверки и установки, не отчёт о развёртывании. Не подключайте клиентов до staging-проверки.

## Допуск к запуску

Сначала `scripts/verify_backend.sh` на чистой отдельной PostgreSQL должен пройти полностью. Затем зафиксируйте реально установленные зависимости в backend/requirements.lock и повторите проверку с ним. Укажите одобренные конкретные digests Python 3.13, PostgreSQL 17 и Nginx — в поставке нет выдуманных digests. Проверка точных security-патчей относится к дате вашего развёртывания.

Создайте `.env.production` из `.env.production.example`, права 600. Не копируйте development-окружение. Заполните домен/HTTPS origin/SITE_URL, случайный Django secret, раздельные пароли PostgreSQL bootstrap и прикладной роли, SMTP, DEFAULT_FROM_EMAIL, EMAIL_MESSAGE_DOMAIN и контакты. Секреты не включаются в архив/git и не выводятся `docker compose config` без `--quiet`.

В примерах ниже функция сокращает команду, но ничего не выполняет в фоне:

```bash
prod() { docker compose --env-file .env.production -f compose.prod.yaml "$@"; }
prod config --quiet
prod build backend
prod up -d --wait db
prod run --rm backend python manage.py makemigrations --check --dry-run
prod run --rm backend python manage.py migrate --noinput
prod run --rm backend python manage.py collectstatic --noinput
prod run --rm backend python manage.py check --deploy
prod run --rm backend python manage.py createsuperuser
prod up -d backend
```

Миграции — отдельный явный шаг релиза. Entrypoint только запускает команду: нет бесконечных ожиданий и автоматического migrate в каждом Gunicorn worker. `collectstatic` пишет в общий volume, media — отдельный volume. App работает от непривилегированного пользователя; исходники production-контейнера read-only, writable только media/static и /tmp.

## PostgreSQL: две роли

Для новой базы `infra/postgres/init-app.sh` создаёт прикладную роль с NOSUPERUSER/NOCREATEDB/NOCREATEROLE. Она владеет своей базой/схемой для миграций. Django не получает bootstrap-пароль. У development/PostgreSQL роль проще, потому что test runner создаёт отдельную test database; **не запускайте Django test на production**.

Init-скрипт выполняется только при пустом volume. Изменение пароля в `.env.production` **не меняет пароль уже созданной роли**. Ротацию делайте явно в PostgreSQL и согласованно обновляйте окружение приложения. Не удаляйте volume ради смены пароля. Backup перед любыми вмешательствами обязателен.

## Домен, HTTPS и Next.js

Укажите DNS сервера. Получите реальный сертификат выбранным администратором способом после появления домена. Nginx ожидает в каталоге TLS_CERT_DIR два файла: `fullchain.pem` и `privkey.pem`. Каталог монтируется read-only. Настройте безопасные права ключа и автоматическое продление вне backend; после продления проверьте сертификат и reload Nginx.

```bash
prod up -d nginx
prod exec -T nginx nginx -t
prod exec -T nginx nginx -s reload
```

Порт 80 перенаправляет на HTTPS, /api/ и /ops/ — на Gunicorn; /static/ и /media/ отдаёт Nginx. Никакие ticket PDF не хранятся в публичном media. Backend/PostgreSQL не публикуют свои порты хоста.

Остальные URL пока возвращают 404: Next.js не входит в backend. При его добавлении измените только `location /` на proxy к frontend в той же Docker-сети, оставив `/api/`, `/ops/`, `/static/`, `/media/`. Клиент и API должны оставаться на одном origin. Nginx переписывает X-Real-IP/X-Forwarded-Proto; нельзя выставлять TRUST_PROXY_IP при прямом публичном доступе к Django.

`ALLOWED_HOSTS`, CSRF_TRUSTED_ORIGINS, secure cookies, SSL redirect и HSTS настроены в production.py. Health исключён из внутреннего SSL redirect для проверки контейнера, однако внешний Nginx всё равно направляет публичный HTTP на HTTPS.

## SMTP и включение заказов

Отправьте реальный OTP и обычное бизнес-письмо через staging. Проверьте доставку, SPF/DKIM/DMARC у выбранного почтового поставщика и timeout; это внешняя настройка домена, не утверждение, что она уже сделана. Console backend запрещён в production.

В Admin создайте реальные ContentPage privacy/offer/refund-policy RU/EN, пусть ADMIN публикует утверждённые версии. Код не содержит готовых юридических текстов. Проверьте собственные условия Event, права на изображения, контакты, основание наличия билетов и ручной процесс отправки/возвратов. Затем включите PUBLIC_FORMS_ENABLED и ORDER_INTAKE_ENABLED и пересоздайте backend с обновлённым env.

Клиентская аналитика включается отдельно после решения по согласию. Без неё операционные факты заказов сохраняются. Закрытие новых форм не отбирает у прежних клиентов доступ к истории/обращениям.

## Периодические команды

Пример crontab на Linux, абсолютный путь к проекту и рабочий пользователь с доступом Docker:

```cron
* * * * * cd /opt/tickethub && sh scripts/cron_tickethub.sh >> /var/log/tickethub-jobs.log 2>&1
15 3 * * * cd /opt/tickethub && docker compose --env-file .env.production -f compose.prod.yaml exec -T backend python manage.py cleanup_auth >> /var/log/tickethub-jobs.log 2>&1
```

Ежеминутный скрипт вызывает очистку истёкших Hold/Quote и напоминания. Cron не участвует в доказательстве наличия: API проверяет сроки самостоятельно. Чтобы избежать параллельных cron-запусков при перегрузке, используйте системный `flock` на Linux; никаких Redis-lock не требуется.

EmailLog — не автоматическая надёжная очередь. Следите за FAILED/PENDING/SENDING. Через staff notifications/retry сотрудник повторяет отправку; повтор допускается только после понимания неоднозначной доставки. Если приложение завершилось сразу после commit, письмо может остаться PENDING. Такие записи видны сотруднику, повтор — вручную. OTP не попадает в EmailLog.

## Backup и проверка восстановления

```bash
# Скрипт сам использует compose.prod.yaml/.env.production и pg_dump -Fc.
sh scripts/backup_db.sh ./backups
```

Файл дампа создаётся с ограниченными правами, неполный dump не получает финальное имя. Храните копии за пределами сервера с шифрованием/политикой доступа и разумным сроком хранения. Копия только на том же диске не защищает от потери сервера. Media volume сохраняйте отдельно; staticfiles можно пересобрать.

Восстанавливайте сначала **в отдельную пустую staging-базу**, не поверх рабочей:

```bash
# В отдельном изолированном экземпляре PostgreSQL создайте пустую БД restore_test.
# Переменные ниже должны ссылаться именно на этот экземпляр.
PGHOST=localhost PGPORT=5432 PGUSER=restore_owner PGDATABASE=restore_test \
  pg_restore --no-owner --no-acl --exit-on-error --dbname=restore_test backups/ИМЯ_ДАМПА.dump
```

Пароль передайте через защищённый .pgpass/окружение администратора, не сохраняйте его в истории команд. Формат pg_dump -Fc читается pg_restore; для plain SQL применяют psql, это другой формат. Восстановите media из той же согласованной копии. Запустите migrate/check на тестовом приложении, откройте реальные примерные заказы/позиции/проводки/выдачу, сравните количество и суммы. Используйте изолированный email backend, чтобы восстановленные данные не отправили реальные письма.

Восстановление в этой поставке не выполнялось. Перед запуском проекта этот шаг должен быть реально проверен.

## Наблюдение и релизы

Минимально контролируйте health/ready, ошибки 5xx, свободное место, SMTP-ошибки, очереди обработки/выдачи, сроки закреплений поставщика, возраст последнего успешного backup. Стандартные логи не должны содержать тело запроса, OTP, пароль, cookie или Authorization. URI логируется без query. Development console email — сознательное исключение только локально.

На обновлении: backup → новая сборка по фиксированным зависимостям → проверка миграций в staging → явный migrate → collectstatic → пересоздание backend → health и ручной smoke-test. Откат кода не гарантирует откат схемы: решение по несовместимым миграциям принимается заранее. Не применяйте `--fake` и не удаляйте production volumes ради обхода ошибки.
