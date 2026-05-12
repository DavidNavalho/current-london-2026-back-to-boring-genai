import pytest

from demo.kafka_io import consume_events
from tests.scenario.helpers import demo, runtime_available


@pytest.mark.skipif(not runtime_available(), reason="Confluent runtime is not running")
def test_restricted_evidence_is_withheld_and_rejected():
    run_id = "run-restricted-evidence-scenario-test"

    result = demo(["run", "restricted-evidence", "--run-id", run_id])

    assert result.returncode == 0, result.stdout
    assert "SENSITIVE_DATA" in result.stdout
    assert "RESTRICTED_EVIDENCE" in result.stdout

    internal = consume_events("evidence.internal.v1", run_id=run_id, timeout_seconds=10)
    ai_safe = consume_events("evidence.ai_safe.v1", run_id=run_id, timeout_seconds=10)
    rejected = consume_events("answer.draft.rejected.v1", run_id=run_id, timeout_seconds=10)

    assert "EVID-ADMIN-SECRET" in {item.evidence_id for item in internal}
    assert "EVID-ADMIN-SECRET" not in {item.source_evidence_id for item in ai_safe}
    assert rejected
    assert {"SENSITIVE_DATA", "RESTRICTED_EVIDENCE"} <= set(rejected[-1].reason_codes)
    assert "alex.admin@example.test" not in str(ai_safe)
    assert consume_events("questionnaire.response.ready.v1", run_id=run_id, timeout_seconds=2) == []
