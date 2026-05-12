from __future__ import annotations

import json
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


pytestmark = [
    pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running"),
    pytest.mark.skipif(not _acl_mode(), reason="Kafka ACL mode is not enabled"),
]


def test_attack_response_keeps_default_target_and_includes_acl_rule():
    run_id = f"run-attack-rich-{uuid4()}"

    response = client.post(f"/demo/attack/ai-direct-write/{run_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["target_topic"] == "questionnaire.response.ready.v1"
    assert payload["principal"] == "svc-ai-drafter"
    assert payload["attempted_operation"] == "WRITE"
    assert payload["broker_error_code"] == "TOPIC_AUTHORIZATION_FAILED"
    assert payload["duration_ms"] >= 0
    assert payload["security_alert_event_id"]
    assert payload["acl_rule"] == {
        "principal": "User:svc-ai-drafter",
        "resource_type": "TOPIC",
        "resource_name": "questionnaire.response.ready.v1",
        "operation": "WRITE",
        "permission": "NO_ALLOW_MATCH",
    }


def test_attack_response_supports_reviewed_target():
    run_id = f"run-attack-reviewed-{uuid4()}"

    response = client.post(
        f"/demo/attack/ai-direct-write/{run_id}?target_topic=answer.reviewed.v1"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["target_topic"] == "answer.reviewed.v1"
    assert payload["denied"] is True
    assert payload["acl_rule"]["resource_name"] == "answer.reviewed.v1"
