
"""F03: Crash after PostgreSQL commit, before Kafka offset commit.

Run:
    python -B -m scripts.failure_f03_consumer_crash

Uses a dedicated Kafka consumer group and one valid Kafka record.
Existing Kafka topics and PostgreSQL data are not reset.
"""

import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from kafka import KafkaConsumer, TopicPartition
from kafka.structs import OffsetAndMetadata

from olist.stream_consumer import process_event, validate_event


ROOT = Path(__file__).resolve().parent.parent
TOPIC = "olist.order_events"
BOOTSTRAP = "localhost:29092"
CRASH_CODE = 73


def database_connection():
    load_dotenv(ROOT / ".env")

    return psycopg.connect(
        host="localhost",
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def kafka_consumer(group_id=None):
    return KafkaConsumer(
        bootstrap_servers=BOOTSTRAP,
        group_id=group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        consumer_timeout_ms=1000,
    )


def event_count(event_id):
    with database_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM stream.order_events
                WHERE event_id = %s
                """,
                (event_id,),
            )
            return cur.fetchone()[0]


def current_rank(order_id):
    with database_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT status_rank
                FROM stream.order_current
                WHERE order_id = %s
                """,
                (order_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None


def find_valid_record():
    """Find a recent valid message without changing Kafka offsets."""

    consumer = kafka_consumer()

    try:
        partitions = consumer.partitions_for_topic(TOPIC)

        if not partitions:
            raise RuntimeError(
                f"Topic {TOPIC} has no partitions"
            )

        for partition in sorted(partitions):
            tp = TopicPartition(TOPIC, partition)
            consumer.assign([tp])

            start = consumer.beginning_offsets([tp])[tp]
            end = consumer.end_offsets([tp])[tp]

            # Scan a small recent range; do not read full history.
            consumer.seek(tp, max(start, end - 500))

            while consumer.position(tp) < end:
                batches = consumer.poll(
                    timeout_ms=2000,
                    max_records=100,
                )

                records = batches.get(tp, [])

                if not records:
                    break

                for record in records:
                    try:
                        event = validate_event(record.value)

                        if (
                            event["order_id"].encode("utf-8")
                            != record.key
                        ):
                            continue

                    except ValueError:
                        continue

                    return {
                        "partition": record.partition,
                        "offset": record.offset,
                        "event_id": event["event_id"],
                        "order_id": event["order_id"],
                    }

        raise RuntimeError(
            "No valid message found in recent Kafka offsets"
        )

    finally:
        consumer.close()


def create_group_checkpoint(group_id, partition, offset):
    """Commit a baseline offset for the dedicated test group."""

    consumer = kafka_consumer(group_id)

    try:
        tp = TopicPartition(TOPIC, partition)
        consumer.assign([tp])
        consumer.seek(tp, offset)

        consumer.commit({
            tp: OffsetAndMetadata(offset, "", -1),
        })

        committed = consumer.committed(tp)

        if committed != offset:
            raise AssertionError(
                f"Expected committed offset {offset}, "
                f"found {committed}"
            )

    finally:
        consumer.close()


def consume_one(group_id, expected, crash):
    """Worker: process one exact Kafka record."""

    consumer = kafka_consumer(group_id)

    try:
        tp = TopicPartition(
            TOPIC,
            expected["partition"],
        )

        consumer.assign([tp])

        committed = consumer.committed(tp)

        if committed != expected["offset"]:
            raise AssertionError(
                f"Expected offset {expected['offset']}, "
                f"found {committed}"
            )

        consumer.seek(tp, committed)

        batches = consumer.poll(
            timeout_ms=10000,
            max_records=1,
        )

        records = batches.get(tp, [])

        if len(records) != 1:
            raise AssertionError(
                "Expected exactly one Kafka message"
            )

        record = records[0]

        if record.offset != expected["offset"]:
            raise AssertionError(
                f"Unexpected offset: {record.offset}"
            )

        event = validate_event(record.value)

        if event["event_id"] != expected["event_id"]:
            raise AssertionError(
                "Unexpected event ID"
            )

        if event["order_id"].encode("utf-8") != record.key:
            raise AssertionError(
                "Kafka key does not match order_id"
            )

        with database_connection() as conn:
            result = process_event(conn, event)
            conn.commit()

        print(
            f"DB_COMMITTED offset={record.offset} "
            f"event_id={event['event_id']} "
            f"result={result}",
            flush=True,
        )

        if crash:
            print(
                "INJECT_CRASH: before Kafka offset commit",
                flush=True,
            )
            os._exit(CRASH_CODE)

        # Only the restart worker reaches this point.
        consumer.commit()

        print(
            f"KAFKA_OFFSET_COMMITTED: "
            f"{consumer.committed(tp)}",
            flush=True,
        )

        return result

    finally:
        consumer.close()


def worker():
    group_id = os.environ["F03_GROUP_ID"]
    partition = int(os.environ["F03_PARTITION"])
    offset = int(os.environ["F03_OFFSET"])
    event_id = os.environ["F03_EVENT_ID"]
    order_id = os.environ["F03_ORDER_ID"]

    expected = {
        "partition": partition,
        "offset": offset,
        "event_id": event_id,
        "order_id": order_id,
    }

    crash = os.environ.get("F03_CRASH") == "1"

    consume_one(group_id, expected, crash)


def main():
    print("=== F03 CONSUMER CRASH TEST ===", flush=True)

    target = find_valid_record()
    group_id = "olist-f03-" + uuid.uuid4().hex[:12]

    before_count = event_count(target["event_id"])
    before_rank = current_rank(target["order_id"])

    print(f"Dedicated group: {group_id}")
    print(f"Partition: {target['partition']}")
    print(f"Offset: {target['offset']}")
    print(f"Event ID: {target['event_id']}")
    print(f"Event rows before: {before_count}")

    create_group_checkpoint(
        group_id,
        target["partition"],
        target["offset"],
    )

    worker_env = os.environ.copy()
    worker_env.update({
        "F03_GROUP_ID": group_id,
        "F03_PARTITION": str(target["partition"]),
        "F03_OFFSET": str(target["offset"]),
        "F03_EVENT_ID": target["event_id"],
        "F03_ORDER_ID": target["order_id"],
    })

    command = [
        sys.executable,
        "-B",
        "-m",
        "scripts.failure_f03_consumer_crash",
        "--worker",
    ]

    print(
        "\n[1] Injecting crash after DB commit...",
        flush=True,
    )

    crashed = subprocess.run(
        command,
        cwd=ROOT,
        env={**worker_env, "F03_CRASH": "1"},
        capture_output=True,
        text=True,
        timeout=45,
    )

    print(crashed.stdout, end="")
    if crashed.stderr:
        print(crashed.stderr, file=sys.stderr)

    if crashed.returncode != CRASH_CODE:
        raise AssertionError(
            f"Expected deliberate crash code {CRASH_CODE}, "
            f"got {crashed.returncode}"
        )

    if (
        "DB_COMMITTED" not in crashed.stdout
        or "INJECT_CRASH" not in crashed.stdout
    ):
        raise AssertionError(
            "Crash point was not confirmed"
        )

    # The Kafka offset should still point to the same message.
    inspector = kafka_consumer(group_id)

    try:
        tp = TopicPartition(
            TOPIC,
            target["partition"],
        )
        inspector.assign([tp])

        committed_after_crash = inspector.committed(tp)

    finally:
        inspector.close()

    assert committed_after_crash == target["offset"], (
        "Kafka offset unexpectedly advanced during crash"
    )

    print(
        "\n[2] Restarting consumer on same group...",
        flush=True,
    )

    restarted = subprocess.run(
        command,
        cwd=ROOT,
        env={**worker_env, "F03_CRASH": "0"},
        capture_output=True,
        text=True,
        timeout=45,
    )

    print(restarted.stdout, end="")
    if restarted.stderr:
        print(restarted.stderr, file=sys.stderr)

    if restarted.returncode != 0:
        raise AssertionError(
            "Restart worker failed"
        )

    if "KAFKA_OFFSET_COMMITTED" not in restarted.stdout:
        raise AssertionError(
            "Offset commit after restart not confirmed"
        )

    after_count = event_count(target["event_id"])
    after_rank = current_rank(target["order_id"])

    assert after_count == 1, (
        f"Expected one stored event, got {after_count}"
    )

    assert (
        before_rank is None
        or (
            after_rank is not None
            and after_rank >= before_rank
        )
    ), "Order status regressed"

    verifier = kafka_consumer(group_id)

    try:
        tp = TopicPartition(
            TOPIC,
            target["partition"],
        )
        verifier.assign([tp])
        final_offset = verifier.committed(tp)

    finally:
        verifier.close()

    assert final_offset == target["offset"] + 1

    print("\n=== F03 RESULTS ===")
    print(f"Crash return code: {crashed.returncode}")
    print(
        "Committed offset after crash: "
        f"{committed_after_crash}"
    )
    print(f"Committed offset after restart: {final_offset}")
    print(f"Event rows before: {before_count}")
    print(f"Event rows after: {after_count}")
    print("Status regression: 0")
    print("F03 verdict: TERTANGKAP")
    print("Crash recovery and idempotency: PASS")


if __name__ == "__main__":
    if "--worker" in sys.argv:
        worker()
    else:
        main()
