SYSTEM_PYTHON ?= python3
VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
IMAGE ?= questionnaire-ai-demo:dev
HOST ?= 0.0.0.0
PORT ?= 8000

.PHONY: venv install image up down runtime-health bootstrap-topics bootstrap-schemas bootstrap-acls serve test-unit test-contract test-service test-integration test-scenario test-acl test-api test-ui

venv:
	$(SYSTEM_PYTHON) -m venv $(VENV)

install: venv
	$(PYTHON) -m pip install -e ".[dev]"

image:
	docker build -t $(IMAGE) .

up:
	docker compose up -d

down:
	docker compose down -v

runtime-health:
	$(SYSTEM_PYTHON) scripts/wait_for_kafka.py localhost 9092
	$(SYSTEM_PYTHON) scripts/wait_for_schema_registry.py http://localhost:8081

bootstrap-topics: install
	$(PYTHON) scripts/bootstrap_topics.py

bootstrap-schemas: install
	$(PYTHON) scripts/bootstrap_schemas.py

bootstrap-acls: install
	$(PYTHON) scripts/bootstrap_acls.py

serve: install
	$(PYTHON) -m uvicorn demo.api.app:app --host $(HOST) --port $(PORT)

test-unit: install
	$(PYTHON) -m pytest tests/unit

test-contract: install
	$(PYTHON) -m pytest tests/contract

test-service: install
	$(PYTHON) -m pytest tests/service

test-integration: install
	$(PYTHON) -m pytest tests/integration

test-scenario: install
	$(PYTHON) -m pytest tests/scenario

test-acl: install
	$(PYTHON) -m pytest tests/acl

test-api: install
	$(PYTHON) -m pytest tests/integration/test_api.py tests/api

test-ui: install
	$(PYTHON) -m pytest tests/ui
