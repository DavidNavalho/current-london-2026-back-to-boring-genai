from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from demo.api.authority import authority_boundary
from demo.api.event_stream import LiveSubscriberExists, RunStreamObserver, event_broker, reset_streams
from demo.api.health import connection_health
from demo.api.inspectors import schema_lookup, structured_audit_events, topic_events
from demo.api.pacing import Pacing, parse_pacing
from demo.api.questionnaire_view import question_detail, questionnaire_overview
from demo.api.run_store import allocate_run, get_run, list_runs, mark_completed, mark_started, reset_runs
from demo.api.state import build_state_snapshot
from demo.config import Settings
from demo.scenario_runner import (
    export_reviewed_response,
    render_audit_for_run,
    review_accepted_answer,
    run_ai_direct_write_attack,
    run_export_shortcut,
    run_hallucinated_evidence,
    run_happy_path,
    run_happy_path_until_evidence,
    run_happy_path_until_review,
    run_malformed_draft,
    run_prompt_injection,
    run_restricted_evidence,
    run_unsupported_claim,
    ScenarioRunContext,
)


ROOT = Path(__file__).resolve().parents[3]
WEB_INDEX = ROOT / "web" / "index.html"
WEB_INDEX_V2 = ROOT / "web" / "v2" / "index.html"
WEB_INDEX_V3 = ROOT / "web" / "v3" / "index.html"

app = FastAPI(title="Questionnaire AI Demo API")


@app.middleware("http")
async def dev_cors(request, call_next):
    response = await call_next(request)
    if Settings().demo_env == "dev":
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
    return response


SCENARIO_RUNNERS = {
    "prompt-injection": run_prompt_injection,
    "restricted-evidence": run_restricted_evidence,
    "hallucinated-evidence": run_hallucinated_evidence,
    "malformed-draft": run_malformed_draft,
    "unsupported-claim": run_unsupported_claim,
    "export-shortcut": run_export_shortcut,
}
KNOWN_SCENARIOS = {"happy-path", *SCENARIO_RUNNERS}


class RunAllocationRequest(BaseModel):
    scenario_id: str
    pacing: str | None = None


@app.get("/")
def index():
    return FileResponse(WEB_INDEX)


@app.get("/v2")
def index_v2():
    if not WEB_INDEX_V2.exists():
        raise HTTPException(status_code=404, detail="UI v2 has not been built yet")
    return FileResponse(WEB_INDEX_V2)


@app.get("/v3")
def index_v3():
    if not WEB_INDEX_V3.exists():
        raise HTTPException(status_code=404, detail="UI v3 has not been built yet")
    return FileResponse(WEB_INDEX_V3)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/health/connection")
def health_connection() -> dict:
    return connection_health()


@app.post("/demo/run/{scenario_id}")
def run_scenario(
    scenario_id: str,
    until: str | None = None,
    run_id: str | None = None,
    pacing: str | None = None,
) -> dict:
    resolved_pacing = _resolve_pacing(pacing)
    if scenario_id not in KNOWN_SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Unknown scenario: {scenario_id}")
    started_at = datetime.now(UTC)
    context = _make_context(
        run_id,
        scenario_id=scenario_id,
        pacing=resolved_pacing,
        started_at=started_at,
    )
    if run_id is not None:
        mark_started(run_id, scenario_id=scenario_id, pacing=resolved_pacing.name, started_at=started_at)
        _notify_status(context, "running", scenario_id=scenario_id)
    try:
        if scenario_id == "happy-path":
            if until == "evidence":
                result = run_happy_path_until_evidence(run_id, context=context)
                mark_completed(
                    result.run_id,
                    scenario_id=scenario_id,
                    pacing=resolved_pacing.name,
                    final_status="ready_for_ai_drafter",
                    question_id=result.question_id,
                    telemetry=context.telemetry if context else None,
                    started_at=started_at,
                )
                _notify_status(
                    context,
                    "ready_for_ai_drafter",
                    scenario_id=scenario_id,
                    question_id=result.question_id,
                )
                return {
                    "scenario_id": scenario_id,
                    "run_id": result.run_id,
                    "status": "ready_for_ai_drafter",
                    "human_review_required": False,
                    "response_ready": False,
                    "question_id": result.question_id,
                    "reason_codes": [],
                }
            if until == "review":
                result = run_happy_path_until_review(run_id, context=context)
                mark_completed(
                    result.run_id,
                    scenario_id=scenario_id,
                    pacing=resolved_pacing.name,
                    final_status="waiting_for_human_review",
                    question_id=result.question_id,
                    telemetry=context.telemetry if context else None,
                    started_at=started_at,
                )
                _notify_status(
                    context,
                    "waiting_for_human_review",
                    scenario_id=scenario_id,
                    question_id=result.question_id,
                )
                return {
                    "scenario_id": scenario_id,
                    "run_id": result.run_id,
                    "status": "waiting_for_human_review",
                    "human_review_required": True,
                    "response_ready": False,
                    "question_id": result.question_id,
                    "reason_codes": [],
                }
            result = run_happy_path(run_id, context=context)
            mark_completed(
                result.run_id,
                scenario_id=scenario_id,
                pacing=resolved_pacing.name,
                final_status="export_ready",
                question_id=result.question_id,
                telemetry=context.telemetry if context else None,
                started_at=started_at,
            )
            _notify_status(
                context,
                "export_ready",
                scenario_id=scenario_id,
                question_id=result.question_id,
            )
            return {
                "scenario_id": scenario_id,
                "run_id": result.run_id,
                "status": "passed",
                "human_review_required": False,
                "response_ready": True,
                "reason_codes": [],
            }
        runner = SCENARIO_RUNNERS[scenario_id]
        result = runner(run_id, context=context)
        final_status = "rejected" if result.reason_codes else result.status
        mark_completed(
            result.run_id,
            scenario_id=result.scenario_id,
            pacing=resolved_pacing.name,
            final_status=final_status,
            reason_codes=result.reason_codes,
            question_id=result.question_id,
            telemetry=context.telemetry if context else None,
            started_at=started_at,
        )
        _notify_status(
            context,
            final_status,
            scenario_id=result.scenario_id,
            question_id=result.question_id,
            reason_codes=result.reason_codes,
        )
        return {
            "scenario_id": result.scenario_id,
            "run_id": result.run_id,
            "status": result.status,
            "reason_codes": result.reason_codes,
            "message": result.message,
        }
    except HTTPException:
        raise
    except Exception as exc:
        _notify_status(context, "failed", scenario_id=scenario_id, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/demo/runs/allocate")
def demo_runs_allocate(request: RunAllocationRequest) -> dict:
    if request.scenario_id not in KNOWN_SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Unknown scenario: {request.scenario_id}")
    pacing = _resolve_pacing(request.pacing)
    record = allocate_run(request.scenario_id, pacing.name)
    return {"run_id": record.run_id, "scenario_id": record.scenario_id, "pacing": record.pacing}


@app.get("/demo/runs")
def demo_runs() -> dict:
    return {"runs": list_runs()}


@app.post("/demo/reset")
def demo_reset() -> dict:
    return {"cleared_runs": reset_runs(), "cleared_streams": reset_streams()}


@app.get("/demo/questionnaire")
def demo_questionnaire() -> dict:
    return questionnaire_overview()


@app.get("/demo/question/{question_id}")
def demo_question(question_id: str) -> dict:
    try:
        return question_detail(question_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/demo/state/{run_id}")
def demo_state(run_id: str) -> dict:
    return build_state_snapshot(run_id)


@app.get("/demo/audit/{run_id}")
def demo_audit(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "timeline": render_audit_for_run(run_id),
        "events": structured_audit_events(run_id),
    }


@app.get("/demo/stream/{run_id}")
def demo_stream(run_id: str, from_elapsed_ms: int | None = None):
    try:
        stream = event_broker.open_stream(run_id, from_elapsed_ms=from_elapsed_ms)
    except LiveSubscriberExists as exc:
        raise HTTPException(status_code=409, detail=f"Run already has a live stream: {run_id}") from exc
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/demo/topics/{topic}/events")
def demo_topic_events(topic: str, run_id: str, limit: int = 20) -> dict:
    try:
        return topic_events(topic, run_id=run_id, limit=limit)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown topic: {topic}") from exc


@app.get("/demo/schemas/{subject}")
def demo_schema(subject: str) -> dict:
    try:
        return schema_lookup(subject)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown schema subject: {subject}") from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/demo/authority-boundary")
def demo_authority_boundary() -> dict:
    return authority_boundary()


@app.post("/demo/review/{run_id}/{question_id}")
def demo_review(run_id: str, question_id: str, pacing: str | None = None) -> dict:
    resolved_pacing = _resolve_pacing(pacing)
    existing = get_run(run_id)
    context = _make_context(
        run_id,
        scenario_id=existing.scenario_id if existing else "manual-review",
        question_id=question_id,
        pacing=resolved_pacing,
        started_at=existing.started_at if existing else datetime.now(UTC),
    )
    try:
        reviewed = review_accepted_answer(run_id, question_id, context=context)
    except Exception as exc:
        _notify_status(context, "failed", scenario_id=context.scenario_id, error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    mark_completed(
        run_id,
        scenario_id=existing.scenario_id if existing else "manual-review",
        pacing=resolved_pacing.name,
        final_status="reviewed_pending_export",
        question_id=question_id,
        telemetry=context.telemetry,
    )
    _notify_status(
        context,
        "reviewed_pending_export",
        scenario_id=existing.scenario_id if existing else "manual-review",
        question_id=question_id,
    )
    return {
        "run_id": run_id,
        "question_id": question_id,
        "reviewed_event_id": reviewed.event_id,
        "decision": reviewed.review_decision.value,
    }


@app.post("/demo/export/{run_id}")
def demo_export(run_id: str, pacing: str | None = None) -> dict:
    resolved_pacing = _resolve_pacing(pacing)
    existing = get_run(run_id)
    context = _make_context(
        run_id,
        scenario_id=existing.scenario_id if existing else "manual-export",
        pacing=resolved_pacing,
        started_at=existing.started_at if existing else datetime.now(UTC),
    )
    try:
        response = export_reviewed_response(run_id, context=context)
    except Exception as exc:
        _notify_status(context, "failed", scenario_id=context.scenario_id, error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    mark_completed(
        run_id,
        scenario_id=existing.scenario_id if existing else "manual-export",
        pacing=resolved_pacing.name,
        final_status="export_ready",
        telemetry=context.telemetry,
    )
    _notify_status(
        context,
        "export_ready",
        scenario_id=existing.scenario_id if existing else "manual-export",
    )
    return {
        "run_id": run_id,
        "response_ready_event_id": response.event_id,
        "export_summary": response.export_summary,
    }


@app.post("/demo/attack/ai-direct-write/{run_id}")
def demo_attack_ai_direct_write(
    run_id: str,
    pacing: str | None = None,
    target_topic: str = "questionnaire.response.ready.v1",
) -> dict:
    resolved_pacing = _resolve_pacing(pacing)
    started_at = datetime.now(UTC)
    context = _make_context(
        run_id,
        scenario_id="direct-ai-write",
        pacing=resolved_pacing,
        started_at=started_at,
    )
    mark_started(
        run_id,
        scenario_id="direct-ai-write",
        pacing=resolved_pacing.name,
        started_at=started_at,
    )
    _notify_status(context, "running", scenario_id="direct-ai-write")
    try:
        result = run_ai_direct_write_attack(run_id, target_topic=target_topic, context=context)
    except ValueError as exc:
        _notify_status(context, "failed", scenario_id="direct-ai-write", error=str(exc))
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    mark_completed(
        result.run_id,
        scenario_id="direct-ai-write",
        pacing=resolved_pacing.name,
        final_status="denied" if result.denied else "allowed",
        reason_codes=["ACL_DENIED"] if result.denied else [],
        denied=result.denied,
        telemetry=context.telemetry,
        started_at=started_at,
    )
    _notify_status(
        context,
        "denied" if result.denied else "allowed",
        scenario_id="direct-ai-write",
        target_topic=result.target_topic,
    )
    return {
        "run_id": result.run_id,
        "target_topic": result.target_topic,
        "denied": result.denied,
        "reason": result.reason,
        "principal": result.principal,
        "attempted_operation": result.attempted_operation,
        "attempted_event_type": result.attempted_event_type,
        "attempted_payload": result.attempted_payload,
        "broker_error_code": result.broker_error_code,
        "acl_rule": result.acl_rule,
        "duration_ms": result.duration_ms,
        "security_alert_event_id": result.security_alert_event_id,
    }


def _resolve_pacing(value: str | None) -> Pacing:
    try:
        return parse_pacing(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _make_context(
    run_id: str | None,
    *,
    scenario_id: str,
    pacing: Pacing,
    started_at: datetime,
    question_id: str | None = None,
) -> ScenarioRunContext | None:
    if run_id is None:
        return None
    context = ScenarioRunContext(
        run_id=run_id,
        scenario_id=scenario_id,
        question_id=question_id,
        pacing=pacing,
        observer=None,
        started_at=started_at,
    )
    context.observer = RunStreamObserver(context)
    return context


def _notify_status(context: ScenarioRunContext | None, status: str, **fields) -> None:
    if context and context.observer:
        context.observer.status(context.run_id, status, **fields)
