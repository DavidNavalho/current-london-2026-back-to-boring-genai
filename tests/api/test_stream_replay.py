from __future__ import annotations

import json
import urllib.error
import urllib.request
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from demo.api.app import app
from demo.api.event_stream import event_broker, reset_streams


client = TestClient(app)


def _runtime_available() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:8081/subjects", timeout=2) as response:
            json.loads(response.read().decode("utf-8"))
        return True
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False


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
        payload = None
        for line in block.splitlines():
            if line.startswith(":"):
                continue
            if line.startswith("event: "):
                event_type = line.removeprefix("event: ")
            elif line.startswith("data: "):
                payload = json.loads(line.removeprefix("data: "))
        if payload is not None:
            events.append({"event": event_type, "data": payload})
    return events


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_stream_reconnect_replays_from_elapsed_ms():
    client.post("/demo/reset")
    run_id = f"run-stream-replay-{uuid4()}"

    run = client.post(f"/demo/run/hallucinated-evidence?run_id={run_id}&pacing=realtime")
    assert run.status_code == 200
    full = _stream_events(run_id)
    stage_elapsed = [
        event["data"]["elapsed_ms"]
        for event in full
        if event["event"] == "stage"
    ]
    cutoff = stage_elapsed[2]

    replay = _stream_events(run_id, from_elapsed_ms=cutoff)

    assert replay
    assert all(event["data"]["elapsed_ms"] >= cutoff for event in replay)
    assert any(event["event"] == "status" and event["data"]["status"] == "rejected" for event in replay)


def test_stream_replay_reports_truncated_buffer_gap():
    reset_streams()
    run_id = f"run-stream-stale-{uuid4()}"
    for index in range(205):
        event_broker.publish(
            run_id,
            "status",
            {"run_id": run_id, "status": f"tick-{index}", "elapsed_ms": index},
        )
    event_broker.publish(
        run_id,
        "status",
        {"run_id": run_id, "status": "rejected", "elapsed_ms": 205},
    )

    events = _stream_events(run_id, from_elapsed_ms=0)

    assert events[0]["event"] == "status"
    assert events[0]["data"]["status"] == "replay_gap"
    assert events[0]["data"]["earliest_elapsed_ms"] > 0
