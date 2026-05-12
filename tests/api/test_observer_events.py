from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from demo.api.pacing import parse_pacing
from demo.scenario_runner import (
    ScenarioRunContext,
    run_hallucinated_evidence,
    run_malformed_draft,
)


class RecordingObserver:
    def __init__(self) -> None:
        self.status_events: list[dict] = []
        self.stage_events: list[dict] = []
        self.audit_events: list[dict] = []
        self.security_events: list[dict] = []
        self.telemetry_events: list[dict] = []

    def status(self, run_id: str, status: str, **fields) -> None:
        self.status_events.append({"run_id": run_id, "status": status, **fields})

    def stage(self, topic, event, principal: str, summary: str) -> None:
        self.stage_events.append(
            {
                "topic": topic,
                "event_id": event.event_id,
                "principal": principal,
                "summary": summary,
            }
        )

    def audit(self, event) -> None:
        self.audit_events.append(event.model_dump(mode="json"))

    def security(self, event) -> None:
        self.security_events.append(event.model_dump(mode="json"))

    def telemetry(self, run_id: str, **metrics) -> None:
        self.telemetry_events.append({"run_id": run_id, **metrics})


def test_deterministic_scenario_emits_stage_events_in_order():
    observer = RecordingObserver()
    run_id = f"run-observer-hallucinated-{uuid4()}"
    context = ScenarioRunContext(
        run_id=run_id,
        scenario_id="hallucinated-evidence",
        question_id="Q-001",
        pacing=parse_pacing("realtime"),
        observer=observer,
        started_at=datetime.now(UTC),
    )

    result = run_hallucinated_evidence(run_id, context=context)

    assert result.status == "passed"
    first_topics = list(dict.fromkeys(event["topic"] for event in observer.stage_events))
    assert first_topics == [
        "questionnaire.received.v1",
        "questionnaire.questions.v1",
        "evidence.ai_safe.v1",
        "answer.draft.proposed.v1",
        "answer.draft.rejected.v1",
    ]
    assert observer.audit_events
    assert run_hallucinated_evidence(f"run-observer-default-{uuid4()}").status == "passed"


def test_audit_and_security_observer_methods_fire():
    observer = RecordingObserver()
    run_id = f"run-observer-malformed-{uuid4()}"
    context = ScenarioRunContext(
        run_id=run_id,
        scenario_id="malformed-draft",
        question_id="Q-001",
        pacing=parse_pacing("realtime"),
        observer=observer,
        started_at=datetime.now(UTC),
    )

    result = run_malformed_draft(run_id, context=context)

    assert result.reason_codes == ["MALFORMED_EVENT", "FORBIDDEN_WORKFLOW_FIELD"]
    assert any(event["action"] == "malformed" for event in observer.audit_events)
    assert len(observer.security_events) == 1
    assert observer.security_events[0]["principal"] == "svc-ai-drafter"
    assert observer.security_events[0]["reason"] == "MALFORMED_EVENT"
    assert observer.security_events[0]["resource"] == "answer.draft.proposed.v1"
