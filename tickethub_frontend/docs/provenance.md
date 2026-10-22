> Обновление 06.10.2026: новый дизайн, темы, тексты и trailing slash описаны в `../UPDATE.md`. Текущий отчёт — `verification.md`; исходные архитектура и ограничения ниже сохранены для справки.

# Основания поставки

Использованные вложения пользователя. Хэши фиксируют именно прочитанные файлы; Django-код не изменялся.

- `Вставленный текст(4).txt` — SHA-256 `a8a617c143e8fdf67ebe4f800b5a7385c8ce89edd75ba017f1cc481db32d0e2a`.
- `02_FRONTEND(1).md` — SHA-256 `09e80e60989c676d8394a3fe7ed5a50784b43f22b3ef995780b46674a2c3e829`.
- `tickethub_backend_complete(1).zip` — SHA-256 `891f5e7cf7bb5861d7b50c565828c7ecc5f2029d3a031a5f4b2303f8b3ea9a24`.
- `photo_2026-09-17_16-18-04.png` — SHA-256 `9b80ea3f6a7aeed218de9b8f56bdb09e7777f2741f7e639c9491d8c28177252d`.

Точный исходный логотип скопирован в `public/logo-original.png`. Файлы шрифтов не включены. OpenAPI JSON/YAML в docs получены из приложенного backend, не из живого сервера.

Список app-маршрутов из исходников:

```text
[locale]/(site)/[information]/page.tsx
[locale]/(site)/account/orders/[id]/page.tsx
[locale]/(site)/account/orders/page.tsx
[locale]/(site)/account/page.tsx
[locale]/(site)/account/profile/page.tsx
[locale]/(site)/account/requests/[id]/page.tsx
[locale]/(site)/account/requests/page.tsx
[locale]/(site)/auth/page.tsx
[locale]/(site)/checkout/[order]/page.tsx
[locale]/(site)/checkout/page.tsx
[locale]/(site)/events/[slug]/page.tsx
[locale]/(site)/events/page.tsx
[locale]/(site)/legal/[slug]/page.tsx
[locale]/(site)/login/page.tsx
[locale]/(site)/page.tsx
[locale]/(site)/request/page.tsx
[locale]/(site)/request-ticket/page.tsx
[locale]/staff/[resource]/[id]/page.tsx
[locale]/staff/[resource]/page.tsx
[locale]/staff/analytics/page.tsx
[locale]/staff/customers/page.tsx
[locale]/staff/dashboard/page.tsx
[locale]/staff/login/page.tsx
[locale]/staff/notifications/page.tsx
[locale]/staff/orders/[id]/page.tsx
[locale]/staff/orders/page.tsx
[locale]/staff/page.tsx
[locale]/staff/privacy/page.tsx
[locale]/staff/refunds/[id]/page.tsx
[locale]/staff/refunds/page.tsx
[locale]/staff/requests/[id]/page.tsx
[locale]/staff/requests/page.tsx
[locale]/staff/seating-plans/[id]/editor/page.tsx
[locale]/staff/settings/page.tsx
page.tsx
```
