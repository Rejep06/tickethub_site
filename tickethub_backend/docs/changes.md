# Изменения исходного проекта

Сравнение с байтами переданного `tickethub_stage2_blocked.zip`. Сохранены конфигурационный каркас, custom User/manager, health/CSRF, общая обработка ошибок/request ID и совместимые исходные тесты. Старые блокировки окружения не выдаются за результаты текущей реализации.

## Что и почему изменено

| Файлы | Изменение и причина |
|---|---|
| backend/config/settings/*.py, config/urls.py | Реальные приложения/маршруты, роли и сессии, SMTP/media/flags, безопасная production-конфигурация. |
| backend/users/{models,managers,admin,forms}.py | Сохранён User, добавлены OTP/лимиты и безопасное управление сотрудниками, без обязательной MFA. |
| backend/core/{views,serializers,exceptions,middleware,permissions}.py | Сохраняются контракт ошибок/CSRF/health, strict входы, public flags, раздельный staff-доступ. |
| backend/*/{models,serializers,views,services,urls,admin}.py | Полные приложения каталога/запаса/заказов/подбора/денег/аналитики; без пустого skeleton. |
| backend/*/migrations/*.py | Ручные ещё не применённые миграции; требование реального сравнения и fresh DB. |
| backend/*/tests/*.py, checks/*.py | Django/PG-сценарии отдельно от действительно исполняемых автономных проверок. |
| infra/, compose*.yaml, scripts/ | Запуск/isolated verification/production/HTTPS/backup и конечные cron-команды. |
| docs/ и README.md | Полностью актуализированные инструкции и честный отчёт, вместо прежнего stage2-only описания. |

Весь файл дан в проекте, а не отдельные вырванные фрагменты. Дальнейшие изменения следует делать с указанием файла/участка/причины по backend-guide.

## Неизменённые файлы основы

```text
.dockerignore
backend/config/__init__.py
backend/config/env.py
backend/config/settings/__init__.py
backend/config/wsgi.py
backend/core/__init__.py
backend/core/authentication.py
backend/core/pagination.py
backend/core/tests/__init__.py
backend/core/tests/urls.py
backend/manage.py
backend/users/__init__.py
backend/users/apps.py
backend/users/forms.py
backend/users/managers.py
backend/users/migrations/0001_initial.py
backend/users/migrations/__init__.py
backend/users/tests/__init__.py
backend/users/tests/test_models.py
checks/test_environment_helpers.py
docs/file-manifest.txt
docs/spec/01_BACKEND.md
docs/spec/02_FRONTEND.md
docs/spec/03_implementation_instructions.txt
```

## Изменённые файлы основы

```text
.env.example
.gitignore
README.md
backend/config/settings/base.py
backend/config/settings/local.py
backend/config/settings/production.py
backend/config/settings/test.py
backend/config/urls.py
backend/core/apps.py
backend/core/exceptions.py
backend/core/middleware.py
backend/core/serializers.py
backend/core/tests/test_api.py
backend/core/urls.py
backend/core/views.py
backend/requirements.txt
backend/users/admin.py
backend/users/models.py
backend/users/tests/test_admin.py
compose.yaml
docs/backend-guide.md
docs/decisions.md
docs/frontend-api.md
docs/stages.md
infra/docker/Dockerfile
scripts/check_foundation.sh
scripts/create_local_env.py
```

## Удалённые либо перемещённые старые файлы

```text
docs/verification/django-check.txt
docs/verification/django-tests.txt
docs/verification/docker-config.txt
docs/verification/install.txt
docs/verification/makemigrations.txt
docs/verification/migrate.txt
docs/verification/migration-consistency.txt
docs/verification/offline-tests.txt
docs/verification/openapi.txt
docs/verification/postgres-install-attempt.txt
docs/verification/postgres-version.txt
docs/verification/python-compile.txt
docs/verification/report.md
docs/verification/results.json
docs/verification/shell-syntax.txt
docs/verification/yaml-syntax.txt
```

Точный машинный список новых/изменённых путей: verification/source-changes.json. Старые журналы сохранены в verification/previous_stage2/ и не смешиваются с текущими проверками.
