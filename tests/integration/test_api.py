from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from demo.config import Settings
from demo.api.app import app


ROOT = Path(__file__).resolve().parents[2]
client = TestClient(app)


def _runtime_available() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:8081/subjects", timeout=2) as response:
            json.loads(response.read().decode("utf-8"))
        return True
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False


def _acl_mode() -> bool:
    return Settings().kafka_security_protocol.startswith("SASL")


def _codex_enabled() -> bool:
    return os.getenv("DEMO_RUN_CODEX_TESTS") == "1"


def _demo(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(ROOT / ".venv" / "bin" / "demo"), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_api_scenario_outcome_matches_cli_expectation():
    api_response = client.post("/demo/run/hallucinated-evidence")
    assert api_response.status_code == 200
    api_payload = api_response.json()
    assert "UNKNOWN_EVIDENCE_ID" in api_payload["reason_codes"]

    cli = _demo(["run", "hallucinated-evidence"])
    assert cli.returncode == 0, cli.stdout
    assert "UNKNOWN_EVIDENCE_ID" in cli.stdout


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_api_state_shows_rejection_for_negative_scenario():
    run = client.post("/demo/run/unsupported-claim").json()

    state = client.get(f"/demo/state/{run['run_id']}")

    assert state.status_code == 200
    payload = state.json()
    assert payload["topics"]["answer.draft.rejected.v1"]["count"] >= 1
    assert "UNSUPPORTED_CLAIM" in payload["reason_codes"]
    assert payload["topics"]["questionnaire.response.ready.v1"]["count"] == 0


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
@pytest.mark.skipif(not _acl_mode(), reason="Kafka ACL mode is not enabled")
def test_api_direct_ai_write_attack_returns_denied():
    run_id = "run-api-direct-write"

    response = client.post(f"/demo/attack/ai-direct-write/{run_id}")

    assert response.status_code == 200
    assert response.json()["denied"] is True


@pytest.mark.codex
@pytest.mark.skipif(not _codex_enabled(), reason="Set DEMO_RUN_CODEX_TESTS=1 to run Codex API test")
@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_api_can_trigger_happy_path_when_codex_enabled():
    response = client.post("/demo/run/happy-path")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario_id"] == "happy-path"
    assert payload["response_ready"] is True


@pytest.mark.codex
@pytest.mark.skipif(not _codex_enabled(), reason="Set DEMO_RUN_CODEX_TESTS=1 to run Codex API test")
@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_api_can_pause_happy_path_for_human_review_then_export():
    response = client.post("/demo/run/happy-path?until=review")

    assert response.status_code == 200
    payload = response.json()
    run_id = payload["run_id"]
    assert payload["human_review_required"] is True
    assert payload["response_ready"] is False

    paused_state = client.get(f"/demo/state/{run_id}").json()
    assert paused_state["workflow_status"] == "human_review_required"
    assert paused_state["topics"]["answer.draft.accepted.v1"]["count"] == 1
    assert paused_state["topics"]["answer.reviewed.v1"]["count"] == 0
    assert paused_state["topics"]["questionnaire.response.ready.v1"]["count"] == 0

    review = client.post(f"/demo/review/{run_id}/Q-001")
    assert review.status_code == 200
    reviewed_state = client.get(f"/demo/state/{run_id}").json()
    assert reviewed_state["workflow_status"] == "reviewed_pending_export"

    export = client.post(f"/demo/export/{run_id}")
    assert export.status_code == 200
    exported_state = client.get(f"/demo/state/{run_id}").json()
    assert exported_state["workflow_status"] == "export_ready"
    assert exported_state["topics"]["questionnaire.response.ready.v1"]["count"] == 1
