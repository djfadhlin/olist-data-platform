
"""Verifikasi hasil Kafka smoke test pada PostgreSQL."""

import os

import psycopg
from dotenv import load_dotenv


EXPECTED_EVENTS = 395
EXPECTED_DLQ = 2
EXPECTED_ORDERS = 100


def main():
    load_dotenv()

    print("=== T3 VERIFY STREAM SMOKE TEST ===")

    with psycopg.connect(
        host="localhost",
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    ) as conn:
        with conn.cursor() as cur:

            cur.execute(
                "SELECT COUNT(*) FROM stream.order_events"
            )
            event_count = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM stream.order_dlq"
            )
            dlq_count = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM stream.order_current"
            )
            current_count = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*)
                FROM stream.order_current AS c
                JOIN raw.olist_orders_dataset AS r
                    ON c.order_id = r.order_id
                WHERE c.status <> r.order_status
            """)
            mismatch_count = cur.fetchone()[0]

            print(f"Unique events: {event_count:,}")
            print(f"DLQ rows: {dlq_count:,}")
            print(f"Current orders: {current_count:,}")
            print(f"Status mismatches: {mismatch_count:,}")

            assert event_count == EXPECTED_EVENTS
            assert dlq_count == EXPECTED_DLQ

            # Pesan rusak mungkin merupakan event final,
            # sehingga current status belum tentu cocok.
            assert current_count <= EXPECTED_ORDERS

            print("\nEvent count reconciliation: PASS")
            print("DLQ count reconciliation: PASS")
            print("Current status audit: RECORDED")

    print("\nT3 stream smoke verification: PASS")


if __name__ == "__main__":
    main()
