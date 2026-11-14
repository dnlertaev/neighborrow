# Neighborrow

Neighborrow — учебный веб-проект для обмена вещами и услугами между соседями. Пользователь выбирает жилой комплекс, подтверждает его кодом и видит объявления жителей своего ЖК. Можно разместить своё объявление, найти подходящее предложение и связаться с автором.

## Что реализовано

- Регистрация, вход и профиль пользователя.
- Подтверждение жилого комплекса по коду.
- Создание, поиск и фильтрация объявлений по категориям.
- Подбор встречных предложений, отклики и история активности.
- Разграничение доступа: объявления и контакты доступны с учётом ЖК и прав пользователя.

Фронтенд написан на React и TypeScript с использованием Vinext. Серверная часть — Django REST Framework, авторизация — JWT. Для локальной работы используется SQLite.

## Запуск на Windows

Понадобятся Python 3.12+, Node.js 22.13+ и pnpm. Команды ниже выполняются в PowerShell из корня проекта.

Сначала запустите сервер:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
.\.venv\Scripts\python.exe backend\manage.py migrate
.\.venv\Scripts\python.exe backend\manage.py runserver
```

Во втором терминале запустите интерфейс. Если зависимости уже установлены в `frontend/node_modules`, шаг с `pnpm install` можно пропустить:

```powershell
cd frontend
pnpm install --frozen-lockfile
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm.cmd run dev
```

Приложение откроется по адресу `http://localhost:5173`, API — `http://127.0.0.1:8000/api/v1/`. Локальная база выбирается в `backend/.env` через `NEIGHBORROW_SQLITE_PATH`; если переменная не задана, используется `backend/db.sqlite3`.

Для PostgreSQL вместо основного списка зависимостей установите `backend/requirements-postgres.txt` и задайте `DATABASE_URL` в `backend/.env`.

## Как попробовать

Для новой базы после миграций создайте администратора из корня проекта:

```powershell
.\.venv\Scripts\python.exe backend\manage.py createsuperuser
```

В админке `http://127.0.0.1:8000/admin/` добавьте жилой комплекс в разделе **Residential complexes** и задайте код длиной не менее восьми символов. Затем зарегистрируйте пользователя в приложении и подтвердите ЖК этим кодом. В новой базе миграции создают категории, но пользователей и объявлений изначально нет.

## Проверка

Из корня проекта можно запустить тесты сервера и сквозную проверку API-клиента:

```powershell
.\.venv\Scripts\python.exe backend\manage.py test accounts listings
.\.venv\Scripts\python.exe scripts\test-fullstack.py
```

Сквозной тест использует временную базу и не меняет локальные данные. Описание маршрутов и форматов запросов находится в [документации API](backend/API.md).

## Ограничения проекта

Фотографии объявлений добавляются ссылкой. Загрузка файлов, встроенный чат и независимая проверка проживания пока не реализованы: принадлежность к ЖК подтверждается общим кодом. После обновления страницы нужно войти повторно; объявления и профиль при этом сохраняются в базе.
