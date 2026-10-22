# PortalBilet mapping verified from real capture

Проверено по `portalbilet_capture.zip`, полученному 2026-10-07 для события `event.id=114696`, `event_source_id=10679`, `hall_layout_id=3513`.

## Что реально пришло

`coordinates.json`:

- `id=3513`;
- `width=5314`, `height=4180`;
- `bg=https://cdn.pbilet.com/origin/1993a985-e200-4230-b77b-9fcef724cf55.svg`;
- 12 075 объектов вида `{x, y}`;
- все 12 075 пар координат уникальны.

`tickets-402328.json`:

- 77 секторов;
- 2 109 доступных нумерованных мест;
- каждое место содержит сектор, ряд, номер, цену RUB и абсолютные `x/y`;
- все 2 109 пар `ticket.x/y` в точности присутствуют в `coordinates`;
- каждая такая точка встречается там ровно один раз;
- внутри compact ticket `k.x/k.y/k.z` повторяют номер/сектор/ряд, а `k.e=402328` подтверждает дату.

`tickets-402417.json` содержит те же 77 геометрических секторов, но ноль доступных нумерованных мест.

`standing-402417.json` содержит отдельную группу `Парковка`: `count=200`, `price=500 RUB`. Это не Seat и не преобразуется в 200 фиктивных мест.

## Подтверждённая связь

Геометрическая связь:

```text
assigned ticket (x, y)
        ==
одна уникальная точка coordinates (x, y)
```

Локальная физическая идентичность места, поскольку `coordinates` не предоставляет seat ID:

```text
provider + hall_layout_id + sector + row + seat_number
```

`ticket.d` сохраняется как внешний ID конкретного provider ticket/listing, но не используется как ID физического кресла: в захвате нет доказательства, что этот UUID стабилен между разными датами.

Пример из реального payload:

```text
Сектор 112 / ряд 5 / место 11
pixel: x=3746, y=3158
normalized: x=3746/5314=0.704930, y=3158/4180=0.755502
price: 1300 RUB
provider ticket id: ba00ae81-6115-4fb0-8797-33d641d1f3aa
```

## Как импортируется в Tickethub

- `SeatingPlan` хранит внешний layout ID, размеры, background URL, полный point cloud и SVG-path секторов.
- Подписанные доступные места становятся обычными `Seat` с нормализованными координатами 0..1.
- Пер-date availability/price хранится в `ExternalSeatInventory`.
- Standing/GA/add-on группы хранятся отдельно в `ExternalStandingInventory`.
- `enabled_for_sale` — только локальное решение администратора и никогда не сбрасывается sync.
- `TicketUnit` автоматически НЕ создаётся. Read-only PortalBilet API не доказывает владение/резервирование места.

Таким образом схема уже может рисоваться полностью: SVG или нейтральный canvas + 12 075 серых geometry points, поверх них — подписанные Seats, которые реально появились в provider inventory.
