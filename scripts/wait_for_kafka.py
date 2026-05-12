from __future__ import annotations

import socket
import sys
import time


def main() -> int:
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 9092
    deadline = time.time() + 90

    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"Kafka reachable at {host}:{port}")
                return 0
        except OSError as exc:
            last_error = exc
            time.sleep(2)

    print(f"Kafka not reachable at {host}:{port}: {last_error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

