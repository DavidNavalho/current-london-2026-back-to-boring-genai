from __future__ import annotations

import json
from pathlib import Path

from fastavro import parse_schema

from demo.avro_contracts import SUBJECT_AVRO_SCHEMAS
from demo.contracts import SUBJECT_MODELS


ROOT = Path(__file__).resolve().parents[2]


def test_every_subject_has_avro_schema():
    assert set(SUBJECT_AVRO_SCHEMAS) == set(SUBJECT_MODELS)

    names = set()
    for subject, schema in SUBJECT_AVRO_SCHEMAS.items():
        assert subject.endswith("-value")
        assert schema["type"] == "record"
        assert schema["name"] not in names
        names.add(schema["name"])
        parse_schema(schema)
        json.dumps(schema)


def test_avro_schema_files_match_in_code_map():
    schema_dir = ROOT / "contracts" / "avro"

    for subject, schema in SUBJECT_AVRO_SCHEMAS.items():
        schema_path = schema_dir / f"{subject}.avsc"
        assert schema_path.exists(), f"Missing Avro schema file for {subject}"
        assert json.loads(schema_path.read_text()) == schema


def test_json_schema_artifacts_are_not_used_for_kafka_contracts():
    assert not (ROOT / "contracts" / "schemas").exists()


def test_expected_subjects_are_present():
    assert set(SUBJECT_MODELS) == {
        "questionnaire.received.v1-value",
        "questionnaire.questions.v1-value",
        "evidence.internal.v1-value",
        "evidence.ai_safe.v1-value",
        "answer.draft.proposed.v1-value",
        "answer.draft.accepted.v1-value",
        "answer.draft.rejected.v1-value",
        "answer.reviewed.v1-value",
        "questionnaire.response.ready.v1-value",
        "audit.timeline.v1-value",
        "security.alert.v1-value",
    }
