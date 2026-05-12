from datetime import UTC, datetime, timedelta

from demo.contracts import make_event_id
from demo.services.audit import build_audit_event, render_timeline


def test_audit_renderer_orders_events_and_includes_outcomes():
    later = build_audit_event(
        run_id="run-audit-test",
        source_event_id=make_event_id(),
        producer="svc-review-export",
        action="exported",
        outcome="response-ready",
        details={"topic": "questionnaire.response.ready.v1"},
        occurred_at=datetime.now(UTC) + timedelta(seconds=1),
    )
    earlier = build_audit_event(
        run_id="run-audit-test",
        source_event_id=make_event_id(),
        producer="svc-ingest",
        action="received",
        outcome="ok",
        details={"topic": "questionnaire.received.v1"},
        occurred_at=datetime.now(UTC),
    )

    rendered = render_timeline([later, earlier], [])

    assert rendered.index("received") < rendered.index("exported")
    assert "questionnaire.response.ready.v1" in rendered

