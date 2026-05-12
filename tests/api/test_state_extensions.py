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
def test_state_includes_ordered_stage_rows_and_current_question():
    run = client.post("/demo/run/hallucinated-evidence").json()

    response = client.get(f"/demo/state/{run['run_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stage_keys"] == [
        "received",
        "prepared",
        "ai_safe_evidence",
        "draft_proposed",
        "draft_accepted",
        "draft_rejected",
        "reviewed",
        "response_ready",
    ]
    stages = {stage["key"]: stage for stage in payload["stages"]}
    assert stages["prepared"]["principal"] == "svc-preparer"
    assert stages["draft_proposed"]["count"] == 1
    assert stages["draft_proposed"]["last_event_id"]
    assert stages["draft_rejected"]["count"] == 1
    assert stages["response_ready"]["count"] == 0
    assert stages["response_ready"]["last_event_id"] is None
    assert payload["principal_by_stage"]["draft_proposed"] == "svc-ai-drafter"
    assert payload["current_question_id"] == "Q-001"
    assert payload["telemetry"] == {}
    assert "topics" in payload
    assert "workflow_status" in payload
