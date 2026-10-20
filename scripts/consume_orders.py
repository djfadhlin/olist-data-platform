
"""Kafka consumer Olist: deduplication, DLQ, manual offset commit.

Contoh:
    python -B -m scripts.consume_orders --idle-seconds 8
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import psycopg
from dotenv import load_dotenv
from kafka import KafkaConsumer, KafkaProducer

from olist.stream_consumer import process_event, validate_event


TOPIC = "olist.order_events"
DLQ_TOPIC = "olist.order_events.dlq"
GROUP_ID = "olist-stream-consumer-v1"
REPORT_PATH = Path("outputs/consumer_metrics.json")


def percentile(values, fraction):
    """Persentil dengan interpolasi linear."""
    if not values:
        return None

    values = sorted(values)
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values))
    weight = position - lower

    return values[lower] * (1 - weight) + values[upper] * weight


def database_params():
    return {
        "host": "localhost",
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": os.environ["POSTGRES_DB"],
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
    }


def handle_batch(conn, dlq_producer, records):
    """Proses satu batch dalam satu transaksi PostgreSQL.

    Pesan DLQ dikirim dengan acknowledgement sebelum commit DB.
    Offset Kafka hanya boleh di-commit oleh pemanggil setelah
    transaksi berhasil.
    """
    counts = {
        "messages": 0,
        "new": 0,
        "duplicate": 0,
        "out_of_order": 0,
        "dlq": 0,
    }
    freshness = []

    try:
        for record in records:
            counts["messages"] += 1

            try:
                event = validate_event(record.value)

                if event["order_id"].encode("utf-8") != record.key:
                    raise ValueError(
                        "Kafka key does not match order_id"
                    )

            except ValueError as exc:
                reason = str(exc)

                # Publikasi DLQ bisa terulang apabila crash terjadi
                # sebelum commit offset. Tabel DLQ tetap idempoten.
                dlq_message = {
                    "source_topic": record.topic,
                    "partition": record.partition,
                    "offset": record.offset,
                    "error_reason": reason,
                    "raw_payload_hex": record.value.hex(),
                }

                dlq_producer.send(
                    DLQ_TOPIC,
                    key=record.key,
                    value=json.dumps(
                        dlq_message
                    ).encode("utf-8"),
                ).get(timeout=30)

                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO stream.order_dlq (
                            topic,
                            partition_id,
                            offset_id,
                            raw_payload,
                            error_reason
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (
                            topic,
                            partition_id,
                            offset_id
                        ) DO NOTHING
                        """,
                        (
                            record.topic,
                            record.partition,
                            record.offset,
                            record.value,
                            reason,
                        ),
                    )

                counts["dlq"] += 1
                continue

            result = process_event(conn, event)
            counts[result] += 1

            if result == "out_of_order":
                counts["out_of_order"] += 1
                counts["new"] -= 1

            consumed_at = datetime.now(timezone.utc)
            lag_ms = (
                consumed_at - event["produced_at"]
            ).total_seconds() * 1000
            freshness.append(max(0, lag_ms))

        conn.commit()
        return counts, freshness

    except Exception:
        conn.rollback()
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--idle-seconds",
        type=float,
        default=8,
        help="Stop after this many seconds without messages",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
    )
    args = parser.parse_args()

    if args.idle_seconds <= 0 or args.batch_size <= 0:
        parser.error("Arguments must be positive")

    load_dotenv()

    print("=== T3 KAFKA ORDER CONSUMER ===")
    print(f"Topic: {TOPIC}")
    print(f"Group: {GROUP_ID}")
    print("Offset commit: MANUAL")

    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers="localhost:29092",
        group_id=GROUP_ID,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        max_poll_records=args.batch_size,
        max_poll_interval_ms=600000,
        consumer_timeout_ms=1000,
    )

    dlq_producer = KafkaProducer(
        bootstrap_servers="localhost:29092",
        acks="all",
        retries=5,
    )

    totals = {
        "messages": 0,
        "new": 0,
        "duplicate": 0,
        "out_of_order": 0,
        "dlq": 0,
    }
    all_freshness = []
    started = time.perf_counter()
    last_activity = started

    try:
        with psycopg.connect(**database_params()) as conn:
            while True:
                batches = consumer.poll(timeout_ms=1000)

                if not batches:
                    if (
                        time.perf_counter() - last_activity
                        >= args.idle_seconds
                    ):
                        break
                    continue

                records = [
                    record
                    for partition_records in batches.values()
                    for record in partition_records
                ]

                if not records:
                    continue

                counts, freshness = handle_batch(
                    conn,
                    dlq_producer,
                    records,
                )

                # DB sudah COMMITTED. Kafka offset menyusul.
                # Jika commit offset gagal, proses berhenti.
                # Setelah restart, pesan aman diproses ulang.
                consumer.commit()

                for name in totals:
                    totals[name] += counts[name]

                all_freshness.extend(freshness)
                last_activity = time.perf_counter()

                print(
                    f"Processed: {totals['messages']:,} | "
                    f"new={totals['new']:,} | "
                    f"duplicate={totals['duplicate']:,} | "
                    f"out_of_order={totals['out_of_order']:,} | "
                    f"dlq={totals['dlq']:,}"
                )

    finally:
        consumer.close()
        dlq_producer.close(timeout=30)

    duration = time.perf_counter() - started

    report = {
        "topic": TOPIC,
        "consumer_group": GROUP_ID,
        **totals,
        "freshness_p50_ms": (
            round(median(all_freshness), 2)
            if all_freshness else None
        ),
        "freshness_p95_ms": (
            round(percentile(all_freshness, 0.95), 2)
            if all_freshness else None
        ),
        "duration_seconds": round(duration, 3),
        "completed_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    REPORT_PATH.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("\n=== CONSUMER SUMMARY ===")
    for key, value in report.items():
        print(f"{key}: {value}")

    print("\nT3 Kafka consumer: PASS")


if __name__ == "__main__":
    main()
