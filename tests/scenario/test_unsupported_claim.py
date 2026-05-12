import pytest

from demo.kafka_io import consume_events
from tests.scenario.helpers import demo, runtime_available


@pytest.mark.skipif(not runtime_available(), reason="Confluent runtime is not running")
def test_unsupported_certification_claim_is_rejected():
    run_id = "run-unsupported-claim-scenario-test"

    result = demo(["run", "unsupported-claim", "--run-id", run_id])

    assert result.returncode == 0, result.stdout
    assert "UNSUPPORTED_CLAIM" in result.stdout

    rejected = consume_events("answer.draft.rejected.v1", run_id=run_id, timeout_seconds=10)
    assert rejected
    assert "UNSUPPORTED_CLAIM" in rejected[-1].reason_codes
    assert consume_events("questionnaire.response.ready.v1", run_id=run_id, timeout_seconds=2) == []
