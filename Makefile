SYSTEM_PYTHON ?= python3
VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
IMAGE ?= questionnaire-ai-demo:dev
HOST ?= 0.0.0.0
PORT ?= 8000

.PHONY: venv install install-observability image up down observability-up observability-health observability-stop runtime-health bootstrap-topics bootstrap-schemas bootstrap-acls serve serve-traced test-unit test-contract test-service test-integration test-scenario test-acl test-api test-ui

venv:
	$(SYSTEM_PYTHON) -m venv $(VENV)

install: venv
	$(PYTHON) -m pip install -e ".[dev]"

install-observability: venv
	$(PYTHON) -m pip install -e ".[dev,observability]"

image:
	docker build -t $(IMAGE) .

up:
	docker compose up -d

down:
	docker compose down -v

observability-up:
	docker compose --profile observability up -d langfuse-web langfuse-worker

observability-health:
	$(SYSTEM_PYTHON) scripts/wait_for_langfuse.py http://localhost:3000

observability-stop:
	docker compose --profile observability stop langfuse-web langfuse-worker langfuse-postgres langfuse-clickhouse langfuse-minio langfuse-redis

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

serve-traced: install-observability
	LANGFUSE_BASE_URL=http://localhost:3000 LANGFUSE_PUBLIC_KEY=pk-lf-demo-local LANGFUSE_SECRET_KEY=sk-lf-demo-local $(PYTHON) -m uvicorn demo.api.app:app --host $(HOST) --port $(PORT)

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
