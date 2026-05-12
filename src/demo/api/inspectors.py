from __future__ import annotations

import json
import urllib.error

from demo.config import Settings
from demo.contracts import SUBJECT_MODELS, TOPICS, AuditEvent, SecurityAlert
from demo.kafka_io import TOPIC_SUBJECTS, consume_events
from demo.schema_registry import SchemaRegistryClient


def structured_audit_events(run_id: str) -> list[dict]:
    audits = consume_events(
        "audit.timeline.v1",
        run_id=run_id,
        timeout_seconds=10,
        principal="svc-audit-viewer",
    )
    alerts = consume_events(
        "security.alert.v1",
        run_id=run_id,
        timeout_seconds=2,
        principal="svc-audit-viewer",
    )
    combined = [*_audit_rows(audits), *_security_rows(alerts)]
    combined.sort(key=lambda item: (item["occurred_at"], item["event_id"]))
    if not combined:
        return []
    first_at = min(item["_occurred_at_dt"] for item in combined)
    for item in combined:
        item["elapsed_ms"] = int((item["_occurred_at_dt"] - first_at).total_seconds() * 1000)
        del item["_occurred_at_dt"]
    return combined


def topic_events(topic: str, *, run_id: str, limit: int = 20) -> dict:
    if topic not in TOPICS:
        raise KeyError(topic)
    capped_limit = min(max(limit, 0), 100)
    subject = TOPIC_SUBJECTS[topic]
    events = consume_events(topic, run_id=run_id, timeout_seconds=10)
    selected = events[-capped_limit:] if capped_limit else []
    schema_version = _schema_version(subject)
    return {
        "topic": topic,
        "schema_subject": subject,
        "schema_version": schema_version,
        "limit": capped_limit,
        "events": [
            {
                "event_id": event.event_id,
                "occurred_at": event.occurred_at.isoformat().replace("+00:00", "Z"),
                "producer": event.producer,
                "payload": event.model_dump(mode="json"),
            }
            for event in selected
        ],
    }


def schema_lookup(subject: str, *, schema_registry_url: str | None = None) -> dict:
    if subject not in SUBJECT_MODELS:
        raise KeyError(subject)
    client = SchemaRegistryClient(schema_registry_url or Settings().schema_registry_url)
    try:
        metadata = client.get_latest_subject_metadata(subject)
    except (OSError, urllib.error.URLError) as exc:
        raise ConnectionError(str(exc)) from exc
    schema = metadata["schema"]
    return {
        "subject": subject,
        "version": metadata["version"],
        "schema_type": metadata.get("schemaType", "AVRO"),
        "schema": schema,
        "schema_text": json.dumps(schema, indent=2),
    }


def _schema_version(subject: str) -> int:
    try:
        return int(schema_lookup(subject)["version"])
    except Exception:
        return 1


def _audit_rows(events: list[AuditEvent]) -> list[dict]:
    return [
        {
            "event_id": event.event_id,
            "occurred_at": event.occurred_at.isoformat().replace("+00:00", "Z"),
            "_occurred_at_dt": event.occurred_at,
            "kind": "audit",
            "producer": event.producer,
            "action": event.action,
            "outcome": event.outcome,
            "topic": event.details.get("topic"),
            "source_event_id": event.source_event_id,
            "details": event.details,
        }
        for event in events
    ]


def _security_rows(events: list[SecurityAlert]) -> list[dict]:
    return [
        {
            "event_id": event.event_id,
            "occurred_at": event.occurred_at.isoformat().replace("+00:00", "Z"),
            "_occurred_at_dt": event.occurred_at,
            "kind": "security",
            "severity": event.severity,
            "principal": event.principal,
            "attempted_operation": event.attempted_operation,
            "resource": event.resource,
            "reason": event.reason,
        }
        for event in events
    ]
