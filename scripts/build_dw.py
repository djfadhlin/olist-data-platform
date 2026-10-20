
"""Build and verify the Olist dimensional warehouse.

Run:
    python -B -m scripts.build_dw

Rebuilds dw schema in a single PostgreSQL transaction.
Does not modify raw or stream schemas.
"""

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv


SQL_FILE = Path("sql/dw_build.sql")
REPORT_FILE = Path("outputs/dw_report.md")

TABLES = [
    "dim_date",
    "dim_customer",
    "dim_product",
    "dim_seller",
    "dim_geo",
    "fact_order",
    "fact_order_item",
    "fact_payment",
    "fact_review",
]

EXPECTED_COUNTS = {
    "dim_customer": 96096,
    "fact_order": 99441,
    "fact_order_item": 112650,
}

# Each query returns a single number.
# Every integrity violation count must equal zero.
CHECKS = {
    "Missing customer reference": """
        SELECT COUNT(*)
        FROM dw.fact_order f
        LEFT JOIN dw.dim_customer d
          ON d.customer_unique_id = f.customer_unique_id
        WHERE d.customer_unique_id IS NULL
    """,

    "Missing customer geo reference": """
        SELECT COUNT(*)
        FROM dw.dim_customer c
        LEFT JOIN dw.dim_geo g
          ON g.geo_key = c.geo_key
        WHERE g.geo_key IS NULL
    """,

    "Missing seller geo reference": """
        SELECT COUNT(*)
        FROM dw.dim_seller s
        LEFT JOIN dw.dim_geo g
          ON g.geo_key = s.geo_key
        WHERE g.geo_key IS NULL
    """,

    "Missing order item reference": """
        SELECT COUNT(*)
        FROM dw.fact_order_item i
        LEFT JOIN dw.fact_order o
          ON o.order_id = i.order_id
        WHERE o.order_id IS NULL
    """,

    "Missing item product reference": """
        SELECT COUNT(*)
        FROM dw.fact_order_item i
        LEFT JOIN dw.dim_product p
          ON p.product_id = i.product_id
        WHERE p.product_id IS NULL
    """,

    "Missing item seller reference": """
        SELECT COUNT(*)
        FROM dw.fact_order_item i
        LEFT JOIN dw.dim_seller s
          ON s.seller_id = i.seller_id
        WHERE s.seller_id IS NULL
    """,

    "Missing payment order reference": """
        SELECT COUNT(*)
        FROM dw.fact_payment p
        LEFT JOIN dw.fact_order o
          ON o.order_id = p.order_id
        WHERE o.order_id IS NULL
    """,

    "Missing review order reference": """
        SELECT COUNT(*)
        FROM dw.fact_review r
        LEFT JOIN dw.fact_order o
          ON o.order_id = r.order_id
        WHERE o.order_id IS NULL
    """,

    "Duplicate customer grain": """
        SELECT COUNT(*)
        FROM (
            SELECT customer_unique_id
            FROM dw.dim_customer
            GROUP BY customer_unique_id
            HAVING COUNT(*) > 1
        ) x
    """,

    "Duplicate order grain": """
        SELECT COUNT(*)
        FROM (
            SELECT order_id
            FROM dw.fact_order
            GROUP BY order_id
            HAVING COUNT(*) > 1
        ) x
    """,

    "Duplicate item grain": """
        SELECT COUNT(*)
        FROM (
            SELECT order_id, order_item_id
            FROM dw.fact_order_item
            GROUP BY order_id, order_item_id
            HAVING COUNT(*) > 1
        ) x
    """,

    "Duplicate payment grain": """
        SELECT COUNT(*)
        FROM (
            SELECT order_id, payment_sequential
            FROM dw.fact_payment
            GROUP BY order_id, payment_sequential
            HAVING COUNT(*) > 1
        ) x
    """,

    "Duplicate review grain": """
        SELECT COUNT(*)
        FROM (
            SELECT order_id
            FROM dw.fact_review
            GROUP BY order_id
            HAVING COUNT(*) > 1
        ) x
    """,

    "Invalid late flag for undelivered orders": """
        SELECT COUNT(*)
        FROM dw.fact_order
        WHERE (
            order_status <> 'delivered'
            OR order_delivered_customer_date IS NULL
            OR order_estimated_delivery_date IS NULL
        )
        AND is_late IS NOT NULL
    """,

    "Incorrect late flag for delivered orders": """
        SELECT COUNT(*)
        FROM dw.fact_order
        WHERE order_status = 'delivered'
          AND order_delivered_customer_date IS NOT NULL
          AND order_estimated_delivery_date IS NOT NULL
          AND is_late IS DISTINCT FROM (
              order_delivered_customer_date::date
              > order_estimated_delivery_date::date
          )
    """,

    "Invalid Brazil coordinates": """
        SELECT COUNT(*)
        FROM dw.dim_geo
        WHERE is_unknown = FALSE
          AND (
              latitude NOT BETWEEN -34 AND 5
              OR longitude NOT BETWEEN -74 AND -35
          )
    """,

    "Missing English product category": """
        SELECT COUNT(*)
        FROM dw.dim_product
        WHERE category_english IS NULL
           OR BTRIM(category_english) = ''
    """,

    "Invalid review count": """
        SELECT COUNT(*)
        FROM dw.fact_review
        WHERE review_count < 1
    """,

    "Incorrect item-missing flags": """
        SELECT COUNT(*)
        FROM dw.fact_order
        WHERE has_no_items IS DISTINCT FROM (item_count = 0)
    """,

    "Incorrect payment-missing flags": """
        SELECT COUNT(*)
        FROM dw.fact_order
        WHERE has_no_payment IS DISTINCT FROM (payment_count = 0)
    """,
}


def get_connection():
    load_dotenv(dotenv_path=".env")

    return psycopg.connect(
        host="localhost",
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def scalar(cur, query):
    cur.execute(query)
    return cur.fetchone()[0]


def main():
    print("=== T4 BUILD DATA WAREHOUSE ===")

    if not SQL_FILE.exists():
        raise FileNotFoundError(
            f"SQL file not found: {SQL_FILE}"
        )

    sql = SQL_FILE.read_text(encoding="utf-8-sig")

    started = time.perf_counter()

    counts = {}
    checks = {}
    extra = {}

    # All DDL and checks run in one transaction.
    # Failure triggers rollback automatically.
    with get_connection() as conn:
        with conn.cursor() as cur:
            print("Executing:", SQL_FILE, flush=True)
            cur.execute(sql)

            print("Checking row counts...", flush=True)

            for table in TABLES:
                count = scalar(
                    cur,
                    f"SELECT COUNT(*) FROM dw.{table}"
                )

                counts[table] = count
                print(f"  {table}: {count:,}", flush=True)

            for table, expected in EXPECTED_COUNTS.items():
                actual = counts[table]

                if actual != expected:
                    raise AssertionError(
                        f"{table}: expected {expected:,}, "
                        f"got {actual:,}"
                    )

            print("Checking integrity...", flush=True)

            for name, query in CHECKS.items():
                violations = scalar(cur, query)
                checks[name] = violations

                print(
                    f"  {name}: {violations:,}",
                    flush=True,
                )

                if violations != 0:
                    raise AssertionError(
                        f"Integrity check failed: "
                        f"{name} = {violations}"
                    )

            extra["orders_without_items"] = scalar(
                cur,
                """
                SELECT COUNT(*) FROM dw.fact_order
                WHERE has_no_items
                """,
            )

            extra["orders_without_payments"] = scalar(
                cur,
                """
                SELECT COUNT(*) FROM dw.fact_order
                WHERE has_no_payment
                """,
            )

            extra["orders_with_reviews"] = counts[
                "fact_review"
            ]

            extra["unknown_customer_geo"] = scalar(
                cur,
                """
                SELECT COUNT(*) FROM dw.dim_customer
                WHERE geo_key = 'UNKNOWN'
                """,
            )

            extra["unknown_seller_geo"] = scalar(
                cur,
                """
                SELECT COUNT(*) FROM dw.dim_seller
                WHERE geo_key = 'UNKNOWN'
                """,
            )

            extra["multi_review_orders"] = scalar(
                cur,
                """
                SELECT COUNT(*) FROM dw.fact_review
                WHERE review_count > 1
                """,
            )

            extra["delivered_orders"] = scalar(
                cur,
                """
                SELECT COUNT(*) FROM dw.fact_order
                WHERE order_status = 'delivered'
                """,
            )

            # Confirm expected source-level reference counts.
            assert extra["orders_without_items"] == 775, (
                "Expected 775 orders without items"
            )

            assert extra["orders_without_payments"] == 1, (
                "Expected 1 order without payments"
            )

            assert extra["orders_with_reviews"] == 98673, (
                "Expected 98673 reviewed orders"
            )

            assert extra["delivered_orders"] == 96478, (
                "Expected 96478 delivered orders"
            )

        # Commit happens here if all tests passed.

    duration = time.perf_counter() - started

    REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    lines = [
        "# T4 - Olist Data Warehouse Report",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Build duration: {duration:.2f} seconds",
        "",
        "## Row counts",
        "",
        "| Table | Rows |",
        "|---|---:|",
    ]

    for table in TABLES:
        lines.append(
            f"| `dw.{table}` | {counts[table]:,} |"
        )

    lines.extend([
        "",
        "## Grain and integrity tests",
        "",
        "| Test | Violations |",
        "|---|---:|",
    ])

    for name, violations in checks.items():
        lines.append(
            f"| {name} | {violations:,} |"
        )

    lines.extend([
        "",
        "## Reconciliation metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ])

    for name, value in extra.items():
        lines.append(
            f"| {name} | {value:,} |"
        )

    lines.extend([
        "",
        "## Modeling decisions",
        "",
        "- `dim_customer`: one row per `customer_unique_id`, "
        "using latest order attributes (SCD Type 1).",
        "- `dim_geo`: one row per valid Brazilian ZIP prefix; "
        "`UNKNOWN` for unmatched locations.",
        "- `dim_product`: corrected source column spelling "
        "and translated category with fallback.",
        "- `fact_order`: includes orders without items "
        "or payments, with explicit flags.",
        "- `fact_review`: one review per order, selected "
        "by latest answer timestamp, then creation timestamp, "
        "then review ID; original review count retained.",
        "- `is_late`: NULL for non-delivered orders or "
        "missing delivery/estimate dates; date-based comparison.",
        "- `dim_date.is_complete_month`: January 2017 "
        "through August 2018 inclusive.",
        "- Full rebuild is idempotent because the warehouse "
        "is recreated from unchanged raw tables within "
        "one database transaction.",
        "- SCD Type 1 does not retain historical changes "
        "in customer attributes.",
        "",
        "## Result",
        "",
        "**T4 database validation: PASS**",
        "",
    ])

    REPORT_FILE.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print()
    print("=== T4 SUMMARY ===")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Report: {REPORT_FILE}")
    print("All integrity checks: 0 violations")
    print("T4 Data Warehouse: PASS")


if __name__ == "__main__":
    main()
