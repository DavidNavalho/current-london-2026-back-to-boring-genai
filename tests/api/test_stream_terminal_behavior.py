from __future__ import annotations

from threading import Thread
import time
from uuid import uuid4

from demo.api.event_stream import event_broker, reset_streams


def test_stream_waits_at_human_review_gate_until_terminal_status():
    reset_streams()
    run_id = f"run-stream-terminal-{uuid4()}"
    collected: list[str] = []

    def consume() -> None:
        for chunk in event_broker.open_stream(run_id, terminal_grace_seconds=0.01):
            collected.append(chunk)

    thread = Thread(target=consume)
    thread.start()
    time.sleep(0.1)

    event_broker.publish(
        run_id,
        "status",
        {"run_id": run_id, "status": "waiting_for_human_review", "elapsed_ms": 10},
    )
    time.sleep(0.1)

    assert thread.is_alive()
    event_broker.publish(
        run_id,
        "status",
        {"run_id": run_id, "status": "export_ready", "elapsed_ms": 20},
    )
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert any('"waiting_for_human_review"' in chunk for chunk in collected)
    assert any('"export_ready"' in chunk for chunk in collected)
