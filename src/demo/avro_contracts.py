from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from io import BytesIO
from typing import Any

from fastavro import parse_schema, schemaless_reader, schemaless_writer
from pydantic import TypeAdapter

from demo.contracts import SUBJECT_MODELS, StrictEvent


NAMESPACE = "demo.events"


def _base_fields(event_type: str) -> list[dict[str, Any]]:
    return [
        {"name": "event_id", "type": "string"},
        {"name": "run_id", "type": "string"},
        {"name": "event_type", "type": "string", "default": event_type},
        {"name": "occurred_at", "type": {"type": "long", "logicalType": "timestamp-millis"}},
        {"name": "producer", "type": "string"},
        {"name": "schema_version", "type": "int", "default": 1},
    ]


def _record(name: str, event_type: str, fields: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "record",
        "name": name,
        "namespace": NAMESPACE,
        "fields": [*_base_fields(event_type), *fields],
    }


NULL_STRING = ["null", "string"]
STRING_ARRAY = {"type": "array", "items": "string"}


SUBJECT_AVRO_SCHEMAS: dict[str, dict[str, Any]] = {
    "questionnaire.received.v1-value": _record(
        "QuestionnaireReceivedValue",
        "questionnaire.received",
        [
            {"name": "questionnaire_id", "type": "string"},
            {"name": "title", "type": "string"},
            {
                "name": "questions",
                "type": {
                    "type": "array",
                    "items": {
                        "type": "record",
                        "name": "QuestionnaireQuestion",
                        "fields": [
                            {"name": "question_id", "type": "string"},
                            {"name": "scenario", "type": NULL_STRING, "default": None},
                            {"name": "control_area", "type": NULL_STRING, "default": None},
                            {"name": "risk_hint", "type": NULL_STRING, "default": None},
                            {"name": "text", "type": "string"},
                        ],
                    },
                },
            },
        ],
    ),
    "questionnaire.questions.v1-value": _record(
        "PreparedQuestionValue",
        "questionnaire.question_prepared",
        [
            {"name": "questionnaire_id", "type": "string"},
            {"name": "question_id", "type": "string"},
            {"name": "question_text", "type": "string"},
            {"name": "ordinal", "type": "int"},
            {"name": "control_area", "type": "string"},
            {"name": "scenario_tags", "type": STRING_ARRAY, "default": []},
            {"name": "risk_hint", "type": "string", "default": "normal"},
        ],
    ),
    "evidence.internal.v1-value": _record(
        "EvidenceItemValue",
        "evidence.internal",
        [
            {"name": "evidence_id", "type": "string"},
            {"name": "title", "type": "string"},
            {"name": "source_type", "type": "string"},
            {"name": "control_area", "type": "string"},
            {"name": "classification", "type": "string"},
            {"name": "allowed_for_ai", "type": "boolean"},
            {"name": "allowed_for_external_response", "type": "boolean"},
            {"name": "content", "type": "string"},
            {"name": "safe_summary", "type": NULL_STRING, "default": None},
            {"name": "valid_from", "type": NULL_STRING, "default": None},
            {"name": "valid_until", "type": NULL_STRING, "default": None},
            {"name": "owner", "type": "string"},
        ],
    ),
    "evidence.ai_safe.v1-value": _record(
        "AiSafeEvidenceValue",
        "evidence.ai_safe",
        [
            {"name": "evidence_id", "type": "string"},
            {"name": "question_id", "type": "string"},
            {"name": "title", "type": "string"},
            {"name": "control_area", "type": "string"},
            {"name": "classification", "type": "string"},
            {"name": "content", "type": "string"},
            {"name": "source_evidence_id", "type": "string"},
        ],
    ),
    "answer.draft.proposed.v1-value": _record(
        "ProposedAnswerValue",
        "answer.draft.proposed",
        [
            {"name": "question_id", "type": "string"},
            {"name": "control_area", "type": "string"},
            {"name": "answer_type", "type": "string"},
            {"name": "draft_answer", "type": "string"},
            {"name": "evidence_ids", "type": STRING_ARRAY},
            {"name": "confidence", "type": "double"},
            {"name": "risk_level", "type": "string"},
            {"name": "requires_human_review", "type": "boolean", "default": True},
            {"name": "cannot_answer_reason", "type": NULL_STRING, "default": None},
        ],
    ),
    "answer.draft.accepted.v1-value": _record(
        "AcceptedDraftValue",
        "answer.draft.accepted",
        [
            {"name": "question_id", "type": "string"},
            {"name": "draft_event_id", "type": "string"},
            {"name": "evidence_ids", "type": STRING_ARRAY},
            {"name": "policy_result", "type": "string", "default": "accepted"},
            {"name": "requires_human_review", "type": "boolean", "default": True},
        ],
    ),
    "answer.draft.rejected.v1-value": _record(
        "RejectedDraftValue",
        "answer.draft.rejected",
        [
            {"name": "question_id", "type": "string"},
            {"name": "draft_event_id", "type": NULL_STRING, "default": None},
            {"name": "reason_codes", "type": STRING_ARRAY},
            {"name": "message", "type": "string"},
            {"name": "evidence_ids", "type": STRING_ARRAY, "default": []},
        ],
    ),
    "answer.reviewed.v1-value": _record(
        "ReviewedAnswerValue",
        "answer.reviewed",
        [
            {"name": "question_id", "type": "string"},
            {"name": "reviewer_id", "type": "string"},
            {"name": "review_decision", "type": "string"},
            {"name": "reviewed_answer", "type": "string"},
            {"name": "approved_evidence_ids", "type": STRING_ARRAY},
            {"name": "review_notes", "type": NULL_STRING, "default": None},
        ],
    ),
    "questionnaire.response.ready.v1-value": _record(
        "ResponseReadyValue",
        "questionnaire.response.ready",
        [
            {"name": "questionnaire_id", "type": "string"},
            {"name": "reviewed_answer_ids", "type": STRING_ARRAY},
            {"name": "export_summary", "type": "string"},
        ],
    ),
    "audit.timeline.v1-value": _record(
        "AuditEventValue",
        "audit.timeline",
        [
            {"name": "source_event_id", "type": "string"},
            {"name": "action", "type": "string"},
            {"name": "outcome", "type": "string"},
            {
                "name": "details",
                "type": {
                    "type": "map",
                    "values": [
                        "null",
                        "string",
                        "boolean",
                        "int",
                        "long",
                        "double",
                        STRING_ARRAY,
                    ],
                },
                "default": {},
            },
        ],
    ),
    "security.alert.v1-value": _record(
        "SecurityAlertValue",
        "security.alert",
        [
            {"name": "severity", "type": "string"},
            {"name": "principal", "type": "string"},
            {"name": "attempted_operation", "type": "string"},
            {"name": "resource", "type": "string"},
            {"name": "reason", "type": "string"},
        ],
    ),
}


@lru_cache
def parsed_avro_schema(subject: str) -> dict[str, Any]:
    return parse_schema(deepcopy(SUBJECT_AVRO_SCHEMAS[subject]))


def encode_avro_event(subject: str, event: StrictEvent) -> bytes:
    expected_model = SUBJECT_MODELS[subject]
    if not isinstance(event, expected_model):
        raise TypeError(f"{subject} expects {expected_model.__name__}, got {type(event).__name__}")
    payload = event.model_dump(mode="python")
    output = BytesIO()
    schemaless_writer(output, parsed_avro_schema(subject), payload)
    return output.getvalue()


def decode_avro_event(subject: str, payload: bytes) -> StrictEvent:
    input_stream = BytesIO(payload)
    decoded = schemaless_reader(input_stream, parsed_avro_schema(subject))
    return TypeAdapter(SUBJECT_MODELS[subject]).validate_python(decoded)
