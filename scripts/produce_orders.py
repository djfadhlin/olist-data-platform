
"""Kafka producer Olist dengan asynchronous batching.

Contoh:
    python -B -m scripts.produce_orders --limit 100
    python -B -m scripts.produce_orders --limit 1000

Tanpa --limit, replay seluruh 99.441 order.
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from kafka import KafkaProducer

from olist.stream_producer import make_replay_messages


TOPIC = "olist.order_events"
BOOTSTRAP = "localhost:29092"
REPORT_PATH = Path("outputs/producer_manifest.json")
MAX_PENDING = 1000


def load_orders(limit: int | None):
    params = {
        "host": "localhost",
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": os.environ["POSTGRES_DB"],
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
    }

    query = """
        SELECT
            order_id,
            order_status,
            order_purchase_timestamp,
            order_approved_at,
            order_delivered_carrier_date,
            order_delivered_customer_date
        FROM raw.olist_orders_dataset
        ORDER BY order_id
    """

    if limit is not None:
        query += " LIMIT %s"

    with psycopg.connect(**params) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if limit is None:
                cur.execute(query)
            else:
                cur.execute(query, (limit,))

            return cur.fetchall()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--delay-ms", type=float, default=0)
    args = parser.parse_args()

    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")

    if args.delay_ms < 0:
        parser.error("--delay-ms must be >= 0")

    load_dotenv()

    print("=== T3 ASYNC KAFKA PRODUCER ===")

    start = perf_counter()
    orders = load_orders(args.limit)

    messages, manifest = make_replay_messages(
        orders,
        seed=args.seed,
    )

    print(f"Orders: {len(orders):,}")
    print(f"Base events: {manifest['base_events']:,}")
    print(f"Messages to send: {len(messages):,}")

    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        client_id="olist-async-producer",
        acks="all",
        retries=5,
        linger_ms=10,
        batch_size=65536,
        buffer_memory=67108864,
        max_in_flight_requests_per_connection=1,
        request_timeout_ms=30000,
    )

    pending = []
    acknowledged = 0

    def check_pending():
        nonlocal acknowledged

        for future in pending:
            metadata = future.get(timeout=60)

            if metadata.topic != TOPIC:
                raise RuntimeError("Unexpected Kafka topic")

            acknowledged += 1

        pending.clear()

    try:
        for message in messages:
            pending.append(
                producer.send(
                    TOPIC,
                    key=message["key"],
                    value=message["value"],
                )
            )

            if len(pending) >= MAX_PENDING:
                check_pending()

            if args.delay_ms:
                time.sleep(args.delay_ms / 1000)

        check_pending()
        producer.flush(timeout=60)

    finally:
        producer.close(timeout=30)

    duration = perf_counter() - start

    if acknowledged != len(messages):
        raise RuntimeError(
            f"Sent {len(messages)}, acknowledged {acknowledged}"
        )

    manifest.update({
        "topic": TOPIC,
        "bootstrap_servers": BOOTSTRAP,
        "sent_messages": acknowledged,
        "failed_messages": 0,
        "duration_seconds": round(duration, 3),
        "completed_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "limit": args.limit,
    })

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    REPORT_PATH.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\n=== PRODUCER SUMMARY ===")
    print(f"Messages acknowledged: {acknowledged:,}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Manifest: {REPORT_PATH}")
    print("\nT3 async Kafka producer: PASS")


if __name__ == "__main__":
    main()
