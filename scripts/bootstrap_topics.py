from __future__ import annotations

import subprocess

from demo.contracts import TOPICS


def main() -> int:
    for topic in TOPICS:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "broker",
                "kafka-topics",
                "--bootstrap-server",
                "broker:29092",
                "--create",
                "--if-not-exists",
                "--topic",
                topic,
                "--partitions",
                "1",
                "--replication-factor",
                "1",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if result.returncode != 0:
            print(result.stdout)
            return result.returncode
        print(f"Topic ready: {topic}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
