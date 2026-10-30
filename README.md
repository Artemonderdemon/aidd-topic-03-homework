# Investing Demo

Учебное Django-приложение для мониторинга акций через Tinkoff Invest API.

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
python manage.py migrate
python manage.py add_shares
python manage.py runserver
```

Приложение будет доступно по адресу http://127.0.0.1:8000/.

## Внешние сервисы

PostgreSQL и Redis можно поднять через Docker Compose:

```bash
docker compose up -d
```

Для PostgreSQL установите `DB_ENGINE=postgres` в `.env`.

## Фоновые задачи

```bash
celery -A config worker -l info
celery -A config beat
```

## API

REST API доступен по адресу `/api/v1/shares/`.

## Проверка

```bash
python manage.py test
```
