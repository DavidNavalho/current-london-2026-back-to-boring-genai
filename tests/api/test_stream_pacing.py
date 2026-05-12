from __future__ import annotations

import json
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


def _stream_events(run_id: str) -> list[dict]:
    with client.stream("GET", f"/demo/stream/{run_id}") as response:
        assert response.status_code == 200
        text = "".join(response.iter_text())
    return _parse_sse(text)


def _parse_sse(text: str) -> list[dict]:
    events = []
    for block in [item for item in text.split("\n\n") if item.strip()]:
        event_type = None
        payload = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event_type = line.removeprefix("event: ")
            elif line.startswith("data: "):
                payload = json.loads(line.removeprefix("data: "))
        if event_type and payload:
            events.append({"event": event_type, "data": payload})
    return events


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_demo_pacing_spaces_workflow_stage_events():
    client.post("/demo/reset")
    run_id = f"run-stream-pacing-{uuid4()}"

    run = client.post(f"/demo/run/hallucinated-evidence?run_id={run_id}&pacing=demo")
    assert run.status_code == 200

    events = _stream_events(run_id)
    elapsed = [
        event["data"]["elapsed_ms"]
        for event in events
        if event["event"] == "stage"
    ]

    assert len(elapsed) >= 5
    gaps = [right - left for left, right in zip(elapsed, elapsed[1:])]
    assert min(gaps) >= 500
