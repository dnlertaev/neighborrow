# Neighborrow Backend

Django REST API для обмена вещами между соседями. Backend обслуживает сайт и Android-приложение через общий контракт `/api/v1`.

В проект входят регистрация и JWT, профиль, предложения и запросы, категории, поиск и фильтры, подбор встречных объявлений, отклики, контакты и личная активность.

## Требования

- Python 3.12 или новее для установки версий из `requirements.lock.txt`.
- SQLite для локального запуска. PostgreSQL подключается через `DATABASE_URL`.

Команды ниже выполняются из папки с `manage.py`. Фронтенд и Android Studio для запуска backend не нужны.

## Запуск на Windows

Откройте PowerShell в папке проекта:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
Copy-Item .env.example .env
```

Сгенерируйте секретный ключ:

```powershell
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Впишите результат в локальный `.env` как `DJANGO_SECRET_KEY='полученный-ключ'`. Одинарные кавычки сохраняют специальные символы ключа. Затем:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Проверка в браузере: <http://127.0.0.1:8000/api/v1/categories>.

Миграции создают шесть категорий. Пользователи и объявления изначально отсутствуют. Для входа сначала зарегистрируйтесь через API.

## Конфигурация

Шаблон настроек: [.env.example](.env.example). Реальный `.env` создаётся локально и в Git не добавляется.

| Переменная | Назначение |
| --- | --- |
| `DJANGO_DEBUG` | `1` для разработки, `0` для сервера |
| `DJANGO_SECRET_KEY` | Собственный секретный ключ; обязателен при `DJANGO_DEBUG=0` |
| `DJANGO_ALLOWED_HOSTS` | Разрешённые имена хостов/IP через запятую, без схемы и порта |
| `CORS_ALLOWED_ORIGINS` | Адреса браузерного фронтенда со схемой и портом |
| `CSRF_TRUSTED_ORIGINS` | Доверенные origins для запросов с cookie, например админки за reverse proxy |
| `DATABASE_URL` | Пусто для SQLite; PostgreSQL URL для общей базы |
| `DJANGO_TRUST_PROXY` | `1` только за доверенным proxy, который устанавливает `X-Forwarded-Proto` |

Для локальной разработки без заданного ключа используется встроенный ключ разработки. Для постоянной сессии и серверного развёртывания задайте собственный ключ в `.env` или переменных окружения.

`requirements.lock.txt` фиксирует версии зависимостей. `requirements.txt` содержит допустимые диапазоны для их отдельного обновления.

### Подключение клиентов

- Сайт передаёт запросы на адрес работающего API. Его origin должен входить в `CORS_ALLOWED_ORIGINS`.
- Стандартный Android Emulator обращается к компьютеру через `http://10.0.2.2:8000/api/v1/`. Добавьте `10.0.2.2` в `DJANGO_ALLOWED_HOSTS` и запустите `manage.py runserver 0.0.0.0:8000`.
- Телефон в той же Wi-Fi сети использует LAN IP компьютера. Добавьте этот IP в `DJANGO_ALLOWED_HOSTS`; порт сервера должен быть доступен телефону.
- Нативному Android-клиенту не требуется настройка CORS. Авторизация выполняется через Bearer JWT.

## API

Описание тел запросов, ответов, фильтров и ограничений находится в [API.md](API.md).

Основные маршруты:

- `POST /api/v1/auth/register`, `login`, `refresh`, `logout`.
- `GET/PATCH/DELETE /api/v1/auth/me`.
- `POST /api/v1/auth/password/change`.
- `GET /api/v1/categories`.
- `GET/POST /api/v1/listings`.
- `GET/PATCH/DELETE /api/v1/listings/{id}`.
- `GET /api/v1/listings/{id}/matches` и `/contacts`.
- `POST /api/v1/listings/{id}/interest`.
- `GET /api/v1/activity`.

URL API используются без завершающего `/`. Админка доступна по `/admin/`; администратора создаёт команда `manage.py createsuperuser`.

Загрузка бинарных фотографий, чат, email-уведомления и проверка проживания не реализованы. Для фотографии используется поле `image_url`.

## Проверка

Windows:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test accounts listings
```

Тесты проверяют авторизацию, JWT rotation и отзыв токенов, права владельца, приватность контактов и активности, фильтры, расстояния, подбор и отклики без дублей. Тестовая база создаётся отдельно от рабочей.

## Развёртывание

Для сервера задайте `DJANGO_DEBUG=0`, собственный `DJANGO_SECRET_KEY`, конкретные `DJANGO_ALLOWED_HOSTS` и origins сайта. Используйте HTTPS и WSGI-сервер с точкой входа `config.wsgi:application`; `runserver` предназначен для локальной разработки.

После настройки PostgreSQL выполните миграции. Для админки соберите статику командой `manage.py collectstatic` и настройте её обслуживание веб-сервером. Регулярно запускайте `manage.py flushexpiredtokens` для очистки истёкших JWT-записей.

Ограничение запросов сейчас использует локальный cache Django. Для нескольких процессов нужен общий cache и внешнее ограничение запросов. PostgreSQL и production-сервер требуют отдельной проверки в целевом окружении.

