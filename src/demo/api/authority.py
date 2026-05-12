from __future__ import annotations

from demo.config import Settings
from scripts.bootstrap_acls import SERVICE_ACLS


LABELS = {
    "svc-ingest": "Questionnaire ingest",
    "svc-preparer": "Question preparer",
    "svc-evidence-gateway": "Evidence gateway",
    "svc-ai-drafter": "AI drafter",
    "svc-policy-guard": "Policy guard",
    "svc-review-export": "Review/export",
    "svc-audit-viewer": "Audit viewer",
}

INTENDED_DENIES = {
    "svc-ai-drafter": [
        ("evidence.internal.v1", "READ"),
        ("answer.reviewed.v1", "WRITE"),
        ("questionnaire.response.ready.v1", "WRITE"),
    ]
}


def authority_boundary() -> dict:
    return {
        "acls_enforced": Settings().kafka_security_protocol.startswith("SASL"),
        "principals": [
            {
                "id": principal,
                "label": LABELS.get(principal, principal),
                "rules": _rules_for(principal, grants),
            }
            for principal, grants in SERVICE_ACLS.items()
        ],
    }


def _rules_for(principal: str, grants: dict[str, list[str]]) -> list[dict]:
    rules = [
        {"topic": topic, "operation": "READ", "permission": "ALLOW"}
        for topic in grants["read"]
    ]
    rules.extend(
        {"topic": topic, "operation": "WRITE", "permission": "ALLOW"}
        for topic in grants["write"]
    )
    rules.extend(
        {"topic": topic, "operation": operation, "permission": "DENY"}
        for topic, operation in INTENDED_DENIES.get(principal, [])
    )
    return sorted(rules, key=lambda item: (item["topic"], item["operation"], item["permission"]))
