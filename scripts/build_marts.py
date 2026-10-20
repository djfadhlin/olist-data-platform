
"""Build Olist Gold Marts, export CSV, and generate T5 report.

Run from the project root:

    python -B -m scripts.build_marts

Requirements:
    - PostgreSQL is running.
    - The T4 dw schema has been built.
    - The T3 stream schema exists.
    - sql/mart_build.sql exists.
    - olist/mart_queries.py provides QUERIES.
"""

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from olist.mart_queries import QUERIES


# ============================================================
# PATHS AND CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parent.parent

SQL_FILE = ROOT / "sql" / "mart_build.sql"
EXPORT_DIR = ROOT / "outputs" / "gold"
REPORT_FILE = ROOT / "outputs" / "marts_report.md"

MARTS = [
    "monthly_sales",
    "delivery_performance",
    "seller_scorecard",
    "customer_rfm",
    "stream_freshness",
    "payment_reconciliation",
]

EXPECTED_COUNTS = {
    "seller_scorecard": 3095,
    "customer_rfm": 96096,
    "payment_reconciliation": 99441,
}


# ============================================================
# POSTGRESQL CONNECTION
# ============================================================

def get_connection():
    """Create PostgreSQL connection using project .env."""

    load_dotenv(dotenv_path=ROOT / ".env")

    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


# ============================================================
# DATABASE QUERY HELPERS
# ============================================================

def scalar(cur, sql):
    """Execute SQL and return the first value."""

    cur.execute(sql)
    return cur.fetchone()[0]


def run_query(conn, sql):
    """Return column names and all result rows."""

    with conn.cursor() as cur:
        cur.execute(sql)

        columns = [
            description.name
            for description in cur.description
        ]

        rows = cur.fetchall()

    return columns, rows


def markdown_table(columns, rows):
    """Convert SQL results into a Markdown table."""

    if not rows:
        return "_Tidak ada data._"

    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]

    for row in rows:
        formatted = []

        for value in row:
            if value is None:
                formatted.append("NULL")
            else:
                formatted.append(str(value))

        lines.append(
            "| " + " | ".join(formatted) + " |"
        )

    return "\n".join(lines)


# ============================================================
# GOLD CSV EXPORT
# ============================================================


def export_csv(conn, table):
    """Export a mart to CSV using PostgreSQL COPY.

    Handles bytes, memoryview, and str returned by psycopg 3.
    """

    EXPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = EXPORT_DIR / f"{table}.csv"

    query = (
        f"COPY mart.{table} TO STDOUT "
        "WITH (FORMAT CSV, HEADER TRUE)"
    )

    with conn.cursor() as cur:
        with output_file.open("wb") as handle:
            with cur.copy(query) as copy:
                for chunk in copy:
                    if isinstance(chunk, memoryview):
                        handle.write(chunk.tobytes())

                    elif isinstance(chunk, bytes):
                        handle.write(chunk)

                    elif isinstance(chunk, str):
                        handle.write(chunk.encode("utf-8"))

                    else:
                        raise TypeError(
                            "Unexpected PostgreSQL COPY "
                            f"chunk type: {type(chunk)!r}"
                        )

    return output_file


# ============================================================
# MART VALIDATION
# ============================================================

def validate_marts(cur):
    """Check row counts and key business invariants."""

    counts = {}

    print("\nChecking mart row counts...", flush=True)

    for table in MARTS:
        count = scalar(
            cur,
            f"SELECT COUNT(*) FROM mart.{table}",
        )

        counts[table] = count

        print(
            f"  mart.{table}: {count:,}",
            flush=True,
        )

        if count == 0:
            raise AssertionError(
                f"Mart has no data: mart.{table}"
            )

    # Expected one row per seller/customer/order.
    for table, expected in EXPECTED_COUNTS.items():
        actual = counts[table]

        if actual != expected:
            raise AssertionError(
                f"mart.{table}: expected {expected:,}, "
                f"found {actual:,}"
            )

    print("\nChecking business rules...", flush=True)

    checks = {
        "Invalid delivery denominator": """
            SELECT COUNT(*)
            FROM mart.delivery_performance
            WHERE evaluable_orders
                  <> late_orders + on_time_orders
        """,

        "Incorrect RFM frequency score": """
            SELECT COUNT(*)
            FROM mart.customer_rfm
            WHERE
                (frequency = 0 AND f_score <> 0)
                OR (frequency = 1 AND f_score <> 1)
                OR (frequency = 2 AND f_score <> 3)
                OR (frequency >= 3 AND f_score <> 5)
        """,

        "Incorrect reconciliation MATCH flag": """
            SELECT COUNT(*)
            FROM mart.payment_reconciliation
            WHERE
                (reconciliation_class = 'MATCH'
                    AND is_matched IS DISTINCT FROM TRUE)
                OR
                (reconciliation_class <> 'MATCH'
                    AND is_matched IS DISTINCT FROM FALSE)
        """,

        "Duplicate reconciliation order": """
            SELECT COUNT(*)
            FROM (
                SELECT order_id
                FROM mart.payment_reconciliation
                GROUP BY order_id
                HAVING COUNT(*) > 1
            ) duplicates
        """,

        "Invalid seller ranking threshold": """
            SELECT COUNT(*)
            FROM mart.seller_scorecard
            WHERE eligible_for_late_ranking
                  IS DISTINCT FROM
                  (evaluable_orders >= 30)
        """,

        "Invalid complete-month range": """
            SELECT COUNT(*)
            FROM mart.monthly_sales
            WHERE is_complete_month IS DISTINCT FROM (
                month_start >= DATE '2017-01-01'
                AND month_start < DATE '2018-09-01'
            )
        """,
    }

    for name, sql in checks.items():
        violations = scalar(cur, sql)

        print(
            f"  {name}: {violations:,}",
            flush=True,
        )

        if violations != 0:
            raise AssertionError(
                f"{name}: {violations} violations"
            )

    print("\nAll mart validations: PASS", flush=True)

    return counts


# ============================================================
# REPORT GENERATION
# ============================================================

def generate_report(conn, counts, duration):
    """Generate T5 report from shared dashboard queries."""

    sections = [
        (
            "Q1 - Monthly product revenue (BRL)",
            "q1_monthly_revenue",
        ),
        (
            "Q1 - Top 10 categories",
            "q1_top_categories",
        ),
        (
            "Q2 - Delivery late rate",
            "q2_delivery_summary",
        ),
        (
            "Q2 - Review score vs lateness",
            "q2_review_vs_lateness",
        ),
        (
            "Q3 - Top 10 eligible sellers",
            "q3_top_sellers",
        ),
        (
            "Q4 - Customer RFM segments",
            "q4_rfm_segments",
        ),
        (
            "Streaming freshness overview",
            "freshness_overview",
        ),
        (
            "Payment reconciliation by class",
            "reconciliation_summary",
        ),
        (
            "Payment reconciliation match rate",
            "reconciliation_match_rate",
        ),
    ]

    lines = [
        "# T5 - Olist Gold Marts Report",
        "",
        "Generated (UTC): "
        + datetime.now(timezone.utc).isoformat(),
        "",
        f"Build duration: {duration:.2f} seconds",
        "",
        "## Mart row counts",
        "",
        "| Mart | Rows |",
        "|---|---:|",
    ]

    for table in MARTS:
        lines.append(
            f"| `mart.{table}` | {counts[table]:,} |"
        )

    for title, query_key in sections:
        if query_key not in QUERIES:
            raise KeyError(
                f"Missing query in olist/mart_queries.py: "
                f"{query_key}"
            )

        columns, rows = run_query(
            conn,
            QUERIES[query_key],
        )

        lines.extend([
            "",
            f"## {title}",
            "",
            markdown_table(columns, rows),
        ])

    lines.extend([
        "",
        "## Business definitions",
        "",
        "- Revenue is the sum of item `price` for "
        "orders with status `delivered`.",
        "- Freight is reported separately from "
        "product revenue.",
        "- Monthly sales and delivery performance "
        "use the purchase month.",
        "- Complete months: January 2017 "
        "through August 2018.",
        "- Late rate uses only orders with "
        "`is_late IS NOT NULL`.",
        "- Each order has at most one selected "
        "review in `dw.fact_review`.",
        "- Seller ranking requires at least "
        "30 evaluable orders.",
        "- RFM recency uses the latest "
        "delivered-order purchase date plus one day.",
        "- RFM frequency uses fixed thresholds, "
        "not raw quintiles.",
        "- Reconciliation tolerance is BRL 0.01.",
        "- Voucher and installment mismatch "
        "classes require further investigation.",
        "",
        "## Limitations",
        "",
        "- Revenue excludes non-delivered orders "
        "by business definition.",
        "- Seller ratings reflect order-level "
        "reviews shared across sellers when an "
        "order has multiple sellers.",
        "- Freshness uses valid unique events "
        "stored in PostgreSQL, not every Kafka "
        "message consumed.",
        "- The current streaming event table "
        "does not explicitly identify replay batches.",
        "- Financial mismatch classes indicate "
        "possible causes, not proven accounting "
        "adjustments.",
        "",
        "## Source lineage",
        "",
        "- `raw.*` -> `dw.*` -> `mart.*` "
        "-> `outputs/gold/*.csv`.",
        "- `stream.order_events` -> "
        "`mart.stream_freshness`.",
        "- Shared report and dashboard queries: "
        "`olist/mart_queries.py`.",
        "",
    ])

    REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_FILE.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    return REPORT_FILE


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():
    started = time.perf_counter()

    print("=== T5 BUILD GOLD MARTS ===", flush=True)

    if not SQL_FILE.exists():
        raise FileNotFoundError(
            f"SQL file not found: {SQL_FILE}"
        )

    sql = SQL_FILE.read_text(
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # STEP 1: Build all six marts transactionally.
    # --------------------------------------------------------

    with get_connection() as conn:
        with conn.cursor() as cur:
            print(
                f"Executing: {SQL_FILE}",
                flush=True,
            )

            cur.execute(sql)

            # Validation happens before commit.
            counts = validate_marts(cur)

        # psycopg commits here only when no exception occurs.

    print(
        "\nGold mart transaction committed.",
        flush=True,
    )

    # --------------------------------------------------------
    # STEP 2: Export Gold CSV and generate report.
    # --------------------------------------------------------

    with get_connection() as conn:
        print(
            "\nExporting Gold CSV files...",
            flush=True,
        )

        for table in MARTS:
            output_file = export_csv(
                conn,
                table,
            )

            print(
                f"  Exported: {output_file}",
                flush=True,
            )

        duration = time.perf_counter() - started

        report_file = generate_report(
            conn,
            counts,
            duration,
        )

    # --------------------------------------------------------
    # STEP 3: Print summary.
    # --------------------------------------------------------

    print()
    print("=== T5 SUMMARY ===")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Report: {report_file}")
    print(f"CSV directory: {EXPORT_DIR}")
    print("Gold mart build: PASS")


if __name__ == "__main__":
    main()
