
"""Verifikasi status terkini Kafka terhadap PostgreSQL raw."""

import argparse
import os

import psycopg
from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Jumlah order pertama berdasarkan order_id",
    )
    args = parser.parse_args()

    if args.limit is not None and args.limit <= 0:
        parser.error("--limit harus positif")

    load_dotenv()

    print("=== T3 STREAM STATUS RECONCILIATION ===")

    params = {
        "host": "localhost",
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": os.environ["POSTGRES_DB"],
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
    }

    query = """
        WITH expected AS (
            SELECT order_id, order_status
            FROM raw.olist_orders_dataset
            ORDER BY order_id
            LIMIT %s
        )
        SELECT
            COUNT(*) AS expected_orders,
            COUNT(c.order_id) AS loaded_orders,
            COUNT(*) FILTER (
                WHERE c.order_id IS NULL
            ) AS missing_orders,
            COUNT(*) FILTER (
                WHERE c.order_id IS NOT NULL
                  AND c.status <> e.order_status
            ) AS status_mismatches
        FROM expected e
        LEFT JOIN stream.order_current c
            ON c.order_id = e.order_id
    """

    with psycopg.connect(**params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    args.limit
                    if args.limit is not None
                    else 99_441,
                ),
            )

            expected, loaded, missing, mismatches = (
                cur.fetchone()
            )

            print(f"Expected orders: {expected:,}")
            print(f"Loaded orders: {loaded:,}")
            print(f"Missing orders: {missing:,}")
            print(f"Status mismatches: {mismatches:,}")

            if missing or mismatches:
                cur.execute(
                    """
                    WITH expected AS (
                        SELECT order_id, order_status
                        FROM raw.olist_orders_dataset
                        ORDER BY order_id
                        LIMIT %s
                    )
                    SELECT
                        e.order_id,
                        e.order_status,
                        c.status
                    FROM expected e
                    LEFT JOIN stream.order_current c
                        ON c.order_id = e.order_id
                    WHERE c.order_id IS NULL
                       OR c.status <> e.order_status
                    ORDER BY e.order_id
                    LIMIT 10
                    """,
                    (
                        args.limit
                        if args.limit is not None
                        else 99_441,
                    ),
                )

                print("\nFirst mismatches:")
                for row in cur.fetchall():
                    print(row)

    assert missing == 0, (
        f"{missing:,} order belum memiliki current status"
    )

    assert mismatches == 0, (
        f"{mismatches:,} status tidak cocok"
    )

    print("\nT3 stream status reconciliation: PASS")


if __name__ == "__main__":
    main()
