# Back to Boring GenAI Demo

Conference demo for **Back to the Boring: GenAI That Ships**.

The demo shows a Kafka-governed questionnaire workflow where every meaningful
transition goes through Kafka, every event is Avro-governed through Schema
Registry, Codex investigates evidence through a bounded agent loop before
drafting, a policy guard validates the draft, a human review event is required
before export, and Kafka ACLs prevent the AI drafter from bypassing review.

## Prerequisites

- Docker Desktop or a compatible Docker runtime.
- A ChatGPT subscription login for Codex. The app image installs Codex CLI and
  mounts `${CODEX_HOME:-$HOME/.codex}` into the app container so the demo can
  reuse or create that login and persist Codex session metadata.

No host Python, Node, Kafka, Schema Registry, or UI build tooling is required.

```bash
docker compose build app
docker compose run --rm --no-deps app codex login status
```

If the status command says you are not logged in, run
`docker compose run --rm --no-deps app codex login`.

## Quick Start

```bash
docker compose --profile observability up -d --build
docker compose exec -T app python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/connection', timeout=15).read()"
```

Then open:

- Demo UI: `http://localhost:8000/v3`
- AKHQ: `http://localhost:8080`
- Langfuse: `http://localhost:3000`

If port 8000 is busy:

```bash
APP_PORT=8003 docker compose --profile observability up -d --build
```

Then open `http://localhost:8003/v3`.

## Start Runtime

The runtime uses Docker Compose for the API, CLI, Confluent Kafka, Schema
Registry, AKHQ, and local Langfuse. Kafka payloads use Avro with Confluent
Schema Registry framing. The app container talks to Kafka through a SASL/PLAIN
listener so the ACL demo remains meaningful inside Docker.

```bash
docker compose --profile observability up -d --build
docker compose exec -T app python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5).read()"
docker compose exec -T app python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/connection', timeout=15).read()"
```

This builds the app image, starts the full stack, and runs the bootstrap
container for topics, schemas, and ACLs. If you have `make`, the same flow is:

```bash
make up
make runtime-health
```

Open AKHQ at `http://localhost:8080` to inspect topics, schema-backed payloads,
consumer groups, and the audit/security events while the demo runs. AKHQ is an
operator console in this local stack; it connects to the internal Docker broker
listener and Schema Registry.

Open Langfuse at `http://localhost:3000`.

Local demo credentials:

- Email: `demo@example.test`
- Password: `demo-password`
- Public key: `pk-lf-demo-local`
- Secret key: `sk-lf-demo-local`

To reset everything:

```bash
docker compose --profile observability down -v
docker compose --profile observability up -d --build
docker compose exec -T app python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5).read()"
```

Use this reset after pulling schema-format changes; old local JSON-serialized
messages are not migrated.

## Containers

| Service | Purpose | Host URL |
| --- | --- | --- |
| `app` | FastAPI API, static demo UIs, CLI entrypoint, tests, Codex CLI | `http://localhost:${APP_PORT:-8000}` |
| `bootstrap` | One-shot topic, schema, and ACL setup | none |
| `broker` | Confluent Kafka broker with ACLs | `localhost:9092` |
| `schema-registry` | Confluent Schema Registry for Avro schemas | `http://localhost:8081` |
| `akhq` | Kafka inspection console | `http://localhost:8080` |
| `langfuse-web` | Local tracing UI | `http://localhost:3000` |
| `langfuse-worker`, `langfuse-postgres`, `langfuse-clickhouse`, `langfuse-redis`, `langfuse-minio` | Local Langfuse dependencies | internal |

The UI is not a separate frontend container. The `app` image copies `web/` into
the container and FastAPI serves:

- `/v3` current presenter UI
- `/v2` fallback UI
- `/` original fallback UI

## CLI Demo

```bash
docker compose run --rm --no-deps app demo codex preflight
docker compose run --rm --no-deps app demo run happy-path --until review
docker compose run --rm --no-deps app demo review approve Q-001 --run-id <run_id>
docker compose run --rm --no-deps app demo export --run-id <run_id>
docker compose run --rm --no-deps app demo run swarm --concurrency 2
docker compose run --rm --no-deps app demo attack ai-direct-write --run-id rehearsal-attack
docker compose run --rm --no-deps app demo audit --run-id rehearsal-attack
```

The happy path is intentionally agentic but bounded. Codex must make at least
two evidence tool calls and no more than four before it can draft. The demo uses
deterministic synthetic evidence search and an AI-safe evidence inspection tool,
so Codex can choose what to inspect while the evidence gateway still controls
what content is exposed.

Useful command-line fallback for a live demo:

```bash
docker compose run --rm --no-deps app demo run happy-path --until review
docker compose run --rm --no-deps app demo review approve Q-001 --run-id <run_id>
docker compose run --rm --no-deps app demo export --run-id <run_id>
docker compose run --rm --no-deps app demo run swarm --concurrency 2
docker compose run --rm --no-deps app demo attack ai-direct-write --run-id rehearsal-attack
docker compose run --rm --no-deps app demo audit --run-id rehearsal-attack
```

The optional CLI swarm path launches bounded Codex drafter agents across all
ten questions with child run IDs and concurrency capped at three. It stops at
draft plus policy guard; it does not review or export swarm answers. Use
Langfuse as the swarm view with the printed `session_id` or `swarm_id`.

Developer validation scenarios still exist for regression testing, but they are
not the presenter flow:

```bash
docker compose run --rm --no-deps app demo scenario test
docker compose run --rm --no-deps app demo run restricted-evidence
docker compose run --rm --no-deps app demo run hallucinated-evidence
docker compose run --rm --no-deps app demo run malformed-draft
docker compose run --rm --no-deps app demo run unsupported-claim
docker compose run --rm --no-deps app demo run export-shortcut
```

## API and UI

The API and UI run inside the `app` container. They are thin wrappers around
the same scenario runner used by the CLI.

```bash
docker compose --profile observability up -d --build
```

Open `http://localhost:8000/v3` for the focused proof-harness presenter
surface. The old root UI remains at `http://localhost:8000/` and UI v2 remains
at `http://localhost:8000/v2` as fallbacks.

If port 8000 is already in use, set `APP_PORT` when starting the stack:

```bash
APP_PORT=8003 docker compose --profile observability up -d --build
```

The v3 presenter flow intentionally pauses after the policy guard accepts the
draft. Use `Run Useful Path` to drive the Q-001 pipeline; the API also starts a
background swarm with separate child run IDs, but the dashboard stays focused on
the single Q-001 flow. Use Langfuse as the swarm view; a `Run Useful Path` click
uses the allocated run ID as the Langfuse session ID for both the visible Q-001
trace and its background swarm traces. Use `Approve Draft` to emit the human
review event, then `Export Response` to emit the final response-ready event. Use
`Test AI Direct Write` to show Kafka denying `svc-ai-drafter` from writing
directly to the export-ready topic. Use `Open AKHQ` from the UI to inspect the
same Kafka topics under the hood.

UI v2 API additions are available for a separate frontend harness: preallocate a
run with `POST /demo/runs/allocate`, subscribe with
`GET /demo/stream/{run_id}`, inspect recent runs with `GET /demo/runs`, load
question/evidence views with `GET /demo/questionnaire` and
`GET /demo/question/{question_id}`, peek Kafka topics with
`GET /demo/topics/{topic}/events`, render Avro schemas with
`GET /demo/schemas/{subject}`, display ACL intent with
`GET /demo/authority-boundary`, and check dependencies with
`GET /health/connection`.

Key endpoints:

- `GET /health`
- `GET /health/connection`
- `POST /demo/runs/allocate`
- `GET /demo/stream/{run_id}`
- `GET /demo/runs`
- `POST /demo/reset`
- `GET /demo/questionnaire`
- `GET /demo/question/{question_id}`
- `POST /demo/run/{scenario_id}`
- `POST /demo/run/happy-path?until=review`
- `GET /demo/state/{run_id}`
- `GET /demo/audit/{run_id}`
- `POST /demo/swarm?concurrency=2`
- `GET /demo/swarm/{swarm_id}`
- `GET /demo/topics/{topic}/events`
- `GET /demo/schemas/{subject}`
- `GET /demo/authority-boundary`
- `POST /demo/review/{run_id}/{question_id}`
- `POST /demo/export/{run_id}`
- `POST /demo/attack/ai-direct-write/{run_id}`
- `POST /demo/attack/ai-direct-write/{run_id}?target_topic=answer.reviewed.v1`

## Tests

```bash
docker compose run --rm --no-deps app python -m pytest tests/unit
docker compose run --rm --no-deps app python -m pytest tests/contract
docker compose run --rm --no-deps app python -m pytest tests/service
docker compose run --rm --no-deps app python -m pytest tests/integration
docker compose run --rm --no-deps app python -m pytest tests/scenario
docker compose run --rm --no-deps app python -m pytest tests/acl
docker compose run --rm --no-deps app python -m pytest tests/integration/test_api.py tests/api
docker compose run --rm --no-deps app python -m pytest tests/ui
```

Codex live smoke tests are intentionally opt-in:

```bash
docker compose run --rm --no-deps -e DEMO_RUN_CODEX_TESTS=1 app python -m pytest tests/scenario/test_happy_path.py -q
docker compose run --rm --no-deps -e DEMO_RUN_CODEX_TESTS=1 app python -m pytest tests/api -q -m codex
```

Recommended rehearsal for the agent loop:

```bash
docker compose run --rm --no-deps app demo run happy-path --until review --run-id rehearsal-agent-1
docker compose run --rm --no-deps app demo run happy-path --until review --run-id rehearsal-agent-2
docker compose run --rm --no-deps app demo run happy-path --until review --run-id rehearsal-agent-3
docker compose run --rm --no-deps app demo run swarm --concurrency 2
```

Each run should report `Agent tool calls: 2`, `Policy guard: accepted`, and
`Human Review: required`.

Local Langfuse tracing is enabled by the Compose stack. Each run records the
Codex turns and governed evidence tool calls as Langfuse observations. The app
container uses the internal `http://langfuse-web:3000` endpoint for ingestion;
presenters open Langfuse through `http://localhost:3000`.

## Rehearsal Checklist

1. `docker compose --profile observability down -v`
2. `docker compose --profile observability up -d --build`
3. `docker compose exec -T app python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/connection', timeout=15).read()"`
4. `docker compose run --rm --no-deps app demo codex preflight`
5. Open AKHQ at `http://localhost:8080`
6. Open Langfuse at `http://localhost:3000`
7. `docker compose run --rm --no-deps app demo run happy-path --until review`
8. `docker compose run --rm --no-deps app demo review approve Q-001 --run-id <run_id>`
9. `docker compose run --rm --no-deps app demo export --run-id <run_id>`
10. `docker compose run --rm --no-deps app demo attack ai-direct-write --run-id rehearsal-attack`
11. `docker compose run --rm --no-deps app demo audit --run-id rehearsal-attack`
12. `docker compose run --rm --no-deps app demo run swarm --concurrency 2`
13. `docker compose run --rm --no-deps app python -m pytest tests/acl`
14. Open `http://localhost:8000/v3`, run Useful Path, approve the draft,
    export the response, switch to Langfuse to show swarm traces, and test AI
    Direct Write.

## Not Production

This is a conference demo. It uses local demo credentials, local Docker,
synthetic fixtures, simple prompts, a compact policy guard, and direct service
principals for clarity. A production implementation would need managed secrets,
network isolation, stronger identity, schema compatibility policy, retries,
dead-letter handling, observability, prompt/version governance, more complete
test data, load tests, failure recovery, and security review.
