
"""Test consumer event tanpa Kafka, menggunakan PostgreSQL."""

import os
import json

import psycopg
from dotenv import load_dotenv

from olist.events import make_event_id, STATUS_RANK
from olist.stream_consumer import validate_event, process_event


def make_test_event(order_id, status):
    return {
        "event_id": make_event_id(order_id, status),
        "order_id": order_id,
        "status": status,
        "status_rank": STATUS_RANK[status],
        "event_ts": "2018-01-01T10:00:00+00:00",
        "produced_at": "2026-10-20T08:00:00+00:00",
    }


def main():
    load_dotenv()

    print("=== T3 STREAM CONSUMER TEST ===")

    with psycopg.connect(
        host="localhost",
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    ) as conn:
        try:
            delivered = validate_event(
                json.dumps(
                    make_test_event(
                        "__t3_test_order__",
                        "delivered",
                    )
                ).encode("utf-8")
            )

            assert process_event(conn, delivered) == "new"
            print("New event: PASS")

            assert process_event(conn, delivered) == "duplicate"
            print("Duplicate ignored: PASS")

            shipped = validate_event(
                json.dumps(
                    make_test_event(
                        "__t3_test_order__",
                        "shipped",
                    )
                ).encode("utf-8")
            )

            assert process_event(conn, shipped) == "out_of_order"
            print("Out-of-order event: PASS")

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status
                    FROM stream.order_current
                    WHERE order_id = %s
                    """,
                    ("__t3_test_order__",),
                )
                status = cur.fetchone()[0]

            assert status == "delivered"
            print("Current status does not regress: PASS")

            corrupt = b'{"order_id": "broken"}'

            try:
                validate_event(corrupt)
            except ValueError:
                print("Corrupt payload rejected: PASS")
            else:
                raise AssertionError(
                    "Corrupt event was not rejected"
                )

        finally:
            conn.rollback()

    print("Test transaction rollback: PASS")
    print("\nT3 stream consumer logic: PASS")


if __name__ == "__main__":
    main()
