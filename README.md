# Neighborrow


## Запуск


```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

`http://127.0.0.1:8000/api/v1/auth/`.

## Маршруты

| Метод | Адрес | Назначение |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | Регистрация |
| POST | `/api/v1/auth/login` | Вход |
| POST | `/api/v1/auth/refresh` | Обновление токена |
| POST | `/api/v1/auth/logout` | Выход |
| GET | `/api/v1/auth/me` | Текущий пользователь |

Для регистрации нужны `email`, `password` и `password_repeat`. После регистрации можно войти с `email` и `password`.

