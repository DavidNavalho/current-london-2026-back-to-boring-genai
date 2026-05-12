from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from uuid import uuid4

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


def _codex_enabled() -> bool:
    return os.getenv("DEMO_RUN_CODEX_TESTS") == "1"


def _stream_events(run_id: str, *, from_elapsed_ms: int | None = None) -> list[dict]:
    query = "" if from_elapsed_ms is None else f"?from_elapsed_ms={from_elapsed_ms}"
    with client.stream("GET", f"/demo/stream/{run_id}{query}") as response:
        assert response.status_code == 200
        text = "".join(response.iter_text())
    return _parse_sse(text)


def _parse_sse(text: str) -> list[dict]:
    events = []
    for block in [item for item in text.split("\n\n") if item.strip()]:
        event_type = "message"
        data = None
        for line in block.splitlines():
            if line.startswith(":"):
                continue
            if line.startswith("event: "):
                event_type = line.removeprefix("event: ")
            elif line.startswith("data: "):
                data = json.loads(line.removeprefix("data: "))
        if data is not None:
            events.append({"event": event_type, "data": data})
    return events


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_stream_replays_stage_events_for_deterministic_scenario():
    client.post("/demo/reset")
    run_id = f"run-stream-hallucinated-{uuid4()}"

    run = client.post(f"/demo/run/hallucinated-evidence?run_id={run_id}&pacing=realtime")
    assert run.status_code == 200

    events = _stream_events(run_id)

    first_stage_keys = list(
        dict.fromkeys(
            event["data"]["stage_key"]
            for event in events
            if event["event"] == "stage"
        )
    )
    assert first_stage_keys == [
        "received",
        "prepared",
        "ai_safe_evidence",
        "draft_proposed",
        "draft_rejected",
    ]
    assert any(
        event["event"] == "status" and event["data"]["status"] == "rejected"
        for event in events
    )


@pytest.mark.codex
@pytest.mark.skipif(not _codex_enabled(), reason="Set DEMO_RUN_CODEX_TESTS=1 to run Codex stream tests")
@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_happy_path_stream_can_reach_export_ready_with_codex():
    client.post("/demo/reset")
    run_id = f"run-stream-happy-{uuid4()}"

    run = client.post(f"/demo/run/happy-path?run_id={run_id}&pacing=realtime")
    assert run.status_code == 200

    events = _stream_events(run_id)

    first_stage_keys = list(
        dict.fromkeys(
            event["data"]["stage_key"]
            for event in events
            if event["event"] == "stage"
        )
    )
    assert first_stage_keys == [
        "received",
        "prepared",
        "ai_safe_evidence",
        "draft_proposed",
        "draft_accepted",
        "reviewed",
        "response_ready",
    ]
    assert events[-1]["event"] == "status"
    assert events[-1]["data"]["status"] == "export_ready"
