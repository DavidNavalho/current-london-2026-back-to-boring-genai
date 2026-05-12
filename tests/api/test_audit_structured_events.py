from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest
from fastapi.testclient import TestClient

from demo.api.app import app


client = TestClient(app)


def _runtime_available() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:8081/subjects", timeout=2) as response:
            json.loads(response.read().decode("utf-8"))
        return True
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_audit_endpoint_includes_timeline_and_structured_events():
    run = client.post("/demo/run/malformed-draft").json()

    response = client.get(f"/demo/audit/{run['run_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["timeline"], str)
    assert payload["events"]
    kinds = {event["kind"] for event in payload["events"]}
    assert "audit" in kinds
    assert "security" in kinds
    audit_event = next(event for event in payload["events"] if event["kind"] == "audit")
    assert {"event_id", "occurred_at", "producer", "action", "outcome", "details"}.issubset(
        audit_event
    )
    security_event = next(event for event in payload["events"] if event["kind"] == "security")
    assert security_event["principal"] == "svc-ai-drafter"
    assert security_event["reason"] == "MALFORMED_EVENT"
