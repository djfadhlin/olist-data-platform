
"""T4 Data Warehouse integration tests.

Run:
    python -m pytest tests/test_dw_integrity.py -v

Tests query the actual PostgreSQL database.
"""

import os

import psycopg
import pytest
from dotenv import load_dotenv


load_dotenv(dotenv_path=".env")


@pytest.fixture(scope="module")
def conn():
    connection = psycopg.connect(
        host="localhost",
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )

    try:
        yield connection
    finally:
        connection.close()


def scalar(conn, sql):
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()[0]


@pytest.mark.parametrize(
    "table,expected",
    [
        ("dim_customer", 96096),
        ("fact_order", 99441),
        ("fact_order_item", 112650),
        ("fact_review", 98673),
    ],
)
def test_expected_grain_counts(conn, table, expected):
    actual = scalar(
        conn,
        f"SELECT COUNT(*) FROM dw.{table}",
    )
    assert actual == expected


def test_all_nine_tables_exist(conn):
    actual = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'dw'
          AND table_name IN (
              'dim_date',
              'dim_customer',
              'dim_product',
              'dim_seller',
              'dim_geo',
              'fact_order',
              'fact_order_item',
              'fact_payment',
              'fact_review'
          )
        """,
    )
    assert actual == 9


@pytest.mark.parametrize(
    "table,pk_columns",
    [
        ("dim_date", 1),
        ("dim_customer", 1),
        ("dim_product", 1),
        ("dim_seller", 1),
        ("dim_geo", 1),
        ("fact_order", 1),
        ("fact_order_item", 2),
        ("fact_payment", 2),
        ("fact_review", 1),
    ],
)
def test_primary_keys_exist(conn, table, pk_columns):
    actual = scalar(
        conn,
        f"""
        SELECT COUNT(*)
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'dw'
          AND t.relname = '{table}'
          AND c.contype = 'p'
          AND array_length(c.conkey, 1) = {pk_columns}
        """,
    )
    assert actual == 1


def test_foreign_keys_exist(conn):
    actual = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'dw'
          AND c.contype = 'f'
        """,
    )
    assert actual >= 10


def test_no_orphan_order_items(conn):
    actual = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM dw.fact_order_item i
        LEFT JOIN dw.fact_order o
            ON o.order_id = i.order_id
        WHERE o.order_id IS NULL
        """,
    )
    assert actual == 0


def test_no_orphan_products(conn):
    actual = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM dw.fact_order_item i
        LEFT JOIN dw.dim_product p
            ON p.product_id = i.product_id
        WHERE p.product_id IS NULL
        """,
    )
    assert actual == 0


def test_no_orphan_sellers(conn):
    actual = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM dw.fact_order_item i
        LEFT JOIN dw.dim_seller s
            ON s.seller_id = i.seller_id
        WHERE s.seller_id IS NULL
        """,
    )
    assert actual == 0


def test_customer_grain_is_unique(conn):
    actual = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM (
            SELECT customer_unique_id
            FROM dw.dim_customer
            GROUP BY customer_unique_id
            HAVING COUNT(*) > 1
        ) duplicates
        """,
    )
    assert actual == 0


def test_review_grain_is_unique(conn):
    actual = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM (
            SELECT order_id
            FROM dw.fact_review
            GROUP BY order_id
            HAVING COUNT(*) > 1
        ) duplicates
        """,
    )
    assert actual == 0


def test_review_count_matches_raw(conn):
    actual = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM (
            SELECT
                order_id,
                COUNT(*) AS expected_count
            FROM raw.olist_order_reviews_dataset
            GROUP BY order_id
        ) raw_counts
        JOIN dw.fact_review r
          ON r.order_id = raw_counts.order_id
        WHERE r.review_count <> raw_counts.expected_count
        """,
    )
    assert actual == 0


def test_missing_item_and_payment_flags(conn):
    assert scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM dw.fact_order
        WHERE has_no_items
        """,
    ) == 775

    assert scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM dw.fact_order
        WHERE has_no_payment
        """,
    ) == 1


def test_late_is_null_for_non_delivered(conn):
    actual = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM dw.fact_order
        WHERE order_status <> 'delivered'
          AND is_late IS NOT NULL
        """,
    )
    assert actual == 0


def test_geo_coordinates_valid(conn):
    actual = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM dw.dim_geo
        WHERE is_unknown = FALSE
          AND (
              latitude NOT BETWEEN -34 AND 5
              OR longitude NOT BETWEEN -74 AND -35
          )
        """,
    )
    assert actual == 0


def test_unknown_geo_row_exists(conn):
    actual = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM dw.dim_geo
        WHERE geo_key = 'UNKNOWN'
          AND is_unknown = TRUE
        """,
    )
    assert actual == 1


def test_date_complete_month_flag(conn):
    assert scalar(
        conn,
        """
        SELECT is_complete_month
        FROM dw.dim_date
        WHERE date_key = DATE '2018-08-15'
        """,
    ) is True

    assert scalar(
        conn,
        """
        SELECT is_complete_month
        FROM dw.dim_date
        WHERE date_key = DATE '2018-09-15'
        """,
    ) is False
