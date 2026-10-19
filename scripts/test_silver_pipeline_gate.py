
"""Uji karantina dan quality gate pada pipeline Silver."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from olist.silver_pipeline import prepare_silver


TABLE_NAME = "olist_order_payments_dataset"


def make_payments(total_rows, bad_rows):
    """Buat data sintetis dengan sejumlah nilai pembayaran negatif."""

    source = pd.DataFrame({
        "order_id": [
            f"order_{i:05d}" for i in range(total_rows)
        ],
        "payment_sequential": ["1"] * total_rows,
        "payment_type": ["credit_card"] * total_rows,
        "payment_installments": ["1"] * total_rows,
        "payment_value": ["100.00"] * total_rows,
    })

    for idx in range(bad_rows):
        source.loc[idx, "payment_value"] = "-10.00"

    return source


def run_case(total_rows, bad_rows, expected_verdict):
    with TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        raw_dir = base / "raw"
        output_dir = base / "silver"
        raw_dir.mkdir()

        source = make_payments(total_rows, bad_rows)

        source.to_csv(
            raw_dir / f"{TABLE_NAME}.csv",
            index=False,
        )

        with (
            patch(
                "olist.silver_pipeline.TABLE_SCHEMAS",
                {TABLE_NAME: None},
            ),
            patch(
                "olist.silver_pipeline.validate_csv_headers",
            ),
        ):
            if expected_verdict == "FAIL":
                try:
                    prepare_silver(raw_dir, output_dir)
                except RuntimeError as exc:
                    assert "Quality gate FAIL" in str(exc)
                else:
                    raise AssertionError(
                        "Pipeline seharusnya gagal"
                    )

                assert not output_dir.exists()
                print(
                    f"{bad_rows}/{total_rows} quarantined: "
                    "FAIL correctly blocked"
                )
                return

            summary = prepare_silver(raw_dir, output_dir)
            result = summary[TABLE_NAME]

            assert result["verdict"] == expected_verdict
            assert result["quarantine_rows"] == bad_rows
            assert result["silver_rows"] == total_rows - bad_rows

            silver_path = output_dir / f"{TABLE_NAME}.parquet"
            quarantine_path = (
                output_dir / f"{TABLE_NAME}_quarantine.parquet"
            )

            assert silver_path.exists()
            assert quarantine_path.exists()

            silver = pd.read_parquet(silver_path)
            quarantine = pd.read_parquet(quarantine_path)

            assert len(silver) == total_rows - bad_rows
            assert len(quarantine) == bad_rows

            print(
                f"{bad_rows}/{total_rows} quarantined: "
                f"{expected_verdict}"
            )


def main():
    print("=== SILVER PIPELINE QUALITY GATE TEST ===")

    run_case(
        total_rows=200,
        bad_rows=1,
        expected_verdict="PASS+KARANTINA",
    )

    run_case(
        total_rows=100,
        bad_rows=2,
        expected_verdict="FAIL",
    )

    print("\nSilver pipeline quality gate test: PASS")


if __name__ == "__main__":
    main()
