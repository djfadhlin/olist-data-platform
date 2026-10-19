
"""Uji publikasi ulang Silver tanpa file karantina usang."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from olist.silver_pipeline import prepare_silver


TABLE = "olist_order_payments_dataset"


def make_source(total_rows, bad_rows):
    source = pd.DataFrame({
        "order_id": [
            f"order_{i:04d}" for i in range(total_rows)
        ],
        "payment_sequential": ["1"] * total_rows,
        "payment_type": ["credit_card"] * total_rows,
        "payment_installments": ["1"] * total_rows,
        "payment_value": ["100.00"] * total_rows,
    })

    for i in range(bad_rows):
        source.loc[i, "payment_value"] = "-10.00"

    return source


def main():
    print("=== SILVER REPUBLISH TEST ===")

    with TemporaryDirectory() as temp:
        base = Path(temp)
        raw_dir = base / "raw"
        output_dir = base / "silver"

        raw_dir.mkdir()

        csv_path = raw_dir / f"{TABLE}.csv"

        with (
            patch(
                "olist.silver_pipeline.TABLE_SCHEMAS",
                {TABLE: None},
            ),
            patch(
                "olist.silver_pipeline.validate_csv_headers",
            ),
        ):
            # Run 1: ada satu record karantina (0.5%).
            make_source(200, 1).to_csv(
                csv_path, index=False
            )

            first = prepare_silver(raw_dir, output_dir)

            quarantine_path = (
                output_dir / f"{TABLE}_quarantine.parquet"
            )

            assert quarantine_path.exists()
            assert first[TABLE]["verdict"] == "PASS+KARANTINA"

            print("Run 1: quarantine exists — PASS")

            # Run 2: semua record sudah valid.
            make_source(200, 0).to_csv(
                csv_path, index=False
            )

            second = prepare_silver(raw_dir, output_dir)

            assert second[TABLE]["verdict"] == "PASS"
            assert not quarantine_path.exists()

            silver_path = output_dir / f"{TABLE}.parquet"
            assert silver_path.exists()

            silver = pd.read_parquet(silver_path)
            assert len(silver) == 200

            assert (output_dir / "dq_report.md").exists()
            assert (
                output_dir / "soft_quality_flags.parquet"
            ).exists()

            print("Run 2: stale quarantine removed — PASS")

    print("\nSilver republish test: PASS")


if __name__ == "__main__":
    main()
