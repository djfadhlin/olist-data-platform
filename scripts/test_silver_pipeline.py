
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from olist.silver_pipeline import prepare_silver


def main():
    print("=== SILVER PIPELINE TEST ===")

    table_name = "olist_order_payments_dataset"

    source = pd.DataFrame({
        "order_id": ["o1", "o2"],
        "payment_sequential": ["1", "1"],
        "payment_type": ["credit_card", "boleto"],
        "payment_installments": ["2", "1"],
        "payment_value": ["100.00", "50.00"],
    })

    with TemporaryDirectory() as temp:
        base = Path(temp)

        raw_dir = base / "raw"
        output_dir = base / "silver"

        raw_dir.mkdir()

        source.to_csv(
            raw_dir / f"{table_name}.csv",
            index=False,
        )

        # Gunakan satu tabel untuk unit test.
        # Validasi header 9 tabel dinonaktifkan hanya di test ini.
        with (
            patch(
                "olist.silver_pipeline.TABLE_SCHEMAS",
                {table_name: None},
            ),
            patch(
                "olist.silver_pipeline.validate_csv_headers",
            ),
        ):
            summary = prepare_silver(raw_dir, output_dir)

        # ==========================================
        # TEST SILVER PARQUET
        # ==========================================

        parquet_path = output_dir / f"{table_name}.parquet"

        assert parquet_path.exists()

        report_path = output_dir / "dq_report.md"

        assert report_path.exists()

        report_content = report_path.read_text(
            encoding="utf-8"
        )

        assert "Verdict: **PASS**" in report_content
        assert "Source rows: **2**" in report_content
        assert "Silver rows: **2**" in report_content

        print("DQ report:", report_path.name)

        restored = pd.read_parquet(
            parquet_path,
            engine="pyarrow",
        )

        assert len(restored) == 2
        assert list(restored.columns) == list(source.columns)

        assert summary[table_name]["verdict"] == "PASS"
        assert summary[table_name]["source_rows"] == 2
        assert summary[table_name]["silver_rows"] == 2
        assert summary[table_name]["quarantine_rows"] == 0

        print("Parquet created:", parquet_path.name)
        print("Rows:", len(restored))
        print("Verdict:", summary[table_name]["verdict"])

        # ==========================================
        # TEST SOFT QUALITY FLAGS PARQUET
        # ==========================================

        flags_path = output_dir / "soft_quality_flags.parquet"

        assert flags_path.exists(), (
            "soft_quality_flags.parquet belum dibuat"
        )

        flags = pd.read_parquet(
            flags_path,
            engine="pyarrow",
        )

        expected_columns = [
            "source_table",
            "source_row",
            "column",
            "rule_id",
            "reason",
        ]

        assert list(flags.columns) == expected_columns

        # Test hanya memakai Payments.
        # Soft rules lintas tabel belum dapat dijalankan.
        assert len(flags) == 0

        print("Soft flags file:", flags_path.name)
        print("Soft flags rows:", len(flags))

        # ==========================================
        # TEST RECONCILIATION
        # ==========================================

        assert (
            summary[table_name]["source_rows"]
            == summary[table_name]["silver_rows"]
            + summary[table_name]["quarantine_rows"]
        )

        print("Row reconciliation: PASS")

    print("\nSilver pipeline test: PASS")


if __name__ == "__main__":
    main()
