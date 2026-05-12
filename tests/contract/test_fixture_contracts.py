from __future__ import annotations

from datetime import UTC, datetime

from demo.contracts import EvidenceItem, make_event_id
from demo.fixtures import load_evidence_library


def _base_event() -> dict:
    return {
        "event_id": make_event_id(),
        "run_id": "fixture-contract-test",
        "occurred_at": datetime.now(UTC),
        "producer": "fixture-test",
        "schema_version": 1,
    }


def test_evidence_fixtures_validate_as_evidence_items():
    for item in load_evidence_library()["evidence"]:
        event = EvidenceItem(**_base_event(), **item)
        assert event.evidence_id == item["evidence_id"]

