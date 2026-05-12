from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest
from fastapi.testclient import TestClient

from demo.api.app import app
from demo.config import Settings


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


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_existing_run_endpoint_keeps_negative_scenario_fields():
    response = client.post("/demo/run/hallucinated-evidence")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload).issuperset(
        {
            "scenario_id",
            "run_id",
            "status",
            "reason_codes",
            "message",
        }
    )
    assert payload["scenario_id"] == "hallucinated-evidence"
    assert payload["status"] == "passed"
    assert "UNKNOWN_EVIDENCE_ID" in payload["reason_codes"]


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_existing_state_endpoint_keeps_v1_fields():
    run = client.post("/demo/run/unsupported-claim").json()

    response = client.get(f"/demo/state/{run['run_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload).issuperset(
        {
            "run_id",
            "topics",
            "workflow_status",
            "reason_codes",
            "draft",
            "accepted",
            "reviewed",
            "response_ready",
        }
    )
    assert payload["run_id"] == run["run_id"]
    assert payload["workflow_status"] == "rejected"
    assert "answer.draft.rejected.v1" in payload["topics"]


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_existing_audit_endpoint_keeps_timeline_string():
    run = client.post("/demo/run/malformed-draft").json()

    response = client.get(f"/demo/audit/{run['run_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload).issuperset({"run_id", "timeline"})
    assert isinstance(payload["timeline"], str)
    assert "malformed" in payload["timeline"]


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
@pytest.mark.skipif(not _acl_mode(), reason="Kafka ACL mode is not enabled")
def test_existing_attack_endpoint_keeps_v1_fields():
    response = client.post("/demo/attack/ai-direct-write/run-api-compat-attack")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload).issuperset({"run_id", "target_topic", "denied", "reason"})
    assert payload["run_id"] == "run-api-compat-attack"
    assert payload["target_topic"] == "questionnaire.response.ready.v1"
    assert payload["denied"] is True
