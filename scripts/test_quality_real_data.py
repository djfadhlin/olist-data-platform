
"""Dry-run Data Quality pada seluruh dataset Olist asli.

Tidak mengubah CSV, MinIO, maupun PostgreSQL.
"""

from pathlib import Path
from time import perf_counter

import pandas as pd

from olist.schema import TABLE_SCHEMAS, validate_csv_headers
from olist.silver import parse_table
from olist.quality import collect_all_hard_violations
from olist.soft_quality import run_all_soft_rules


RAW_DIR = Path("data/raw")


def main():
    print("=== REAL DATA QUALITY DRY RUN ===")

    # Wajib lolos sebelum membaca seluruh isi dataset.
    validate_csv_headers(RAW_DIR)

    silver_tables = {}
    quarantine_summary = {}
    total_source = 0
    total_silver = 0
    total_quarantine = 0

    start = perf_counter()

    for table_name in TABLE_SCHEMAS:
        csv_path = RAW_DIR / f"{table_name}.csv"

        source = pd.read_csv(
            csv_path,
            dtype="string",
            encoding="utf-8-sig",
            keep_default_na=False,
        )

        parsed = parse_table(source, table_name)

        violations = collect_all_hard_violations(
            source, parsed, table_name
        )

        bad_rows = set(violations["source_row"].tolist())

        silver = parsed.loc[
            ~parsed.index.isin(bad_rows)
        ].copy()

        quarantine_count = len(bad_rows)

        assert len(source) == len(silver) + quarantine_count

        silver_tables[table_name] = silver

        quarantine_summary[table_name] = {
            "source": len(source),
            "silver": len(silver),
            "quarantine": quarantine_count,
            "violations": len(violations),
        }

        total_source += len(source)
        total_silver += len(silver)
        total_quarantine += quarantine_count

        print(
            f"{table_name}: "
            f"source={len(source):,} "
            f"silver={len(silver):,} "
            f"quarantine={quarantine_count:,} "
            f"violations={len(violations):,}"
        )

    print("\n=== SOFT RULE COUNTS ===")

    flags = run_all_soft_rules(silver_tables)

    soft_counts = (
        flags.groupby("rule_id").size().to_dict()
        if not flags.empty else {}
    )

    for rule_id in (
        "S01", "S02", "S03", "S04",
        "S05", "S06", "S07", "S08",
    ):
        print(f"{rule_id}: {soft_counts.get(rule_id, 0):,}")

    elapsed = perf_counter() - start

    print("\n=== TOTAL ===")
    print(f"Source: {total_source:,}")
    print(f"Silver: {total_silver:,}")
    print(f"Quarantine: {total_quarantine:,}")
    print(f"Soft flags: {len(flags):,}")
    print(f"Duration: {elapsed:.2f} seconds")

    assert total_source == total_silver + total_quarantine

    print("\nReal data quality dry run: PASS")


if __name__ == "__main__":
    main()
