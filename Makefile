.PHONY: init up down ps logs migrate backend frontend status

COMPOSE := docker compose --env-file .env

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
