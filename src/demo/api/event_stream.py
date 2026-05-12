from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from queue import Empty, Full, Queue
from threading import Lock
import time
from collections.abc import Iterator

from demo.api.stages import STAGES
from demo.contracts import AuditEvent, SecurityAlert, StrictEvent
from demo.scenario_runner import ScenarioRunContext


BUFFER_SIZE = 200
LIVE_QUEUE_SIZE = 1000
HEARTBEAT_SECONDS = 15.0
TERMINAL_GRACE_SECONDS = 2.0
TERMINAL_STATUSES = {"export_ready", "rejected", "denied", "failed"}

STAGE_BY_TOPIC = {stage.topic: stage for stage in STAGES}


class LiveSubscriberExists(RuntimeError):
    """Raised when a second live subscriber tries to attach to a run."""


@dataclass(frozen=True)
class StreamEvent:
    event_type: str
    data: dict

    @property
    def elapsed_ms(self) -> int:
        return int(self.data.get("elapsed_ms", 0))

    @property
    def terminal(self) -> bool:
        return self.event_type == "status" and self.data.get("status") in TERMINAL_STATUSES

    def as_sse(self) -> str:
        encoded = json.dumps(self.data, separators=(",", ":"), sort_keys=True)
        return f"event: {self.event_type}\ndata: {encoded}\n\n"


class RunEventBroker:
    def __init__(self) -> None:
        self._buffers: dict[str, deque[StreamEvent]] = {}
        self._truncated: set[str] = set()
        self._subscribers: dict[str, Queue[StreamEvent]] = {}
        self._dropped: dict[str, int] = {}
        self._lock = Lock()

    def publish(self, run_id: str, event_type: str, data: dict) -> None:
        payload = dict(data)
        payload.setdefault("run_id", run_id)
        payload.setdefault("elapsed_ms", 0)
        event = StreamEvent(event_type=event_type, data=payload)
        subscriber: Queue[StreamEvent] | None = None
        with self._lock:
            buffer = self._buffers.setdefault(run_id, deque(maxlen=BUFFER_SIZE))
            if len(buffer) == BUFFER_SIZE:
                self._truncated.add(run_id)
            buffer.append(event)
            subscriber = self._subscribers.get(run_id)
        if subscriber is not None:
            self._enqueue(run_id, subscriber, event)

    def open_stream(
        self,
        run_id: str,
        *,
        from_elapsed_ms: int | None = None,
        terminal_grace_seconds: float = TERMINAL_GRACE_SECONDS,
    ) -> Iterator[str]:
        with self._lock:
            if run_id in self._subscribers:
                raise LiveSubscriberExists(run_id)
            queue: Queue[StreamEvent] = Queue(maxsize=LIVE_QUEUE_SIZE)
            self._subscribers[run_id] = queue
            snapshot = list(self._buffers.get(run_id, []))
            truncated = run_id in self._truncated

        def _events() -> Iterator[str]:
            terminal_deadline: float | None = None
            try:
                if (
                    from_elapsed_ms is not None
                    and truncated
                    and snapshot
                    and from_elapsed_ms < snapshot[0].elapsed_ms
                ):
                    yield StreamEvent(
                        "status",
                        {
                            "run_id": run_id,
                            "status": "replay_gap",
                            "elapsed_ms": snapshot[0].elapsed_ms,
                            "earliest_elapsed_ms": snapshot[0].elapsed_ms,
                        },
                    ).as_sse()
                for event in snapshot:
                    if from_elapsed_ms is not None and event.elapsed_ms < from_elapsed_ms:
                        continue
                    yield event.as_sse()
                    if event.terminal and terminal_deadline is None:
                        terminal_deadline = time.monotonic() + terminal_grace_seconds

                while True:
                    if terminal_deadline is not None:
                        timeout = max(0.0, terminal_deadline - time.monotonic())
                        if timeout == 0:
                            break
                    else:
                        timeout = HEARTBEAT_SECONDS
                    try:
                        event = queue.get(timeout=timeout)
                    except Empty:
                        if terminal_deadline is not None:
                            break
                        yield ": heartbeat\n\n"
                        continue
                    yield event.as_sse()
                    if event.terminal and terminal_deadline is None:
                        terminal_deadline = time.monotonic() + terminal_grace_seconds
            finally:
                with self._lock:
                    if self._subscribers.get(run_id) is queue:
                        del self._subscribers[run_id]

        return _events()

    def reset(self) -> int:
        with self._lock:
            count = len(self._buffers)
            self._buffers.clear()
            self._truncated.clear()
            self._dropped.clear()
            self._subscribers.clear()
            return count

    def _enqueue(self, run_id: str, queue: Queue[StreamEvent], event: StreamEvent) -> None:
        try:
            queue.put_nowait(event)
        except Full:
            try:
                queue.get_nowait()
            except Empty:
                pass
            self._dropped[run_id] = self._dropped.get(run_id, 0) + 1
            queue.put_nowait(event)


class RunStreamObserver:
    def __init__(self, context: ScenarioRunContext) -> None:
        self.context = context

    def status(self, run_id: str, status: str, **fields) -> None:
        event_broker.publish(
            run_id,
            "status",
            {
                "run_id": run_id,
                "status": status,
                "occurred_at": _now_iso(),
                "elapsed_ms": self._elapsed_ms(),
                **fields,
            },
        )

    def stage(self, topic: str, event: StrictEvent, principal: str, summary: str) -> None:
        stage = STAGE_BY_TOPIC[topic]
        event_broker.publish(
            event.run_id,
            "stage",
            {
                "run_id": event.run_id,
                "stage_key": stage.key,
                "topic": topic,
                "principal": principal,
                "event_id": event.event_id,
                "event_type": event.event_type,
                "occurred_at": event.occurred_at.isoformat().replace("+00:00", "Z"),
                "elapsed_ms": self._elapsed_ms(),
                "summary": summary,
            },
        )

    def audit(self, event: AuditEvent) -> None:
        event_broker.publish(
            event.run_id,
            "audit",
            {
                "run_id": event.run_id,
                "event_id": event.event_id,
                "occurred_at": event.occurred_at.isoformat().replace("+00:00", "Z"),
                "elapsed_ms": self._elapsed_ms(),
                "producer": event.producer,
                "source_event_id": event.source_event_id,
                "action": event.action,
                "outcome": event.outcome,
                "details": event.details,
            },
        )

    def security(self, event: SecurityAlert) -> None:
        event_broker.publish(
            event.run_id,
            "security",
            {
                "run_id": event.run_id,
                "event_id": event.event_id,
                "occurred_at": event.occurred_at.isoformat().replace("+00:00", "Z"),
                "elapsed_ms": self._elapsed_ms(),
                "severity": event.severity,
                "principal": event.principal,
                "attempted_operation": event.attempted_operation,
                "resource": event.resource,
                "reason": event.reason,
            },
        )

    def telemetry(self, run_id: str, **metrics) -> None:
        event_broker.publish(
            run_id,
            "telemetry",
            {
                "run_id": run_id,
                "occurred_at": _now_iso(),
                "elapsed_ms": self._elapsed_ms(),
                **metrics,
            },
        )

    def _elapsed_ms(self) -> int:
        return int((datetime.now(UTC) - self.context.started_at).total_seconds() * 1000)


event_broker = RunEventBroker()


def reset_streams() -> int:
    return event_broker.reset()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
