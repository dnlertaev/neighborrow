# Neighborrow Auth

Бэкенд для регистрации и входа пользователей. После регистрации пользователь подтверждает email, затем может войти.

## Запуск

Открыть папку проекта в VS Code и выполнить в командной строке:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Сервер запускается на `http://127.0.0.1:8000/`.

## Маршруты

| Метод | Адрес | Назначение |
| ----- | ----- | ---------- |
| POST | `/api/v1/auth/register` | Регистрация |
| POST | `/api/v1/auth/verify-email` | Подтверждение email |
| POST | `/api/v1/auth/login` | Вход |
| POST | `/api/v1/auth/refresh` | Обновление токена |
| POST | `/api/v1/auth/logout` | Выход |
| GET | `/api/v1/auth/me` | Данные пользователя |

При локальном запуске письмо со ссылкой подтверждения выводится в терминал сервера.

## Тесты

```powershell
.\.venv\Scripts\python.exe manage.py test accounts
```

Если в конце написано `OK`, тесты прошли.
