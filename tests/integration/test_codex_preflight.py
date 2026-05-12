from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from demo.fixtures import get_question, load_evidence_library
from demo.kafka_io import consume_events
from demo.model.codex_client import CodexCliClient, CodexUnavailable
from demo.services.ai_drafter import generate_draft
from demo.services.evidence_gateway import make_ai_safe_evidence, select_evidence
from demo.services.prepare_questions import prepared_question_from_fixture


ROOT = Path(__file__).resolve().parents[2]


def _codex_tests_enabled() -> bool:
    return os.getenv("DEMO_RUN_CODEX_TESTS") == "1"


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


@pytest.mark.codex
@pytest.mark.skipif(not _codex_tests_enabled(), reason="Set DEMO_RUN_CODEX_TESTS=1 to run Codex smoke tests")
def test_codex_preflight_cli_succeeds_when_enabled():
    if not shutil.which("codex"):
        pytest.skip("Codex CLI is not installed")

    result = _demo(["codex", "preflight"])

    assert result.returncode == 0, result.stdout
    assert "Codex preflight passed" in result.stdout


@pytest.mark.codex
@pytest.mark.skipif(not _codex_tests_enabled(), reason="Set DEMO_RUN_CODEX_TESTS=1 to run Codex smoke tests")
def test_codex_happy_path_smoke_produces_parseable_proposed_answer():
    question = prepared_question_from_fixture("run-codex-smoke", get_question("Q-001"), 1)
    selected = select_evidence(question, load_evidence_library())
    ai_safe = make_ai_safe_evidence(question, selected)

    try:
        proposed = generate_draft(question, ai_safe, CodexCliClient(timeout_seconds=180))
    except CodexUnavailable as exc:
        pytest.skip(str(exc))

    assert proposed.event_type == "answer.draft.proposed"
    assert proposed.question_id == "Q-001"
    assert proposed.requires_human_review is True
    assert "EVID-ENC-001" in proposed.evidence_ids


@pytest.mark.codex
@pytest.mark.skipif(not _codex_tests_enabled(), reason="Set DEMO_RUN_CODEX_TESTS=1 to run Codex smoke tests")
@pytest.mark.skipif(not _runtime_available(), reason="Confluent runtime is not running")
def test_draft_worker_publishes_codex_draft_when_enabled():
    run_id = "run-codex-worker-test"

    for args in (
        ["seed", "evidence", "--run-id", run_id],
        ["ingest", "questionnaire", "--run-id", run_id],
        ["worker", "prepare", "--run-id", run_id],
        ["worker", "evidence", "--run-id", run_id, "--question-id", "Q-001"],
        ["worker", "draft", "--run-id", run_id, "--question-id", "Q-001"],
    ):
        result = _demo(args)
        assert result.returncode == 0, result.stdout

    drafts = consume_events("answer.draft.proposed.v1", run_id=run_id, timeout_seconds=15)
    assert any(item.question_id == "Q-001" for item in drafts)
