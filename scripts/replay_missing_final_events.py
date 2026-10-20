
"""Replay final order events yang statusnya belum cocok.

Cara menjalankan:
    python -B -m scripts.replay_missing_final_events --limit 99441

Script ini:
- Membandingkan status raw dengan stream.order_current.
- Menghasilkan ulang final event dari sumber raw.
- Mengirim event recovery melalui Kafka.
- Tidak mengubah PostgreSQL secara langsung.
- Aman dijalankan ulang karena event_id deterministik.
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone

import psycopg
from dotenv import load_dotenv
from kafka import KafkaProducer

from olist.events import build_order_events


TOPIC = "olist.order_events"
KAFKA_BOOTSTRAP = "localhost:29092"


def get_db_params():
    load_dotenv(dotenv_path=".env")

    return {
        "host": "localhost",
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": os.environ["POSTGRES_DB"],
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
    }


def find_missing_orders(conn, limit):
    """Cari order dengan status stream yang belum cocok."""

    query = """
        WITH selected_orders AS (
            SELECT *
            FROM raw.olist_orders_dataset
            ORDER BY order_id
            LIMIT %s
        )
        SELECT
            r.order_id,
            r.order_status,
            r.order_purchase_timestamp,
            r.order_approved_at,
            r.order_delivered_carrier_date,
            r.order_delivered_customer_date
        FROM selected_orders AS r
        LEFT JOIN stream.order_current AS c
            ON r.order_id = c.order_id
        WHERE c.order_id IS NULL
           OR c.status <> r.order_status
        ORDER BY r.order_id
    """

    with conn.cursor() as cur:
        cur.execute(query, (limit,))
        columns = [col.name for col in cur.description]
        rows = cur.fetchall()

    return [
        dict(zip(columns, row))
        for row in rows
    ]


def build_recovery_messages(orders):
    """Buat final events valid dengan event_id deterministik."""

    messages = []
    produced_at = datetime.now(timezone.utc).isoformat()

    for order in orders:
        events = build_order_events(order)
        final_status = order["order_status"]

        final_events = [
            event
            for event in events
            if event["status"] == final_status
        ]

        if len(final_events) != 1:
            raise RuntimeError(
                f"Order {order['order_id']}: "
                f"expected 1 final event, "
                f"got {len(final_events)}"
            )

        event = {
            **final_events[0],
            "produced_at": produced_at,
        }

        messages.append(
            {
                "key": order["order_id"].encode("utf-8"),
                "value": json.dumps(
                    event,
                    ensure_ascii=False,
                ).encode("utf-8"),
            }
        )

    return messages


def send_recovery_messages(messages):
    """Kirim event ke Kafka dengan timeout dan retry lebih besar."""

    if not messages:
        return 0

    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        client_id="olist-final-status-recovery",
        acks="all",
        retries=10,
        linger_ms=10,
        batch_size=65536,
        buffer_memory=67108864,
        request_timeout_ms=60000,
        max_block_ms=120000,
        max_in_flight_requests_per_connection=1,
    )

    acknowledged = 0
    start_time = time.perf_counter()

    try:
        # Batasi jumlah pesan yang menunggu acknowledgement.
        # Mengurangi tekanan ke broker dibanding mengirim
        # seluruh pesan sekaligus.
        batch_size = 100

        for start in range(0, len(messages), batch_size):
            batch = messages[start:start + batch_size]

            futures = []

            for message in batch:
                future = producer.send(
                    TOPIC,
                    key=message["key"],
                    value=message["value"],
                )
                futures.append(future)

            for future in futures:
                metadata = future.get(timeout=120)

                if metadata.topic != TOPIC:
                    raise RuntimeError(
                        f"Unexpected topic: {metadata.topic}"
                    )

                acknowledged += 1

            print(
                f"Acknowledged: {acknowledged:,}"
                f"/{len(messages):,}"
            )

        producer.flush(timeout=120)

    finally:
        try:
            producer.close(timeout=120)
        except Exception as exc:
            print(f"Warning during producer close: {exc}")

    duration = time.perf_counter() - start_time

    print(f"Duration: {duration:.2f} seconds")

    return acknowledged


def main():
    parser = argparse.ArgumentParser(
        description="Recover missing final order events via Kafka"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=99441,
        help="Number of raw orders to verify (default: 99441)",
    )

    args = parser.parse_args()

    if args.limit <= 0:
        parser.error("--limit must be positive")

    print("=== T3 RECOVER MISSING FINAL EVENTS ===")

    db_params = get_db_params()

    with psycopg.connect(**db_params) as conn:
        missing_orders = find_missing_orders(
            conn,
            args.limit,
        )

    print(
        f"Orders requiring recovery: "
        f"{len(missing_orders):,}"
    )

    if not missing_orders:
        print("No recovery required.")
        print("T3 final event recovery: PASS")
        return

    messages = build_recovery_messages(missing_orders)

    print(f"Recovery messages prepared: {len(messages):,}")
    print(f"Kafka topic: {TOPIC}")

    acknowledged = send_recovery_messages(messages)

    print()
    print("=== RECOVERY PRODUCER SUMMARY ===")
    print(f"Orders requiring recovery: {len(missing_orders):,}")
    print(f"Messages acknowledged: {acknowledged:,}")

    if acknowledged != len(messages):
        raise RuntimeError(
            f"Incomplete recovery: "
            f"{acknowledged}/{len(messages)}"
        )

    print()
    print("T3 final event recovery: PASS")
    print(
        "Next: run Kafka consumer, "
        "then verify stream status."
    )


if __name__ == "__main__":
    main()
