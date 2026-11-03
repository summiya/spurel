.PHONY: init up down ps logs migrate backend frontend status

# Pass the local file owner's UID/GID for bind-mounted Next.js sources.
COMPOSE := env SPUREL_HOST_UID=$(shell id -u) SPUREL_HOST_GID=$(shell id -g) docker compose --env-file .env

init:
	python3 scripts/init_dev_env.py

up: init
	$(COMPOSE) up --build -d --wait

down:
	$(COMPOSE) down

ps:
	$(COMPOSE) ps -a

logs:
	$(COMPOSE) logs --follow --tail=100

migrate:
	$(COMPOSE) run --rm migrate

backend:
	$(COMPOSE) logs --follow --tail=100 backend

frontend:
	$(COMPOSE) logs --follow --tail=100 frontend

status:
	python3 scripts/check_dev_stack.py
