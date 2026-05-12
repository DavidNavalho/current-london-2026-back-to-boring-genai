from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "demo_fixtures"
KNOWN_REASON_CODES = {
    "MISSING_EVIDENCE",
    "UNKNOWN_EVIDENCE_ID",
    "RESTRICTED_EVIDENCE",
    "FORBIDDEN_WORKFLOW_FIELD",
    "APPROVAL_ATTEMPT",
    "EXPORT_ATTEMPT",
    "SENSITIVE_DATA",
    "UNSUPPORTED_CLAIM",
    "PROMPT_INJECTION",
    "MALFORMED_EVENT",
    "ACL_DENIED",
}


def _load_json(name: str) -> dict[str, Any]:
    path = FIXTURE_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache
def load_questionnaire() -> dict[str, Any]:
    return _load_json("questionnaire.json")


@lru_cache
def load_evidence_library() -> dict[str, Any]:
    return _load_json("evidence.json")


@lru_cache
def load_scenarios() -> dict[str, Any]:
    return _load_json("attack_scenarios.json")


def get_question(question_id: str) -> dict[str, Any]:
    for question in load_questionnaire()["questions"]:
        if question["question_id"] == question_id:
            return question
    raise KeyError(f"Unknown question ID: {question_id}")


def get_evidence(evidence_id: str) -> dict[str, Any]:
    for evidence in load_evidence_library()["evidence"]:
        if evidence["evidence_id"] == evidence_id:
            return evidence
    raise KeyError(f"Unknown evidence ID: {evidence_id}")


def get_scenario(scenario_id: str) -> dict[str, Any]:
    for scenario in load_scenarios()["scenarios"]:
        if scenario["scenario_id"] == scenario_id:
            return scenario
    raise KeyError(f"Unknown scenario ID: {scenario_id}")


def validate_fixture_consistency() -> None:
    questionnaire = load_questionnaire()
    evidence_library = load_evidence_library()
    scenarios = load_scenarios()

    question_ids = [question["question_id"] for question in questionnaire["questions"]]
    if len(question_ids) != len(set(question_ids)):
        raise ValueError("Duplicate question IDs in questionnaire fixture")

    evidence_ids = [evidence["evidence_id"] for evidence in evidence_library["evidence"]]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("Duplicate evidence IDs in evidence fixture")

    question_set = set(question_ids)
    for scenario in scenarios["scenarios"]:
        unknown_questions = set(scenario["question_ids"]) - question_set
        if unknown_questions:
            raise ValueError(
                f"Scenario {scenario['scenario_id']} references unknown questions: "
                + ", ".join(sorted(unknown_questions))
            )
        unknown_reasons = set(scenario["expected_reason_codes"]) - KNOWN_REASON_CODES
        if unknown_reasons:
            raise ValueError(
                f"Scenario {scenario['scenario_id']} references unknown reason codes: "
                + ", ".join(sorted(unknown_reasons))
            )

