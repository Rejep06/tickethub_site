# Фактические результаты проверки

## Итог

```text
CODE: INCOMPLETE
BUILD: FAILED — запуск команды остановлен отсутствием Next.js
BACKEND INTEGRATION: BLOCKED
PRODUCTION READY: NO
```

Основные сценарии публичного сайта и staff-панели написаны. Это не подтверждение прохождения полного Definition of Done. Известные ограничения кода перечислены в `feature-matrix.md`; отсутствующие/ограниченные backend API — в `backend-gaps.md`.

## Что действительно выполнено

| Команда | Exit | Результат |
| --- | ---: | --- |
| `npm install --fetch-retries=0 --fetch-timeout=6000 --no-audit --no-fund` | 124 | Остановка по лимиту 18 секунд; dependencies не установлены |
| `curl -I --connect-timeout 5 --max-time 8 https://registry.npmjs.org/next` | 6 | DNS: `Could not resolve host: registry.npmjs.org` |
| `npm run generate:api` | 0 | Сгенерировано 186 TypeScript aliases из приложенной OpenAPI |
| `npm run check:translations` | 0 | 338 одинаковых ключей RU/EN, соответствующие ICU-параметры и literal t() |
| `npm run check:source` | 0 | 104 TS/TSX файла: нет найденных синтаксических ошибок/неразрешённых локальных named imports |
| `npm test` | 0 | 93 автономных теста: 93 passed, 0 failed |
| `npm run typecheck` | 2 | Нет установленных Next/React/next-intl/types; полная типизация приложения не проверена |
| `npm run lint` | 127 | `eslint: not found`; lint не выполнен |
| `npm run test:components` | 127 | `vitest: not found`; component cases не выполнялись |
| `npm run test:e2e` | 1 | Найден внешний Python Playwright CLI без команды `test`; npm @playwright/test не установлен, E2E не выполнялись |
| `npm run build` | 127 | `next: not found`; production build не создан |
| `python manage.py check` в приложенном backend | 1 | `ModuleNotFoundError: No module named 'django'` |

Неудачная команда build действительно вызывалась. Это не сообщение о конкретной выявленной ошибке компилятора Next.js: сам Next не установлен. Полный `tsc` также нельзя считать пройденным на основании отдельного синтаксического анализа.

## Объём тестирования

| Набор | Написано | Выполнено | Успешно | Упало | Не выполнено |
| --- | ---: | ---: | ---: | ---: | ---: |
| Unit / domain / mocked API contract | 93 | 93 | 93 | 0 | 0 |
| Vitest + Testing Library | 12 | 0 | 0 | 0 | 12 |
| Playwright + настоящий Django | 4 | 0 | 0 | 0 | 4 |
| **Всего** | **109** | **93** | **93** | **0** | **16** |

«0 упавших тестов» не означает успешную попытку запуска недоступного runner. Ошибки запуска component/E2E показаны в таблице команд выше. В E2E не было ни passed, ни фактически выполненных skips: runner не дошёл до тестов.

Автономный runner сначала строго компилирует **13 самостоятельных TypeScript-модулей** с доступным глобальным TypeScript **5.8.3**, потом запускает Node built-in test на Node **22.16.0**. Это не целевой установленный TypeScript 5.9.3 из package.json. В unit-тестах fetch подменён; сессии, hold и ledger проверяются на изолированном контракте, не на запущенном Django.

## Что не делалось и не объявляется выполненным

Нет настоящих HTTP-запросов к Django, PostgreSQL, тестов миграций/двух конкурентных покупателей, реальной почты OTP, staff login, server Hold/Order или refund settlement. Нет открытых браузером страниц Next, проверки мобильных экранов, Safari/Chrome, WCAG/контраста, Lighthouse, production server или реальных платёжных операций.

Нет сгенерированного реестром package-lock.json. Его отсутствие обозначено явно; вручную придуманный lock не поставляется. Шаблоны Docker/Nginx/CI не запускались. Предоставленный backend тоже должен пройти собственный процесс проверки: наличие исходников не означает, что его миграции и конкурентные операции уже проверены здесь.

## Артефакты доказательств

Исходный вывод команд: `docs/verification/*.log`, коды: `*.exit`. Машиночитаемый отчёт: `docs/verification/manifest.json`. В ZIP нет искусственных React/Next typings, которые могли бы замаскировать отсутствие настоящих зависимостей.

## Следующий релизный gate

На подключённой машине установить dependencies и сохранить настоящий lock; повторить `npm ci`, typecheck, lint, unit/component tests и build; запустить приложенный Django с PostgreSQL; выполнить E2E и ручной негативный/мобильный сценарий. Ошибки первого полного запуска нужно исправить, после чего обновить именно этот отчёт фактическими логами. До этого не объявлять VERIFIED или production-ready.
