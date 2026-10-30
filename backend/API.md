# Neighborrow API v1

Базовый путь: `/api/v1`. Все примеры — JSON. URL без завершающего слеша. Для закрытых методов передавайте:

```http
Authorization: Bearer <access>
Content-Type: application/json
```

## Авторизация

`POST /auth/register`:

```json
{
  "email": "neighbor@example.com",
  "password": "Use-your-own-strong-password!",
  "password_repeat": "Use-your-own-strong-password!",
  "first_name": "Sultan",
  "last_name": "Baibolov"
}
```

Успех: `201`, профиль из регистрационных полей без пароля. Подтверждение почты не требуется. Следующий запрос — `POST /auth/login` с `email` и `password`. Ответ `200`:

```json
{
  "access": "<access JWT>",
  "refresh": "<refresh JWT>",
  "user": {
    "id": 1,
    "email": "neighbor@example.com",
    "first_name": "Sultan",
    "last_name": "Baibolov",
    "address": "",
    "phone": "",
    "social_url": ""
  }
}
```

Email нормализуется в нижний регистр. Неверные данные входа возвращают `400` с `non_field_errors`, неверный/истёкший JWT — `401`. Доступ ограничивается по частоте: `429`.

`POST /auth/refresh`: `{"refresh":"<refresh>"}`. Возвращает новую пару `access`/`refresh`. Сохраняйте оба новых значения: использованный refresh больше не действителен.

`POST /auth/logout`: тот же JSON + access в Authorization. Отзывает только refresh текущей сессии, ответ `204`. Клиент должен очистить оба токена. Уже выданный access действует до истечения срока (15 минут); logout не является немедленным отзывом access. Refresh действует до 7 дней. Для регулярной очистки истёкших токенов доступна штатная команда `manage.py flushexpiredtokens`.

## Профиль и пароль

`GET /auth/me` возвращает профиль. `PATCH /auth/me` принимает `first_name`, `last_name`, `address`, `phone`, `social_url`. Поля `id` и `email` только для чтения; административные права нельзя изменить через этот API. Телефон и адрес профиля не публикуются автоматически.

`POST /auth/password/change`:

```json
{
  "current_password": "<current password>",
  "new_password": "<new strong password>",
  "new_password_repeat": "<new strong password>"
}
```

После `200` очистите токены и откройте вход. Старые access и refresh больше не принимаются.

`DELETE /auth/me`: `{"current_password":"<current password>"}`. Ответ `204`. Удаляет текущий аккаунт и его объявления. Требует явного подтверждения пользователя в интерфейсе.

## Категории

`GET /categories` доступен без входа и возвращает массив `{id,name,slug}`. Категории: Tools, Garden, Outdoors, Electronics, Sports, Home & living. Используйте полученные `id`, не закрепляйте номера в интерфейсе.

## Объявления

`POST /listings` требует входа:

```json
{
  "type": "offer",
  "title": "Small hammer",
  "description": "A hammer for small projects. Please return it clean.",
  "category": 1,
  "condition": "good",
  "duration": "Up to 2 hours",
  "needed_until": null,
  "available": true,
  "neighborhood": "Almaly, Almaty",
  "latitude": 43.25,
  "longitude": 76.95,
  "image_url": "",
  "contact_phone": "+77001234567",
  "contact_social": ""
}
```

Здесь `category: 1` — пример, подставьте фактический ID из `/categories`.

Обязательны `type`, `title`, `description`, `category`, `duration`. Тип: `offer` или `request`. Условие: `good`, `like_new`, `any_working`. Дата `needed_until` — `YYYY-MM-DD`, не раньше текущей даты; можно `null`. Координаты передаются парой, без них расстояние неизвестно. `image_url` и `contact_social` — HTTP(S)-ссылки, backend их не скачивает. Бинарная загрузка файлов не предусмотрена.

Успех `201`. Владелец определяется по JWT. Ответ и `GET /listings/{id}` содержат публичные поля объявления, `owner: {id,display_name}`, `category_name`, `mine`, `has_responded`, `created_at`, `updated_at`, `distance_km`. Контакты и точные координаты из публичного ответа исключены. Расстояние — километры или `null`; не показывайте случайное расстояние для записей без координат.

`PATCH /listings/{id}` и `DELETE /listings/{id}` разрешены только владельцу. Другой пользователь получает `403`. Тип существующего объявления менять нельзя: создайте новое. Удаление возвращает `204`. Поля контактов доступны для записи, чтение — через `/contacts`.

### Лента и фильтры

`GET /listings`:

| Параметр | Значение |
| --- | --- |
| `type` | `all`, `offer`, `request` |
| `category` | ID категории |
| `search` | Поиск по названию, описанию и категории; до 200 символов |
| `available` | `true` / `false`; true исключает просроченные объявления; при отсутствии возвращаются оба состояния |
| `mine` | `true` — объявления текущего пользователя, требуется JWT |
| `ordering` | `newest` (по умолчанию), `oldest`, `nearest` |
| `latitude`, `longitude` | Текущие координаты для расчёта расстояния |
| `radius_km` | От 0.1 до 100; требует координат |
| `page` | Номер страницы, начиная с 1 |
| `page_size` | По умолчанию 20, максимум 100 |

`nearest` также требует координат; записи без координат идут последними. Радиус исключает записи с неизвестным расстоянием. Расстояние вычисляется по прямой на сфере, не по автомобильному маршруту. Адрес в профиле не геокодируется.

Пример: `/listings?type=offer&search=hammer&latitude=43.25&longitude=76.95&radius_km=2&ordering=nearest`.

Ответ списков (`listings`, `matches`, `activity`):

```json
{"count": 1, "next": null, "previous": null, "results": []}
```

`results` в реальном ответе содержит найденные записи; в примере массив сокращён.

### Подбор

`GET /listings/{id}/matches` ищет доступные объявления противоположного типа в той же категории, исключает того же владельца и объявления с прошедшим `needed_until`. Совпадения слов в названиях поднимаются выше, затем сортировка по новизне. Это список кандидатов, а не гарантия соответствия конкретной модели предмета. Закрытое или просроченное исходное объявление даёт пустой список. Отклики/принятие не создаются автоматически.

### Связь и отклик

`GET /listings/{id}/contacts` требует JWT:

```json
{"owner":{"id":1,"display_name":"Sultan B."},"phone":"+77001234567","social_url":""}
```

Показываются только контакты, явно указанные при публикации этого объявления. Пустые строки означают, что контакты не указаны. Личный телефон профиля не используется как скрытый запасной вариант.

`POST /listings/{id}/interest` — отклик без тела. Первый запрос возвращает `201`, повторный от того же пользователя — `200`, дубль не создаётся:

```json
{"id":1,"listing":1,"created":true}
```

На собственное, недоступное или просроченное объявление откликнуться нельзя (`400`). Отклик создаёт события в активности автора объявления и откликнувшегося пользователя. Сообщение, SMS или email не отправляются.

## Активность

`GET /activity` требует JWT и возвращает только события текущего пользователя. Поля: `id`, `actor: {id,display_name}` или `null`, `type`, `listing` (ID или `null` после удаления), `item_title`, `description`, `created_at`.

Типы: `offer_created`, `request_created`, `listing_updated`, `listing_deleted`, `offer_requested`, `request_response`. Даты — ISO 8601 UTC; фронтенд форматирует их под часовой пояс пользователя.

## Подключение клиентов

1. Задать URL запущенного API и его CORS whitelist. Для HTTPS-сайта API тоже должен использовать HTTPS.
2. Для регистрации и входа вызывать `/auth/register` и `/auth/login`; при регистрации отправлять `password_repeat`.
3. После входа использовать профиль из ответа; дальнейшие изменения отправлять `PATCH /auth/me`.
4. Загружать категории и объявления через API. Названия пользователя брать из `owner.display_name`; condition отображать по словарю. В UI `All` соответствует `type=all`.
5. Создание/редактирование форм: `POST`/`PATCH /listings`; недоступность — `PATCH {"available":false}`; свои записи — `mine=true`.
6. Для контактов вызывать `/contacts`, для отклика — `/interest`. Отдельный чат не предусмотрен.
7. Активность загружать через `/activity`, подбор — через `/matches`.
8. При `401` один раз обновить пару JWT и повторить запрос; если refresh отклонён — очистить сессию и открыть вход. При `403`, `400`, `429` показывать соответствующую ошибку без автоматического повторения.
9. Токены не передавать в URL, не логировать и не хранить вместе с паролем. API возвращает Bearer JWT в JSON. Способ хранения сессии выбирается на стороне клиента: для браузера можно использовать память вкладки или отдельно реализованный cookie/BFF-поток; для Android — защищённое хранилище устройства.

`has_responded` показывает, откликнулся ли текущий пользователь; оно вычисляется по базе и не зависит от состояния клиента. Точный адрес сервера задаётся в конфигурации клиента. Для нативного Android-клиента CORS не требуется.

## Документация используемых механизмов

- [DRF: object permissions](https://www.django-rest-framework.org/api-guide/permissions/) — права владельца и отдельная проверка создания.
- [Simple JWT: settings](https://django-rest-framework-simplejwt.readthedocs.io/en/latest/settings.html) — rotation, blacklist и проверка пароля в JWT.
- [django-cors-headers](https://github.com/adamchainz/django-cors-headers) — список разрешённых origins.
