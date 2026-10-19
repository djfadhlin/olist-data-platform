
"""Verifikasi jumlah baris aktual di PostgreSQL raw."""

import os

import psycopg
from psycopg import sql
from dotenv import load_dotenv

from olist.schema import TABLE_SCHEMAS


EXPECTED = {
    "olist_customers_dataset": 99441,
    "olist_geolocation_dataset": 1000163,
    "olist_order_items_dataset": 112650,
    "olist_order_payments_dataset": 103886,
    "olist_order_reviews_dataset": 99224,
    "olist_orders_dataset": 99441,
    "olist_products_dataset": 32951,
    "olist_sellers_dataset": 3095,
    "product_category_name_translation": 71,
}


def main():
    print("=== VERIFY POSTGRES RAW COUNTS ===")

    load_dotenv()

    total_rows = 0

    with psycopg.connect(
        host="localhost",
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    ) as conn:
        with conn.cursor() as cur:

            for table_name in TABLE_SCHEMAS:
                query = sql.SQL(
                    "SELECT COUNT(*) FROM {}"
                ).format(
                    sql.Identifier("raw", table_name)
                )

                cur.execute(query)
                actual = cur.fetchone()[0]
                expected = EXPECTED[table_name]

                assert actual == expected, (
                    f"{table_name}: expected {expected}, "
                    f"found {actual}"
                )

                total_rows += actual

                print(
                    f"PASS: raw.{table_name} "
                    f"({actual:,} rows)"
                )

    assert total_rows == 1_550_922

    print("\nTotal PostgreSQL raw rows:", f"{total_rows:,}")
    print("Raw row count verification: PASS")


if __name__ == "__main__":
    main()
