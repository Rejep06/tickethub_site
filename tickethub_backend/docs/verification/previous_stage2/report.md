# Фактические проверки поставки

**Статус: BLOCKED на проверке этапа 2. Проект не проверен запуском Django.**

Окружение выполнения: Python 3.13.5, Debian 13. Изначально отсутствуют Django, DRF, psycopg, PostgreSQL client/server и Docker. Пустое виртуальное окружение было создано, но установка пакетов из PyPI не завершилась. Установка PostgreSQL из Debian также не завершилась.

## Результаты

| Проверка | Фактический результат |
| --- | --- |
| `uv pip install ... -r backend/requirements.txt` | Exit 2, сеть/таймаут до получения Django |
| `manage.py makemigrations users` | Exit 1, `ModuleNotFoundError: No module named 'django'` |
| `manage.py makemigrations --check --dry-run` | Exit 1, та же ошибка импорта |
| `manage.py migrate --noinput` | Exit 1, та же ошибка импорта; к БД не обращались |
| `manage.py check` | Exit 1, та же ошибка импорта; Django checks не выполнены |
| `manage.py test ...` | Exit 1 до запуска test runner; ни один из 30 методов не выполнен |
| `manage.py spectacular ...` | Exit 1 до генерации; OpenAPI не создан |
| `docker compose config --quiet` | Команда Docker отсутствует |
| `psql --version` | Команда psql отсутствует |
| `python -m unittest discover -s checks -v` | 12 passed, 0 failed |
| `python -m compileall -q backend scripts checks` | Exit 0; синтаксис 35 Python-файлов |
| `sh -n scripts/check_foundation.sh` | Exit 0; только синтаксис shell |
| YAML-парсер для compose.yaml | Успех; это не проверка Docker Compose/контейнеров |

Машиночитаемый результат: `results.json`. Для каждой команды сохранён отдельный `.txt` с stdout/stderr и exit code.

Установка системных пакетов: `postgres-install-attempt.txt`. Предварительные попытки показали недоступность DNS; повтор с HTTPS не разрешил проблему. Отдельная попытка загрузить wheel через доступный инструмент скачивания также не удалась.

## Ограничения

- Первая миграция написана вручную, не сгенерирована Django и не применена.
- Lock-файл не получен разрешением зависимостей и поэтому не включён.
- Отсутствует runtime-проверка маршрутов, Admin, моделей и constraints.
- Нет тестов продажи, резервирования, возвратов: соответствующие модули ещё не реализованы.
- Нет результата сборки Docker, нагрузки, восстановления backup или deploy.
- 12 автономных тестов и компиляция не доказывают работоспособность backend.

## Воспроизведение следующей проверки

В окружении с Docker и доступными registry/PyPI: создать локальный `.env`, затем запустить `sh scripts/check_foundation.sh`. Скрипт не проходит мимо ошибки. Полученные результаты нужно сохранить отдельно и обновить журнал только после реального исполнения.
