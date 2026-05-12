from __future__ import annotations

from demo.api.run_store import get_run
from demo.api.stages import PRINCIPAL_BY_STAGE, STAGE_KEYS, STAGES
from demo.contracts import TOPICS
from demo.kafka_io import consume_events


def build_state_snapshot(run_id: str) -> dict:
    topics: dict[str, dict] = {}
    events_by_topic: dict[str, list] = {}
    reason_codes: list[str] = []
    draft = None
    accepted = None
    rejected = None
    reviewed = None
    response_ready = None

    for topic in TOPICS:
        events = consume_events(topic, run_id=run_id, timeout_seconds=2)
        events_by_topic[topic] = events
        topics[topic] = {
            "count": len(events),
            "event_types": [event.event_type for event in events],
        }
        if topic == "answer.draft.rejected.v1":
            for event in events:
                reason_codes.extend(event.reason_codes)
            if events:
                latest = events[-1]
                rejected = {
                    "question_id": latest.question_id,
                    "draft_event_id": latest.draft_event_id,
                    "reason_codes": latest.reason_codes,
                }
        elif topic == "answer.draft.proposed.v1" and events:
            latest = events[-1]
            draft = {
                "question_id": latest.question_id,
                "answer_type": latest.answer_type.value,
                "confidence": latest.confidence,
                "evidence_ids": latest.evidence_ids,
                "draft_answer": latest.draft_answer,
            }
        elif topic == "answer.draft.accepted.v1" and events:
            latest = events[-1]
            accepted = {
                "question_id": latest.question_id,
                "draft_event_id": latest.draft_event_id,
                "evidence_ids": latest.evidence_ids,
                "requires_human_review": latest.requires_human_review,
            }
        elif topic == "answer.reviewed.v1" and events:
            latest = events[-1]
            reviewed = {
                "question_id": latest.question_id,
                "reviewer_id": latest.reviewer_id,
                "decision": latest.review_decision.value,
            }
        elif topic == "questionnaire.response.ready.v1" and events:
            latest = events[-1]
            response_ready = {
                "questionnaire_id": latest.questionnaire_id,
                "export_summary": latest.export_summary,
            }

    return {
        "run_id": run_id,
        "topics": topics,
        "stages": _stage_rows(events_by_topic),
        "stage_keys": STAGE_KEYS,
        "principal_by_stage": PRINCIPAL_BY_STAGE,
        "workflow_status": _workflow_status(
            draft=draft,
            accepted=accepted,
            reviewed=reviewed,
            response_ready=response_ready,
            reason_codes=reason_codes,
        ),
        "reason_codes": list(dict.fromkeys(reason_codes)),
        "draft": draft,
        "accepted": accepted,
        "reviewed": reviewed,
        "response_ready": response_ready,
        "current_question_id": _current_question_id(
            run_id=run_id,
            draft=draft,
            accepted=accepted,
            rejected=rejected,
            reviewed=reviewed,
            events_by_topic=events_by_topic,
        ),
        "telemetry": _telemetry(run_id),
    }


def _workflow_status(
    *,
    draft: dict | None,
    accepted: dict | None,
    reviewed: dict | None,
    response_ready: dict | None,
    reason_codes: list[str],
) -> str:
    if response_ready:
        return "export_ready"
    if reviewed:
        return "reviewed_pending_export"
    if accepted:
        return "human_review_required"
    if reason_codes:
        return "rejected"
    if draft:
        return "draft_proposed"
    return "not_started"


def _stage_rows(events_by_topic: dict[str, list]) -> list[dict]:
    rows = []
    for stage in STAGES:
        events = events_by_topic.get(stage.topic, [])
        rows.append(
            {
                "key": stage.key,
                "topic": stage.topic,
                "principal": stage.principal,
                "count": len(events),
                "last_event_id": events[-1].event_id if events else None,
            }
        )
    return rows


def _current_question_id(
    *,
    run_id: str,
    draft: dict | None,
    accepted: dict | None,
    rejected: dict | None,
    reviewed: dict | None,
    events_by_topic: dict[str, list],
) -> str | None:
    record = get_run(run_id)
    if record and record.question_id:
        return record.question_id
    for item in (reviewed, accepted, rejected, draft):
        if item and item.get("question_id"):
            return item["question_id"]
    for topic in ("evidence.ai_safe.v1", "questionnaire.questions.v1"):
        events = events_by_topic.get(topic, [])
        question_events = [event for event in events if getattr(event, "question_id", None)]
        if question_events:
            return question_events[-1].question_id
    return None


def _telemetry(run_id: str) -> dict:
    record = get_run(run_id)
    return dict(record.telemetry) if record else {}
