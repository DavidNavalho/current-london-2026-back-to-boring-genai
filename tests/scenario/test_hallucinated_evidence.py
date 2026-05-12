import pytest

from demo.kafka_io import consume_events
from tests.scenario.helpers import demo, runtime_available


@pytest.mark.skipif(not runtime_available(), reason="Confluent runtime is not running")
def test_hallucinated_evidence_id_is_rejected():
    run_id = "run-hallucinated-evidence-scenario-test"

    result = demo(["run", "hallucinated-evidence", "--run-id", run_id])

    assert result.returncode == 0, result.stdout
    assert "UNKNOWN_EVIDENCE_ID" in result.stdout

    rejected = consume_events("answer.draft.rejected.v1", run_id=run_id, timeout_seconds=10)
    assert rejected
    assert "UNKNOWN_EVIDENCE_ID" in rejected[-1].reason_codes
    assert consume_events("answer.draft.accepted.v1", run_id=run_id, timeout_seconds=2) == []
    assert consume_events("answer.reviewed.v1", run_id=run_id, timeout_seconds=2) == []
    assert consume_events("questionnaire.response.ready.v1", run_id=run_id, timeout_seconds=2) == []
