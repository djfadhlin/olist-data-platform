
"""Audit event model terhadap seluruh order asli PostgreSQL."""

import os
from collections import Counter

import psycopg
from dotenv import load_dotenv

from olist.events import STATUS_RANK, build_order_events


def main():
    load_dotenv()

    print("=== T3 REAL ORDER EVENT AUDIT ===")

    connection_params = {
        "host": "localhost",
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": os.environ["POSTGRES_DB"],
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
    }

    status_counts = Counter()
    event_counts = Counter()
    failures = []
    order_count = 0
    total_events = 0

    with psycopg.connect(**connection_params) as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute("""
                SELECT
                    order_id,
                    order_status,
                    order_purchase_timestamp,
                    order_approved_at,
                    order_delivered_carrier_date,
                    order_delivered_customer_date
                FROM raw.olist_orders_dataset
                ORDER BY order_id
            """)

            for order in cur:
                order_count += 1
                status = order["order_status"]
                status_counts[status] += 1

                if status not in STATUS_RANK:
                    failures.append(
                        (order["order_id"], f"Unknown status: {status}")
                    )
                    continue

                try:
                    events = build_order_events(order)

                    if not events:
                        raise ValueError("No events generated")

                    if status not in {
                        event["status"] for event in events
                    }:
                        raise ValueError(
                            f"Final status {status} missing"
                        )

                    event_ids = [
                        event["event_id"] for event in events
                    ]

                    if len(event_ids) != len(set(event_ids)):
                        raise ValueError("Duplicate event IDs within order")

                    total_events += len(events)

                    for event in events:
                        event_counts[event["status"]] += 1

                except Exception as exc:
                    failures.append(
                        (order["order_id"], str(exc))
                    )

    print(f"\nOrders audited: {order_count:,}")

    print("\nSource order statuses:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count:,}")

    print("\nGenerated event statuses:")
    for status, count in sorted(event_counts.items()):
        print(f"  {status}: {count:,}")

    print(f"\nGenerated events: {total_events:,}")
    print(f"Audit failures: {len(failures):,}")

    if failures:
        print("\nFirst 10 failures:")
        for order_id, reason in failures[:10]:
            print(f"  {order_id}: {reason}")

    assert order_count == 99_441, (
        f"Expected 99,441 orders, found {order_count:,}"
    )
    assert not failures, (
        f"{len(failures):,} orders failed event generation"
    )

    print("\nT3 real order event audit: PASS")


if __name__ == "__main__":
    main()
