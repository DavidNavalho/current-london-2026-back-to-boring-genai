from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from demo.kafka_io import consume_events


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
def test_ingest_prepare_and_evidence_workers():
    run_id = "run-command-workers-test"

    seed = _demo(["seed", "evidence", "--run-id", run_id])
    assert seed.returncode == 0, seed.stdout
    assert consume_events("evidence.internal.v1", run_id=run_id, timeout_seconds=10)

    ingest = _demo(["ingest", "questionnaire", "--run-id", run_id])
    assert ingest.returncode == 0, ingest.stdout
    assert consume_events("questionnaire.received.v1", run_id=run_id, timeout_seconds=10)

    prepare = _demo(["worker", "prepare", "--run-id", run_id])
    assert prepare.returncode == 0, prepare.stdout
    prepared = consume_events("questionnaire.questions.v1", run_id=run_id, timeout_seconds=10)
    assert any(item.question_id == "Q-001" for item in prepared)

    evidence = _demo(["worker", "evidence", "--run-id", run_id, "--question-id", "Q-001"])
    assert evidence.returncode == 0, evidence.stdout
    ai_safe = consume_events("evidence.ai_safe.v1", run_id=run_id, timeout_seconds=10)
    assert any(item.source_evidence_id == "EVID-ENC-001" for item in ai_safe)

