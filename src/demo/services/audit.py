from __future__ import annotations

from datetime import UTC, datetime

from demo.contracts import AuditEvent, SecurityAlert, make_event_id


def build_audit_event(
    *,
    run_id: str,
    source_event_id: str,
    producer: str,
    action: str,
    outcome: str,
    details: dict | None = None,
    occurred_at: datetime | None = None,
) -> AuditEvent:
    return AuditEvent(
        event_id=make_event_id(),
        run_id=run_id,
        occurred_at=occurred_at or datetime.now(UTC),
        producer=producer,
        schema_version=1,
        source_event_id=source_event_id,
        action=action,
        outcome=outcome,
        details=details or {},
    )


def render_timeline(
    events: list[AuditEvent], security_alerts: list[SecurityAlert]
) -> str:
    lines: list[str] = []
    for event in sorted(events, key=lambda item: (item.occurred_at, item.event_id)):
        topic = event.details.get("topic", "n/a")
        lines.append(
            f"{event.occurred_at.isoformat()} | {event.action} | {event.outcome} | {topic}"
        )
    for alert in sorted(security_alerts, key=lambda item: (item.occurred_at, item.event_id)):
        lines.append(
            f"{alert.occurred_at.isoformat()} | security | {alert.severity} | {alert.reason}"
        )
    return "\n".join(lines)

