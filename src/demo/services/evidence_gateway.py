from __future__ import annotations

from datetime import UTC, datetime

from demo.contracts import AiSafeEvidence, EvidenceItem, PreparedQuestion, make_event_id


QUESTION_EVIDENCE: dict[str, list[str]] = {
    "Q-001": ["EVID-ENC-001", "EVID-DP-001"],
    "Q-002": ["EVID-ENC-001"],
    "Q-003": ["EVID-IR-001"],
    "Q-004": ["EVID-IAM-001"],
    "Q-005": ["EVID-DP-001"],
    "Q-006": ["EVID-LOG-001"],
    "Q-007": ["EVID-SOC2-001"],
    "Q-008": ["EVID-ADMIN-SECRET"],
    "Q-009": ["EVID-MAL-001"],
    "Q-010": [],
}


def _evidence_event(run_id: str, item: dict) -> EvidenceItem:
    return EvidenceItem(
        event_id=make_event_id(),
        run_id=run_id,
        occurred_at=datetime.now(UTC),
        producer="svc-evidence-fixture",
        schema_version=1,
        **item,
    )


def select_evidence(
    prepared_question: PreparedQuestion, evidence_library: dict
) -> list[EvidenceItem]:
    by_id = {item["evidence_id"]: item for item in evidence_library["evidence"]}
    selected_ids = QUESTION_EVIDENCE.get(prepared_question.question_id, [])
    return [_evidence_event(prepared_question.run_id, by_id[evidence_id]) for evidence_id in selected_ids]


def make_ai_safe_evidence(
    prepared_question: PreparedQuestion, evidence_items: list[EvidenceItem]
) -> list[AiSafeEvidence]:
    ai_safe: list[AiSafeEvidence] = []
    for item in evidence_items:
        if item.classification.value in {"restricted", "secret"} or not item.allowed_for_ai:
            continue
        content = item.safe_summary or item.content
        ai_safe.append(
            AiSafeEvidence(
                event_id=make_event_id(),
                run_id=prepared_question.run_id,
                occurred_at=datetime.now(UTC),
                producer="svc-evidence-gateway",
                schema_version=1,
                evidence_id=item.evidence_id,
                question_id=prepared_question.question_id,
                title=item.title,
                control_area=item.control_area,
                classification=item.classification,
                content=content,
                source_evidence_id=item.evidence_id,
            )
        )
    return ai_safe
