import pytest

from demo.kafka_io import consume_events
from tests.scenario.helpers import demo, runtime_available


@pytest.mark.skipif(not runtime_available(), reason="Confluent runtime is not running")
def test_malformed_draft_is_visible_and_stops_downstream_flow():
    run_id = "run-malformed-draft-scenario-test"

    result = demo(["run", "malformed-draft", "--run-id", run_id])

    assert result.returncode == 0, result.stdout
    assert "MALFORMED_EVENT" in result.stdout
    assert "FORBIDDEN_WORKFLOW_FIELD" in result.stdout

    rejected = consume_events("answer.draft.rejected.v1", run_id=run_id, timeout_seconds=10)
    alerts = consume_events("security.alert.v1", run_id=run_id, timeout_seconds=10)
    assert rejected
    assert {"MALFORMED_EVENT", "FORBIDDEN_WORKFLOW_FIELD"} <= set(rejected[-1].reason_codes)
    assert alerts
    assert alerts[-1].reason == "MALFORMED_EVENT"
    assert consume_events("answer.draft.accepted.v1", run_id=run_id, timeout_seconds=2) == []
    assert consume_events("questionnaire.response.ready.v1", run_id=run_id, timeout_seconds=2) == []
