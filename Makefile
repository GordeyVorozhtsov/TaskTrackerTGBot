.PHONY: help env db up down down-v logs mysql migrate app-logs backup restore backups \
	beget-up beget-down beget-logs beget-deploy beget-native

VENV     := .venv
COMPOSE  := docker compose --env-file .env -f deploy/docker-compose.yml
COMPOSE_BEGET := docker compose --env-file .env -f deploy/docker-compose.beget.yml
BACKUPS  := data/backups

help: ## Все команды
	@grep -E '^[a-zA-Z0-9_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-10s %s\n", $$1, $$2}'

# Локально
env: ## venv + зависимости
	python3.13 -m venv $(VENV)
	$(VENV)/bin/pip install -r backend/requirements.txt

db: ## только MySQL
	$(COMPOSE) up db -d

migrate: ## миграции Alembic
	cd backend && ../$(VENV)/bin/alembic upgrade head

app-logs: ## tail data/logs/application.log
	tail -f data/logs/application.log

# Docker
up: ## app + db (фон, с rebuild)
	$(COMPOSE) up -d --build

down: ## остановить контейнеры
	$(COMPOSE) down

down-v: ## остановить + удалить volumes
	$(COMPOSE) down -v

logs: ## логи контейнеров
	$(COMPOSE) logs -f

mysql: ## консоль MySQL
	$(COMPOSE) exec db sh -c 'mysql -u "$$MYSQL_USER" -p"$$MYSQL_PASSWORD" "$$MYSQL_DATABASE"'

# Бэкапы
backup: ## снепшот БД → data/backups/
	bash scripts/backup-db.sh

restore: ## восстановить (SNAPSHOT=... FORCE=1)
	bash scripts/restore-db.sh "$(SNAPSHOT)"

backups: ## список снепшотов
	@ls -lh $(BACKUPS)/tasktracker_*.sql 2>/dev/null || echo "Нет снепшотов — make backup"

# Beget (VPS + внешний MySQL)
beget-up: ## prod: только app, MySQL в панели Beget
	$(COMPOSE_BEGET) up -d --build

beget-down: ## остановить app на Beget
	$(COMPOSE_BEGET) down

beget-logs: ## логи app на Beget
	$(COMPOSE_BEGET) logs -f app

beget-deploy: ## деплoy VPS (Docker)
	bash scripts/deploy-beget.sh

beget-native: ## Beget shared: запуск/остановка (make beget-native / make beget-native-stop)
	bash scripts/deploy-beget-native.sh

beget-native-stop:
	bash scripts/deploy-beget-native.sh stop
