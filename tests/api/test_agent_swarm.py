from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

import demo.api.app as app_module
from demo.api.app import app
from demo.services.agent_swarm import SwarmQuestionResult, SwarmRunResult
from demo.api.swarm_store import reserve_swarm


client = TestClient(app)


def test_swarm_endpoint_runs_and_stores_summary(monkeypatch):
    now = datetime.now(UTC)
    swarm_result = SwarmRunResult(
        swarm_id="swarm-demo",
        concurrency=2,
        questions=(
            SwarmQuestionResult(
                swarm_id="swarm-demo",
                run_id="swarm-demo-Q-001",
                question_id="Q-001",
                status="accepted",
                answer_type="yes_with_evidence",
                tool_call_count=2,
                trace_url="http://localhost:3000/project/demo/traces/q1",
            ),
        ),
        started_at=now,
        ended_at=now,
    )

    def fake_run_agent_swarm(**kwargs):
        assert kwargs["concurrency"] == 2
        return swarm_result

    monkeypatch.setattr(app_module, "run_agent_swarm", fake_run_agent_swarm)

    response = client.post("/demo/swarm?concurrency=2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["swarm_id"] == "swarm-demo"
    assert payload["accepted_count"] == 1
    assert payload["questions"][0]["run_id"] == "swarm-demo-Q-001"

    stored = client.get("/demo/swarm/swarm-demo")
    assert stored.status_code == 200
    assert stored.json()["swarm_id"] == "swarm-demo"


def test_swarm_endpoint_rejects_too_much_concurrency():
    response = client.post("/demo/swarm?concurrency=4")

    assert response.status_code == 422


def test_reserved_swarm_is_visible_while_background_work_runs():
    client.post("/demo/reset")

    payload = reserve_swarm("swarm-background", concurrency=2, total_count=10)

    assert payload["status"] == "running"
    assert payload["completed_count"] == 0
    response = client.get("/demo/swarm/swarm-background")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_happy_path_can_launch_background_swarm_without_waiting(monkeypatch):
    client.post("/demo/reset")

    monkeypatch.setattr(
        app_module,
        "run_happy_path_until_review",
        lambda run_id, context=None: SimpleNamespace(run_id=run_id, question_id="Q-001"),
    )
    monkeypatch.setattr(
        app_module,
        "_launch_background_swarm",
        lambda *, concurrency: "swarm-from-happy-path",
    )

    response = client.post(
        "/demo/run/happy-path"
        "?run_id=run-visible-q1"
        "&until=review"
        "&launch_swarm=true"
        "&swarm_concurrency=2"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run-visible-q1"
    assert payload["question_id"] == "Q-001"
    assert payload["swarm_id"] == "swarm-from-happy-path"
