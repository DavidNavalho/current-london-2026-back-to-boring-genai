from __future__ import annotations

from confluent_kafka import KafkaError, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic

from demo.contracts import TOPICS
from demo.kafka_io import kafka_client_config


def main() -> int:
    admin = AdminClient(kafka_client_config())
    futures = admin.create_topics(
        [
            NewTopic(topic, num_partitions=1, replication_factor=1)
            for topic in TOPICS
        ],
        operation_timeout=10,
        request_timeout=15,
    )

    for topic in TOPICS:
        try:
            futures[topic].result()
        except KafkaException as exc:
            error = exc.args[0]
            if error.code() != KafkaError.TOPIC_ALREADY_EXISTS:
                print(f"Topic bootstrap failed for {topic}: {error}")
                return 1
        print(f"Topic ready: {topic}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
