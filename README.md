# TG Task Tracker — Telegram Mini App

Таск-трекер в формате Telegram Mini App: доски, задачи по статусам, участники и комментарии.

## Стек

- **Python 3.13**, FastAPI, SQLAlchemy 2 (async), aiogram 3, Alembic
- **MySQL 8**
- Vanilla JS + Telegram WebApp SDK

## Структура проекта

```
TGTaskTracker/
├── backend/                 # Python API (FastAPI)
│   ├── app/
│   │   ├── api/             # HTTP-роуты
│   │   ├── services/        # бизнес-логика
│   │   ├── repositories/    # доступ к БД
│   │   ├── models/          # SQLAlchemy ORM
│   │   ├── schemas/         # Pydantic DTO
│   │   ├── auth/            # Telegram WebApp auth
│   │   ├── infra/           # БД, логи, storage, rate limit
│   │   ├── core/            # config, paths, Application
│   │   └── bot/             # Telegram-бот
│   ├── alembic/             # миграции
│   ├── Dockerfile
│   └── run.py
├── frontend/                # Mini App (HTML + JS)
├── deploy/
│   └── docker-compose.yml   # Docker для prod/dev
├── scripts/                 # backup-db, restore-db
├── data/                    # runtime (gitignored)
│   ├── logs/
│   ├── uploads/
│   └── backups/
├── Makefile
└── .env                     # конфиг
```

## Возможности

- **Доски** — список, создание, редактирование, удаление
- **Задачи** — 5 статусов: «Новая», «В работе», «На согласовании», «Правки», «Согласована»
- **Описание задачи**, дедлайн, редактирование и удаление
- **Участники** — добавление и удаление по `@username`
- **Комментарии** — текст и фото (сжатие на сервере)
- **Темы** — светлая / тёмная
- **Логирование** — `data/logs/application.log` с ротацией
- **Снепшоты БД** — `make backup` / `make restore`

## Быстрый старт

```bash
make help      # все команды
make env       # venv + зависимости
make db        # MySQL
make up        # всё в Docker
make app-logs  # логи приложения
```

### Локально (без Docker для API)

```bash
make env && make db
cd backend && ../.venv/bin/python run.py
```

При `DEBUG=true` API принимает заголовок `X-Dev-User-Id`.

### Telegram-бот

1. [@BotFather](https://t.me/BotFather) → `/newbot` → `BOT_TOKEN`
2. `/newapp` → HTTPS-URL (ngrok: `ngrok http 8000` → `WEBAPP_URL`)

## API

Заголовок `X-Telegram-Init-Data` (автоматически из mini app).

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/health` | Проверка БД |
| GET | `/api/me` | Текущий пользователь |
| GET | `/api/boards` | Список досок |
| POST | `/api/boards` | Создать доску |
| GET | `/api/boards/{id}` | Доска + участники + задачи |
| PATCH | `/api/boards/{id}` | Переименовать (владелец) |
| DELETE | `/api/boards/{id}` | Удалить (владелец) |
| GET | `/api/boards/{id}/members` | Участники |
| POST | `/api/boards/{id}/members` | Добавить участника |
| DELETE | `/api/boards/{id}/members/{id}` | Удалить участника |
| POST | `/api/boards/{id}/tasks` | Создать задачу |
| GET | `/api/tasks/{id}` | Задача |
| PATCH | `/api/tasks/{id}` | Обновить задачу |
| DELETE | `/api/tasks/{id}` | Удалить задачу |
| GET | `/api/tasks/{id}/comments` | Комментарии |
| POST | `/api/tasks/{id}/comments` | Комментарий (+ фото) |
| DELETE | `/api/tasks/{id}/comments/{id}` | Удалить комментарий |
| GET | `/api/uploads/{file}?e=&sig=` | Фото (подписанный URL) |

## Безопасность (production)

```env
ENV=production
DEBUG=false
BOT_TOKEN=<токен>
MYSQL_PASSWORD=<сильный пароль>
WEBAPP_URL=https://your-domain.com
CORS_ORIGINS=https://your-domain.com
```

При `ENV=production` приложение **не запустится**, если `DEBUG=true`, нет `BOT_TOKEN`, слабый пароль БД, `WEBAPP_URL` без HTTPS или `CORS_ORIGINS=*`.

## Beget (VPS + MySQL)

На VPS поднимается только приложение. MySQL — в панели Beget (раздел «MySQL»).

```env
DATABASE_URL=mysql://user:password@host.beget.tech:3306/dbname
BOT_TOKEN=...
WEBAPP_URL=https://your-domain.com
ENV=production
DEBUG=false
```

```bash
docker compose -f deploy/docker-compose.yml up -d --build app
```

## Логи

- Файл: `data/logs/application.log`
- Ротация: 5 MB × 5 файлов
- Уровень: `LOG_LEVEL=DEBUG|INFO|WARNING|ERROR`

```bash
make app-logs
grep "action=" data/logs/application.log
grep ERROR data/logs/application.log
```

## Бэкапы MySQL

```bash
make backup    # → data/backups/
make backups   # список

FORCE=1 make restore SNAPSHOT=data/backups/tasktracker_2026-07-03_120000.sql
```

Перед restore: `make down`. Для полного переноса скопируйте также `data/uploads/`.

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `BACKUPS_DIR` | `./data/backups` | Папка снепшотов |
| `SNAPSHOT_KEEP` | `10` | Сколько хранить |
| `FORCE` | — | `FORCE=1` для restore |

## Масштабирование

- Stateless API + MySQL (volume `mysqldata` в Docker или Beget MySQL)
- Файлы в `data/` (логи, uploads, backups)
- Миграции: `make migrate` или автоматически при старте
