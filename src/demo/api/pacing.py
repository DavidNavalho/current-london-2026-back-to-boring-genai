from __future__ import annotations

from dataclasses import dataclass
import time

from demo.config import Settings


PRESETS = {
    "realtime": 0,
    "demo": 600,
    "slow": 1500,
}
MAX_DELAY_MS = 5000


@dataclass(frozen=True)
class Pacing:
    name: str
    delay_ms: int

    def sleep_after_stage(self) -> None:
        if self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000)


def parse_pacing(value: str | None) -> Pacing:
    raw = (value if value is not None else Settings().demo_pacing).strip()
    if raw in PRESETS:
        return Pacing(name=raw, delay_ms=PRESETS[raw])
    try:
        delay_ms = int(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid pacing value: {value}") from exc
    if str(delay_ms) != raw or delay_ms < 0 or delay_ms > MAX_DELAY_MS:
        raise ValueError(f"Invalid pacing value: {value}")
    return Pacing(name=raw, delay_ms=delay_ms)
