from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8081"
    subjects_url = url.rstrip("/") + "/subjects"
    deadline = time.time() + 90
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(subjects_url, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if isinstance(payload, list):
                print(f"Schema Registry reachable at {subjects_url}")
                return 0
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(2)

    print(f"Schema Registry not reachable at {subjects_url}: {last_error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

