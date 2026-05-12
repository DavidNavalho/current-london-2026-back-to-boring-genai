# Back to Boring GenAI Demo

Conference demo for **Back to the Boring: GenAI That Ships**.

The demo shows a Kafka-governed questionnaire workflow where every meaningful
transition goes through Kafka, every event is Avro-governed through Schema
Registry, Codex drafts answers, a policy guard validates them, a human review
event is required before export, and Kafka ACLs prevent the AI drafter from
bypassing review.

## Prerequisites

- Docker Desktop or a compatible Docker runtime.
- Python 3.11 or newer.
- Codex CLI installed and authenticated with ChatGPT subscription access.

```bash
codex login
codex login status
```

## Start Runtime

The runtime uses Confluent Kafka, Schema Registry, and AKHQ. Kafka payloads use
Avro with Confluent Schema Registry framing. Host Kafka access uses SASL/PLAIN
demo principals; internal bootstrap still runs explicitly.

```bash
make up
make runtime-health
make bootstrap-topics
make bootstrap-schemas
make bootstrap-acls
```

Open AKHQ at `http://localhost:8080` to inspect topics, schema-backed payloads,
consumer groups, and the audit/security events while the demo runs. AKHQ is an
operator console in this local stack; it connects to the internal Docker broker
listener and Schema Registry.

To reset everything:

```bash
make down
make up
make runtime-health
make bootstrap-topics
make bootstrap-schemas
make bootstrap-acls
```

Use this reset after pulling schema-format changes; old local JSON-serialized
messages are not migrated.

## CLI Demo

```bash
make install
.venv/bin/demo codex preflight
.venv/bin/demo run happy-path --until review
.venv/bin/demo review approve Q-001 --run-id <run_id>
.venv/bin/demo export --run-id <run_id>
.venv/bin/demo attack ai-direct-write --run-id rehearsal-attack
.venv/bin/demo audit --run-id rehearsal-attack
```

Useful command-line fallback for a live demo:

```bash
.venv/bin/demo run happy-path --until review
.venv/bin/demo review approve Q-001 --run-id <run_id>
.venv/bin/demo export --run-id <run_id>
.venv/bin/demo attack ai-direct-write --run-id rehearsal-attack
.venv/bin/demo audit --run-id rehearsal-attack
```

Developer validation scenarios still exist for regression testing, but they are
not the presenter flow:

```bash
.venv/bin/demo scenario test
.venv/bin/demo run restricted-evidence
.venv/bin/demo run hallucinated-evidence
.venv/bin/demo run malformed-draft
.venv/bin/demo run unsupported-claim
.venv/bin/demo run export-shortcut
```

## API and UI

The API and UI are thin wrappers around the same scenario runner used by the
CLI.

```bash
make serve
```

Open `http://localhost:8000/v3` for the focused proof-harness presenter
surface. The old root UI remains at `http://localhost:8000/` and UI v2 remains
at `http://localhost:8000/v2` as fallbacks.

If port 8000 is already in use:

```bash
.venv/bin/python -m uvicorn demo.api.app:app --host 0.0.0.0 --port 8001
```

The v3 presenter flow intentionally pauses after the policy guard accepts the
draft. Use `Approve Draft` to emit the human review event, then `Export Response`
to emit the final response-ready event. Use `Test AI Direct Write` to show
Kafka denying `svc-ai-drafter` from writing directly to the export-ready topic.
Use `Open AKHQ` from the UI to inspect the same Kafka topics under the hood.

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
- `GET /demo/topics/{topic}/events`
- `GET /demo/schemas/{subject}`
- `GET /demo/authority-boundary`
- `POST /demo/review/{run_id}/{question_id}`
- `POST /demo/export/{run_id}`
- `POST /demo/attack/ai-direct-write/{run_id}`
- `POST /demo/attack/ai-direct-write/{run_id}?target_topic=answer.reviewed.v1`

## Tests

```bash
make test-unit
make test-contract
make test-service
make test-integration
make test-scenario
make test-acl
make test-api
make test-ui
```

Codex live smoke tests are intentionally opt-in:

```bash
DEMO_RUN_CODEX_TESTS=1 .venv/bin/python -m pytest tests/scenario/test_happy_path.py -q
DEMO_RUN_CODEX_TESTS=1 .venv/bin/python -m pytest tests/api -q -m codex
```

## Rehearsal Checklist

1. `make down`
2. `make up`
3. `make runtime-health`
4. `make bootstrap-topics bootstrap-schemas bootstrap-acls`
5. `.venv/bin/demo codex preflight`
6. Open AKHQ at `http://localhost:8080`
7. `.venv/bin/demo run happy-path --until review`
8. `.venv/bin/demo review approve Q-001 --run-id <run_id>`
9. `.venv/bin/demo export --run-id <run_id>`
10. `.venv/bin/demo attack ai-direct-write --run-id rehearsal-attack`
11. `.venv/bin/demo audit --run-id rehearsal-attack`
12. `make test-acl`
13. `make serve`
14. Open `http://localhost:8000/v3`, run Useful Path, approve the draft,
    export the response, and test AI Direct Write.

## Not Production

This is a conference demo. It uses local demo credentials, local Docker,
synthetic fixtures, simple prompts, a compact policy guard, and direct service
principals for clarity. A production implementation would need managed secrets,
network isolation, stronger identity, schema compatibility policy, retries,
dead-letter handling, observability, prompt/version governance, more complete
test data, load tests, failure recovery, and security review.
