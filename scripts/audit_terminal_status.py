
"""Audit konsistensi status akhir pada event replay Olist."""

import os
from collections import Counter

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

from olist.events import build_order_events


def main():
    load_dotenv()

    params = {
        "host": "localhost",
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": os.environ["POSTGRES_DB"],
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
    }

    total = 0
    mismatches = []
    anomalies = Counter()
    terminal_cases = Counter()

    print("=== T3 TERMINAL STATUS AUDIT ===")

    with psycopg.connect(**params) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT
                    order_id,
                    order_status,
                    order_purchase_timestamp,
                    order_approved_at,
                    order_delivered_carrier_date,
                    order_delivered_customer_date
                FROM raw.olist_orders_dataset
            """)

            for order in cur:
                total += 1
                expected = order["order_status"]
                events = build_order_events(order)

                # Simulasi aturan current status:
                # status_rank lebih tinggi selalu menang.
                current = None

                for event in events:
                    if (
                        current is None
                        or event["status_rank"]
                        > current["status_rank"]
                    ):
                        current = event

                actual = current["status"]

                if actual != expected:
                    mismatches.append({
                        "order_id": order["order_id"],
                        "expected": expected,
                        "actual": actual,
                    })
                    anomalies[(expected, actual)] += 1

                if expected in ("canceled", "unavailable"):
                    terminal_cases[expected] += 1

                    if any(
                        event["status"] == "delivered"
                        for event in events
                    ):
                        terminal_cases[
                            f"{expected}_with_delivered_event"
                        ] += 1

    print(f"Orders audited: {total:,}")
    print(f"Current status mismatches: {len(mismatches):,}")

    print("\nTerminal status cases:")
    for label, count in sorted(terminal_cases.items()):
        print(f"  {label}: {count:,}")

    if anomalies:
        print("\nMismatch categories:")
        for (expected, actual), count in sorted(
            anomalies.items()
        ):
            print(f"  {expected} -> {actual}: {count:,}")

        print("\nFirst 10 mismatches:")
        for item in mismatches[:10]:
            print(
                f"  {item['order_id']}: "
                f"expected={item['expected']}, "
                f"actual={item['actual']}"
            )

    assert total == 99_441

    if mismatches:
        raise AssertionError(
            f"{len(mismatches):,} current statuses "
            "do not match raw.orders"
        )

    print("\nT3 terminal status reconciliation: PASS")


if __name__ == "__main__":
    main()
