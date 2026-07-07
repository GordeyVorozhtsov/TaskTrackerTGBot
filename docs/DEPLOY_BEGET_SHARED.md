# Деплой на Beget SHARED (mayday)

Один pipeline для shared-хостинга Beget: **без Docker, без sudo, без python3-venv**.

## Ограничения Beget shared

| Что | Статус |
|-----|--------|
| Docker | ❌ нет прав |
| `apt install` | ❌ нет sudo |
| `python3 -m venv` | ❌ нет python3-venv |
| MySQL localhost | ✅ работает |
| pip --user | ✅ работает |
| Долгоживущий процесс | ⚠️ держите через `screen` |

---

## Pipeline (copy-paste)

### 0. Локально — push в GitHub

```bash
git add -A && git commit -m "deploy" && git push
```

### 1. SSH на сервер

```bash
ssh gvoroz2u_user@mayday.beget.tech
```

### 2. Первый раз — клон

```bash
cd ~
git clone https://github.com/ВАШ_АККАУНТ/TaskTrackerTGBot.git
cd TaskTrackerTGBot
```

Если репо уже есть:

```bash
cd ~/TaskTrackerTGBot   # или ~/public_html/TaskTrackerTGBot
git pull
```

### 3. `.env` (один раз)

```bash
cp .env.beget.example .env
nano .env
```

```env
DATABASE_URL=mysql://gvoroz2u_db:ВАШ_ПАРОЛЬ@localhost:3306/gvoroz2u_db

BOT_TOKEN=123456789:ABC...
WEBAPP_URL=https://gvoroz2u.beget.tech

ENV=production
DEBUG=false
CORS_ORIGINS=https://gvoroz2u.beget.tech
LOG_LEVEL=INFO
```

**Не указывайте** `DATA_DIR=/data` и **не используйте** `host.docker.internal`.

### 4. Проверка окружения

```bash
bash scripts/check-beget.sh
```

### 5. Деплой (рекомендуется через screen)

```bash
screen -S tasktracker
bash scripts/deploy-beget-native.sh
```

Если всё OK — отсоединиться: `Ctrl+A`, затем `D`.

Без screen (процесс умрёт при закрытии SSH):

```bash
bash scripts/deploy-beget-native.sh
```

### 6. Проверка

```bash
curl http://127.0.0.1:8000/api/health
tail -20 data/logs/application.log
grep bot data/logs/application.log
```

### 7. HTTPS + домен (панель Beget)

1. Привяжите домен к сайту в панели Beget
2. Включите SSL (Let's Encrypt) в панели
3. Настройте проксирование на `127.0.0.1:8000` (nginx в панели или через поддержку)

В BotFather:
- **Domain** → ваш домен
- Mini App URL = `WEBAPP_URL` из `.env`

### 8. Каждое обновление

```bash
cd ~/TaskTrackerTGBot
git pull
bash scripts/deploy-beget-native.sh
```

---

## Команды

```bash
bash scripts/check-beget.sh          # проверка перед деплоем
bash scripts/deploy-beget-native.sh  # деплой / обновление
bash scripts/stop-beget-native.sh    # остановка
tail -f data/logs/application.log    # логи приложения
tail -f data/logs/uvicorn.stdout.log # stdout uvicorn
screen -r tasktracker                # вернуться в screen
```

---

## Если что-то сломалось

```bash
tail -50 data/logs/uvicorn.stdout.log
```

| Ошибка | Решение |
|--------|---------|
| `permission denied` docker.sock | Используйте `deploy-beget-native.sh`, не Docker |
| `ensurepip is not available` | Обновите скрипт (`git pull`) — теперь pip --user |
| MySQL connection refused | В `.env` хост `localhost`, не `host.docker.internal` |
| `ENV=production` crash | `DEBUG=false`, HTTPS в `WEBAPP_URL`, `CORS_ORIGINS` не `*` |
| Бот молчит | `BOT_TOKEN`, логи `grep bot data/logs/application.log` |
| Процесс пропал | Запускайте через `screen -S tasktracker` |

---

## VPS Beget (если перейдёте)

Тогда Docker + `deploy-beget.sh` + `host.docker.internal` в DATABASE_URL.
