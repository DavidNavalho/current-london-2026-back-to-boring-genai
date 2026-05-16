from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock

from demo.services.agent_swarm import SwarmRunResult


MAX_SWARMS = 20

_SWARMS: dict[str, dict] = {}
_LOCK = Lock()


def save_swarm(result: SwarmRunResult) -> dict:
    payload = result.to_dict()
    payload["status"] = "completed"
    payload["message"] = ""
    with _LOCK:
        _SWARMS[result.swarm_id] = payload
        _trim_locked()
    return payload


def reserve_swarm(swarm_id: str, *, concurrency: int, total_count: int) -> dict:
    now = datetime.now(UTC)
    payload = {
        "swarm_id": swarm_id,
        "status": "running",
        "concurrency": concurrency,
        "started_at": now.isoformat().replace("+00:00", "Z"),
        "ended_at": None,
        "duration_ms": None,
        "total_count": total_count,
        "completed_count": 0,
        "accepted_count": 0,
        "rejected_count": 0,
        "failed_count": 0,
        "questions": [],
        "message": "",
    }
    with _LOCK:
        _SWARMS[swarm_id] = payload
        _trim_locked()
    return payload


def get_swarm(swarm_id: str) -> dict | None:
    with _LOCK:
        payload = _SWARMS.get(swarm_id)
        return dict(payload) if payload is not None else None


def fail_swarm(swarm_id: str, message: str) -> dict:
    ended_at = datetime.now(UTC)
    with _LOCK:
        existing = dict(_SWARMS.get(swarm_id, {}))
        started_at = _parse_datetime(existing.get("started_at")) or ended_at
        total_count = int(existing.get("total_count", 0))
        payload = {
            **existing,
            "swarm_id": swarm_id,
            "status": "failed",
            "ended_at": ended_at.isoformat().replace("+00:00", "Z"),
            "duration_ms": int((ended_at - started_at).total_seconds() * 1000),
            "failed_count": total_count,
            "message": message,
        }
        _SWARMS[swarm_id] = payload
        _trim_locked()
        return payload


def reset_swarms() -> int:
    with _LOCK:
        count = len(_SWARMS)
        _SWARMS.clear()
        return count


def _trim_locked() -> None:
    if len(_SWARMS) <= MAX_SWARMS:
        return
    ordered = sorted(
        _SWARMS.values(),
        key=lambda item: item["started_at"],
        reverse=True,
    )
    keep = {item["swarm_id"] for item in ordered[:MAX_SWARMS]}
    for swarm_id in list(_SWARMS):
        if swarm_id not in keep:
            del _SWARMS[swarm_id]


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
