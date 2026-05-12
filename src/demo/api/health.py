from __future__ import annotations

from datetime import UTC, datetime
import time

from confluent_kafka.admin import AdminClient

from demo.config import Settings
from demo.kafka_io import kafka_client_config
from demo.model.codex_client import CodexCliClient
from demo.schema_registry import SchemaRegistryClient


CODEX_CACHE_SECONDS = 30.0
_CODEX_CACHE: tuple[float, dict] | None = None


def connection_health() -> dict:
    dependencies = {
        "kafka": _safe_probe(_probe_kafka),
        "schema_registry": _safe_probe(_probe_schema_registry),
        "codex": _safe_probe(_probe_codex_cached),
    }
    return {
        "ok": all(item["ok"] for item in dependencies.values()),
        "checked_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "dependencies": dependencies,
    }


def reset_codex_cache() -> None:
    global _CODEX_CACHE
    _CODEX_CACHE = None


def _safe_probe(func) -> dict:
    try:
        return func()
    except Exception as exc:
        return {"ok": False, "detail": str(exc)}


def _probe_kafka() -> dict:
    metadata = AdminClient(kafka_client_config()).list_topics(timeout=2)
    return {
        "ok": True,
        "detail": "metadata available",
        "topic_count": len(metadata.topics),
    }


def _probe_schema_registry() -> dict:
    subjects = SchemaRegistryClient(Settings().schema_registry_url).list_subjects()
    return {
        "ok": True,
        "detail": "subjects available",
        "subject_count": len(subjects),
    }


def _probe_codex_cached() -> dict:
    global _CODEX_CACHE
    now = time.monotonic()
    if _CODEX_CACHE and now - _CODEX_CACHE[0] < CODEX_CACHE_SECONDS:
        cached = dict(_CODEX_CACHE[1])
        cached["cached"] = True
        return cached
    result = _run_codex_preflight()
    _CODEX_CACHE = (now, dict(result))
    return result


def _run_codex_preflight() -> dict:
    CodexCliClient(timeout_seconds=30).preflight()
    return {"ok": True, "detail": "Codex CLI authenticated"}
