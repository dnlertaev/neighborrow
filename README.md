# Neighborrow

Платформа для обмена вещами между соседями.

- `backend/` - Django REST API, JWT-авторизация, профиль, предложения и запросы, категории, поиск, подбор, отклики и контакты.
- `frontend/` - папка веб-клиента.

## Запуск backend на Windows

Python 3.12 или новее. Откройте PowerShell из корня репозитория:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Впишите полученный ключ в локальный `.env` как `DJANGO_SECRET_KEY='полученный-ключ'`.

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Проверка: <http://127.0.0.1:8000/api/v1/categories>.

Миграции создают категории. Пользователей и объявлений изначально нет; сначала зарегистрируйтесь через API.

Подробная инструкция по запуску, настройка клиентов и развёртывания: [backend/README.md](backend/README.md).

Поля запросов, ответы и маршруты без завершающего слеша: [backend/API.md](backend/API.md).

## Проверка

Из папки `backend`:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test accounts listings
```

Тесты проверяют авторизацию и JWT, права владельца, приватность контактов и активности, ленту, фильтры, подбор и отклики без дублей.

В репозитории хранится только `.env.example`. Реальный `.env`, базы и пользовательские файлы остаются локально.
