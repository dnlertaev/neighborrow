# Neighborrow

Сервис для обмена вещами между соседями.

## Структура

- `backend/` — Django API: регистрация, подтверждение email и вход.
- `frontend/` — приложение с интерфейсом (код добавим сюда позже).

## Запуск бэкенда на Windows

Открой терминал PowerShell в папке `backend`:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

API будет доступно на `http://127.0.0.1:8000/api/v1/auth/`. На корневом адресе пока будет 404 — там нет страницы сайта.

Для проверки открой второй терминал в папке `backend`:

```powershell
.\.venv\Scripts\python.exe manage.py test accounts
```

После регистрации письмо с ссылкой подтверждения выводится в терминал сервера. Настоящую отправку писем подключим отдельно.

## API авторизации

| Метод | Адрес |
| --- | --- |
| POST | `/api/v1/auth/register` |
| POST | `/api/v1/auth/verify-email` |
| POST | `/api/v1/auth/login` |
| POST | `/api/v1/auth/refresh` |
| POST | `/api/v1/auth/logout` |
| GET | `/api/v1/auth/me` |
