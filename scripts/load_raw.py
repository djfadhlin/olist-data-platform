
"""Load Silver Parquet ke PostgreSQL raw secara transaksional."""

import os
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import psycopg
from dotenv import load_dotenv

from olist.raw_loader import load_raw
from olist.schema import TABLE_SCHEMAS


SILVER_DIR = Path("outputs/silver")
REPORT_PATH = Path("outputs/load_report.md")


def build_load_report(result: dict, elapsed: float) -> str:
    """Bangun laporan hasil load PostgreSQL."""

    total_expected = 0

    lines = [
        "# T2 PostgreSQL Raw Load Report",
        "",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Load Configuration",
        "",
        "- Source: `outputs/silver/*.parquet`",
        "- Destination: PostgreSQL schema `raw`",
        "- Method: `TRUNCATE + COPY FROM STDIN`",
        "- Transaction: one transaction for all tables",
        "- Failure behavior: rollback",
        "",
        "## Table Load Summary",
        "",
        "| Table | Loaded Rows | Status |",
        "|---|---:|---|",
    ]

    for table_name in TABLE_SCHEMAS:
        count = result["tables"][table_name]
        total_expected += count

        lines.append(
            f"| {table_name} | {count:,} | PASS |"
        )

    lines.extend([
        "",
        "## Overall Result",
        "",
        f"- Tables loaded: **{len(result['tables'])}**",
        f"- Total loaded rows: **{total_expected:,}**",
        f"- Duration: **{elapsed:.2f} seconds**",
        "- Row reconciliation: **PASS**",
        "- Transaction committed: **YES**",
        "",
    ])

    return "\n".join(lines)


def main():
    print("=== T2 POSTGRESQL RAW PRODUCTION LOAD ===")

    load_dotenv()

    connection_params = {
        "host": "localhost",
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": os.environ["POSTGRES_DB"],
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
    }

    start = perf_counter()

    # Semua perubahan terjadi dalam satu transaksi.
    # Jika ada exception, psycopg melakukan rollback.
    with psycopg.connect(**connection_params) as conn:
        result = load_raw(
            conn=conn,
            silver_dir=SILVER_DIR,
        )

        assert len(result["tables"]) == 9
        assert result["total_rows"] == 1_550_922

    # Keluar dari blok koneksi tanpa exception = COMMIT sukses.
    elapsed = perf_counter() - start

    report = build_load_report(result, elapsed)

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_PATH.write_text(
        report,
        encoding="utf-8",
    )

    print("\n=== PRODUCTION LOAD SUMMARY ===")
    print(f"Tables loaded: {len(result['tables'])}")
    print(f"Total loaded rows: {result['total_rows']:,}")
    print(f"Duration: {elapsed:.2f} seconds")
    print(f"Report: {REPORT_PATH}")
    print("Transaction: COMMITTED")

    print("\nPostgreSQL raw production load: PASS")


if __name__ == "__main__":
    main()
