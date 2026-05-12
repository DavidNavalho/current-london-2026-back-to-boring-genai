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


def test_topic_peek_rejects_unknown_topic():
    response = client.get("/demo/topics/not-a-topic/events?run_id=run-x")

    assert response.status_code == 404


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_topic_peek_returns_deserialised_events_and_caps_limit():
    run = client.post("/demo/run/hallucinated-evidence").json()

    response = client.get(
        f"/demo/topics/answer.draft.proposed.v1/events?run_id={run['run_id']}&limit=500"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["topic"] == "answer.draft.proposed.v1"
    assert payload["schema_subject"] == "answer.draft.proposed.v1-value"
    assert payload["schema_version"] == 1
    assert payload["limit"] == 100
    assert len(payload["events"]) == 1
    event = payload["events"][0]
    assert event["producer"] == "scenario-attack-draft"
    assert event["payload"]["question_id"] == "Q-001"
