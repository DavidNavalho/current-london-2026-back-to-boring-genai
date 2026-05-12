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


def test_allocate_returns_run_id_and_reset_clears_history():
    client.post("/demo/reset")

    response = client.post(
        "/demo/runs/allocate",
        json={"scenario_id": "hallucinated-evidence", "pacing": "demo"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario_id"] == "hallucinated-evidence"
    assert payload["run_id"].startswith("run-hallucinated-evidence-")
    assert payload["pacing"] == "demo"

    history = client.get("/demo/runs").json()
    assert history["runs"][0]["run_id"] == payload["run_id"]
    assert history["runs"][0]["final_status"] == "allocated"

    reset = client.post("/demo/reset")
    assert reset.status_code == 200
    assert reset.json()["cleared_runs"] >= 1
    assert client.get("/demo/runs").json()["runs"] == []


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_preallocated_run_id_is_honoured_when_scenario_runs():
    client.post("/demo/reset")
    allocation = client.post(
        "/demo/runs/allocate",
        json={"scenario_id": "hallucinated-evidence", "pacing": "realtime"},
    ).json()

    run = client.post(
        f"/demo/run/hallucinated-evidence?run_id={allocation['run_id']}&pacing=demo"
    )

    assert run.status_code == 200
    payload = run.json()
    assert payload["run_id"] == allocation["run_id"]
    assert "UNKNOWN_EVIDENCE_ID" in payload["reason_codes"]

    history = client.get("/demo/runs").json()["runs"]
    assert history[0]["run_id"] == allocation["run_id"]
    assert history[0]["scenario_id"] == "hallucinated-evidence"
    assert history[0]["pacing"] == "demo"
    assert history[0]["final_status"] == "rejected"
    assert history[0]["reason_codes"] == ["UNKNOWN_EVIDENCE_ID"]
    assert history[0]["duration_ms"] >= 0
