from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from demo.api.pacing import parse_pacing
from demo.scenario_runner import ScenarioRunContext, run_happy_path


class RecordingObserver:
    def __init__(self) -> None:
        self.telemetry_events: list[dict] = []

    def status(self, run_id: str, status: str, **fields) -> None:
        pass

    def stage(self, topic, event, principal: str, summary: str) -> None:
        pass

    def audit(self, event) -> None:
        pass

    def security(self, event) -> None:
        pass

    def telemetry(self, run_id: str, **metrics) -> None:
        self.telemetry_events.append({"run_id": run_id, **metrics})


class StaticAgentProvider:
    def __init__(self) -> None:
        self.actions = [
            {"action": "search_evidence", "query": "encryption customer data"},
            {"action": "inspect_evidence", "evidence_ids": ["EVID-ENC-001"]},
            {
                "action": "finish_draft",
                "answer_type": "yes_with_evidence",
                "draft_answer": "Yes. Customer data is encrypted at rest using managed encryption controls.",
                "evidence_ids": ["EVID-ENC-001"],
                "confidence": 0.86,
                "risk_level": "low",
                "requires_human_review": True,
                "cannot_answer_reason": None,
            },
        ]

    def generate_action(self, prompt: str) -> dict:
        return self.actions.pop(0)


def test_context_records_workflow_telemetry_without_codex_metrics():
    observer = RecordingObserver()
    run_id = f"run-telemetry-happy-{uuid4()}"
    context = ScenarioRunContext(
        run_id=run_id,
        scenario_id="happy-path",
        question_id="Q-001",
        pacing=parse_pacing("realtime"),
        observer=observer,
        started_at=datetime.now(UTC),
    )

    result = run_happy_path(run_id, provider=StaticAgentProvider(), context=context)

    assert result.response_ready.run_id == run_id
    assert set(context.telemetry) >= {"draft_ms", "guard_ms", "review_ms", "export_ms", "agent_tool_calls"}
    assert all(isinstance(value, int) and value >= 0 for value in context.telemetry.values())
    assert "codex_tokens" not in context.telemetry
    assert observer.telemetry_events[-1]["export_ms"] == context.telemetry["export_ms"]
    assert context.telemetry["agent_tool_calls"] == 2
