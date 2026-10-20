
"""Membuat dan memverifikasi topic Kafka secara idempoten."""

import os
import time

from kafka import KafkaAdminClient
from kafka.admin import NewTopic
from kafka.errors import TopicAlreadyExistsError


BOOTSTRAP = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "localhost:29092",
)

TOPICS = {
    "olist.order_events": 3,
    "olist.order_events.dlq": 1,
}

VERIFY_TIMEOUT_SECONDS = 30
VERIFY_INTERVAL_SECONDS = 1


def wait_for_topics(admin, expected_topics):
    """Tunggu hingga seluruh topic muncul di metadata Kafka."""

    deadline = time.monotonic() + VERIFY_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        actual = set(admin.list_topics())
        missing = expected_topics - actual

        if not missing:
            return

        print(
            "WAITING: metadata topic belum lengkap:",
            sorted(missing),
        )

        time.sleep(VERIFY_INTERVAL_SECONDS)

    actual = set(admin.list_topics())
    missing = expected_topics - actual

    raise RuntimeError(
        f"Kafka topics not visible after "
        f"{VERIFY_TIMEOUT_SECONDS}s: {sorted(missing)}"
    )


def main():
    print("=== T3 CREATE KAFKA TOPICS ===")

    admin = KafkaAdminClient(
        bootstrap_servers=BOOTSTRAP,
        client_id="olist-topic-admin",
        request_timeout_ms=10000,
    )

    try:
        for name, partitions in TOPICS.items():
            topic = NewTopic(
                name=name,
                num_partitions=partitions,
                replication_factor=1,
            )

            try:
                admin.create_topics(
                    new_topics=[topic],
                    validate_only=False,
                )
                print(f"CREATED: {name}")

            except TopicAlreadyExistsError:
                print(f"EXISTS: {name}")

        wait_for_topics(admin, set(TOPICS))

        for name in TOPICS:
            print(f"PASS: {name}")

    finally:
        admin.close()

    print("\nT3 Kafka topics: PASS")


if __name__ == "__main__":
    main()
