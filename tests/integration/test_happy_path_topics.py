from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pytest

from demo.contracts import ProposedAnswer, make_event_id
from demo.kafka_io import consume_events, produce_event


ROOT = Path(__file__).resolve().parents[2]


def _runtime_available() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:8081/subjects", timeout=2) as response:
            json.loads(response.read().decode("utf-8"))
        return True
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False


def _demo(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(ROOT / ".venv" / "bin" / "demo"), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_guard_review_and_export_publish_happy_path_topics():
    run_id = "run-happy-path-topics-test"

    for args in (
        ["seed", "evidence", "--run-id", run_id],
        ["ingest", "questionnaire", "--run-id", run_id],
        ["worker", "prepare", "--run-id", run_id],
        ["worker", "evidence", "--run-id", run_id, "--question-id", "Q-001"],
    ):
        result = _demo(args)
        assert result.returncode == 0, result.stdout

    produce_event(
        "answer.draft.proposed.v1",
        ProposedAnswer(
            event_id=make_event_id(),
            run_id=run_id,
            occurred_at=datetime.now(UTC),
            producer="svc-test-drafter",
            schema_version=1,
            question_id="Q-001",
            control_area="encryption",
            answer_type="yes_with_evidence",
            draft_answer="Yes. Customer data is encrypted at rest.",
            evidence_ids=["EVID-ENC-001"],
            confidence=0.91,
            risk_level="low",
            requires_human_review=True,
            cannot_answer_reason=None,
        ),
    )

    guard = _demo(["worker", "guard", "--run-id", run_id, "--question-id", "Q-001"])
    assert guard.returncode == 0, guard.stdout
    assert "accepted" in guard.stdout
    assert consume_events("answer.draft.accepted.v1", run_id=run_id, timeout_seconds=10)

    review = _demo(["review", "approve", "Q-001", "--run-id", run_id])
    assert review.returncode == 0, review.stdout
    assert consume_events("answer.reviewed.v1", run_id=run_id, timeout_seconds=10)

    export = _demo(["export", "--run-id", run_id])
    assert export.returncode == 0, export.stdout
    assert consume_events("questionnaire.response.ready.v1", run_id=run_id, timeout_seconds=10)

    rejected = consume_events("answer.draft.rejected.v1", run_id=run_id, timeout_seconds=2)
    alerts = consume_events("security.alert.v1", run_id=run_id, timeout_seconds=2)
    assert rejected == []
    assert alerts == []

    audit = consume_events("audit.timeline.v1", run_id=run_id, timeout_seconds=10)
    assert {"received", "prepared", "evidence", "accepted", "reviewed", "exported"} <= {
        item.action for item in audit
    }


@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_export_requires_reviewed_answer():
    run_id = "run-export-before-review-test"

    result = _demo(["export", "--run-id", run_id])

    assert result.returncode != 0
    assert "reviewed approved answer" in result.stdout
