SYSTEM_PYTHON ?= python3
VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
IMAGE ?= questionnaire-ai-demo:dev
HOST ?= 0.0.0.0
PORT ?= 8000
COMPOSE ?= docker compose
COMPOSE_PROFILE ?= --profile observability

.PHONY: venv install install-observability image up down ps logs runtime-health bootstrap bootstrap-topics bootstrap-schemas bootstrap-acls cli serve serve-traced test-unit test-contract test-service test-integration test-scenario test-acl test-api test-ui

venv:
	$(SYSTEM_PYTHON) -m venv $(VENV)

install: venv
	$(PYTHON) -m pip install -e ".[dev]"

install-observability: venv
	$(PYTHON) -m pip install -e ".[dev,observability]"

image:
	docker build -t $(IMAGE) .

up:
	$(COMPOSE) $(COMPOSE_PROFILE) up -d --build

down:
	$(COMPOSE) $(COMPOSE_PROFILE) down -v

ps:
	$(COMPOSE) $(COMPOSE_PROFILE) ps

logs:
	$(COMPOSE) $(COMPOSE_PROFILE) logs -f app

runtime-health:
	$(COMPOSE) exec -T app python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5).read()"
	$(COMPOSE) exec -T app python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/connection', timeout=15).read()"

bootstrap:
	$(COMPOSE) run --rm bootstrap

bootstrap-topics:
	$(COMPOSE) run --rm --no-deps app python scripts/bootstrap_topics.py

bootstrap-schemas:
	$(COMPOSE) run --rm --no-deps app python scripts/bootstrap_schemas.py

bootstrap-acls:
	$(COMPOSE) run --rm --no-deps app python scripts/bootstrap_acls.py

cli:
	$(COMPOSE) run --rm --no-deps app demo --help

serve:
	$(COMPOSE) up -d --build app

serve-traced:
	$(COMPOSE) $(COMPOSE_PROFILE) up -d --build app langfuse-web langfuse-worker

test-unit:
	$(COMPOSE) run --rm --no-deps app python -m pytest tests/unit

test-contract:
	$(COMPOSE) run --rm --no-deps app python -m pytest tests/contract

test-service:
	$(COMPOSE) run --rm --no-deps app python -m pytest tests/service

test-integration:
	$(COMPOSE) run --rm --no-deps app python -m pytest tests/integration

test-scenario:
	$(COMPOSE) run --rm --no-deps app python -m pytest tests/scenario

test-acl:
	$(COMPOSE) run --rm --no-deps app python -m pytest tests/acl

test-api:
	$(COMPOSE) run --rm --no-deps app python -m pytest tests/integration/test_api.py tests/api

test-ui:
	$(COMPOSE) run --rm --no-deps app python -m pytest tests/ui
