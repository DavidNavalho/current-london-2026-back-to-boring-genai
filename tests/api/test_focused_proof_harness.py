from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from uuid import uuid4

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


def _codex_enabled() -> bool:
    return os.getenv("DEMO_RUN_CODEX_TESTS") == "1"


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
@pytest.mark.skipif(not _acl_mode(), reason="Kafka ACL mode is not enabled")
def test_happy_path_until_evidence_stops_before_ai_draft():
    run_id = f"run-v3-evidence-gate-{uuid4()}"

    response = client.post(f"/demo/run/happy-path?run_id={run_id}&until=evidence&pacing=realtime")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready_for_ai_drafter"
    assert payload["human_review_required"] is False
    assert payload["response_ready"] is False

    state = client.get(f"/demo/state/{run_id}")
    assert state.status_code == 200
    snapshot = state.json()
    stages = {stage["key"]: stage["count"] for stage in snapshot["stages"]}
    assert stages["received"] == 1
    assert stages["prepared"] > 0
    assert stages["ai_safe_evidence"] > 0
    assert stages["draft_proposed"] == 0
    assert stages["draft_accepted"] == 0
    assert stages["reviewed"] == 0
    assert stages["response_ready"] == 0
    assert snapshot["draft"] is None
    assert snapshot["reviewed"] is None
    assert snapshot["response_ready"] is None


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
@pytest.mark.skipif(not _acl_mode(), reason="Kafka ACL mode is not enabled")
def test_direct_ai_write_denial_does_not_create_target_event():
    run_id = f"run-v3-direct-write-{uuid4()}"

    response = client.post(f"/demo/attack/ai-direct-write/{run_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["denied"] is True
    assert payload["target_topic"] == "questionnaire.response.ready.v1"
    assert payload["broker_error_code"] == "TOPIC_AUTHORIZATION_FAILED"
    assert payload["acl_rule"]["resource_name"] == "questionnaire.response.ready.v1"
    assert payload["attempted_event_type"] == "questionnaire.response.ready"
    assert payload["attempted_payload"]["producer"] == "svc-ai-drafter"
    assert payload["attempted_payload"]["export_summary"] == "Forged export-ready response."
    assert payload["attempted_payload"]["reviewed_answer_ids"] == ["forged-reviewed-answer"]

    target_events = client.get(
        f"/demo/topics/questionnaire.response.ready.v1/events?run_id={run_id}&limit=20"
    )
    assert target_events.status_code == 200
    assert target_events.json()["events"] == []

    security_events = client.get(f"/demo/topics/security.alert.v1/events?run_id={run_id}&limit=20")
    assert security_events.status_code == 200
    alerts = security_events.json()["events"]
    assert len(alerts) == 1
    assert alerts[0]["payload"]["principal"] == "svc-ai-drafter"
    assert alerts[0]["payload"]["reason"] == "ACL_DENIED"

    audit = client.get(f"/demo/audit/{run_id}")
    assert audit.status_code == 200
    assert any(
        event["kind"] == "security"
        and event["resource"] == "questionnaire.response.ready.v1"
        and event["reason"] == "ACL_DENIED"
        for event in audit.json()["events"]
    )


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
@pytest.mark.skipif(not _acl_mode(), reason="Kafka ACL mode is not enabled")
def test_direct_ai_write_denial_can_target_human_review_topic():
    run_id = f"run-v3-direct-review-{uuid4()}"

    response = client.post(
        f"/demo/attack/ai-direct-write/{run_id}?target_topic=answer.reviewed.v1"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["denied"] is True
    assert payload["target_topic"] == "answer.reviewed.v1"
    assert payload["attempted_event_type"] == "answer.reviewed"
    assert payload["attempted_payload"]["producer"] == "svc-ai-drafter"
    assert payload["attempted_payload"]["reviewer_id"] == "forged-reviewer"

    target_events = client.get(
        f"/demo/topics/answer.reviewed.v1/events?run_id={run_id}&limit=20"
    )
    assert target_events.status_code == 200
    assert target_events.json()["events"] == []


@pytest.mark.codex
@pytest.mark.skipif(not _codex_enabled(), reason="Set DEMO_RUN_CODEX_TESTS=1 to run Codex tests")
@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_happy_path_until_review_pauses_before_review_and_export():
    run_id = f"run-v3-review-gate-{uuid4()}"

    response = client.post(f"/demo/run/happy-path?run_id={run_id}&until=review&pacing=realtime")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "waiting_for_human_review"
    assert payload["human_review_required"] is True
    assert payload["response_ready"] is False

    state = client.get(f"/demo/state/{run_id}")
    assert state.status_code == 200
    snapshot = state.json()
    assert snapshot["workflow_status"] == "human_review_required"
    assert snapshot["accepted"]["requires_human_review"] is True
    assert snapshot["reviewed"] is None
    assert snapshot["response_ready"] is None
