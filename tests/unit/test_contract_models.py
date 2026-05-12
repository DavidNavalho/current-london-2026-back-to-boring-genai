from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from demo.contracts import (
    AiSafeEvidence,
    Classification,
    EvidenceItem,
    ProposedAnswer,
    make_event_id,
)


def _base_event() -> dict:
    return {
        "event_id": make_event_id(),
        "run_id": "run-test",
        "occurred_at": datetime.now(UTC),
        "producer": "svc-test",
        "schema_version": 1,
    }


def test_valid_proposed_answer():
    event = ProposedAnswer(
        **_base_event(),
        question_id="Q-001",
        control_area="encryption",
        answer_type="yes_with_evidence",
        draft_answer="Yes. Evidence supports encryption at rest.",
        evidence_ids=["EVID-ENC-001"],
        confidence=0.84,
        risk_level="low",
        requires_human_review=True,
        cannot_answer_reason=None,
    )

    assert event.event_type == "answer.draft.proposed"


def test_proposed_answer_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        ProposedAnswer(
            **_base_event(),
            question_id="Q-001",
            control_area="encryption",
            answer_type="yes_with_evidence",
            draft_answer="Approved.",
            evidence_ids=["EVID-ENC-001"],
            confidence=0.84,
            risk_level="low",
            requires_human_review=True,
            cannot_answer_reason=None,
            approved=True,
        )


def test_proposed_answer_requires_human_review():
    with pytest.raises(ValidationError):
        ProposedAnswer(
            **_base_event(),
            question_id="Q-001",
            control_area="encryption",
            answer_type="yes_with_evidence",
            draft_answer="Yes.",
            evidence_ids=["EVID-ENC-001"],
            confidence=0.84,
            risk_level="low",
            requires_human_review=False,
            cannot_answer_reason=None,
        )


def test_proposed_answer_requires_evidence_unless_cannot_answer():
    with pytest.raises(ValidationError):
        ProposedAnswer(
            **_base_event(),
            question_id="Q-001",
            control_area="encryption",
            answer_type="yes_with_evidence",
            draft_answer="Yes.",
            evidence_ids=[],
            confidence=0.84,
            risk_level="low",
            requires_human_review=True,
            cannot_answer_reason=None,
        )


def test_ai_safe_evidence_rejects_restricted_classification():
    with pytest.raises(ValidationError):
        AiSafeEvidence(
            **_base_event(),
            evidence_id="EVID-SECRET",
            question_id="Q-008",
            title="Restricted list",
            control_area="access_control",
            classification=Classification.RESTRICTED,
            content="restricted content",
            source_evidence_id="EVID-SECRET",
        )


def test_evidence_item_accepts_restricted_internal_source():
    event = EvidenceItem(
        **_base_event(),
        evidence_id="EVID-ADMIN-SECRET",
        title="Administrator list",
        source_type="fixture",
        control_area="access_control",
        classification=Classification.RESTRICTED,
        allowed_for_ai=False,
        allowed_for_external_response=False,
        content="synthetic restricted content",
        safe_summary=None,
        valid_from="2026-01-01",
        valid_until="2026-12-31",
        owner="security",
    )

    assert event.classification == Classification.RESTRICTED

