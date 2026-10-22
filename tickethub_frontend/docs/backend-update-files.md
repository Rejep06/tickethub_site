# Состав обновления

База сравнения: `tickethub_frontend_redesign.zip`. Полный архив содержит весь проект; patch — только добавленные и изменённые файлы.

## Изменены

- `README.md`
- `UPDATE.md`
- `docs/backend-gaps.md`
- `docs/decisions.md`
- `docs/frontend-guide.md`
- `docs/verification.md`
- `infra/nginx.conf.template`
- `scripts/test-unit.mjs`
- `src/components/ui/index.tsx`
- `src/components/ui/unsaved-guard.tsx`
- `src/features/catalog/event-card.tsx`
- `src/features/catalog/event-detail.tsx`
- `src/features/seat-map/seat-picker.tsx`
- `src/features/staff/layout.tsx`
- `src/features/staff/resource-page.tsx`
- `src/features/staff/resources.ts`
- `src/features/staff/seat-editor.tsx`
- `src/lib/api/client.ts`
- `src/messages/en.json`
- `src/messages/ru.json`
- `src/styles/globals.css`

## Добавлены

- `docs/backend-gaps-redesign.md`
- `docs/backend-update-evidence/backend-contracts.log`
- `docs/backend-update-evidence/build.log`
- `docs/backend-update-evidence/command-status.txt`
- `docs/backend-update-evidence/generate-api.log`
- `docs/backend-update-evidence/lint.log`
- `docs/backend-update-evidence/npm-install-result.txt`
- `docs/backend-update-evidence/source.log`
- `docs/backend-update-evidence/test-components.log`
- `docs/backend-update-evidence/test-e2e.log`
- `docs/backend-update-evidence/translations.log`
- `docs/backend-update-evidence/typecheck.log`
- `docs/backend-update-evidence/unit.log`
- `docs/backend-update.md`
- `docs/verification-redesign.md`
- `scripts/check-backend-source.py`
- `src/app/[locale]/staff/external-events/[id]/page.tsx`
- `src/app/[locale]/staff/external-events/page.tsx`
- `src/features/staff/external-events.tsx`
- `src/features/staff/image-upload.tsx`
- `src/features/staff/seat-editor-batch.tsx`
- `src/features/staff/seat-editor-canvas.tsx`
- `src/lib/api/editor.ts`
- `src/lib/api/error-details.ts`
- `src/lib/api/external-events.ts`
- `src/lib/image-upload.ts`
- `src/lib/seat-editor.ts`
- `src/styles/staff-editor.css`
- `tests/components/backend-update.test.tsx`
- `tests/components/external-events.test.tsx`
- `tests/unit/backend-update.test.cjs`
- `docs/backend-update-files.md` (этот список)

Удаляемых файлов нет. package.json, next.config.ts и исходные API URL-настройки не менялись. node_modules, .next, личные .env, lock-файл пользователя и файлы шрифтов не включены.
