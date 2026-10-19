
"""Unit test validasi file Silver untuk PostgreSQL loader."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from olist.raw_loader import validate_silver_files
from olist.schema import TABLE_SCHEMAS


def main():
    print("=== RAW LOADER UNIT TEST ===")

    table_name = "olist_order_payments_dataset"

    source = pd.DataFrame({
        "order_id": ["o1", "o2"],
        "payment_sequential": [1, 1],
        "payment_type": ["credit_card", "boleto"],
        "payment_installments": [1, 1],
        "payment_value": [100.00, 50.00],
    })

    with TemporaryDirectory() as temp_dir:
        silver_dir = Path(temp_dir)

        parquet_path = silver_dir / f"{table_name}.parquet"
        source.to_parquet(
            parquet_path,
            engine="pyarrow",
            index=False,
        )

        # Batasi daftar tabel untuk unit test ini.
        with patch(
            "olist.raw_loader.TABLE_SCHEMAS",
            {table_name: TABLE_SCHEMAS[table_name]},
        ):
            metadata = validate_silver_files(silver_dir)

            assert metadata[table_name]["rows"] == 2
            print("Valid Parquet: PASS")

            # Uji schema drift: hilangkan payment_value.
            broken = source.drop(columns=["payment_value"])

            broken.to_parquet(
                parquet_path,
                engine="pyarrow",
                index=False,
            )

            try:
                validate_silver_files(silver_dir)
            except ValueError as exc:
                assert "Schema Parquet" in str(exc)
                print("Missing column rejected: PASS")
            else:
                raise AssertionError(
                    "Schema drift seharusnya ditolak"
                )

    print("\nRaw loader unit test: PASS")


if __name__ == "__main__":
    main()
