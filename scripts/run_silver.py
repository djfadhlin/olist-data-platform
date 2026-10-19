
"""Jalankan pipeline Silver pada 9 dataset Olist asli."""

from pathlib import Path
from time import perf_counter

from olist.silver_pipeline import prepare_silver


RAW_DIR = Path("data/raw")
OUTPUT_DIR = Path("outputs/silver")


def main():
    print("=== T2 SILVER PIPELINE PRODUCTION RUN ===")

    start = perf_counter()

    summary = prepare_silver(
        raw_dir=RAW_DIR,
        output_dir=OUTPUT_DIR,
    )

    total_source = sum(
        item["source_rows"] for item in summary.values()
    )
    total_silver = sum(
        item["silver_rows"] for item in summary.values()
    )
    total_quarantine = sum(
        item["quarantine_rows"] for item in summary.values()
    )

    elapsed = perf_counter() - start

    assert len(summary) == 9
    assert total_source == total_silver + total_quarantine

    parquet_files = list(OUTPUT_DIR.glob("*.parquet"))
    report_path = OUTPUT_DIR / "dq_report.md"

    assert report_path.exists()

    for table_name in summary:
        assert (OUTPUT_DIR / f"{table_name}.parquet").exists()

    print("\n=== PRODUCTION SUMMARY ===")
    print(f"Tables: {len(summary)}")
    print(f"Source rows: {total_source:,}")
    print(f"Silver rows: {total_silver:,}")
    print(f"Quarantine rows: {total_quarantine:,}")
    print(f"Parquet files: {len(parquet_files)}")
    print(f"Duration: {elapsed:.2f} seconds")
    print(f"Output directory: {OUTPUT_DIR}")

    print("\nSilver production run: PASS")


if __name__ == "__main__":
    main()
