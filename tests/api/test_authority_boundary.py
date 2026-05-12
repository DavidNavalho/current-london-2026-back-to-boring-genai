from __future__ import annotations

from fastapi.testclient import TestClient

from demo.api.app import app
from scripts.bootstrap_acls import SERVICE_ACLS


client = TestClient(app)


def test_authority_boundary_exposes_ai_drafter_denials():
    response = client.get("/demo/authority-boundary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["acls_enforced"] is True
    drafter = next(item for item in payload["principals"] if item["id"] == "svc-ai-drafter")
    rules = {
        (rule["topic"], rule["operation"]): rule["permission"]
        for rule in drafter["rules"]
    }
    assert rules[("evidence.internal.v1", "READ")] == "DENY"
    assert rules[("answer.reviewed.v1", "WRITE")] == "DENY"
    assert rules[("questionnaire.response.ready.v1", "WRITE")] == "DENY"
    assert rules[("answer.draft.proposed.v1", "WRITE")] == "ALLOW"


def test_authority_boundary_allows_match_acl_bootstrap_intent():
    payload = client.get("/demo/authority-boundary").json()
    principals = {item["id"]: item for item in payload["principals"]}

    for principal, grants in SERVICE_ACLS.items():
        api_rules = {
            (rule["topic"], rule["operation"], rule["permission"])
            for rule in principals[principal]["rules"]
        }
        for topic in grants["read"]:
            assert (topic, "READ", "ALLOW") in api_rules
        for topic in grants["write"]:
            assert (topic, "WRITE", "ALLOW") in api_rules
