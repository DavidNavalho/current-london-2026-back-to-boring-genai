from __future__ import annotations

from demo.fixtures import get_question, load_evidence_library, load_questionnaire
from demo.services.evidence_gateway import QUESTION_EVIDENCE


def questionnaire_overview() -> dict:
    questionnaire = load_questionnaire()
    return {
        "questionnaire_id": questionnaire["questionnaire_id"],
        "title": questionnaire["title"],
        "questions": [
            {
                "question_id": question["question_id"],
                "text": question["text"],
                "control_area": question["control_area"],
                "risk_hint": question["risk_hint"],
                "scenario": question["scenario"],
            }
            for question in questionnaire["questions"]
        ],
    }


def question_detail(question_id: str) -> dict:
    question = get_question(question_id)
    questionnaire = load_questionnaire()
    by_evidence_id = {
        item["evidence_id"]: item for item in load_evidence_library()["evidence"]
    }
    selected = [
        by_evidence_id[evidence_id]
        for evidence_id in QUESTION_EVIDENCE.get(question_id, [])
        if evidence_id in by_evidence_id
    ]
    return {
        "question_id": question["question_id"],
        "questionnaire_id": questionnaire["questionnaire_id"],
        "control_area": question["control_area"],
        "risk_hint": question["risk_hint"],
        "scenario": question["scenario"],
        "text": question["text"],
        "ai_safe_evidence": [_ai_safe_view(item) for item in selected if _allowed_for_ai(item)],
        "withheld_evidence": [_withheld_view(item) for item in selected if not _allowed_for_ai(item)],
    }


def _allowed_for_ai(item: dict) -> bool:
    return item["allowed_for_ai"] and item["classification"] not in {"restricted", "secret"}


def _ai_safe_view(item: dict) -> dict:
    return {
        "evidence_id": item["evidence_id"],
        "title": item["title"],
        "control_area": item["control_area"],
        "classification": item["classification"],
        "safe_summary": item["safe_summary"] or item["content"],
    }


def _withheld_view(item: dict) -> dict:
    return {
        "evidence_id": item["evidence_id"],
        "title": item["title"],
        "control_area": item["control_area"],
        "classification": item["classification"],
        "redaction_label": f"withheld - {item['classification']}",
    }
