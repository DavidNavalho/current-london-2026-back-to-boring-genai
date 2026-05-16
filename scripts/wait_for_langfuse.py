from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"
    deadline = time.time() + 120
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status < 500:
                    print(f"Langfuse is reachable at {url}")
                    return 0
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(2)
    print(f"Timed out waiting for Langfuse at {url}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
