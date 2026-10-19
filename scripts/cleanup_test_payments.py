
"""Hapus hanya dua record sintetis dari pengujian sebelumnya."""

import os

import psycopg
from dotenv import load_dotenv


def main():
    print("=== CLEANUP SYNTHETIC PAYMENT RECORDS ===")

    load_dotenv()

    with psycopg.connect(
        host="localhost",
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM raw.olist_order_payments_dataset
                WHERE
                    (order_id = %s AND payment_value = %s)
                    OR
                    (order_id = %s AND payment_value = %s)
                RETURNING order_id
                """,
                (
                    "order_test_001", "100.00",
                    "order_test_002", "50.00",
                ),
            )

            deleted = [row[0] for row in cur.fetchall()]

            if set(deleted) != {
                "order_test_001",
                "order_test_002",
            } or len(deleted) != 2:
                raise RuntimeError(
                    f"Unexpected cleanup result: {deleted}"
                )

            print("Deleted:", deleted)

    print("Synthetic payment cleanup: PASS")


if __name__ == "__main__":
    main()
