from __future__ import annotations

import json
import uuid
import urllib.error
import urllib.request
from datetime import UTC, datetime

import pytest
from confluent_kafka.admin import AdminClient, NewTopic

from demo.config import Settings
from demo.contracts import (
    ProposedAnswer,
    ResponseReady,
    ReviewedAnswer,
    ReviewDecision,
    make_event_id,
)
from demo.kafka_io import KafkaClientError, consume_events, kafka_client_config, produce_event


def _runtime_available() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:8081/subjects", timeout=2) as response:
            json.loads(response.read().decode("utf-8"))
        return True
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False


def _acl_mode() -> bool:
    return Settings().kafka_security_protocol.startswith("SASL")


def _draft(run_id: str) -> ProposedAnswer:
    return ProposedAnswer(
        event_id=make_event_id(),
        run_id=run_id,
        occurred_at=datetime.now(UTC),
        producer="svc-ai-drafter",
        schema_version=1,
        question_id="Q-001",
        control_area="encryption",
        answer_type="yes_with_evidence",
        draft_answer="Yes. Customer data is encrypted at rest.",
        evidence_ids=["EVID-ENC-001"],
        confidence=0.8,
        risk_level="low",
        requires_human_review=True,
        cannot_answer_reason=None,
    )


def _reviewed(run_id: str) -> ReviewedAnswer:
    return ReviewedAnswer(
        event_id=make_event_id(),
        run_id=run_id,
        occurred_at=datetime.now(UTC),
        producer="svc-review-export",
        schema_version=1,
        question_id="Q-001",
        reviewer_id="reviewer-demo",
        review_decision=ReviewDecision.APPROVED,
        reviewed_answer="Reviewed answer.",
        approved_evidence_ids=["EVID-ENC-001"],
        review_notes=None,
    )


def _response_ready(run_id: str) -> ResponseReady:
    return ResponseReady(
        event_id=make_event_id(),
        run_id=run_id,
        occurred_at=datetime.now(UTC),
        producer="svc-review-export",
        schema_version=1,
        questionnaire_id="DEMO-QUESTIONNAIRE-001",
        reviewed_answer_ids=["reviewed-1"],
        export_summary="1 reviewed answer ready for export.",
    )


pytestmark = [
    pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running"),
    pytest.mark.skipif(not _acl_mode(), reason="Kafka ACL mode is not enabled"),
]


def test_ai_drafter_can_write_proposed_draft():
    run_id = "run-acl-draft-allowed"

    produce_event("answer.draft.proposed.v1", _draft(run_id), principal="svc-ai-drafter")

    events = consume_events(
        "answer.draft.proposed.v1",
        run_id=run_id,
        timeout_seconds=10,
        principal="svc-policy-guard",
    )
    assert events


def test_ai_drafter_cannot_write_reviewed_or_export_ready_topics():
    run_id = "run-acl-draft-denied"

    with pytest.raises(KafkaClientError):
        produce_event("answer.reviewed.v1", _reviewed(run_id), principal="svc-ai-drafter")

    with pytest.raises(KafkaClientError):
        produce_event(
            "questionnaire.response.ready.v1",
            _response_ready(run_id),
            principal="svc-ai-drafter",
        )


def test_ai_drafter_cannot_read_internal_evidence():
    with pytest.raises(KafkaClientError):
        consume_events(
            "evidence.internal.v1",
            run_id="run-acl-no-internal-read",
            timeout_seconds=3,
            principal="svc-ai-drafter",
        )


def test_review_export_can_write_reviewed_answer():
    run_id = "run-acl-review-allowed"

    produce_event("answer.reviewed.v1", _reviewed(run_id), principal="svc-review-export")

    events = consume_events(
        "answer.reviewed.v1",
        run_id=run_id,
        timeout_seconds=10,
        principal="svc-review-export",
    )
    assert events


def test_application_principal_cannot_create_topics():
    admin = AdminClient(kafka_client_config(principal="svc-ai-drafter"))
    future = admin.create_topics(
        [NewTopic(f"acl-denied-{uuid.uuid4()}", num_partitions=1, replication_factor=1)]
    )

    with pytest.raises(Exception):
        future[next(iter(future))].result(timeout=10)
