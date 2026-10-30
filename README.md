# Investing Demo

Django-приложение для просмотра списка акций, управления инструментами, REST API и получения котировок через Tinkoff Invest.

## Быстрый запуск на Windows

Требуется Python 3.12–3.14 и `uv`:

```powershell
uv venv .venv --python 3.14
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py runserver
```

Локальная разработка по умолчанию использует SQLite. Веб-интерфейс и REST API работают без PostgreSQL, Redis и токена Tinkoff. Стартовая страница доступна по адресу `http://127.0.0.1:8000/`, API акций — по адресу `http://127.0.0.1:8000/api/v1/shares/`.

## PostgreSQL и Redis

Чтобы запустить PostgreSQL и Redis в контейнерах:

```powershell
docker compose up -d
$env:DB_ENGINE = "postgresql"
$env:POSTGRES_DB = "investing"
$env:POSTGRES_USER = "postgres"
$env:POSTGRES_PASSWORD = "postgres"
$env:POSTGRES_HOST = "localhost"
$env:CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"
.venv\Scripts\python.exe manage.py migrate
```

Пароль в примере предназначен только для локальной разработки. Перед развертыванием задайте собственные секреты и корректные `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false` и `DJANGO_ALLOWED_HOSTS`.

Для запуска периодического обновления котировок нужны отдельные процессы:

```powershell
.venv\Scripts\python.exe -m celery -A config beat
.venv\Scripts\python.exe -m celery -A config worker -l info
```

Celery Beat запускает задачу обновления цен каждые 10 секунд. Broker задается переменной `CELERY_BROKER_URL`.

## Интеграция с Tinkoff Invest

SDK `tinkoff-investments` и его зависимость `tinkoff` больше не опубликованы в PyPI (публичный JSON API PyPI возвращает 404); официальный репозиторий SDK архивирован. Поэтому SDK не включен в обязательные зависимости, и основное приложение можно установить и запустить без него. Исторический график, импорт справочника и обновление котировок требуют SDK и действующий токен. SDK и его зависимости успешно установлены из последнего исходного коммита; для повторения установки:

```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements-market-data.txt
uv pip install --python .venv\Scripts\python.exe --no-deps "git+https://github.com/Tinkoff/invest-python.git@1cc84950266d62cd0bc7a43ad764dddfd4252630"
$env:TINKOFF_TOKEN = "ваш токен"
```

Upstream SDK архивирован и не тестируется с современными версиями Python. Проверены установка и импорт SDK под Python 3.14, но работа внешних вызовов требует действующий токен и отдельно не проверялась.

Импорт справочника акций:

```powershell
.venv\Scripts\python.exe manage.py add_shares
```

Данные интеграции загружаются лениво; при отсутствии SDK операция с котировками завершается явной ошибкой с пояснением вместо ошибки импорта при запуске сайта.

## Персональный мониторинг

После входа откройте «Мониторинг», добавьте акцию и задайте один или несколько целевых уровней. Переход цены через уровень вверх или вниз создаёт внутреннее уведомление; повторные наблюдения на той же стороне уровня не дублируют уведомление. Новое уведомление для того же уровня возможно после пересечения обратно. Список уведомлений доступен в меню; пользователь может отметить записи прочитанными. Автоматическое наблюдение работает, когда запущены Redis, Celery Worker, Celery Beat и доступна интеграция Tinkoff с действующим токеном.

## API и доступ

Анонимным клиентам разрешено читать список акций и отдельные записи. Для создания, изменения и удаления требуется аутентификация Django REST Framework. Пагинация списка — limit/offset, по умолчанию 100 записей; поддерживаются фильтр и сортировка по `name` и `ticker`, поиск по названию.
