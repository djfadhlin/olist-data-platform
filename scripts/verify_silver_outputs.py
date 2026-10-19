
"""Verifikasi hasil Silver Parquet produksi."""

from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from olist.schema import TABLE_SCHEMAS


SILVER_DIR = Path("outputs/silver")

EXPECTED_ROWS = {
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
    print("=== VERIFY SILVER PRODUCTION OUTPUTS ===")

    total_rows = 0

    for table_name, schema in TABLE_SCHEMAS.items():
        path = SILVER_DIR / f"{table_name}.parquet"

        assert path.exists(), f"File tidak ditemukan: {path}"

        parquet_file = pq.ParquetFile(path)

        rows = parquet_file.metadata.num_rows
        columns = parquet_file.schema_arrow.names

        expected_columns = [
            column.name for column in schema.columns
        ]

        assert rows == EXPECTED_ROWS[table_name], (
            f"Row mismatch: {table_name}"
        )

        assert columns == expected_columns, (
            f"Column mismatch: {table_name}"
        )

        total_rows += rows

        print(f"{table_name}: {rows:,} rows — PASS")

    flags_path = SILVER_DIR / "soft_quality_flags.parquet"
    report_path = SILVER_DIR / "dq_report.md"

    assert flags_path.exists()
    assert report_path.exists()

    flags = pd.read_parquet(flags_path)

    assert len(flags) == 13344

    report = report_path.read_text(encoding="utf-8")

    assert "Verdict: **PASS**" in report
    assert "Source rows: **1,550,922**" in report
    assert "## Hard Rule Counts" in report
    assert "## Soft Rule Counts" in report

    assert total_rows == 1550922

    print("\n=== SUMMARY ===")
    print(f"Silver rows: {total_rows:,}")
    print(f"Soft flags: {len(flags):,}")
    print("DQ report: PASS")
    print("\nSilver outputs verification: PASS")


if __name__ == "__main__":
    main()
