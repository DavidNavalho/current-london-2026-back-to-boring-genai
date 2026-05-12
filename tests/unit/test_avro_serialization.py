from __future__ import annotations

from datetime import UTC, datetime

from demo.avro_contracts import decode_avro_event, encode_avro_event
from demo.contracts import (
    AcceptedDraft,
    AiSafeEvidence,
    AnswerType,
    AuditEvent,
    Classification,
    EvidenceItem,
    PreparedQuestion,
    ProposedAnswer,
    QuestionnaireReceived,
    RejectedDraft,
    ResponseReady,
    ReviewDecision,
    ReviewedAnswer,
    SecurityAlert,
    make_event_id,
)


def _base() -> dict:
    return {
        "event_id": make_event_id(),
        "run_id": "run-avro-roundtrip",
        "occurred_at": datetime.now(UTC).replace(microsecond=123000),
        "producer": "svc-test",
        "schema_version": 1,
    }


def _events():
    received = QuestionnaireReceived(
        **_base(),
        questionnaire_id="DEMO-QUESTIONNAIRE-001",
        title="Security Questionnaire",
        questions=[
            {
                "question_id": "Q-001",
                "scenario": "happy-path",
                "control_area": "encryption",
                "risk_hint": "low",
                "text": "Do you encrypt customer data at rest?",
            }
        ],
    )
    prepared = PreparedQuestion(
        **_base(),
        questionnaire_id="DEMO-QUESTIONNAIRE-001",
        question_id="Q-001",
        question_text="Do you encrypt customer data at rest?",
        ordinal=1,
        control_area="encryption",
        scenario_tags=["happy-path"],
        risk_hint="low",
    )
    internal = EvidenceItem(
        **_base(),
        evidence_id="EVID-ENC-001",
        title="Encryption Standard",
        source_type="synthetic_standard",
        control_area="encryption",
        classification=Classification.CUSTOMER_SHAREABLE,
        allowed_for_ai=True,
        allowed_for_external_response=True,
        content="Customer data is encrypted at rest.",
        safe_summary="Customer data is encrypted at rest.",
        valid_from="2026-01-01",
        valid_until=None,
        owner="security",
    )
    ai_safe = AiSafeEvidence(
        **_base(),
        evidence_id="EVID-ENC-001",
        question_id="Q-001",
        title="Encryption Standard",
        control_area="encryption",
        classification=Classification.CUSTOMER_SHAREABLE,
        content="Customer data is encrypted at rest.",
        source_evidence_id="EVID-ENC-001",
    )
    proposed = ProposedAnswer(
        **_base(),
        question_id="Q-001",
        control_area="encryption",
        answer_type=AnswerType.YES_WITH_EVIDENCE,
        draft_answer="Yes. Customer data is encrypted at rest.",
        evidence_ids=["EVID-ENC-001"],
        confidence=0.87,
        risk_level="low",
        requires_human_review=True,
        cannot_answer_reason=None,
    )
    accepted = AcceptedDraft(
        **_base(),
        question_id="Q-001",
        draft_event_id=proposed.event_id,
        evidence_ids=["EVID-ENC-001"],
    )
    rejected = RejectedDraft(
        **_base(),
        question_id="Q-001",
        draft_event_id=proposed.event_id,
        reason_codes=["UNKNOWN_EVIDENCE_ID"],
        message="Unknown evidence.",
        evidence_ids=["EVID-DOES-NOT-EXIST"],
    )
    reviewed = ReviewedAnswer(
        **_base(),
        question_id="Q-001",
        reviewer_id="reviewer-demo",
        review_decision=ReviewDecision.APPROVED,
        reviewed_answer="Reviewed answer.",
        approved_evidence_ids=["EVID-ENC-001"],
        review_notes=None,
    )
    response = ResponseReady(
        **_base(),
        questionnaire_id="DEMO-QUESTIONNAIRE-001",
        reviewed_answer_ids=[reviewed.event_id],
        export_summary="1 reviewed answer ready for export.",
    )
    audit = AuditEvent(
        **_base(),
        source_event_id=accepted.event_id,
        action="accepted",
        outcome="policy_guard",
        details={
            "topic": "answer.draft.accepted.v1",
            "count": 1,
            "ok": True,
            "evidence_ids": ["EVID-ENC-001"],
        },
    )
    alert = SecurityAlert(
        **_base(),
        severity="critical",
        principal="svc-ai-drafter",
        attempted_operation="WRITE",
        resource="questionnaire.response.ready.v1",
        reason="ACL_DENIED",
    )
    return [
        ("questionnaire.received.v1-value", received),
        ("questionnaire.questions.v1-value", prepared),
        ("evidence.internal.v1-value", internal),
        ("evidence.ai_safe.v1-value", ai_safe),
        ("answer.draft.proposed.v1-value", proposed),
        ("answer.draft.accepted.v1-value", accepted),
        ("answer.draft.rejected.v1-value", rejected),
        ("answer.reviewed.v1-value", reviewed),
        ("questionnaire.response.ready.v1-value", response),
        ("audit.timeline.v1-value", audit),
        ("security.alert.v1-value", alert),
    ]


def test_events_round_trip_through_avro():
    for subject, event in _events():
        encoded = encode_avro_event(subject, event)
        decoded = decode_avro_event(subject, encoded)

        assert decoded.event_id == event.event_id
        assert decoded.run_id == event.run_id
        assert decoded.occurred_at.tzinfo is not None
        assert decoded.model_dump(mode="json") == event.model_dump(mode="json")


def test_optional_fields_round_trip_as_none():
    subject, event = next(item for item in _events() if item[0] == "answer.draft.proposed.v1-value")

    decoded = decode_avro_event(subject, encode_avro_event(subject, event))

    assert decoded.cannot_answer_reason is None
